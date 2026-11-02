"""
Ferrari F140HC (Daytona SP3), 6.5 L 65-degree V12
Parametric Blender build with working internals.

Run inside Blender:   Scripting tab > Open > f140hc_build.py > Run Script
Run headless:         blender -b -P f140hc_build.py -- --save /path/out.blend
                      (or with the `bpy` pip module: python f140hc_build.py --save out.blend)

Everything is built inside an "F140HC" collection. Re-running the script deletes and
rebuilds that collection and leaves the rest of your scene alone.

Motion
------
Select the F140HC_CONTROL empty and edit its custom properties (Object properties >
Custom Properties):
  deg_per_frame   crank degrees per frame. Default 6 = one full 720-degree four-stroke
                  cycle in 120 frames, which loops seamlessly over the 1-120 range.
  offset_deg      crank angle offset, for posing a still.
  cutaway         1 = cylinder bank 7-12, crankcase, sump, timing cover and plenum are cut
                  open along the bank's bore plane. 0 = closed engine.
Every driver is a Blender "simple expression", so the engine runs without turning on
Auto Run Python Scripts.

What moves: crankshaft (with sprockets and damper), 12 titanium rods and 12 pistons on
correct slider-crank kinematics, 4 camshafts at half crank speed with lobes phased to
the firing order, 48 valves, 48 sliding finger followers, 48 valve springs that compress
with lift. Valve lift is computed from the same function the lobe profiles are cut
from, so cam, follower and valve stay in contact.

Data
----
Everything tagged SOURCED below comes from Ferrari's published Daytona SP3 technical
sheet. Everything tagged EST is an engineering estimate, because Ferrari does not
publish it. The whole engine re-derives from the P table, so swap numbers in as you find
better data (see README.md for where to look).
"""

import os
import sys
import math
from math import radians, sin, cos, sqrt, pi, asin

import bpy
import bmesh
from mathutils import Vector, Matrix

MM = 0.001  # the build is authored in millimetres; Blender stores metres

# ---------------------------------------------------------------------------------------
# 1. PARAMETERS (millimetres / degrees)
# ---------------------------------------------------------------------------------------
P = {
    # --- SOURCED: Ferrari Daytona SP3 technical sheet -------------------------------
    "bore": 94.0,
    "stroke": 78.0,
    "bank_angle": 65.0,

    # --- EST: bottom end -------------------------------------------------------------
    "rod_length": 140.0,           # centre-to-centre; front photo 11 cover height implies ~140
    "bore_pitch": 104.0,           # cylinder centre spacing inside one bank
    "bank_offset": 23.0,           # bank 7-12 sits this far rearward (side-by-side rods)
    "comp_height": 28.0,           # wrist-pin centre to crown edge
    "crown_dome": 1.0,             # dome height above crown edge
    "deck_clearance": 0.5,         # crown edge below deck at TDC
    "pin_diameter": 45.0,          # crankpin
    "pin_length": 46.0,            # holds two rods side by side
    "main_diameter": 60.0,
    "main_width": 22.0,
    "counterweight_radius": 76.0,  # must clear the piston skirt at BDC (checked in verify.py)
    "piston_skirt": 22.0,          # skirt below the wrist-pin centre
    "rod_width": 21.0,
    "wrist_pin_diameter": 20.0,

    # --- EST: valvetrain (4 valves/cyl, DOHC per bank, sliding finger followers) ------
    "intake_valve_d": 36.0,
    "exhaust_valve_d": 30.0,
    "intake_valve_len": 100.0,
    "exhaust_valve_len": 97.0,
    "intake_valve_angle": 12.0,    # lean from bore axis
    "exhaust_valve_angle": 13.0,
    "intake_valve_x": 18.0,        # face centre offset from bore axis, across the bank
    "exhaust_valve_x": 19.0,
    "intake_valve_y": 19.5,        # +/- along the bank
    "exhaust_valve_y": 17.0,
    "valve_face_above_deck": 7.0,
    "stem_d": 6.0,
    "intake_lift": 13.0,
    "exhaust_lift": 11.5,
    "IVO_btdc": 30.0, "IVC_abdc": 70.0,   # cam timing at 0 lash
    "EVO_bbdc": 70.0, "EVC_atdc": 30.0,
    "cam_base_radius": 18.0,
    "follower_thickness": 6.0,
    "follower_arm": 32.0,          # pivot to valve tip
    "spring_installed": 36.0,
    "spring_wire_d": 3.6,
    "spring_coil_d_in": 26.0,
    "spring_coil_d_ex": 24.0,
    "spring_coils": 6.0,

    # --- EST: castings ----------------------------------------------------------------
    "barrel_half_width": 78.0,     # cylinder bank casting, half width
    "head_half_width": 105.0,      # front photo 11 trace: cover ~210 mm across
    "head_height": 95.0,           # deck to cover joint; front photo 11 trace: joint ~305 mm from crank
    "gallery_floor": 62.0,         # above deck
    "cover_height": 70.0,          # front photo 11 trace: ~60 mm (+cam clearance)
    "crankcase_half_width": 150.0,
    "crankcase_bottom": -110.0,    # below crank axis
    "crankcase_top": 105.0,
    "sump_depth": 40.0,            # dry-sump pan below crankcase
    "edge_bevel_mm": 1.5,          # rounded edges on castings (photorealism)
    "hdri_rot_deg": 0.0,           # studio HDRI orientation (env F140_HDRI_ROT overrides)
    "hdri_strength": 1.0,
    # MEASURED (Amalgam 1:4 photos, top view 20 + side view 13): cam covers run ~7.2 bore
    # pitches, overhanging the block at the front to enclose the cam drive
    # side photo 13, coil centres found by segmentation: cover = 7.5 coil pitches; front coil
    # sits 1.8 pitches behind the cover front, rear coil 0.7 pitches ahead of the cover rear
    "front_valley_z": 280.0,
    # exhaust layout (mm, root frame; side photo 13 with the coil pitch as ruler, top photo 20
    # with the cam cover as ruler, rear photos 10 / 18). EST +-10%
    "exhaust": {
        # Header tubes traced from a 2x zoom of side photo 13 (zoom origin u=560, v=560).
        # Each tube: (cylinder index, depth x, [(X, Y, tube radius) in zoom px], bellows segments)
        "traced_tubes": [
            (5, -355.0, [(0, 250, 50), (140, 250, 50), (270, 245, 50), (420, 240, 55), (520, 230, 55),
                         (650, 320, 60), (720, 470, 62)], [(1, 2)]),
            # cyl 5: upper arch under the cover lip, then the fat 2-into-1 pipe (~70 mm, weld seam where
            # the cyl-4 arch joins) bending down into the clamp. Fat-pipe centreline from 3x crops of
            # photo 13 + video frame 20.8 s; radius column = silhouette half-width in zoom px.
            (4, -345.0, [(260, 160, 62), (340, 90, 64), (450, 45, 64), (580, 40, 64), (680, 70, 66),
                         (726, 166, 84), (740, 266, 98), (714, 366, 98), (666, 454, 94), (640, 494, 90)], []),
            # cyl 4: the lower front arch (photo 13 / video 20.8 s). From its port it runs rearward behind
            # the cyl-6 bellows tube (hidden), rises at u~728, arches forward and merges into the fat pipe.
            (3, -330.0, [(550, 224, 52), (460, 230, 52), (370, 220, 52), (336, 170, 53), (356, 116, 53),
                         (430, 92, 53), (540, 92, 53), (640, 110, 54), (696, 160, 56)], [], {"merge_into": 4}),
            # cyl 3: loop, then drops into the weld seam on the long run (photo 13 at u~1100, v~745) and
            # merges into the cyl-2 pipe (same 2-into-1 layout as the rear group)
            (2, -340.0, [(860, 230, 52), (820, 120, 55), (880, 40, 55), (980, 20, 55), (1060, 70, 55),
                         (1080, 170, 55), (1058, 268, 55), (1078, 346, 56)], [], {"merge_into": 1}),
            # cyl 2: loop, then the long run to the clamp; widens after the seam (2-into-1, ~50-55 mm)
            (1, -350.0, [(1150, 220, 50), (1110, 130, 50), (1180, 80, 50), (1260, 110, 50), (1290, 200, 50),
                         (1260, 300, 52), (1180, 340, 56), (1080, 370, 66), (950, 400, 72), (800, 440, 76)], []),
            (0, -345.0, [(1320, 250, 60), (1300, 380, 60), (1240, 480, 60), (1150, 520, 60), (1060, 520, 60),
                         (950, 560, 60), (880, 580, 60), (790, 545, 62), (730, 510, 62)], [(4, 5)]),
        ],
        "tube_zoom": (560.0, 560.0, 2.0),             # zoom origin u, v and scale
        "photo13": (513.0, 605.0, 0.730, 600.0, 199.0, 0.737),   # u0, y0, mm/px, v0, z0, mm/px
        # jointly solved photo-13 camera (tools/bundle_adjust.py: lens pinned 100 mm, look-down prior
        # from the stand-cup ellipses). Traced pixels are back-projected through it onto the plane
        # x = anchor depth, so a tube sits exactly on its trace whatever its depth.
        "photo13_cam": {"lens": 99.9990, "loc": (-3.890903, 0.375616, 0.532600), "size": (1800, 1200),
                        "rot": ((-0.013987, 0.053072, -0.998493), (-0.999897, 0.002480, 0.014139), (0.003227, 0.998588, 0.053032))},
        "port_z_above_deck": 20.0,
        # primary OD: each tube's traced silhouette radius (zoom px / 2 = photo px) times the camera's
        # mm/px at that depth, no fudge factor. Spot checks in photo 13 (ray-cast verified): rear tube
        # 50 px = 36 mm, the big arch ~64 px = 46 mm (the tubes are stepped: a weld ring is visible on
        # the long run). Bellows convolutions 60 mm OD, end sleeves 44 mm OD, ~8 convolutions in 57 mm.
        "bellows_od": 60.0, "bellows_sleeve_od": 44.0, "bellows_pitch": 7.2,
        "collector": (-382.0, 284.0, 62.0),
        # plan view (top photo 20): primaries leave their ports just outside the cover edge and
        # sweep outward toward the clamp, which sits ~50 mm outboard of the dome's centre
        "port_x": -292.0, "sweep_x": -372.0, "loop_bulge": 18.0,
        # triangulated landmarks (tools/triangulate.py, reference_data/picks_headers.json): photo 13 +
        # video frame 11.4 s. clamp (-366, 327, 59); rear bellows x -331; front bellows x -307
        # V-band ring: photo 13 sees it exactly edge-on as a 157 mm band from pixel (785, 790) to
        # (953, 930); centre = band midpoint back-projected at x -330 (top photo 20: ring arc at
        # -380..-395 apparent, T-bolt nuts -405..-415, i.e. ring outer edge ~-409 true). Edge-on means
        # the axis has no x component; it rises 50 deg forward-up, perpendicular to the band.
        "clamp_pos": (-330.0, 347.0, 9.0),
        # depth (x) of every traced point, solved by tools/solve_header_depth.py: each point stays on
        # its photo-13 pixel ray; tubes keep >= 4 mm between surfaces, centrelines stay inside the
        # top-photo-20 envelope (x >= -360) and clear of the head (x <= -282)
        "tube_anchors": [
            {0: -283.5, 1: -288.8, 2: -294.5, 3: -300.3, 4: -306.2, 5: -312.1, 6: -317.9, 7: -323.5, 8: -328.7},
            {0: -283.0, 1: -289.5, 2: -297.5, 3: -306.5, 4: -315.4, 5: -323.1, 6: -329.3, 7: -334.1, 8: -337.4, 9: -338.9},
            {0: -281.1, 1: -281.9, 2: -291.2, 3: -304.5, 4: -318.3, 5: -329.4, 6: -337.5, 7: -344.0},
            {0: -304.6, 1: -309.3, 2: -315.2, 3: -323.7, 4: -332.7, 5: -339.8, 6: -345.3, 7: -349.3, 8: -352.6},
            {0: -281.8, 1: -283.5, 2: -292.1, 3: -304.7, 4: -316.9, 5: -323.0, 6: -315.6, 7: -302.2, 8: -305.4, 9: -315.8},
            {0: -342.4, 1: -348.0, 2: -354.9, 3: -359.8, 4: -360.2, 5: -360.5, 6: -360.1}],
        "merge_axis": (0.0, 50.3),                    # (inboard x per unit forward-up, elevation deg)
        "collector_dist": 35.0,                       # merge plenum centre above the ring plane
        "sensor_angle": 22.0,                         # O2 sensor shoulder angle: joint solve puts it at x ~-359
        "clamp_r": 69.0,                              # neck radius; band adds 9 mm -> 156 mm ring
        "cat_x": 320.0,
        # traced catalyst outline: (y, top z, bottom z), clamp -> outlet
        # front dome (video frames 20-22 s, photos 16/08 mirrored, side photo 13): an ellipsoidal
        # cap as wide as the canister, ending ~150 mm ahead of the front seam
        # dome: matches the re-traced can at the seam (r 86, centre -13); its front-bottom bulges low
        # (photo 13: front-most outline at y ~309, z ~-64), so the centre line drops toward the tip
        "cat_dome": {"y_seam": 449.0, "length": 150.0, "r": 87.0, "zc": -13.0, "rise": -15.0},
        # canister + rear cone silhouette re-traced on a gridded full-res crop of photo 13 and back-projected
        # through the solved camera at the can's axis depth (x -320). The earlier "+15 mm" correction was
        # made through a 35 mm-lens camera whose perspective inflated near parts; this replaces it.
        "cat_sections": [(449, 74, -99), (470, 74, -100), (532, 68, -103), (568, 66, -104), (603, 65, -104),
                         (639, 61, -105), (675, 53, -107), (711, 38, -108), (746, 23, -108), (782, 7, -108),
                         (818, -9, -106), (854, -27, -103), (876, -40, -100), (892, -45, -98),
                         (905, -45, -98), (1000, -45, -98)],
        "cat_beads": [449.0, 507.0, 682.0],                # seam lines at photo-13 u ~733 / 645 / 405
        # plan width vs height: top photo 20 shows the dome as round (outer edge -414 at y 410..460)
        # but the canister behind it narrower (outer -390 at y 500..560): an oval can, 0.74 as wide.
        "cat_oval": [(459.0, 1.0), (500.0, 0.74), (690.0, 0.74), (760.0, 0.9), (1000.0, 1.0)],
        "sensor": (549.0, 66.0), "sensor_r": 85.0, "slip_joint": (916.0, 960.0),
        "muffler_y": (1402.0, 1553.0), "muffler_x_span": (14.0, 340.0),
        "muffler_x": 220.0, "muffler_z": 120.0, "muffler_h": 210.0,
        "outlet_x": (120.0, 225.0),
    },
    # gearbox (7-speed DCT) envelope: top photo 20 / side photo 13
    "gearbox": {"half_width": 175.0, "rear_y": 1340.0, "centre_z": 33.0, "height": 326.0},       # top of the front casting between the banks
    # front accessories: (x, z) of the pulley centre vs crank axis, pulley r, body r, body length
    # front photo 11, scaled with the cam cover as the ruler (EST +-10%)
    "crank_pulley_r": 72.0,                       # front photo 11: 145 mm across
    # front casting outline (x, z) on the cover front plane (y = -100): photo 11 picks back-projected
    # through the jointly solved camera (tools/bundle_adjust.py + tools/backproject.py)
    "front_casting": [(-250, 198), (-260, 172), (-242, 154), (-257, 8), (-230, -135), (-127, -141),
                      (-1, -147), (101, -115), (214, 9), (237, 117), (250, 200), (79, 309),
                      (5, 233), (-79, 309)],
    # belt order after the crank, CCW seen from the front; -1 = belt runs over the back of an idler
    "belt_route": [("ac_compressor", 1), ("idler_upper", 1), ("alternator", 1), ("idler_lower", -1),
                   ("water_pump", 1)],
    # near-side lower details, traced from side photo 13 (y, z via the coil-pitch ruler)
    "near_side": {
        "alt_xz": (-257.0, 37.0),                              # joint 3-view solve
        # (y start, y end, radius, kind): rear cover, rear housing, stator band, front housing, nose
        "alt_sections": [(50, 6, 70, "ribbed"), (6, -48, 75, "slots"), (-48, -62, 77, "band"),
                         (-62, -96, 75, "slots"), (-96, -106, 50, "nose")],
        "alt_lug": (-233.0, -40.0, 128.0, 34.0, 40.0, 46.0),   # mounting lug box (x, y, z, sx, sy, sz)
        "oil_pump_x": -172.0,
        # oil pump / water pump: outlines picked in side photo 13 and back-projected through the solved
        # camera at the part's depth (tools: see HANDOVER "back-projection")
        "oil_pump": {"rear": (150.0, 205.0, 40.0), "front_box": (118.0, 64.0, 76.0, 90.0), "z": -78.0,
                     "cover_y": 86.0, "relief": (161.0, -32.0), "boss": (143.0, -67.0),
                     "elbow": [(-182.0, 194.0, -112.0), (-182.0, 192.0, -150.0)], "drive": (30.0, 88.0, 33.0)},
        "sump_boss": (-146.0, 296.0, -75.0, 12.0, 45.0, 64.0),
        "water_pump_body": {"x": -180.0, "y": 0.0, "z": -97.0, "sx": 58.0, "sy": 70.0, "sz": 118.0,
                            "cover": (-58.0, -98.0, 75.0, 112.0), "cover_x": -205.0,
                            "cover_bolts": [(-50.0, -48.0), (-87.0, -52.0), (-40.0, -142.0), (-88.0, -149.0),
                                            (-96.0, -100.0)],
                            "stub": [(-203.0, -100.0, -86.0), (-240.0, -114.0, -66.0)]},
        "oil_fittings": [(292.0, -50.0), (248.0, -62.0), (160.0, -46.0), (118.0, -46.0), (300.0, -110.0)],
        "oil_sensor": (-182.0, 180.0, -20.0),
        # diff side cover: 11 rim bolts fit a circle (residual 0.2 px) centred at photo-13 pixel (65, 787),
        # r 176 px = 131 mm at the case face; the polished output flange is concentric
        "diff_centre": (944.0, 44.0), "diff_bolt_start_deg": -97.5,
        # polished hairpin tube on top of the gearbox (photo 13 2x: two runs at v ~575 / ~600 meeting in a
        # U-bend at u ~395 by the head bracket); both legs enter the gearbox top
        "hairpin": [(-172.0, 945.0, 204.0), (-205.0, 770.0, 204.0), (-238.0, 702.0, 202.0), (-252.0, 690.0, 212.0),
                    (-238.0, 702.0, 222.0), (-205.0, 770.0, 222.0), (-172.0, 950.0, 220.0)],
        "bracket_puck": (680.0, 119.0, 24.0, 30.0),            # y, z, radius, length (black, on the bracket)
        # cast gearbox-mount gusset on the case's front-top flank (photo 13 u 250-390 / v 640-770)
        "gb_gusset": [(700.0, 175.0), (805.0, 175.0), (805.0, 148.0), (738.0, 82.0), (700.0, 82.0)],
        "sump_lobe": (-215.0, 486.0, -107.0, 130.0, 111.0, 69.0),
        "rear_bracket": (-262.0, 671.0, 133.0, 150.0),         # x, y, z centre, height; photo 13 v 590-790 -> up to the head
    },
    "accessories": {
        "alternator": (-257.0, 37.0, 32.0, 0, 0),         # joint solve (bundle_adjust.py)
        "idler_upper": (-131.0, 88.0, 25.0, 0, 0),
        "idler_lower": (-170.0, 15.0, 24.0, 0, 0),
        "ac_compressor": (167.0, -25.0, 55.0, 58.0, 170.0),
        "water_pump": (-162.0, -90.0, 34.0, 0, 0),       # housing built in near_side
    },
    "head_front": -100.0,          # head / cam cover front face (block front = 0)
    "head_rear_ext": 10.0,         # head / cam cover overhang past the block rear

    # --- MEASURED: SP3 carbon intake. Plan widths from top photo 20 (as a fraction of the cam
    # cover half-width, x 273 mm); heights from side photo 13 (fraction of cover length above
    # the cover top). Extracted by colour segmentation, see tools/ in the README. --------------
    "pod_base_z": 395.0,           # pod flange height above crank axis
    "pod_inner_x": 16.0,           # pod inner edge from engine centreline (spine half-width)
    "pod_length_frac": 0.97,       # pod length / cam cover length (rear ends flush)
    "pod_outer": [(0.0, 245.0), (0.22, 247.0), (0.34, 240.0), (0.45, 224.0), (0.56, 208.0),
                  (0.67, 183.0), (0.79, 147.0), (0.90, 110.0), (1.0, 80.0)],
    "pod_height": [(0.0, 194.0), (0.16, 206.0), (0.28, 210.0), (0.40, 206.0), (0.53, 194.0),
                   (0.66, 174.0), (0.78, 147.0), (0.84, 130.0), (0.90, 111.0), (1.0, 84.0)],
    "pod_nose_start": 0.92,        # where the blunt nose begins to round off
    "pod_crest": 0.62,             # crest position across the pod, inner 0 .. outer 1
    "pod_scoop": 0.38,             # inner-rear scoop depth (fraction of height)
    "tb_radius": 52.0,             # throttle body (side photo: ~104 mm across)
    "tb_offset_x": 210.0,          # top photo: 0.77 of cover half-width
    "tb_height": 113.0,            # above pod flange (side photo)

    # --- EST: timing drive (chain, one per bank) -----------------------------------------
    "chain_pitch": 8.0,
    "crank_sprocket_teeth": 17,
    "cam_sprocket_teeth": 34,      # 2:1

    # --- EST: overall envelope from the Amalgam 1:4 SP3 engine + gearbox replica --------
    # ">43 cm long, 21 cm wide" (Amalgam), "18 cm / 7 in tall" (press) -> x4
    "envelope_length": 1720.0,
    "envelope_width": 840.0,
    "envelope_height": 720.0,
}

# Crank throw phase per crankpin, front to rear (inline-six crank shared by both banks).
PIN_PHASE = [0.0, 240.0, 120.0, 120.0, 240.0, 0.0]
# Firing order inside one bank (classic Ferrari V12 pattern; F140 order is unconfirmed).
BANK_ORDER = [1, 5, 3, 6, 2, 4]

COLL_NAME = "F140HC"


# ---------------------------------------------------------------------------------------
# 2. SMALL GEOMETRY KIT
# ---------------------------------------------------------------------------------------
ROT_Z_TO_Y = Matrix.Rotation(-pi / 2, 4, 'X')    # maps local +Z onto +Y
ROT_Z_TO_NY = Matrix.Rotation(pi / 2, 4, 'X')    # maps local +Z onto -Y


def T(x, y, z):
    return Matrix.Translation((x * MM, y * MM, z * MM))


def RY(deg):
    return Matrix.Rotation(radians(deg), 4, 'Y')


def RX(deg):
    return Matrix.Rotation(radians(deg), 4, 'X')


def rot_xz(x, z, deg):
    """Rotate a point in the XZ plane the same way Blender's Y rotation does."""
    a = radians(deg)
    return (x * cos(a) + z * sin(a), -x * sin(a) + z * cos(a))


def hull2d(pts):
    pts = sorted(set((round(p[0], 6), round(p[1], 6)) for p in pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]          # counter-clockwise


def circle_pts(cx, cz, r, n=48):
    return [(cx + r * cos(2 * pi * i / n), cz + r * sin(2 * pi * i / n)) for i in range(n)]


def resample_closed(poly, spacing):
    out, segs = [], list(zip(poly, poly[1:] + poly[:1]))
    total = sum(math.dist(a, b) for a, b in segs)
    n = max(3, int(total / spacing))
    step, acc, si = total / n, 0.0, 0
    for k in range(n):
        target = k * step
        while si < len(segs) and acc + math.dist(*segs[si]) < target:
            acc += math.dist(*segs[si])
            si += 1
        a, b = segs[min(si, len(segs) - 1)]
        L = math.dist(a, b) or 1.0
        t = (target - acc) / L
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def serpentine(route, arc_step_deg=6.0):
    """Closed belt path (CCW in XZ) around pulleys [((x, z), signed r)], r < 0 = back-side wrap."""
    n = len(route)
    tan = []
    for i in range(n):
        (c1, R1), (c2, R2) = route[i], route[(i + 1) % n]
        dx, dz = c2[0] - c1[0], c2[1] - c1[1]
        L = math.hypot(dx, dz)
        ux, uz = dx / L, dz / L
        rx, rz = uz, -ux                                  # right-hand perpendicular (outside of a CCW loop)
        cphi = max(-1.0, min(1.0, (R1 - R2) / L))
        sphi = sqrt(1 - cphi * cphi)
        nx, nz = ux * cphi + rx * sphi, uz * cphi + rz * sphi
        tan.append(((c1[0] + R1 * nx, c1[1] + R1 * nz), (c2[0] + R2 * nx, c2[1] + R2 * nz)))
    path = []
    for i in range(n):
        c, R = route[i]
        a_in = math.atan2(tan[i - 1][1][1] - c[1], tan[i - 1][1][0] - c[0]) if R > 0 else \
            math.atan2(c[1] - tan[i - 1][1][1], c[0] - tan[i - 1][1][0])
        a_out = math.atan2(tan[i][0][1] - c[1], tan[i][0][0] - c[0]) if R > 0 else \
            math.atan2(c[1] - tan[i][0][1], c[0] - tan[i][0][0])
        sweep = (a_out - a_in) % (2 * pi) if R > 0 else -((a_in - a_out) % (2 * pi))
        steps = max(2, int(abs(math.degrees(sweep)) / arc_step_deg))
        r_ = abs(R)
        sgn = 1 if R > 0 else -1
        for k in range(steps + 1):
            a = a_in + sweep * k / steps
            path.append((c[0] + sgn * r_ * cos(a), c[1] + sgn * r_ * sin(a)))
    return path


def sprocket_radius(teeth):
    return P["chain_pitch"] / (2 * sin(pi / teeth))


def gear_profile(cx, cz, teeth, r_pitch):
    pts = []
    r_root, r_tip = r_pitch - 3.2, r_pitch + 2.0
    for i in range(teeth):
        a0 = 2 * pi * i / teeth
        da = 2 * pi / teeth
        for frac, r in ((0.0, r_root), (0.30, r_root), (0.42, r_tip), (0.58, r_tip), (0.70, r_root)):
            a = a0 + frac * da
            pts.append((cx + r * sin(a), cz + r * cos(a)))
    return pts


class MB:
    """bmesh builder that works in millimetres and tags material slots per part."""

    def __init__(self):
        self.bm = bmesh.new()

    def _tag(self, verts, mi):
        for v in verts:
            for f in v.link_faces:
                f.material_index = mi

    def box(self, cx, cy, cz, sx, sy, sz, M=None, mi=0):
        Mloc = (M or Matrix()) @ T(cx, cy, cz) @ Matrix.Diagonal((sx * MM, sy * MM, sz * MM, 1))
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=Mloc)
        self._tag(res["verts"], mi)
        return res["verts"]

    def lathe(self, prof, seg=32, M=None, mi=0, closed=False):
        """Surface of revolution about local Z. prof = [(r, z), ...] in mm."""
        M = M or Matrix()
        bm = self.bm
        rings, new = [], []
        for r, z in prof:
            if r <= 1e-9:
                v = bm.verts.new(M @ Vector((0, 0, z * MM)))
                rings.append([v])
                new.append(v)
            else:
                ring = [bm.verts.new(M @ Vector((r * MM * cos(2 * pi * i / seg),
                                                  r * MM * sin(2 * pi * i / seg), z * MM)))
                        for i in range(seg)]
                rings.append(ring)
                new.extend(ring)
        pairs = list(zip(rings[:-1], rings[1:]))
        if closed:
            pairs.append((rings[-1], rings[0]))
        for a, b in pairs:
            if len(a) == 1 and len(b) == 1:
                continue
            for i in range(seg):
                j = (i + 1) % seg
                if len(a) == 1:
                    bm.faces.new((a[0], b[j], b[i]))
                elif len(b) == 1:
                    bm.faces.new((a[i], a[j], b[0]))
                else:
                    bm.faces.new((a[i], a[j], b[j], b[i]))
        if not closed:
            if len(rings[0]) > 1:
                bm.faces.new(list(reversed(rings[0])))
            if len(rings[-1]) > 1:
                bm.faces.new(rings[-1])
        self._tag(new, mi)
        return new

    def cyl(self, r, z0, z1, M=None, seg=32, mi=0):
        return self.lathe([(r, z0), (r, z1)], seg, M, mi)

    def cyl_y(self, r, y0, y1, cx=0.0, cz=0.0, seg=32, mi=0, M=None):
        """Cylinder along Y between y0 and y1, centred on (cx, cz)."""
        Mloc = (M or Matrix()) @ T(cx, 0, cz) @ ROT_Z_TO_Y
        return self.lathe([(r, y0), (r, y1)], seg, Mloc, mi)

    def ring_y(self, r_in, r_out, y0, y1, cx=0.0, cz=0.0, seg=32, mi=0, M=None):
        Mloc = (M or Matrix()) @ T(cx, 0, cz) @ ROT_Z_TO_Y
        return self.lathe([(r_in, y0), (r_out, y0), (r_out, y1), (r_in, y1)], seg, Mloc, mi,
                          closed=True)

    def between(self, p0, p1, r, seg=24, mi=0, M=None):
        """Cylinder of radius r between two mm points."""
        a, b = Vector(p0), Vector(p1)
        d = b - a
        rot = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        Mloc = (M or Matrix()) @ T(*a) @ rot
        return self.lathe([(r, 0.0), (r, d.length)], seg, Mloc, mi)

    def prism_xz(self, pts, y0, y1, M=None, mi=0):
        """Closed prism from an XZ polygon (mm), extruded from y0 to y1."""
        M = M or Matrix()
        bm = self.bm
        f = [bm.verts.new(M @ Vector((x * MM, y0 * MM, z * MM))) for x, z in pts]
        b = [bm.verts.new(M @ Vector((x * MM, y1 * MM, z * MM))) for x, z in pts]
        n = len(pts)
        bm.faces.new(f)
        bm.faces.new(list(reversed(b)))
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((f[i], f[j], b[j], b[i]))
        self._tag(f + b, mi)
        return f + b

    def ribbon_xz(self, path, half_t, y0, y1, M=None, mi=0):
        """Closed band following a closed CCW XZ path (a chain or belt)."""
        M = M or Matrix()
        bm = self.bm
        n = len(path)
        outer, inner = [], []
        for i in range(n):
            px, pz = path[i]
            ax, az = path[i - 1]
            bx, bz = path[(i + 1) % n]
            tx, tz = bx - ax, bz - az
            L = math.hypot(tx, tz) or 1.0
            nx, nz = tz / L, -tx / L                   # outward for a CCW path
            outer.append((px + nx * half_t, pz + nz * half_t))
            inner.append((px - nx * half_t, pz - nz * half_t))
        rows = []
        for (x, z) in outer + inner:
            rows.append((bm.verts.new(M @ Vector((x * MM, y0 * MM, z * MM))),
                         bm.verts.new(M @ Vector((x * MM, y1 * MM, z * MM)))))
        O, I = rows[:n], rows[n:]
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((O[i][0], O[j][0], O[j][1], O[i][1]))
            bm.faces.new((I[j][0], I[i][0], I[i][1], I[j][1]))
            bm.faces.new((O[j][0], O[i][0], I[i][0], I[j][0]))
            bm.faces.new((O[i][1], O[j][1], I[j][1], I[i][1]))
        self._tag([v for r in rows for v in r], mi)

    def rbox(self, cx, cy, cz, sx, sy, sz, r, segs=3, M=None, mi=0):
        """Box with rounded edges."""
        verts = self.box(cx, cy, cz, sx, sy, sz, M=M, mi=mi)
        edges = list({e for v in verts for e in v.link_edges})
        res = bmesh.ops.bevel(self.bm, geom=edges, offset=r * MM, segments=segs, profile=0.5,
                              affect='EDGES', clamp_overlap=True)
        for f in res.get("faces", []):
            f.material_index = mi

    def loft(self, sections, mi=0, cap_start=True, cap_end=True):
        """Skin closed rings of 3D mm points (same count per ring)."""
        bm = self.bm
        rings = [[bm.verts.new(Vector(p) * MM) for p in sec] for sec in sections]
        n = len(rings[0])
        for a, b in zip(rings[:-1], rings[1:]):
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], a[j], b[j], b[i]))
        if cap_start:
            bm.faces.new(list(reversed(rings[0])))
        if cap_end:
            bm.faces.new(rings[-1])
        self._tag([v for r in rings for v in r], mi)

    def prism_xy(self, pts, z0, z1, mi=0):
        """Closed prism from an XY polygon (mm), extruded from z0 to z1."""
        bm = self.bm
        f = [bm.verts.new(Vector((x, y, z0)) * MM) for x, y in pts]
        b = [bm.verts.new(Vector((x, y, z1)) * MM) for x, y in pts]
        n = len(pts)
        bm.faces.new(list(reversed(f)))
        bm.faces.new(b)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((f[i], f[j], b[j], b[i]))
        self._tag(f + b, mi)

    def bevel_all(self, offset_mm, segments=3):
        bmesh.ops.bevel(self.bm, geom=list(self.bm.edges), offset=offset_mm * MM,
                        segments=segments, profile=0.5, affect='EDGES', clamp_overlap=True)

    def finish(self, name, coll, mats, parent=None, smooth_angle=35.0):
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(m)
        try:
            me.set_sharp_from_angle(angle=radians(smooth_angle))
        except Exception:
            pass
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        if parent:
            ob.parent = parent
        return ob


# ---------------------------------------------------------------------------------------
# 3. MATERIALS
# ---------------------------------------------------------------------------------------
def _set(bsdf, key, val):
    if key in bsdf.inputs:
        bsdf.inputs[key].default_value = val


def material(name, color, metallic=0.0, rough=0.5, coat=0.0, wrinkle=0.0, weave=False, alpha=1.0, cast=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if m.node_tree is None:
        m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (-300, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    _set(bsdf, "Base Color", (*color, 1.0))
    _set(bsdf, "Metallic", metallic)
    _set(bsdf, "Roughness", rough)
    _set(bsdf, "Coat Weight", coat)
    _set(bsdf, "Alpha", alpha)
    if wrinkle > 0:            # crinkle paint on the cam covers
        tc = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 900.0
        if "Detail" in noise.inputs:
            noise.inputs["Detail"].default_value = 6.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = wrinkle
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if cast > 0:               # sand-cast skin: mottled roughness + fine grain
        tc = nt.nodes.new("ShaderNodeTexCoord")
        n1 = nt.nodes.new("ShaderNodeTexNoise")
        n1.inputs["Scale"].default_value = 140.0
        if "Detail" in n1.inputs:
            n1.inputs["Detail"].default_value = 8.0
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value = max(0.0, rough - 0.12)
        mr.inputs["To Max"].default_value = min(1.0, rough + 0.12)
        n2 = nt.nodes.new("ShaderNodeTexNoise")
        n2.inputs["Scale"].default_value = 2400.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = cast
        bump.inputs["Distance"].default_value = 0.0004
        nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
        nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
        nt.links.new(n1.outputs["Fac"], mr.inputs["Value"])
        nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])
        nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if weave:                  # 2x2 twill approximation for carbon
        tc = nt.nodes.new("ShaderNodeTexCoord")
        chk = nt.nodes.new("ShaderNodeTexChecker")
        chk.inputs["Scale"].default_value = 320.0
        chk.inputs["Color1"].default_value = (0.005, 0.005, 0.006, 1)
        chk.inputs["Color2"].default_value = (0.022, 0.022, 0.025, 1)
        nt.links.new(tc.outputs["Object"], chk.inputs["Vector"])
        nt.links.new(chk.outputs["Color"], bsdf.inputs["Base Color"])
    m.diffuse_color = (*color, alpha)
    m.metallic = metallic
    m.roughness = rough
    return m


def build_materials():
    return {
        "alu_cast": material("F140_Aluminium_Cast", (0.60, 0.61, 0.62), 1.0, 0.55, cast=0.35),
        # Amalgam photos 13/16: heads and block are mid-grey sand-cast aluminium, a shade darker than
        # the gearbox case
        "block_cast": material("F140_Block_Cast", (0.48, 0.48, 0.49), 1.0, 0.6, cast=0.4),
        # water pump casting reads warmer and darker than the oil pump in photo 13 (~150/145/135 sRGB)
        "wp_cast": material("F140_WaterPump_Cast", (0.40, 0.38, 0.34), 1.0, 0.62, cast=0.4),
        "alu_mach": material("F140_Aluminium_Machined", (0.80, 0.80, 0.82), 1.0, 0.22),
        "steel": material("F140_Steel_Forged", (0.46, 0.46, 0.48), 1.0, 0.30),
        "titanium": material("F140_Titanium", (0.55, 0.52, 0.48), 1.0, 0.34),
        "dlc": material("F140_DLC_Black", (0.05, 0.05, 0.06), 1.0, 0.15),
        "piston": material("F140_Piston_Forged", (0.72, 0.72, 0.74), 1.0, 0.35),
        "valve": material("F140_Valve_Steel", (0.62, 0.62, 0.64), 1.0, 0.20),
        "spring": material("F140_Spring_Steel", (0.08, 0.09, 0.12), 1.0, 0.35),
        "rosso": material("F140_Rosso_Crinkle", (0.60, 0.0, 0.0), 0.0, 0.55, coat=0.3, wrinkle=0.25),
        "carbon": material("F140_Carbon", (0.01, 0.01, 0.012), 0.0, 0.22, coat=1.0, weave=True),
        "inconel": material("F140_Exhaust_Inconel", (0.36, 0.33, 0.30), 1.0, 0.42),
        "black": material("F140_Black_Plastic", (0.02, 0.02, 0.02), 0.0, 0.50),
        "ceramic": material("F140_Plug_Ceramic", (0.85, 0.85, 0.82), 0.0, 0.30),
        "bolt": material("F140_Bolt_Zinc", (0.70, 0.70, 0.66), 1.0, 0.30),
        "chain": material("F140_Chain", (0.20, 0.20, 0.21), 1.0, 0.30),
        "magnesium": material("F140_Gearbox_Cast", (0.46, 0.46, 0.45), 1.0, 0.55, cast=0.35),   # photo 13: diff cover mean 135 vs 173
        "polished": material("F140_Stainless_Polished", (0.78, 0.78, 0.80), 1.0, 0.14),
        "bellows": material("F140_Bellows", (0.72, 0.72, 0.74), 1.0, 0.20),
        "envelope": material("F140_Envelope", (0.2, 0.6, 1.0), 0.0, 0.5, alpha=0.15),
    }


# ---------------------------------------------------------------------------------------
# 4. SCENE PLUMBING
# ---------------------------------------------------------------------------------------
def setup_hdri(scn, path, strength=1.0, backdrop=(0.60, 0.60, 0.62), rot_deg=0.0):
    """Light and reflect with an HDRI (rotated rot_deg about Z); the camera sees a plain studio-grey
    backdrop."""
    w = scn.world
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(path, check_existing=True)
    if rot_deg:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Rotation"].default_value[2] = radians(rot_deg)
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[1].default_value = strength
    bg2 = nt.nodes.new("ShaderNodeBackground")
    bg2.inputs[0].default_value = (*backdrop, 1.0)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(bg2.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


def remove_previous():
    old = bpy.data.collections.get(COLL_NAME)
    if not old:
        return
    for ob in list(old.all_objects):
        bpy.data.objects.remove(ob, do_unlink=True)

    def drop(c):
        for ch in list(c.children):
            drop(ch)
        bpy.data.collections.remove(c)
    drop(old)
    for blocks in (bpy.data.meshes, bpy.data.curves):
        for d in list(blocks):
            if d.users == 0 and d.name.startswith("F140"):
                blocks.remove(d)


def hide_startup_cube():
    """Blender's untouched 2 m startup cube sits on the origin and swallows the engine."""
    ob = bpy.data.objects.get("Cube")
    if (ob and ob.type == 'MESH' and len(ob.data.vertices) == 8 and ob.location.length < 1e-6
            and abs(max(ob.dimensions) - 2.0) < 1e-3 and not ob.hide_render):
        ob.hide_viewport = True
        ob.hide_render = True
        print("  hid Blender's default startup cube (it would hide the engine); "
              "unhide it in the Outliner if you want it back")


def new_coll(name, parent):
    c = bpy.data.collections.new(name)
    parent.children.link(c)
    return c


def new_empty(name, coll, parent=None, loc=(0, 0, 0), rot=(0, 0, 0), size=0.05, kind='PLAIN_AXES'):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = kind
    e.empty_display_size = size
    coll.objects.link(e)
    if parent:
        e.parent = parent
    e.location = Vector(loc) * MM
    e.rotation_euler = rot
    return e


CRANK = "(frame*dpf+off)"      # crank angle in degrees, as a driver sub-expression


def drive(ob, path, index, expr, ctrl, extra=None):
    fc = ob.driver_add(path, index) if index is not None else ob.driver_add(path)
    d = fc.driver
    d.type = 'SCRIPTED'
    names = [("dpf", "deg_per_frame"), ("off", "offset_deg")] + (extra or [])
    for vname, prop in names:
        v = d.variables.new()
        v.name = vname
        v.type = 'SINGLE_PROP'
        v.targets[0].id = ctrl
        v.targets[0].data_path = f'["{prop}"]'
    d.expression = expr
    return fc


def bake_boolean(target, cutter, operation='DIFFERENCE'):
    """Apply an exact boolean without bpy.ops (works headless)."""
    mod = target.modifiers.new("bake", 'BOOLEAN')
    mod.operation = operation
    mod.solver = 'EXACT'
    mod.use_self = True
    mod.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = target.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = target.data
    target.modifiers.remove(mod)
    target.data = me
    me.name = old.name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    try:
        me.set_sharp_from_angle(angle=radians(35))
    except Exception:
        pass


# ---------------------------------------------------------------------------------------
# 5. DERIVED GEOMETRY
# ---------------------------------------------------------------------------------------
def derive():
    g = {}
    g["r"] = P["stroke"] / 2
    g["l"] = P["rod_length"]
    g["half"] = P["bank_angle"] / 2
    g["deck"] = g["r"] + g["l"] + P["comp_height"] + P["deck_clearance"]
    g["y0"] = P["bore_pitch"] / 2 + 10.0                     # cylinder 1 centre
    g["pin_y"] = [g["y0"] + k * P["bore_pitch"] + P["bank_offset"] / 2 for k in range(6)]
    g["main_y"] = [g["pin_y"][0] - P["bore_pitch"] / 2 + k * P["bore_pitch"] for k in range(7)]
    g["length"] = g["y0"] + 5 * P["bore_pitch"] + P["bank_offset"] + P["bore_pitch"] / 2 + 10.0
    order_index = {c: i for i, c in enumerate(BANK_ORDER)}
    banks = []
    for bi, (gamma, first, yshift, inb, label) in enumerate((
            (-g["half"], 1, P["bank_offset"], +1, "1-6"),     # -X bank sits rearward
            (+g["half"], 7, 0.0, -1, "7-12"))):
        cyls = []
        for k in range(6):
            cyls.append(dict(
                num=first + k, k=k,
                y=g["y0"] + k * P["bore_pitch"] + yshift,
                alpha=PIN_PHASE[k],
                fire=gamma + 120.0 * order_index[k + 1],
            ))
        banks.append(dict(index=bi, gamma=gamma, label=label, inb=inb, yshift=yshift, cyls=cyls,
                          chain_y=(-30.0 if bi == 0 else -12.0)))
    g["banks"] = banks

    # valve and cam layout (bank-local, mm)
    deck = g["deck"]
    valves = {}
    for kind in ("intake", "exhaust"):
        tau = P[f"{kind}_valve_angle"]
        Lv = P[f"{kind}_valve_len"]
        xf = P[f"{kind}_valve_x"]
        zf = deck + P["valve_face_above_deck"]
        tip_x = xf + Lv * sin(radians(tau))
        tip_z = zf + Lv * cos(radians(tau))
        stack = P["follower_thickness"] + P["cam_base_radius"]
        cam_x = tip_x + stack * sin(radians(tau))
        cam_z = tip_z + stack * cos(radians(tau))
        if kind == "intake":
            open_ = 360.0 - P["IVO_btdc"]
            close = 540.0 + P["IVC_abdc"]
        else:
            open_ = 180.0 - P["EVO_bbdc"]
            close = 360.0 + P["EVC_atdc"]
        valves[kind] = dict(tau=tau, Lv=Lv, xf=xf, zf=zf, tip_x=tip_x, tip_z=tip_z,
                            cam_x=cam_x, cam_z=cam_z, D=close - open_, c=(open_ + close) / 2,
                            lift=P[f"{kind}_lift"], R=P[f"{kind}_valve_d"] / 2,
                            vy=P[f"{kind}_valve_y"])
    g["valves"] = valves
    return g


def firing_order(g):
    ev = []
    for b in g["banks"]:
        for c in b["cyls"]:
            ev.append((c["fire"] % 720.0, c["num"]))
    ev.sort()
    i1 = [n for _, n in ev].index(1)
    ev = ev[i1:] + ev[:i1]                      # start the sequence at cylinder 1
    return [n for _, n in ev], ev


def lift_expr(theta_fire, v):
    K = 72000.0 - theta_fire
    psi = f"fmod({CRANK}+{K:.4f},720)"
    L = v["lift"] * MM
    return (f"({L:.6f}*pow(cos(pi*({psi}-{v['c']:.4f})/{v['D']:.4f}),2) "
            f"if abs({psi}-{v['c']:.4f})<{v['D'] / 2:.4f} else 0.0)")


def lobe_radius(a, delta, v):
    """Lobe radius (mm) at cam-local angle a (rad). Same law as lift_expr."""
    w = (a - delta + pi) % (2 * pi) - pi            # cam angle from the nose
    d = 2.0 * math.degrees(w)                        # equivalent crank degrees
    lift = v["lift"] * cos(pi * d / v["D"]) ** 2 if abs(d) < v["D"] / 2 else 0.0
    return P["cam_base_radius"] + lift


# ---------------------------------------------------------------------------------------
# 6. BUILD
# ---------------------------------------------------------------------------------------
def build():
    remove_previous()
    hide_startup_cube()
    scn = bpy.context.scene
    scn.unit_settings.system = 'METRIC'
    scn.unit_settings.length_unit = 'MILLIMETERS'
    scn.frame_start, scn.frame_end = 1, 120
    scn.render.fps = 24

    g = derive()
    M = build_materials()
    r, l, deck = g["r"], g["l"], g["deck"]

    top = new_coll(COLL_NAME, scn.collection)
    c_ctrl = new_coll("F140HC_Control", top)
    c_rot = new_coll("F140HC_Rotating", top)
    c_valve = new_coll("F140HC_Valvetrain", top)
    c_house = new_coll("F140HC_Housings", top)
    c_ind = new_coll("F140HC_Intake_Exhaust", top)
    c_bolt = new_coll("F140HC_Fasteners", top)
    c_drive = new_coll("F140HC_Gearbox_Placeholder", top)
    c_ref = new_coll("F140HC_Reference", top)
    c_tmp = new_coll("F140HC_tmp", top)

    root = new_empty("F140HC_ROOT", c_ctrl, loc=(0, 0, 150.0 + P["sump_depth"] - 40.0),
                     size=0.2, kind='ARROWS')
    ctrl = new_empty("F140HC_CONTROL", c_ctrl, parent=root, loc=(0, -160, 520), size=0.08,
                     kind='SPHERE')
    ctrl["deg_per_frame"] = 6.0
    ctrl["offset_deg"] = 0.0
    ctrl["cutaway"] = 1
    for key, desc, lo, hi in (("deg_per_frame", "Crank degrees per frame", -60.0, 60.0),
                              ("offset_deg", "Crank angle offset (deg)", -720.0, 720.0),
                              ("cutaway", "1 = cut bank 7-12 open", 0, 1)):
        try:
            ctrl.id_properties_ui(key).update(min=lo, max=hi, description=desc)
        except Exception:
            pass

    bank_obj = []
    for b in g["banks"]:
        e = new_empty(f"F140HC_Bank_{b['label']}", c_ctrl, parent=root,
                      rot=(0, radians(b["gamma"]), 0), size=0.06)
        bank_obj.append(e)

    # ---------------- crankshaft ----------------
    mb = MB()
    pr = P["pin_diameter"] / 2
    mr = P["main_diameter"] / 2
    mw = P["main_width"]
    for y in g["main_y"]:
        mb.cyl_y(mr, y - mw / 2, y + mw / 2, seg=40)
    for k, yp in enumerate(g["pin_y"]):
        a = PIN_PHASE[k]
        px, pz = rot_xz(0.0, r, a)
        mb.cyl_y(pr, yp - P["pin_length"] / 2, yp + P["pin_length"] / 2, px, pz, seg=36)
        web = circle_pts(0, r, pr + 7, 28) + [
            (P["counterweight_radius"] * sin(radians(t)), P["counterweight_radius"] * cos(radians(t)))
            for t in range(180 - 62, 180 + 63, 4)]
        web = hull2d([rot_xz(x, z, a) for x, z in web])
        mb.prism_xz(web, g["main_y"][k] + mw / 2, yp - P["pin_length"] / 2)
        mb.prism_xz(web, yp + P["pin_length"] / 2, g["main_y"][k + 1] - mw / 2)
    snout_front = P["head_front"] - 37.0
    mb.cyl_y(22.0, snout_front + 20, g["main_y"][0] - mw / 2 + 0.5, seg=32)
    for b in g["banks"]:                                       # crank sprockets
        rc = sprocket_radius(P["crank_sprocket_teeth"])
        mb.prism_xz(list(reversed(gear_profile(0, 0, P["crank_sprocket_teeth"], rc))),
                    b["chain_y"] - 6, b["chain_y"] + 6, mi=1)
    mb.lathe([(30, snout_front + 20), (30, -20)], 32, ROT_Z_TO_Y, mi=2)   # damper hub
    mb.ring_y(30, P["crank_pulley_r"], snout_front, snout_front + 30, seg=64, mi=2)   # crank pulley (polished)
    mb.cyl_y(55, g["main_y"][-1] + mw / 2 - 0.5, g["length"] + 6, seg=48)   # rear flange
    crank = mb.finish("F140HC_Crankshaft", c_rot, [M["steel"], M["dlc"], M["polished"]], parent=root)
    drive(crank, "rotation_euler", 1, f"radians{CRANK}", ctrl)

    # ---------------- pistons, rods ----------------
    R = P["bore"] / 2
    ch = P["comp_height"]
    wp = P["wrist_pin_diameter"] / 2
    sk = -P["piston_skirt"]
    piston_prof = [(0, sk), (R - 0.4, sk), (R - 0.4, ch - 16), (R - 3, ch - 16), (R - 3, ch - 13),
                   (R - 0.2, ch - 13), (R - 0.2, ch - 10.5), (R - 3, ch - 10.5), (R - 3, ch - 9),
                   (R - 0.2, ch - 9), (R - 0.2, ch - 6.5), (R - 3, ch - 6.5), (R - 3, ch - 5),
                   (R - 0.2, ch - 5), (R - 0.2, ch), (R - 8, ch + 0.4 * P["crown_dome"]),
                   (0, ch + P["crown_dome"])]
    rw = P["rod_width"]
    pistons, rods = {}, {}
    for b, be in zip(g["banks"], bank_obj):
        for c in b["cyls"]:
            phase = c["alpha"] - b["gamma"]
            zexp = (f"{r * MM:.6f}*cos(radians({CRANK}+{phase:.4f}))+sqrt({(l * MM) ** 2:.9f}"
                    f"-pow({r * MM:.6f}*sin(radians({CRANK}+{phase:.4f})),2))")
            # piston + wrist pin + rings
            mb = MB()
            mb.lathe(piston_prof, 48)
            mb.cyl_y(wp, -R * 0.78, R * 0.78, seg=24, mi=1)
            pis = mb.finish(f"F140HC_Piston_C{c['num']:02d}", c_rot, [M["piston"], M["dlc"]], parent=be)
            pis.location = (0, c["y"] * MM, (r + l) * MM)
            drive(pis, "location", 2, zexp, ctrl)
            pistons[c["num"]] = pis
            # titanium rod, origin at the small end
            mb = MB()
            mb.ring_y(wp, wp + 6, -rw * 0.38, rw * 0.38, seg=32)
            mb.ring_y(pr, pr + 9, -rw / 2, rw / 2, cz=-l, seg=40)
            z_top, z_bot = -wp - 3, -l + pr + 4
            w_top, w_bot = 18.0, 32.0
            for sx in (-1, 1):                                   # I-beam flanges
                mb.prism_xz([(sx * (w_top / 2 - 5), z_top), (sx * w_top / 2, z_top),
                             (sx * w_bot / 2, z_bot), (sx * (w_bot / 2 - 5), z_bot)][::sx],
                            -rw * 0.38, rw * 0.38)
            mb.prism_xz([(-(w_top / 2 - 4.5), z_top), (w_top / 2 - 4.5, z_top),
                         (w_bot / 2 - 4.5, z_bot), (-(w_bot / 2 - 4.5), z_bot)][::-1], -3.0, 3.0)
            for sx in (-1, 1):                                   # rod bolts
                bx = sx * (pr + 5.0)
                mb.lathe([(4.2, -l - 15.0), (4.2, -l + 16.0)], 16, T(bx, 0, 0), mi=1)
                mb.lathe([(7.0, -l - 24.0), (7.0, -l - 16.5)], 6, T(bx, 0, 0), mi=1)
            rod = mb.finish(f"F140HC_Rod_C{c['num']:02d}", c_rot, [M["titanium"], M["steel"]], parent=be)
            rod.location = (0, c["y"] * MM, (r + l) * MM)
            drive(rod, "location", 2, zexp, ctrl)
            drive(rod, "rotation_euler", 1,
                  f"-asin({r / l:.6f}*sin(radians({CRANK}+{phase:.4f})))", ctrl)
            rods[c["num"]] = rod
            for o in (pis, rod):
                o["cyl"] = c["num"]
                o["phase_deg"] = phase
                o["theta_fire"] = c["fire"]

    # ---------------- valvetrain ----------------
    tf, Lf = P["follower_thickness"], P["follower_arm"]
    inst = P["spring_installed"]
    journals = {}
    for b, be in zip(g["banks"], bank_obj):
        inb = b["inb"]
        for kind, v in g["valves"].items():
            side = inb if kind == "intake" else -inb             # which side of the bore
            s = side * v["tau"]                                    # signed lean (deg)
            # spring helix (shared shape per kind)
            coil_r = P[f"spring_coil_d_{'in' if kind == 'intake' else 'ex'}"] / 2
            cu = bpy.data.curves.new(f"F140HC_SpringCurve_{kind}_{b['label']}", 'CURVE')
            cu.dimensions = '3D'
            cu.bevel_depth = P["spring_wire_d"] / 2 * MM
            cu.bevel_resolution = 2
            sp = cu.splines.new('POLY')
            npts = int(P["spring_coils"] * 24)
            sp.points.add(npts - 1)
            for i in range(npts):
                t = i / (npts - 1)
                ang = t * P["spring_coils"] * 2 * pi
                sp.points[i].co = (coil_r * MM * cos(ang), coil_r * MM * sin(ang),
                                   (P["spring_wire_d"] / 2 + t * (inst - P["spring_wire_d"])) * MM, 1)
            cu.materials.append(M["spring"])
            lobes = []
            for c in b["cyls"]:
                theta_pk = c["fire"] + v["c"]
                delta = radians(s) + pi - radians(theta_pk) / 2
                lx = lift_expr(c["fire"], v)
                for vi, vy in enumerate((-v["vy"], v["vy"])):
                    tag = f"C{c['num']:02d}_{kind[:2].upper()}{vi + 1}"
                    y = c["y"] + vy
                    guide = new_empty(f"F140HC_Guide_{tag}", c_valve, parent=be,
                                      loc=(side * v["tip_x"], y, v["tip_z"]),
                                      rot=(0, radians(s), 0), size=0.008)
                    # valve: tip at origin, head down -Z; retainer + collets on top
                    mb = MB()
                    sr = P["stem_d"] / 2
                    mb.lathe([(0, -v["Lv"]), (v["R"], -v["Lv"]), (v["R"], -v["Lv"] + 1.6),
                              (v["R"] * 0.62, -v["Lv"] + 6.0), (sr + 1.2, -v["Lv"] + 14.0),
                              (sr, -v["Lv"] + 22.0), (sr, 0.0), (0, 0.0)], 32)
                    mb.lathe([(sr + 0.2, -8.0), (11.0, -8.0), (8.0, -2.5), (sr + 0.2, -2.5)], 28, mi=1,
                             closed=True)
                    valve = mb.finish(f"F140HC_Valve_{tag}", c_valve, [M["valve"], M["titanium"]],
                                      parent=guide)
                    drive(valve, "location", 2, f"-{lx}", ctrl)
                    valve["lobe_delta"] = delta
                    valve["center"] = v["c"]
                    valve["duration"] = v["D"]
                    valve["lift_max"] = v["lift"]
                    valve["theta_fire"] = c["fire"]
                    valve["lean_deg"] = s
                    valve["face_radius"] = v["R"]
                    valve["valve_len"] = v["Lv"]
                    valve["cyl"] = c["num"]
                    valve["kind"] = kind
                    # spring
                    spring = bpy.data.objects.new(f"F140HC_Spring_{tag}", cu)
                    c_valve.objects.link(spring)
                    spring.parent = guide
                    spring.location = (0, 0, (-8.0 - inst) * MM)
                    drive(spring, "scale", 2, f"1-({lx})/{inst * MM:.6f}", ctrl)
                    # sliding finger follower, pivot outboard of the tip
                    px = side * Lf
                    mb = MB()
                    arm = Lf + 9.0
                    mb.box(-side * (arm / 2 - 6.0), 0, 0, arm, 12.0, tf)
                    mb.lathe([(5.5, -tf / 2 - 2.0), (5.5, tf / 2)], 20, mi=1)
                    fin = mb.finish(f"F140HC_Finger_{tag}", c_valve, [M["steel"], M["dlc"]], parent=guide)
                    fin.location = (px * MM, 0, tf / 2 * MM)
                    drive(fin, "rotation_euler", 1, f"{-side}*asin(({lx})/{Lf * MM:.6f})", ctrl)
                    # static: pivot post, guide boss, spring seat
                    mb = MB()
                    mb.lathe([(6.0, -70.0), (6.0, tf / 2 - 7.0), (0, tf / 2 - 4.0)], 16, T(px, 0, 0))
                    mb.lathe([(sr + 0.5, -8.0 - inst - 16.0), (8.0, -8.0 - inst - 16.0),
                              (8.0, -8.0 - inst - 1.5), (14.0, -8.0 - inst - 1.5), (14.0, -8.0 - inst),
                              (sr + 0.5, -8.0 - inst)], 28, closed=True)
                    mb.finish(f"F140HC_Seat_{tag}", c_valve, [M["alu_mach"]], parent=guide)
                    lobes.append((y, delta))
            # camshaft for this kind on this bank
            mb = MB()
            ys = [cc["y"] for cc in b["cyls"]]
            jy = [ys[0] - P["bore_pitch"] / 2 + j * P["bore_pitch"] for j in range(7)]
            journals[(b["index"], kind)] = jy
            cam_front = b["chain_y"] - 6.0
            mb.cyl_y(13.0, cam_front, jy[-1] + 9.0, seg=24)
            for y in jy:
                mb.cyl_y(17.0, y - 8.0, y + 8.0, seg=32)
            for y, delta in lobes:
                prof = []
                for i in range(240):
                    a = 2 * pi * i / 240
                    rr = lobe_radius(a, delta, v)
                    prof.append((rr * sin(a), rr * cos(a)))
                mb.prism_xz(prof[::-1], y - 7.0, y + 7.0, mi=1)
            rcs = sprocket_radius(P["cam_sprocket_teeth"])
            mb.prism_xz(list(reversed(gear_profile(0, 0, P["cam_sprocket_teeth"], rcs))),
                        b["chain_y"] - 6, b["chain_y"] + 6, mi=2)
            mb.cyl_y(31.0, b["chain_y"] + 6, -1.0, seg=40, mi=2)      # VVT phaser body
            cam = mb.finish(f"F140HC_Cam_{kind}_{b['label']}", c_valve,
                            [M["steel"], M["dlc"], M["alu_mach"]], parent=be)
            cam.location = (side * v["cam_x"] * MM, 0, v["cam_z"] * MM)
            drive(cam, "rotation_euler", 1, f"radians{CRANK}*0.5", ctrl)

    # ---------------- housings ----------------
    hw, bw, hh = P["head_half_width"], P["barrel_half_width"], P["head_height"]
    L = g["length"]
    hf, hr = P["head_front"], L + P["head_rear_ext"]          # head / cover y extent
    hc, hl = (hf + hr) / 2, hr - hf
    # block: crankcase + two barrel banks, minus bores, crank cavity, main line
    mb = MB()
    cb, ct = P["crankcase_bottom"], P["crankcase_top"]
    cw = P["crankcase_half_width"]
    mb.box(0, L / 2, (cb + ct) / 2, 2 * cw, L, ct - cb)
    for b in g["banks"]:
        mb.box(0, L / 2, deck / 2, 2 * bw, L, deck, M=RY(b["gamma"]))
    block = mb.finish("F140HC_Block", c_house, [M["block_cast"]], parent=root)
    cut = MB()
    for b in g["banks"]:
        for c in b["cyls"]:
            cut.cyl(R, 40.0, deck + 5.0, M=RY(b["gamma"]) @ T(0, c["y"], 0), seg=48)
    cav_r = max(P["counterweight_radius"] + 8.0, 95.0)
    for k in range(6):
        cut.cyl_y(cav_r, g["main_y"][k] + 9.0, g["main_y"][k + 1] - 9.0, seg=48)
    cut.cyl_y(mr + 0.6, -5.0, L + 5.0, seg=40)
    cutter = cut.finish("F140HC_cut_block", c_tmp, [], parent=root)
    bake_boolean(block, cutter)

    heads, covers = [], []
    for b, be in zip(g["banks"], bank_obj):
        inb = b["inb"]
        mb = MB()
        mb.box(0, hc, deck + hh / 2, 2 * hw, hl, hh)
        head = mb.finish(f"F140HC_Head_{b['label']}", c_house, [M["block_cast"]], parent=be)
        cut = MB()
        cut.box(0, hc, deck + P["gallery_floor"] + (hh - P["gallery_floor"]) / 2 + 1,
                2 * (hw - 6), hl - 16, hh - P["gallery_floor"] + 2)
        vi, ve = g["valves"]["intake"], g["valves"]["exhaust"]
        for c in b["cyls"]:
            cut.cyl(R, deck - 1.0, deck + 9.0, M=T(0, c["y"], 0), seg=48)          # chamber
            cut.cyl(11.0, deck + 5.0, deck + hh + 1, M=T(0, c["y"], 0), seg=24)    # plug well
            cut.between((inb * vi["xf"], c["y"], deck + 14.0),
                        (inb * (hw + 6), c["y"], deck + 70.0), 17.0)               # intake port
            cut.between((-inb * ve["xf"], c["y"], deck + 12.0),
                        (-inb * (hw + 6), c["y"], deck + 45.0), 15.0)              # exhaust port
        cutter = cut.finish("F140HC_cut_head", c_tmp, [], parent=be)
        bake_boolean(head, cutter)
        heads.append(head)
        # block and head side detail (side photo 13, video 19-22 s): vertical ribs between the
        # cylinders on the outboard barrel face, a raised rail along the head joint, and bosses
        o_ = -inb
        mb = MB()
        for c in b["cyls"]:
            for dyr in (-P["bore_pitch"] / 2, P["bore_pitch"] / 2):
                mb.rbox(o_ * (bw + 3.0), c["y"] + dyr, deck - 70.0, 8.0, 12.0, 120.0, 2.5, 2)
            mb.cyl(9.0, -6.0, 6.0, M=T(o_ * (bw + 2.0), c["y"], deck - 40.0) @ RY(90), seg=20)   # water boss
        mb.rbox(o_ * (bw + 4.0), (hf + hr) / 2, deck - 6.0, 10.0, hr - hf - 40.0, 14.0, 3.0, 2)  # joint rail
        for j in range(7):                                                      # head bolt bosses on the face
            yb = b["cyls"][0]["y"] - P["bore_pitch"] / 2 + j * P["bore_pitch"]
            mb.cyl(8.0, -5.0, 5.0, M=T(o_ * (hw + 2.0), yb, deck + 22.0) @ RY(90), seg=16)
        mb.finish(f"F140HC_BlockSideDetail_{b['label']}", c_house, [M["block_cast"]], parent=be)
        # cam towers and bearing caps
        mb = MB()
        for kind, v in g["valves"].items():
            side = inb if kind == "intake" else -inb
            for y in journals[(b["index"], kind)]:
                floor = deck + P["gallery_floor"]
                mb.box(side * v["cam_x"], y, (floor + v["cam_z"]) / 2, 52.0, 16.0, v["cam_z"] - floor)
                mb.box(side * v["cam_x"], y, v["cam_z"] + 12.0, 52.0, 16.0, 24.0)
        towers = mb.finish(f"F140HC_CamTowers_{b['label']}", c_house, [M["alu_mach"]], parent=be)
        cut = MB()
        for kind, v in g["valves"].items():
            side = inb if kind == "intake" else -inb
            cut.cyl_y(17.3, -10.0, L + 10.0, cx=side * v["cam_x"], cz=v["cam_z"], seg=32)
        bake_boolean(towers, cut.finish("F140HC_cut_towers", c_tmp, [], parent=be))
        # cam cover (measured from Amalgam photos 09, 11, 13, 20): flat top, chamfered
        # outboard edge, plan-view rounded ends, hollow
        o = -inb                                        # outboard direction in bank-local x
        z0 = deck + hh
        # flat bolting lip along both lower edges (bolts sit on it: side photo 13, video 11.4 s)
        prof = [(-82, 0), (82, 0), (82, 7), (77, 7), (75, 12), (74, 30), (70, 38), (62, 42), (-46, 42),
                (-62, 38), (-68, 12), (-70, 7), (-82, 7)]
        Hc = P["cover_height"]
        kx = hw / 82.0
        prof = [(o * x * kx, z * Hc / 42.0) for x, z in prof]
        Rend = 34.0

        def ring_at(y, d):
            k = (hw - Rend + sqrt(max(0.0, Rend ** 2 - (Rend - d) ** 2))) / hw
            return [(x * k, y, z0 + z) for x, z in prof]
        sections = []
        for i in range(9):                                # rounded front end
            d = Rend * (1 - cos((pi / 2) * i / 8))
            sections.append(ring_at(hf + d, d))
        for i in range(8, -1, -1):                        # rounded rear end
            d = Rend * (1 - cos((pi / 2) * i / 8))
            sections.append(ring_at(hr - d, d))
        mb = MB()
        mb.loft(sections)
        for j in range(7):                                # bolt bosses on the outboard top edge
            yb = b["cyls"][0]["y"] - P["bore_pitch"] / 2 + j * P["bore_pitch"]
            mb.cyl(8.0, z0 + Hc - 4.0, z0 + Hc + 4.0, M=T(o * 52.0 * kx, yb, 0), seg=20)
        cover = mb.finish(f"F140HC_CamCover_{b['label']}", c_house, [M["rosso"]], parent=be,
                          smooth_angle=50.0)
        cut = MB()
        cut.box(0, hc, z0 + (Hc - 8.0) / 2, 2 * (hw - 12), hl - 24, Hc - 4.0)
        bake_boolean(cover, cut.finish("F140HC_cut_cover", c_tmp, [], parent=be))
        covers.append(cover)
        # coil boots, oil filler cap, plugs
        mb = MB()
        pl = MB()
        for c in b["cyls"]:
            ztop = z0 + Hc
            mb.rbox(o * 18.0, c["y"], ztop + 13.0, 46.0, 36.0, 26.0, 6.0)
            mb.rbox(o * 18.0, c["y"] - 23.0, ztop + 20.0, 16.0, 14.0, 12.0, 3.0)
            mb.cyl(9.0, deck + 70.0, ztop, M=T(0, c["y"], 0), seg=20)
            pl.lathe([(0, deck + 8.0), (2.5, deck + 8.0), (7.0, deck + 12.0), (7.0, deck + 30.0),
                      (8.0, deck + 30.0), (8.0, deck + 40.0), (5.5, deck + 42.0), (5.5, deck + 72.0),
                      (0, deck + 72.0)], 6 * 4, T(0, c["y"], 0))
        for dx in (-13.0, 13.0):                          # figure-8 oil filler cap
            yf = min(c_["y"] for c_ in b["cyls"]) - 0.68 * P["bore_pitch"]   # photo 13: 0.68 pitch ahead
            mb.cyl(14.0, z0 + Hc, z0 + Hc + 16.0, M=T(o * 8.0 + dx, yf, 0), seg=28)
        mb.finish(f"F140HC_Coils_{b['label']}", c_house, [M["black"]], parent=be)
        pl.finish(f"F140HC_SparkPlugs_{b['label']}", c_house, [M["ceramic"]], parent=be)

    # timing chains (static path), timing cover
    cover_pts = []
    for b in g["banks"]:
        rc, rcs = sprocket_radius(P["crank_sprocket_teeth"]), sprocket_radius(P["cam_sprocket_teeth"])
        centres = [((0.0, 0.0), rc)]
        for kind, v in g["valves"].items():
            side = b["inb"] if kind == "intake" else -b["inb"]
            centres.append((rot_xz(side * v["cam_x"], v["cam_z"], b["gamma"]), rcs))
        path = hull2d([p for (cx, cz), rr in centres for p in circle_pts(cx, cz, rr, 72)])
        mb = MB()
        mb.ribbon_xz(path, 3.5, b["chain_y"] - 5.0, b["chain_y"] + 5.0)
        mb.finish(f"F140HC_TimingChain_{b['label']}", c_rot, [M["chain"]], parent=root)
        cover_pts += [p for (cx, cz), rr in centres for p in circle_pts(cx, cz, rr + 16, 48)]
    # front casting: V-shield from the heads down to the dry sump (front photo 11)
    def bank_pt(bi, xl, zl):
        return rot_xz(xl, zl, g["banks"][bi]["gamma"])
    tc_outline = [tuple(map(float, p_)) for p_ in P["front_casting"]]
    tc_c = (0.0, 100.0)

    def shrink(poly, k):
        return [(tc_c[0] + (x - tc_c[0]) * k, tc_c[1] + (z - tc_c[1]) * k) for x, z in poly]
    mb = MB()
    mb.prism_xz(tc_outline, hf, 0.0)
    tcover = mb.finish("F140HC_TimingCover", c_house, [M["alu_cast"]], parent=root)
    cut = MB()
    cut.prism_xz(shrink(tc_outline, 0.92), hf + 5.0, 1.0)
    cut.cyl_y(33.0, hf - 15.0, 5.0, seg=32)
    bake_boolean(tcover, cut.finish("F140HC_cut_tc", c_tmp, [], parent=root))

    # ---------------- front accessory drive (front photo 11, positions vs crank centre) ----
    yp = hf - 25.0                                       # belt plane
    acc = {}
    for name, (ax, az, pr_, body_r, body_len) in P["accessories"].items():
        mb = MB()
        if body_r:
            mb.cyl_y(body_r, hf + 2.0, hf + 2.0 + body_len, cx=ax, cz=az, seg=48)
            mb.cyl_y(body_r * 0.55, yp + 8.0, hf + 2.0, cx=ax, cz=az, seg=32, mi=1)
            if name == "alternator":                     # cooling fins on the nose
                for i in range(18):
                    a = 2 * pi * i / 18
                    mb.box(ax + (body_r - 6) * cos(a), hf + 14.0, az + (body_r - 6) * sin(a),
                           4.0, 22.0, 12.0, M=None, mi=1)
        body = mb.finish(f"F140HC_{name}_body", c_house,
                         [M["alu_cast"], M["alu_mach"]], parent=root) if body_r else None
        mb = MB()                                        # pulley, rotates with the belt
        mb.ring_y(pr_ * 0.35, pr_, yp - 13.0, yp + 13.0, seg=48)
        mb.ring_y(pr_ * 0.35, pr_ + 3.0, yp - 14.0, yp - 11.0, seg=48)
        mb.ring_y(pr_ * 0.35, pr_ + 3.0, yp + 11.0, yp + 14.0, seg=48)
        mb.cyl_y(pr_ * 0.38, yp - 16.0, yp + 2.0, seg=24, mi=1)
        for i in range(5):                               # spokes so rotation reads
            a = 2 * pi * i / 5
            mb.box(0.62 * pr_ * cos(a), yp - 10.0, 0.62 * pr_ * sin(a), 0.3 * pr_, 4.0, 6.0,
                   M=Matrix.Rotation(-a, 4, 'Y'), mi=1)
        pul = mb.finish(f"F140HC_{name}_pulley", c_rot, [M["polished"], M["steel"]], parent=root)
        pul.location = (ax * MM, 0, az * MM)
        ratio = P["crank_pulley_r"] / pr_
        drive(pul, "rotation_euler", 1, f"radians{CRANK}*{ratio:.5f}", ctrl)
        acc[name] = (ax, az, pr_)
    # crank pulley sits on the crank snout (part of the crankshaft mesh); belt around all
    route = [((0.0, 0.0), P["crank_pulley_r"] + 2.5)]
    for name, side in P["belt_route"]:
        ax, az, pr_ = acc[name]
        route.append(((ax, az), side * (pr_ + 2.5)))
    mb = MB()
    mb.ribbon_xz(serpentine(route), 2.5, yp - 10.0, yp + 10.0)
    mb.finish("F140HC_AccessoryBelt", c_rot, [M["black"]], parent=root)
    # ---------------- near-side lower details (traced from side photo 13) -----------------
    NS = P["near_side"]
    m_alt, m_blk, m_cast = M["alu_mach"], M["black"], M["alu_cast"]
    # alternator: black rear cover, slotted housings, stator band, nose (pulley spins separately)
    ax_, az_ = NS["alt_xz"]
    mb = MB()
    for y0s, y1s, r_, kind in NS["alt_sections"]:
        ym, Ls = (y0s + y1s) / 2, abs(y1s - y0s)
        if kind == "slots":
            mb.cyl_y(r_ - 7, y0s, y1s, cx=ax_, cz=az_, seg=48, mi=1)
            for yy in (min(y0s, y1s), max(y0s, y1s) - 5):
                mb.ring_y(r_ - 8, r_, yy, yy + 5, cx=ax_, cz=az_, seg=48)
            nb = 24
            for i in range(nb):
                a = 2 * pi * (i + 0.5) / nb
                mb.box(0, 0, 0, 5.0, Ls - 6, 10.5, M=T(ax_, ym, az_) @ Matrix.Rotation(-a, 4, 'Y') @ T(r_ - 3, 0, 0))
        elif kind == "ribbed":
            mb.cyl_y(r_ - 3, y0s, y1s, cx=ax_, cz=az_, seg=48, mi=1)
            for i in range(16):
                a = 2 * pi * i / 16
                mb.box(0, 0, 0, 6.0, Ls, 5.0, M=T(ax_, ym, az_) @ Matrix.Rotation(-a, 4, 'Y') @ T(r_ - 2, 0, 0), mi=1)
        else:
            mb.cyl_y(r_, y0s, y1s, cx=ax_, cz=az_, seg=48, mi=1)
    lug = NS["alt_lug"]
    mb.rbox(*lug, 4.0, 2)
    mb.lathe([(7, 0), (7, 9)], 6, T(lug[0] - lug[3] / 2 - 1, lug[1], lug[2]) @ RY(-90), mi=0)
    mb.finish("F140HC_Alternator", c_house, [m_alt, m_blk], parent=root)
    # water pump (side photo 13, u 1290-1500 / v 900-1065): rounded cast body with two ribs, a bolted
    # rectangular cover facing outboard, and an outlet stub at the front whose open end faces the camera
    WP = NS["water_pump_body"]
    mb = MB()
    mb.rbox(WP["x"], WP["y"], WP["z"], WP["sx"], WP["sy"], WP["sz"], 14.0, 3)
    for dz in (-20.0, 20.0):
        mb.rbox(WP["x"] - 2, WP["y"], WP["z"] + dz, WP["sx"] + 6, WP["sy"] - 10, 5.0, 2.0, 2)
    cy_, cz_, csy, csz = WP["cover"]
    xc_ = WP["cover_x"]
    mb.rbox((xc_ + WP["x"] - WP["sx"] / 2 + 6) / 2, cy_, cz_, abs(xc_ - (WP["x"] - WP["sx"] / 2 + 6)), csy - 8, csz - 8, 12.0, 3)
    mb.rbox(xc_ + 4, cy_, cz_, 9.0, csy, csz, 16.0, 3)                          # cover plate
    mb.rbox(xc_ - 1, cy_, cz_, 3.0, csy - 30, csz - 36, 10.0, 2)                # raised centre panel
    for by, bz in WP["cover_bolts"]:
        mb.lathe([(7.5, 0), (7.5, 4), (5.0, 4), (5.0, 8)], 6, T(xc_, by, bz) @ RY(-90), mi=1)
    p0s, p1s = Vector(WP["stub"][0]), Vector(WP["stub"][1])
    mb.between(tuple(p0s), tuple(p1s), 15.0)
    mb.lathe([(11, 0), (18, 0), (18, 10), (11, 10)], 32,
             T(*p1s) @ (p1s - p0s).to_track_quat('Z', 'Y').to_matrix().to_4x4(), closed=True)
    mb.finish("F140HC_WaterPumpHousing", c_house, [M["wp_cast"], M["steel"]], parent=root)
    # oil pump (side photo 13, u 1060-1215 / v 885-1065): cylindrical rear stage, boxy front housing with
    # a bolted end cover, relief-valve boss on top, a bolt boss, and the outlet elbow going down. A dark
    # drive housing links it to the water pump; the sump wall behind carries a raised rectangular boss.
    ox = NS["oil_pump_x"]
    OP = NS["oil_pump"]
    mb = MB()
    mb.rbox(ox + 22, 150, -40, 26, 150, 18, 4.0, 2)                              # mounting rail on the sump
    y0r, y1r, rr = OP["rear"]
    mb.cyl_y(rr, y0r, y1r, cx=ox, cz=OP["z"], seg=40)
    for yy in (y0r, y0r + 26, y1r - 6):
        mb.cyl_y(rr + 4, yy, yy + 6, cx=ox, cz=OP["z"], seg=40)
    yb, sy_b, sx_b, sz_b = OP["front_box"]
    mb.rbox(ox, yb, OP["z"] + 2, sx_b, sy_b, sz_b, 12.0, 3)
    mb.rbox(ox, OP["cover_y"] + 4, OP["z"] + 2, sx_b - 6, 8.0, sz_b - 8, 14.0, 3)    # end cover
    for dx_, dz_ in ((-26, -34), (-26, 38), (26, -34), (26, 38)):
        mb.lathe([(5.5, 0), (5.5, 6)], 6, T(ox + dx_, OP["cover_y"], OP["z"] + 2 + dz_) @ RX(90), mi=1)
    ry_, rz_ = OP["relief"]                                                      # relief valve on top
    mb.lathe([(11, 0), (11, 10), (9, 10), (9, 20)], 24, T(ox - 8, ry_, rz_ - 8))
    mb.lathe([(8.5, 20), (8.5, 28)], 6, T(ox - 8, ry_, rz_ - 8), mi=1)
    by_, bz_ = OP["boss"]                                                        # bolt boss, outboard face
    mb.lathe([(12, 0), (12, 8)], 24, T(ox - sx_b / 2 + 2, by_, bz_) @ RY(-90))
    mb.lathe([(7.5, 8), (7.5, 14)], 6, T(ox - sx_b / 2 + 2, by_, bz_) @ RY(-90), mi=1)
    e0, e1 = (Vector(v_) for v_ in OP["elbow"])                                  # outlet: straight down
    mb.between(tuple(e0 + Vector((0, 0, 20))), tuple(e1), 15.0)
    mb.rbox(e1.x, e1.y, e1.z - 4, 40, 34, 9, 5.0, 2)                            # 2-bolt flange
    for dy_ in (-11.0, 11.0):
        mb.lathe([(6, 0), (6, 6)], 6, T(e1.x - 12, e1.y + dy_, e1.z - 8.5) @ RX(180), mi=1)
    for yy, zz in NS["oil_fittings"]:                                            # hex fittings
        if 80 < yy < 210:
            mb.lathe([(9.5, 0), (9.5, 9), (6, 9), (6, 18)], 6, T(ox - 30, yy, zz) @ RY(-90), mi=1)
    for yy in range(85, 230, 36):                                                # rail bolts
        mb.lathe([(6.0, 0), (6.0, 6)], 6, T(ox + 9, yy, -40) @ RY(-90), mi=1)
    sx_, sy_, sz_ = NS["oil_sensor"]
    mb.lathe([(8, 0), (8, 8), (5, 8), (5, 26), (3, 30)], 16, T(sx_, sy_, sz_), mi=1)
    mb.finish("F140HC_OilPumpBody", c_house, [m_cast, M["steel"]], parent=root)
    mb = MB()                                                                    # drive housing (dark)
    d0, d1, dr = OP["drive"]
    mb.cyl_y(dr, d0, d1 + 4, cx=ox, cz=OP["z"], seg=40)
    mb.cyl_y(dr + 3, d1 - 6, d1, cx=ox, cz=OP["z"], seg=40)
    mb.finish("F140HC_PumpDriveHousing", c_house, [M["dlc"]], parent=root)
    mb = MB()
    mb.rbox(*NS["sump_boss"], 8.0, 3)
    mb.finish("F140HC_SumpSideBoss", c_house, [M["block_cast"]], parent=root)
    # black bracket at the rear of the near-bank head (side photo 13: u 393-453, v 630-783;
    # video 19-22 s): a vertical plate with a sensor block, bolted to the head's rear end
    mb = MB()
    hb = NS["rear_bracket"]
    mb.rbox(hb[0], hb[1], hb[2], 12.0, 44.0, hb[3], 3.0, 2)
    py_, pz_, pr_, pl_ = NS["bracket_puck"]                                     # round black sensor puck
    mb.lathe([(0, 0), (pr_, 0), (pr_, pl_ - 3), (pr_ - 3, pl_), (0, pl_)], 40, T(hb[0] - 6.0, py_, pz_) @ RY(-90))
    mb.finish("F140HC_RearHeadBracket", c_house, [M["black"]], parent=root)
    # dry-sump lobe visible under the catalyst front
    mb = MB()
    mb.rbox(*NS["sump_lobe"], 18.0, 4)
    mb.finish("F140HC_SumpLobe", c_house, [M["block_cast"]], parent=root)
    # differential side cover and output flange on the gearbox (left of the section)
    dyc, dzc = NS["diff_centre"]
    dxc = -P["gearbox"]["half_width"]
    Md = T(dxc, dyc, dzc) @ RY(-90)
    mb = MB()
    # stepped cast profile (photo 13, 2x): rim band with the bolt bosses, recessed panel, inner ring
    mb.lathe([(0, 0), (150, 0), (150, 9), (146, 14), (118, 17), (114, 12), (90, 12), (87, 16), (80, 16),
              (77, 12), (58, 13), (56, 18), (0, 18)], 72, Md)
    a0 = radians(NS["diff_bolt_start_deg"])
    for i in range(11):                                                          # double spokes per bolt
        a = a0 + 2 * pi * i / 11
        Mr = Md @ Matrix.Rotation(-a, 4, 'Z')
        for off in (-7.0, 7.0):
            mb.box(0, 0, 0, 58, 4.5, 6, M=Mr @ T(87, off, 15))
        mb.lathe([(13, 12), (13, 17), (11, 19)], 24, Mr @ T(131, 0, 0))         # bolt boss
        mb.lathe([(8.5, 19), (8.5, 21), (6.5, 23), (0, 23.5)], 24, Mr @ T(131, 0, 0), mi=1)   # button head
        mb.lathe([(2.6, 23.4), (2.6, 23.8)], 6, Mr @ T(131, 0, 0), mi=3)                    # Torx recess
    # polished output flange: 6 holes on a 41 mm circle, hub with turned grooves
    mb.lathe([(0, 18), (52, 18), (52, 30), (49, 33), (0, 33)], 64, Md, mi=2)
    for i in range(6):
        a = 2 * pi * i / 6 + 0.26
        mb.lathe([(5.0, 33.0), (5.0, 33.3), (0, 33.3)], 16, Md @ T(41 * cos(a), 41 * sin(a), 0), mi=3)
    mb.lathe([(0, 33), (35, 33), (35, 40), (33, 42), (24, 42), (24, 43), (16, 43), (16, 44), (0, 44)], 64, Md, mi=2)
    mb.finish("F140HC_DiffSideCover", c_drive, [M["magnesium"], M["steel"], M["polished"], M["black"]], parent=root)
    # polished hairpin tube on top of the gearbox, U-bend by the head bracket (photo 13)
    cu = bpy.data.curves.new("F140HC_GearboxHairpin", 'CURVE')
    cu.dimensions = '3D'; cu.bevel_depth = 6.5 * MM; cu.bevel_resolution = 4
    sp = cu.splines.new('NURBS'); sp.points.add(len(NS["hairpin"]) - 1)
    for j_, p_ in enumerate(NS["hairpin"]):
        sp.points[j_].co = (p_[0] * MM, p_[1] * MM, p_[2] * MM, 1)
    sp.order_u = 3; sp.use_endpoint_u = True; sp.resolution_u = 24
    cu.materials.append(M["polished"])
    ob_h = bpy.data.objects.new("F140HC_GearboxHairpin", cu)
    c_drive.objects.link(ob_h); ob_h.parent = root
    mb = MB()
    for p_ in (NS["hairpin"][0], NS["hairpin"][-1]):                             # unions into the case
        mb.lathe([(0, -10), (10, -10), (10, 10), (0, 10)], 6, T(*p_))
    # mount gusset with a bolt boss on the case's front-top flank
    gx0 = -P["gearbox"]["half_width"]
    mb.prism_xz([(z_, y_) for y_, z_ in NS["gb_gusset"]][::-1], gx0 - 18.0, gx0 + 2.0,
                M=Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))))
    mb.lathe([(14, 0), (14, 24)], 24, T(gx0 - 18.0, 740.0, 150.0) @ RY(-90))
    mb.lathe([(8, 24), (8, 31)], 6, T(gx0 - 18.0, 740.0, 150.0) @ RY(-90), mi=1)
    mb.finish("F140HC_GearboxMountGusset", c_drive, [M["magnesium"], M["steel"]], parent=root)

    # coolant Y-manifold in the V and thermostat housing
    mb = MB()
    yc = hf - 12.0
    hub = (0.0, P["front_valley_z"] - 75.0)
    for sx in (-1, 1):
        bi_ = 0 if sx < 0 else 1
        arm_end = bank_pt(bi_, g["banks"][bi_]["inb"] * (hw - 20.0), deck + 40.0)   # head inner face
        mb.between((hub[0], yc, hub[1]), (arm_end[0], yc, arm_end[1]), 19.0)
    mb.lathe([(26, -30), (26, 30)], 32, T(hub[0], yc, hub[1]) @ ROT_Z_TO_Y)
    mb.between((hub[0], yc, hub[1]), (60.0, yc - 30.0, hub[1] - 85.0), 17.0)
    mb.lathe([(22, 0), (22, 40)], 32, T(60.0, yc - 30.0, hub[1] - 85.0) @ RX(90))
    mb.finish("F140HC_CoolantManifold", c_house, [M["alu_cast"]], parent=root)

    # dry-sump pan and scavenge pump stack
    mb = MB()
    mb.box(0, L / 2, cb - P["sump_depth"] / 2, 2 * (cw - 10), L - 20, P["sump_depth"])
    sump = mb.finish("F140HC_DrySumpPan", c_house, [M["alu_cast"]], parent=root)

    # ---------------- intake (SP3: two carbon pods over the V, throttle bodies at the rear) ----
    zb = P["pod_base_z"]
    # cast runners from each inboard port up to the pod flange
    mb = MB()
    for b in g["banks"]:
        inb = b["inb"]
        for c in b["cyls"]:
            px, pz = rot_xz(inb * hw, deck + 70.0, b["gamma"])
            Lr = (zb - 16.0 - pz) / cos(radians(10.0)) + 4.0
            mb.lathe([(21, 0), (25, 0), (25, Lr), (21, Lr)], 32, T(px, c["y"], pz) @ RY(inb * 10.0),
                     closed=True)
    mb.finish("F140HC_IntakeRunners", c_ind, [M["alu_cast"]], parent=root)

    def interp(table, u):
        """Monotone cubic (PCHIP) through the measured samples: smooth, no overshoot."""
        u = min(max(u, 0.0), 1.0)
        xs = [a for a, _ in table]
        ys = [b_ for _, b_ in table]
        n = len(xs)
        h = [xs[i + 1] - xs[i] for i in range(n - 1)]
        dl = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
        m = [dl[0]] + [0.0] * (n - 2) + [dl[-1]]
        for i in range(1, n - 1):
            if dl[i - 1] * dl[i] > 0:
                w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
                m[i] = (w1 + w2) / (w1 / dl[i - 1] + w2 / dl[i])
        i = next((k for k in range(n - 1) if u <= xs[k + 1]), n - 2)
        t = (u - xs[i]) / h[i]
        h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
        h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
        return h00 * ys[i] + h10 * h[i] * m[i] + h01 * ys[i + 1] + h11 * h[i] * m[i + 1]

    y_rear = L + P["head_rear_ext"]                     # pod rear = cam cover rear (side photo)
    y_tip = y_rear - P["pod_length_frac"] * (P["head_rear_ext"] - P["head_front"] + L)
    xi = P["pod_inner_x"]
    NSEC, NT = 72, 40                                    # sections along, points across the top
    pods = []
    pod_bolts = []
    for sx in (-1, 1):
        secs = []
        for i in range(NSEC + 1):
            u = i / NSEC
            y = y_rear - u * (y_rear - y_tip)
            xo = interp(P["pod_outer"], u)
            h = interp(P["pod_height"], u)
            x0, x1 = xi, xo
            # blunt rounded nose: shrink the section about its centre over the last stretch
            un = P["pod_nose_start"]
            if u > un:
                s_ = sqrt(max(0.0, 1.0 - ((u - un) / (1.0 - un)) ** 2))
                s_ = max(s_, 0.04)
                xm = (x0 + x1) / 2
                x0, x1 = xm - (xm - x0) * s_, xm + (x1 - xm) * s_
                h *= max(s_, 0.25) ** 0.6
            # scoop on the inner-rear quarter (photo 09 / 20)
            scoop = P["pod_scoop"] * max(0.0, 1.0 - u / 0.42)
            pts = []
            for k in range(NT + 1):                     # top: inner edge -> outer edge
                t = 0.5 - 0.5 * cos(pi * k / NT)        # denser near the edges
                tc = (t - P["pod_crest"]) / (1.0 - P["pod_crest"]) if t > P["pod_crest"] else \
                    (P["pod_crest"] - t) / P["pod_crest"]
                dome = max(0.0, 1.0 - tc ** 2.6) ** (1 / 2.2)
                dip = scoop * math.exp(-((t - 0.32) / 0.2) ** 2)
                pts.append((x0 + (x1 - x0) * t, zb + h * dome * (1.0 - dip)))
            pts[0] = (x0, zb + 6.0)
            pts[-1] = (x1, zb + 6.0)
            ring = [(sx * x, y, z) for x, z in pts]
            for k in range(1, 6):                        # flat underside, outer -> inner
                t = 1.0 - k / 6
                ring.append((sx * (x0 + (x1 - x0) * t), y, zb))
            if sx < 0:
                ring.reverse()
            secs.append(ring)
        mb = MB()
        mb.loft(secs)
        pod = mb.finish(f"F140HC_IntakePod_{'L' if sx < 0 else 'R'}", c_ind, [M["carbon"]], parent=root,
                        smooth_angle=70.0)
        pods.append(pod)
        # grey cast manifold body between the pod flange and the cam covers
        foot = []
        for i in range(0, int(NSEC * P["pod_nose_start"]) + 1, 3):
            u = i / NSEC
            foot.append((sx * (interp(P["pod_outer"], u) - 14.0), y_rear - u * (y_rear - y_tip)))
        foot.append((sx * (xi - 4.0), y_rear - P["pod_nose_start"] * (y_rear - y_tip)))
        foot.append((sx * (xi - 4.0), y_rear))
        if sx > 0:
            foot.reverse()
        mb = MB()
        mb.prism_xy(foot, zb - 30.0, zb)
        mb.finish(f"F140HC_IntakeManifold_{'L' if sx < 0 else 'R'}", c_ind, [M["alu_cast"]], parent=root)
        # pod flange bolts: inner edge along the spine, outer lower edge
        for j in range(6):
            u = 0.12 + j * 0.14
            yb = y_rear - u * (y_rear - y_tip)
            pod_bolts.append((sx * (xi + 9.0), yb, zb + 4.0))
            pod_bolts.append((sx * (interp(P["pod_outer"], u) - 6.0), yb, zb + 4.0))
        # throttle body: bore, flange, motor housing
        tbx, tbz, tr = sx * P["tb_offset_x"], zb + P["tb_height"], P["tb_radius"]
        mb = MB()
        mb.ring_y(tr - 6, tr + 8, y_rear, y_rear + 14, cx=tbx, cz=tbz, seg=48)
        mb.ring_y(tr - 6, tr + 2, y_rear + 14, y_rear + 78, cx=tbx, cz=tbz, seg=48)
        mb.ring_y(tr - 6, tr + 6, y_rear + 78, y_rear + 92, cx=tbx, cz=tbz, seg=48)
        mb.cyl_y(4.0, y_rear + 40, y_rear + 52, cx=tbx, cz=tbz, seg=12)      # throttle shaft boss
        mb.box(tbx + sx * (tr + 18), y_rear + 46, tbz - 10, 34, 54, 62, mi=1)  # actuator
        mb.finish(f"F140HC_ThrottleBody_{'L' if sx < 0 else 'R'}", c_ind, [M["alu_mach"], M["black"]],
                  parent=root)
    # central aluminium spine between the pods
    mb = MB()
    mb.box(0, (y_tip - 25 + y_rear) / 2, zb + 8, 2 * xi + 6, y_rear - y_tip + 25, 32)
    mb.finish("F140HC_IntakeSpine", c_ind, [M["alu_mach"]], parent=root)

    # ---------------- exhaust: traced from side photo 13 through the solved camera ----------
    # near bank (1-6, -X) coordinates are absolute; bank 7-12 is mirrored in X and shifted
    # forward by the bank offset. Layout: 3-into-1 per half-bank -> flex bellows -> 2-into-1
    # collector -> V-band clamp -> inlet funnel -> catalyst canister -> outlet cone -> slip joint.
    EX = P["exhaust"]
    m_pol = M["polished"]

    def nurbs_tube(name, pts, r, mat, res=24, radii=None):
        """radii: optional per-point radius factors (Blender interpolates point radius along the curve)"""
        cu = bpy.data.curves.new(name, 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = r * MM
        cu.bevel_resolution = 5
        try:
            cu.use_fill_caps = True
        except Exception:
            pass
        sp = cu.splines.new('NURBS')
        sp.points.add(len(pts) - 1)
        for j, p in enumerate(pts):
            sp.points[j].co = (p[0] * MM, p[1] * MM, p[2] * MM, 1)
            if radii:
                sp.points[j].radius = radii[j]
        sp.order_u = min(4, len(pts))
        sp.use_endpoint_u = True
        sp.resolution_u = res
        cu.materials.append(mat)
        ob = bpy.data.objects.new(name, cu)
        c_ind.objects.link(ob)
        ob.parent = root
        return ob

    def axis_matrix(p0, p1):
        a, b_ = Vector(p0), Vector(p1)
        return T(*a) @ (b_ - a).to_track_quat('Z', 'Y').to_matrix().to_4x4(), (b_ - a).length

    for b in g["banks"]:
        sx = -b["inb"]                                   # outboard side in world x (-1 near bank)
        dy = b["yshift"] - P["bank_offset"]              # 0 for the near bank, -offset for 7-12

        def W(p):                                        # near-bank coords -> this bank
            return (p[0] if sx < 0 else -p[0], p[1] + dy, p[2])
        tag = b["label"]
        # dome neck geometry first: the collector sits on the neck axis just beyond the clamp
        CD = EX["cat_dome"]
        cx = -EX["cat_x"]
        dome_c = Vector((cx, CD["y_seam"], CD["zc"]))
        cl3 = Vector(EX["clamp_pos"])                                # triangulated clamp centre
        # ring / merge axis: side photo 13 puts it 39 deg forward-up (clamp ellipse); top photo 20
        # needs the merge cone inboard of the ring (bundle edge x ~-381 ahead of the clamp), so the
        # axis leans inboard as it runs forward. The neck runs back along it into the dome.
        ma = EX["merge_axis"]
        ax3 = Vector((ma[0], -cos(radians(ma[1])), sin(radians(ma[1])))).normalized()
        semi = Vector((CD["r"], CD["length"], CD["r"]))
        q0 = Vector([(cl3[i] - dome_c[i]) / semi[i] for i in range(3)])
        qd = Vector([-ax3[i] / semi[i] for i in range(3)])
        _a, _b, _c = qd.dot(qd), 2 * q0.dot(qd), q0.dot(q0) - 1.0
        t_in = (-_b - sqrt(max(0.0, _b * _b - 4 * _a * _c))) / (2 * _a)   # first hit going back
        t_in = max(4.0, t_in)
        sp3 = cl3 - ax3 * t_in                                       # neck meets the dome here
        col3 = cl3 + ax3 * EX["collector_dist"]
        collector = tuple(col3)
        # header tubes traced from the photo: port stub + traced centreline, flex bellows
        zu0, zv0, zk = EX["tube_zoom"]
        u0_, y0_, ky_, v0_, z0_, kz_ = EX["photo13"]

        PC = EX["photo13_cam"]
        Rc = Matrix(PC["rot"])
        Lc = Vector(PC["loc"])
        fpx = PC["lens"] / 36.0 * PC["size"][0]

        def zoom_to_3d(X, Y, xdep):
            """traced zoom pixel -> root-frame (y, z, mm per px) on the plane x = xdep"""
            u_, v_ = zu0 + X / zk, zv0 + Y / zk
            d_ = Rc @ Vector(((u_ - PC["size"][0] / 2) / fpx, -(v_ - PC["size"][1] / 2) / fpx, -1.0))
            t_ = (xdep * MM - Lc.x) / d_.x
            q_ = Lc + d_ * t_
            zc_ = -(Rc.transposed() @ (q_ - Lc)).z
            return q_.y / MM, q_.z / MM - (150.0 + P["sump_depth"] - 40.0), zc_ / fpx / MM
        mb_b = MB()
        mb_f = MB()
        for entry in EX["traced_tubes"]:
            ci, depth, trace, bell = entry[:4]
            opt = entry[4] if len(entry) > 4 else {}
            c = b["cyls"][ci]
            yc = c["y"] - dy
            px_, pz_ = rot_xz(-b["inb"] * hw, deck + EX["port_z_above_deck"], b["gamma"])
            p0 = (-abs(px_), yc, pz_)
            p1 = (p0[0] - 0.843 * 35, yc, p0[2] - 0.537 * 35)
            pts3 = []
            anc = dict(EX["tube_anchors"][ci])
            anc.setdefault(-1, EX["port_x"])
            anc.setdefault(len(trace), collector[0])
            keys = sorted(anc)
            for j_, (X, Y, rz) in enumerate(trace):
                k0 = max(k for k in keys if k <= j_)
                k1 = min(k for k in keys if k >= j_)
                t_ = 0.0 if k1 == k0 else (j_ - k0) / (k1 - k0)
                t_ = t_ * t_ * (3 - 2 * t_)
                dep = anc[k0] + (anc[k1] - anc[k0]) * t_
                y_, z_, mmpx = zoom_to_3d(X, Y, dep)
                pts3.append((dep, y_, z_, rz / zk * mmpx))
            # primary radius = the tube's traced radius over its first half (the plain primary); where the
            # trace widens (a merged 2-into-1 section) the curve's point radius swells to the traced value
            half = pts3[:max(2, len(pts3) // 2)]
            r_t = sum(p[3] for p in half) / len(half)
            fac = [max(1.0, p[3] / r_t) if p[3] > 1.15 * r_t else 1.0 for p in pts3]
            path = [p0, p1, ((p1[0] + pts3[0][0]) / 2, (p1[1] + pts3[0][1]) / 2, (p1[2] + pts3[0][2]) / 2)]
            path += [p[:3] for p in pts3]
            radii = [1.0, 1.0, 1.0] + fac
            if "merge_into" not in opt:                      # merged tubes end inside their partner
                path.append(collector)
                radii.append(fac[-1])
            nurbs_tube(f"F140HC_Primary_C{c['num']:02d}", [W(p) for p in path], r_t, m_pol,
                       radii=radii if any(f > 1.0 for f in fac) else None)
            Mf, _ = axis_matrix(W(p0), W((p0[0] - 0.843, p0[1], p0[2] - 0.537)))
            # port flange (photos 16 / 13): an obround plate on the diagonal between two studs, one
            # front-lower and one rear-upper of the port; nuts on the studs
            up_ = 1.0 if Mf.col[0][2] > 0 else -1.0          # sign of "up" along the flange's local X
            studs = [(-22.0 * up_, -22.0), (22.0 * up_, 22.0)]
            ob_ = []
            for k_ in range(28):
                a_ = 2 * pi * k_ / 28
                cxo = (31.0 if cos(a_) >= 0 else -31.0)
                ob_.append((cxo + 22.0 * cos(a_), 22.0 * sin(a_)))
            rot45 = 0.7071
            ob_ = [((a * rot45 - b * rot45) * up_, a * rot45 + b * rot45) for a, b in ob_]
            mb_f.prism_xz([(a, -b) for a, b in ob_], 0.0, 9.0, M=Mf @ Matrix.Rotation(radians(90), 4, 'X'))
            for su, sr in studs:
                mb_f.lathe([(4.0, 0.0), (4.0, 22.0)], 12, Mf @ T(su, sr, 0), mi=1)
                mb_f.lathe([(7.5, 9.0), (7.5, 17.0)], 6, Mf @ T(su, sr, 0), mi=1)
            for i0, i1 in bell:                              # corrugated flex section
                Mb, Lb = axis_matrix(W(pts3[i0][:3]), W(pts3[i1][:3]))
                rs, rp = EX["bellows_sleeve_od"] / 2.0, EX["bellows_od"] / 2.0
                Lcv = max(20.0, Lb - 24.0)                   # convolutions between two 12 mm sleeves
                nconv = max(4, int(round(Lcv / EX["bellows_pitch"])))
                n = nconv * 10 + 1
                prof = [(rs, 0.0), (rs, 12.0)]
                prof += [(rs + (rp - rs) * (0.5 - 0.5 * cos(2 * pi * nconv * k_ / (n - 1))),
                          12.0 + Lcv * k_ / (n - 1)) for k_ in range(n)]
                prof += [(rs, 12.0 + Lcv), (rs, Lb), (r_t + 0.5, Lb), (r_t + 0.5, 0.0)]
                mb_b.lathe(prof, 40, Mb, closed=True)
        mb_b.finish(f"F140HC_FlexBellows_{tag}", c_ind, [M["bellows"]], parent=root)
        mb_f.finish(f"F140HC_HeaderFlanges_{tag}", c_ind, [M["steel"], M["bolt"]], parent=root)
        mb = MB()                                            # merge plenum: ring -> domed cap the pipes enter
        _axw = Vector(W(tuple(ax3))) - Vector(W((0.0, 0.0, 0.0)))
        rc_, dc_ = EX["clamp_r"], EX["collector_dist"]
        mb.lathe([(rc_, -dc_ - 6), (rc_, -dc_ + 10), (rc_ - 6, -dc_ + 24), (rc_ - 18, 2), (rc_ - 34, 14),
                  (0, 20)], 48, T(*W(collector)) @ _axw.to_track_quat('Z', 'Y').to_matrix().to_4x4())
        mb.finish(f"F140HC_HeaderCollector_{tag}", c_ind, [m_pol], parent=root)
        # catalyst: lofted canister + cones from the traced (y, top z, bottom z) sections
        cx = -EX["cat_x"]
        secs = []
        def oval(y):
            tab = EX["cat_oval"]
            if y <= tab[0][0]:
                return tab[0][1]
            for (y0o, k0), (y1o, k1) in zip(tab[:-1], tab[1:]):
                if y <= y1o:
                    t_ = (y - y0o) / (y1o - y0o)
                    return k0 + (k1 - k0) * (t_ * t_ * (3 - 2 * t_))
            return tab[-1][1]

        def ring(y, ztop, zbot, grow=0.0):
            zc, r = (ztop + zbot) / 2, (ztop - zbot) / 2 + grow
            rx = (r - grow) * oval(y) + grow
            return [W((cx - (r - rx) * 0.35 + rx * cos(2 * pi * k_ / 56), y, zc + r * sin(2 * pi * k_ / 56)))
                    for k_ in range(56)]
        CD = EX["cat_dome"]
        dome = []
        for k_ in range(14):
            t = 1.0 - k_ / 13.0                                   # 1 at the tip -> 0 at the seam
            t = t ** 1.15
            y_ = CD["y_seam"] - CD["length"] * t
            r_ = CD["r"] * sqrt(max(0.0, 1.0 - t * t)) + 0.6
            zc_ = CD["zc"] + CD["rise"] * t
            dome.append((y_, zc_ + r_, zc_ - r_))
        prof_ = dome + [sec for sec in EX["cat_sections"] if sec[0] > CD["y_seam"]]
        beads = EX["cat_beads"]
        for j, (y, ztop, zbot) in enumerate(prof_):
            for yb_ in beads:
                if j > 0 and prof_[j - 1][0] < yb_ <= y:
                    t0 = (yb_ - prof_[j - 1][0]) / (y - prof_[j - 1][0])
                    tt = prof_[j - 1][1] + (ztop - prof_[j - 1][1]) * t0
                    bb = prof_[j - 1][2] + (zbot - prof_[j - 1][2]) * t0
                    for dyb, gr in ((-4.0, 0.0), (-2.5, 2.6), (2.5, 2.6), (4.0, 0.0)):
                        secs.append(ring(yb_ + dyb, tt, bb, gr))
            secs.append(ring(y, ztop, zbot))
        mb = MB()
        mb.loft(secs)
        # oxygen sensor boss + sensor on top of the canister
        sy, sz = EX["sensor"]
        sa = radians(EX["sensor_angle"])
        sr_ = EX["sensor_r"]
        Ms = T(*W((cx - 0.74 * sr_ * sin(sa) - 9.0, sy, sz - sr_ * (1 - cos(sa))))) @ \
            Matrix.Rotation(-sa if sx < 0 else sa, 4, 'Y')            # tilt outboard
        if sx < 0:      # near bank (photo 13): a plain round bung with a hex socket, no sensor fitted
            mb.lathe([(15, -8), (15, 12), (13, 15), (6.5, 15), (6.5, 13)], 32, Ms, mi=0)
            mb.lathe([(6.5, 13.0), (6.5, 8.0), (0, 8.0)], 6, Ms, mi=2)
        else:           # far bank (photo 16): sensor with its hex and body
            mb.lathe([(14, -6), (14, 4), (12.5, 4), (12.5, 12)], 6, Ms, mi=1)
            mb.lathe([(9, 12), (9, 34), (6, 40), (0, 40)], 24, Ms, mi=2)
        # slip joint on the outlet pipe
        ys0, ys1 = EX["slip_joint"]
        top0, bot0 = prof_[-1][1], prof_[-1][2]
        mb.ring_y((top0 - bot0) / 2 - 1, (top0 - bot0) / 2 + 3.5, ys0 + dy, ys1 + dy,
                  cx=W((cx, 0, 0))[0], cz=(top0 + bot0) / 2, seg=56)
        mb.finish(f"F140HC_Catalyst_{tag}", c_ind, [m_pol, M["steel"], M["black"]], parent=root)
        # inlet neck + V-band clamp on the dome's upper-front face, axis forward-up
        sy_, sz_ = sp3.y, sp3.z
        cy_, cz_ = cl3.y, cl3.z
        ax_w = Vector(W(tuple(ax3))) - Vector(W((0.0, 0.0, 0.0)))
        Mn = T(*W(tuple(sp3 - ax3 * 20.0))) @ ax_w.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        mbn = MB()
        Ln = 20.0 + t_in + 6.0                                       # into the dome .. just past the ring
        mbn.lathe([(0, 0), (EX["clamp_r"] + 2, 0), (EX["clamp_r"] + 2, Ln - 6), (EX["clamp_r"], Ln), (0, Ln)], 48, Mn)
        mbn.finish(f"F140HC_CatNeck_{tag}", c_ind, [m_pol], parent=root)
        a_ = Vector(W(tuple(cl3)))
        dirv = -ax_w
        Mc = T(*a_) @ dirv.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        mb = MB()
        r_c = EX["clamp_r"]
        mb.lathe([(r_c - 2, -9), (r_c + 6, -9), (r_c + 9, -3), (r_c + 9, 3), (r_c + 6, 9), (r_c - 2, 9)],
                 64, Mc, closed=True)
        # T-bolt + trunnion on the outboard rim, rod tangent to the ring (photo 13: it lies along the band)
        rad_ = Vector((sx, 0.0, 0.0)); rad_ = (rad_ - dirv.normalized() * rad_.dot(dirv.normalized())).normalized()
        tan_ = dirv.normalized().cross(rad_).normalized()
        Mt = Matrix.Identity(4)
        Mt.col[0][:3] = rad_; Mt.col[1][:3] = dirv.normalized().cross(tan_); Mt.col[2][:3] = tan_
        Mt = T(*(a_ + rad_ * (r_c + 14))) @ Mt
        mb.lathe([(4.2, -58), (4.2, 58)], 16, Mt, mi=1)
        mb.rbox(0, 0, 0, 14, 18, 22, 3, 2, M=T(*(a_ + rad_ * (r_c + 11))) @ Matrix(Mt.to_3x3()).to_4x4(), mi=1)
        mb.lathe([(7.5, 44), (7.5, 54)], 6, Mt, mi=1)
        mb.lathe([(7.5, -54), (7.5, -44)], 6, Mt, mi=1)
        mb.finish(f"F140HC_VbandClamp_{tag}", c_ind, [m_pol, M["steel"]], parent=root)
        # outlet pipe to the muffler
        ox_, oz_ = cx, (prof_[-1][1] + prof_[-1][2]) / 2
        mx, my0, mz = -EX["muffler_x"], EX["muffler_y"][0], EX["muffler_z"]
        nurbs_tube(f"F140HC_TailPipe_{tag}",
                   [W((ox_, prof_[-1][0] - 5, oz_)), W((ox_, prof_[-1][0] + 120, oz_ - 5)),
                    W((ox_ + 15, my0 - 160, mz - 60)), W((mx, my0 + 10, mz - 20))],
                   (prof_[-1][1] - prof_[-1][2]) / 2.0, m_pol)
        # transverse muffler box with two square outlets on top (rear photos 10 / 18)
        mb = MB()
        y_a, y_b = EX["muffler_y"]
        x_in, x_out = EX["muffler_x_span"]
        mb.rbox(sx * (x_in + x_out) / 2, (y_a + y_b) / 2, mz, x_out - x_in, y_b - y_a, EX["muffler_h"], 28.0, 4)
        for ox in EX["outlet_x"]:
            mb.rbox(sx * ox, y_b - 30.0, mz + EX["muffler_h"] / 2 + 40.0, 92.0, 46.0, 110.0, 6.0, 3, mi=1)
        mb.finish(f"F140HC_Muffler_{tag}", c_ind, [m_pol, m_pol], parent=root)

    # ---------------- gearbox placeholder ----------------
    mb = MB()
    mb.lathe([(150, L), (185, L + 40), (185, L + 120), (170, L + 130)], 48, ROT_Z_TO_Y)
    mb.lathe([(150, L), (196, L), (196, L + 16), (150, L + 16)], 64, ROT_Z_TO_Y)   # bolting flange
    GB = P["gearbox"]
    end = GB["rear_y"]
    mb.box(0, (L + 125 + end) / 2, GB["centre_z"], 2 * GB["half_width"], end - L - 125, GB["height"])
    # cast stiffening ribs: X-lattice panels on both side faces and the top (photos 14, 15, 20)
    gx, gz, gh = GB["half_width"], GB["centre_z"], GB["height"]
    y_a, y_b = L + 140.0, end - 15.0
    npan = max(2, int((y_b - y_a) // 130))
    pw = (y_b - y_a) / npan
    for sxg in (-1, 1):
        for i in range(npan):
            yc_ = y_a + (i + 0.5) * pw
            ang = math.atan2(gh - 30.0, pw)
            for sgn in (-1, 1):
                mb.box(0, 0, 0, 7.0, math.hypot(pw, gh - 30.0), 9.0,
                       M=T(sxg * (gx + 3.0), yc_, gz) @ Matrix.Rotation(sgn * ang, 4, 'X'))
            mb.box(sxg * (gx + 3.0), y_a + i * pw, gz, 7.0, 9.0, gh - 10.0)          # vertical rib
        mb.box(sxg * (gx + 3.0), (y_a + y_b) / 2, gz + gh / 2 - 6.0, 7.0, y_b - y_a, 10.0)   # top rail
        mb.box(sxg * (gx + 3.0), (y_a + y_b) / 2, gz - gh / 2 + 6.0, 7.0, y_b - y_a, 10.0)   # bottom rail
    for i in range(npan):                                                       # top-face lattice
        yc_ = y_a + (i + 0.5) * pw
        ang = math.atan2(2 * gx - 30.0, pw)
        for sgn in (-1, 1):
            mb.box(0, 0, 0, 9.0, math.hypot(pw, 2 * gx - 30.0), 7.0,
                   M=T(0, yc_, gz + gh / 2 + 3.0) @ Matrix.Rotation(sgn * ang, 4, 'Z'))
    mb.finish("F140HC_Gearbox_PLACEHOLDER", c_drive, [M["magnesium"]], parent=root)

    # ---------------- fasteners ----------------
    bolt_meshes = {}

    def bolt_mesh(size, length):
        key = (size, length)
        if key not in bolt_meshes:
            af = {6: 10.0, 8: 13.0, 10: 15.0, 11: 16.0}[size]
            hh_ = {6: 5.0, 8: 6.0, 10: 7.0, 11: 8.0}[size]
            m = MB()
            m.lathe([(af / sqrt(3), 1.6), (af / sqrt(3), 1.6 + hh_)], 6)
            m.lathe([(size / 2, -length), (size / 2, 0.0), (af * 0.68, 0.0), (af * 0.68, 1.6),
                     (size / 2, 1.6), (0, 1.6), (0, -length)], 16)
            ob = m.finish(f"F140HC_BOLT_M{size}x{int(length)}", c_tmp, [M["bolt"]])
            me = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            bolt_meshes[key] = me
        return bolt_meshes[key]

    nbolts = {}
    gamma_cut = g["banks"][1]["gamma"]
    pending_hide = []          # objects that vanish with the housing they bolt into

    def in_cut(root_xz):
        x_l, _ = rot_xz(root_xz[0], root_xz[1], -gamma_cut)
        return x_l > -2.0

    def bolt(group, size, length, loc, rot=(0, 0, 0), parent=root, M_=None):
        coll = bpy.data.collections.get(f"F140HC_Bolts_{group}") or new_coll(f"F140HC_Bolts_{group}", c_bolt)
        ob = bpy.data.objects.new(f"F140HC_Bolt_{group}_{nbolts.get(group, 0):03d}", bolt_mesh(size, length))
        coll.objects.link(ob)
        ob.parent = parent
        if M_ is not None:
            ob.matrix_parent_inverse = Matrix()
            ob.matrix_basis = M_
            px, pz = M_.translation.x / MM, M_.translation.z / MM
        else:
            ob.location = Vector(loc) * MM
            ob.rotation_euler = rot
            px, pz = loc[0], loc[2]
            if parent is not root:                       # bank-local -> root
                px, pz = rot_xz(px, pz, math.degrees(parent.rotation_euler[1]))
        if group != "Bellhousing" and in_cut((px, pz)):
            pending_hide.append(ob)
        nbolts[group] = nbolts.get(group, 0) + 1

    for b, be in zip(g["banks"], bank_obj):
        ys = [c["y"] for c in b["cyls"]]
        rows = [ys[0] - P["bore_pitch"] / 2 + j * P["bore_pitch"] for j in range(7)]
        for y in rows:
            for sx in (-1, 1):
                bolt(f"Head_{b['label']}", 11, 160.0, (sx * 56.0, y, deck + P["gallery_floor"]), parent=be)
        for kind, v in g["valves"].items():
            side = b["inb"] if kind == "intake" else -b["inb"]
            for y in journals[(b["index"], kind)]:
                for dx in (-19.0, 19.0):
                    bolt(f"CamCap_{b['label']}", 8, 45.0, (side * v["cam_x"] + dx, y, v["cam_z"] + 24.0),
                         parent=be)
        ztop = deck + hh + 7.0 * P["cover_height"] / 42.0
        for y in rows:
            for sx in (-1, 1):
                bolt(f"CamCover_{b['label']}", 6, 25.0, (sx * (hw - 3.0 * hw / 82.0), y, ztop), parent=be)
        o = -b["inb"]
        for y in rows:                                    # bolts in the top-edge bosses
            bolt(f"CamCover_{b['label']}", 6, 20.0, (o * 52.0 * hw / 82.0, y, deck + hh + P["cover_height"] + 4.0),
                 parent=be)
        for c in b["cyls"]:
            bolt(f"Coil_{b['label']}", 6, 20.0, (-b["inb"] * 18.0, c["y"] + 12.0,
                                                 deck + hh + P["cover_height"] + 26.0),
                 parent=be)
    for loc in pod_bolts:
        bolt("IntakePod", 6, 20.0, loc)
    for y in g["main_y"]:
        for x in (-62.0, -40.0, 40.0, 62.0):
            bolt("MainCaps", 10, 110.0, (x, y, cb), rot=(pi, 0, 0))
    perim = resample_closed([(-(cw - 18), 20.0), ((cw - 18), 20.0), ((cw - 18), L - 20.0),
                             (-(cw - 18), L - 20.0)][::-1], 70.0)
    for x, y in perim:
        bolt("Sump", 6, 25.0, (x, y, cb - P["sump_depth"]), rot=(pi, 0, 0))
    for i in range(14):
        a = 2 * pi * i / 14
        bolt("Bellhousing", 10, 60.0, None, M_=T(184 * cos(a), L + 16.0, 184 * sin(a)) @ ROT_Z_TO_Y)
    for x, z in resample_closed([(tc_c[0] + (x - tc_c[0]) * 0.95, tc_c[1] + (z - tc_c[1]) * 0.95)
                                 for x, z in tc_outline], 60.0):
        bolt("TimingCover", 6, 30.0, None, M_=T(x, hf, z) @ ROT_Z_TO_NY)

    # ---------------- cutaway ----------------
    cut = MB()
    cut.box(300.0 - 2.0, L / 2, 150.0, 600.0, L + 400, 1200.0)
    cutter = cut.finish("F140HC_CUTAWAY_TOOL", c_ctrl, [], parent=bank_obj[1])
    cutter.display_type = 'WIRE'
    cutter.hide_render = True
    cutter.hide_select = True
    try:
        cutter.visible_camera = False
        cutter.visible_shadow = False
    except Exception:
        pass
    cutter.hide_viewport = True
    pending_hide.append(bpy.data.objects[f"F140HC_Coils_{g['banks'][1]['label']}"])
    for ob in pending_hide:
        for prop in ("hide_viewport", "hide_render"):
            drive(ob, prop, None, "c > 0.5", ctrl, extra=[("c", "cutaway")])
    for ob in [block, heads[1], covers[1], tcover, sump,
               bpy.data.objects[f"F140HC_CamTowers_{g['banks'][1]['label']}"]]:
        mod = ob.modifiers.new("Cutaway", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = cutter
        for prop in ("show_viewport", "show_render"):
            drive(ob, f'modifiers["Cutaway"].{prop}', None, "c > 0.5", ctrl, extra=[("c", "cutaway")])

    # ---------------- reference envelope ----------------
    mb = MB()
    H = P["envelope_height"]
    mb.box(0, snout_front + P["envelope_length"] / 2, cb - P["sump_depth"] + H / 2,
           P["envelope_width"], P["envelope_length"], H)
    env = mb.finish("F140HC_Amalgam_Envelope_x4", c_ref, [M["envelope"]], parent=root)
    env.display_type = 'WIRE'
    env.hide_render = True

    # ---------------- studio ----------------
    studio = bpy.data.collections.get("F140HC_Studio") or new_coll("F140HC_Studio", top)
    target = new_empty("F140HC_CamTarget", studio, parent=root, loc=(0, 330, 200), size=0.05)
    cam_data = bpy.data.cameras.new("F140HC_Camera")
    cam_data.lens = 40
    cam_data.clip_start = 0.01
    cam = bpy.data.objects.new("F140HC_Camera", cam_data)
    studio.objects.link(cam)
    cam.location = (1.55, -0.95, 1.25)
    con = cam.constraints.new('TRACK_TO')
    con.target = target
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    scn.camera = cam
    for name, loc, energy, size in (("Key", (1.2, -1.2, 2.2), 260, 1.2), ("Fill", (-1.8, 0.2, 1.4), 90, 1.5),
                                    ("Rim", (0.2, 2.6, 1.6), 220, 1.0)):
        ld = bpy.data.lights.new(f"F140HC_{name}", 'AREA')
        ld.energy = energy
        ld.size = size
        lo = bpy.data.objects.new(f"F140HC_{name}", ld)
        studio.objects.link(lo)
        lo.location = loc
        c2 = lo.constraints.new('TRACK_TO')
        c2.target = target
    floor = MB()
    floor.box(0, 0.33 / MM, -1.0, 6000, 6000, 2.0)
    floor.finish("F140HC_Floor", studio, [material("F140_Floor", (0.18, 0.18, 0.19), 0.0, 0.6)])
    if scn.world is None:
        scn.world = bpy.data.worlds.new("World")
    try:
        scn.world.color = (0.03, 0.03, 0.035)
        if scn.world.node_tree:
            bg = scn.world.node_tree.nodes.get("Background")
            if bg:
                bg.inputs[0].default_value = (0.03, 0.03, 0.035, 1)
    except Exception:
        pass

    # soften every hard casting edge: real cast and machined parts never have perfectly sharp edges
    for coll_ in (c_house, c_drive, c_ind):
        for ob in coll_.all_objects:
            if ob.type != 'MESH' or "_Bolt_" in ob.name or ob.name.endswith("_pulley"):
                continue
            if any(k in ob.name for k in ("Valve", "Spring", "Finger", "Seat_", "Primary", "Coils", "SparkPlugs")):
                continue
            bev = ob.modifiers.new("EdgeSoften", 'BEVEL')
            bev.width = P["edge_bevel_mm"] * MM
            bev.segments = 2
            bev.limit_method = 'ANGLE'
            bev.angle_limit = radians(40)
            try:
                bev.harden_normals = False
                bev.miter_outer = 'MITER_ARC'
            except Exception:
                pass
    hdr = os.environ.get("F140_HDRI")
    if hdr and os.path.exists(hdr):
        setup_hdri(scn, hdr, strength=float(os.environ.get("F140_HDRI_STRENGTH", P["hdri_strength"])),
                   rot_deg=float(os.environ.get("F140_HDRI_ROT", P["hdri_rot_deg"])))
        for nm in ("Key", "Fill", "Rim"):
            bpy.data.lights[f"F140HC_{nm}"].energy *= 0.35
    bpy.data.collections.remove(c_tmp)
    scn.frame_set(1)

    order, events = firing_order(g)
    report = {
        "firing_order": order,
        "firing_events_deg": events,
        "deck_height_mm": round(deck, 2),
        "block_length_mm": round(L, 1),
        "bolts": dict(sorted(nbolts.items())),
        "bolt_total": sum(nbolts.values()),
    }
    print("F140HC built.")
    print("  firing order:", "-".join(map(str, order)))
    print("  deck height (crank axis to deck): %.1f mm" % deck)
    print("  block length: %.1f mm" % L)
    print("  fasteners: %d" % report["bolt_total"])
    return report, g


if __name__ == "__main__":
    report, _ = build()
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if "--save" in argv:
        path = argv[argv.index("--save") + 1]
        bpy.ops.wm.save_as_mainfile(filepath=path)
        print("saved", path)
