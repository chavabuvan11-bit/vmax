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
    "rod_length": 150.0,           # centre-to-centre
    "bore_pitch": 104.0,           # cylinder centre spacing inside one bank
    "bank_offset": 23.0,           # bank 7-12 sits this far rearward (side-by-side rods)
    "comp_height": 28.0,           # wrist-pin centre to crown edge
    "crown_dome": 1.0,             # dome height above crown edge
    "deck_clearance": 0.5,         # crown edge below deck at TDC
    "pin_diameter": 45.0,          # crankpin
    "pin_length": 46.0,            # holds two rods side by side
    "main_diameter": 60.0,
    "main_width": 22.0,
    "counterweight_radius": 88.0,
    "rod_width": 21.0,
    "wrist_pin_diameter": 20.0,

    # --- EST: valvetrain (4 valves/cyl, DOHC per bank, sliding finger followers) ------
    "intake_valve_d": 36.0,
    "exhaust_valve_d": 30.0,
    "intake_valve_len": 106.0,
    "exhaust_valve_len": 102.0,
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
    "head_half_width": 82.0,
    "head_height": 150.0,          # deck face to cam-cover face
    "gallery_floor": 62.0,         # above deck
    "cover_height": 45.0,
    "crankcase_half_width": 150.0,
    "crankcase_bottom": -110.0,    # below crank axis
    "crankcase_top": 105.0,
    "sump_depth": 40.0,            # dry-sump pan below crankcase

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


def material(name, color, metallic=0.0, rough=0.5, coat=0.0, wrinkle=0.0, weave=False, alpha=1.0):
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
    if weave:                  # 2x2 twill approximation for carbon
        tc = nt.nodes.new("ShaderNodeTexCoord")
        chk = nt.nodes.new("ShaderNodeTexChecker")
        chk.inputs["Scale"].default_value = 320.0
        chk.inputs["Color1"].default_value = (0.010, 0.010, 0.011, 1)
        chk.inputs["Color2"].default_value = (0.035, 0.035, 0.038, 1)
        nt.links.new(tc.outputs["Object"], chk.inputs["Vector"])
        nt.links.new(chk.outputs["Color"], bsdf.inputs["Base Color"])
    m.diffuse_color = (*color, alpha)
    m.metallic = metallic
    m.roughness = rough
    return m


def build_materials():
    return {
        "alu_cast": material("F140_Aluminium_Cast", (0.60, 0.61, 0.62), 1.0, 0.55),
        "alu_mach": material("F140_Aluminium_Machined", (0.80, 0.80, 0.82), 1.0, 0.22),
        "steel": material("F140_Steel_Forged", (0.46, 0.46, 0.48), 1.0, 0.30),
        "titanium": material("F140_Titanium", (0.55, 0.52, 0.48), 1.0, 0.34),
        "dlc": material("F140_DLC_Black", (0.05, 0.05, 0.06), 1.0, 0.15),
        "piston": material("F140_Piston_Forged", (0.72, 0.72, 0.74), 1.0, 0.35),
        "valve": material("F140_Valve_Steel", (0.62, 0.62, 0.64), 1.0, 0.20),
        "spring": material("F140_Spring_Steel", (0.08, 0.09, 0.12), 1.0, 0.35),
        "rosso": material("F140_Rosso_Crinkle", (0.60, 0.0, 0.0), 0.0, 0.55, coat=0.3, wrinkle=0.25),
        "carbon": material("F140_Carbon", (0.02, 0.02, 0.022), 0.0, 0.35, coat=1.0, weave=True),
        "inconel": material("F140_Exhaust_Inconel", (0.36, 0.33, 0.30), 1.0, 0.42),
        "black": material("F140_Black_Plastic", (0.02, 0.02, 0.02), 0.0, 0.50),
        "ceramic": material("F140_Plug_Ceramic", (0.85, 0.85, 0.82), 0.0, 0.30),
        "bolt": material("F140_Bolt_Zinc", (0.70, 0.70, 0.66), 1.0, 0.30),
        "chain": material("F140_Chain", (0.20, 0.20, 0.21), 1.0, 0.30),
        "magnesium": material("F140_Gearbox_Cast", (0.42, 0.43, 0.44), 1.0, 0.60),
        "envelope": material("F140_Envelope", (0.2, 0.6, 1.0), 0.0, 0.5, alpha=0.15),
    }


# ---------------------------------------------------------------------------------------
# 4. SCENE PLUMBING
# ---------------------------------------------------------------------------------------
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
            (-g["half"], 1, 0.0, +1, "1-6"),
            (+g["half"], 7, P["bank_offset"], -1, "7-12"))):
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
    snout_front = -88.0
    mb.cyl_y(22.0, snout_front + 20, g["main_y"][0] - mw / 2 + 0.5, seg=32)
    for b in g["banks"]:                                       # crank sprockets
        rc = sprocket_radius(P["crank_sprocket_teeth"])
        mb.prism_xz(list(reversed(gear_profile(0, 0, P["crank_sprocket_teeth"], rc))),
                    b["chain_y"] - 6, b["chain_y"] + 6, mi=1)
    mb.lathe([(30, -50), (30, -20)], 32, ROT_Z_TO_Y)          # damper hub
    mb.ring_y(30, 84, snout_front, -55, seg=48, mi=1)          # damper ring
    mb.cyl_y(55, g["main_y"][-1] + mw / 2 - 0.5, g["length"] + 6, seg=48)   # rear flange
    crank = mb.finish("F140HC_Crankshaft", c_rot, [M["steel"], M["dlc"]], parent=root)
    drive(crank, "rotation_euler", 1, f"radians{CRANK}", ctrl)

    # ---------------- pistons, rods ----------------
    R = P["bore"] / 2
    ch = P["comp_height"]
    wp = P["wrist_pin_diameter"] / 2
    piston_prof = [(0, -30), (R - 0.4, -30), (R - 0.4, ch - 16), (R - 3, ch - 16), (R - 3, ch - 13),
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
    # block: crankcase + two barrel banks, minus bores, crank cavity, main line
    mb = MB()
    cb, ct = P["crankcase_bottom"], P["crankcase_top"]
    cw = P["crankcase_half_width"]
    mb.box(0, L / 2, (cb + ct) / 2, 2 * cw, L, ct - cb)
    for b in g["banks"]:
        mb.box(0, L / 2, deck / 2, 2 * bw, L, deck, M=RY(b["gamma"]))
    block = mb.finish("F140HC_Block", c_house, [M["alu_cast"]], parent=root)
    cut = MB()
    for b in g["banks"]:
        for c in b["cyls"]:
            cut.cyl(R, 40.0, deck + 5.0, M=RY(b["gamma"]) @ T(0, c["y"], 0), seg=48)
    cav_r = P["counterweight_radius"] + 8.0
    for k in range(6):
        cut.cyl_y(cav_r, g["main_y"][k] + 9.0, g["main_y"][k + 1] - 9.0, seg=48)
    cut.cyl_y(mr + 0.6, -5.0, L + 5.0, seg=40)
    cutter = cut.finish("F140HC_cut_block", c_tmp, [], parent=root)
    bake_boolean(block, cutter)

    heads, covers = [], []
    for b, be in zip(g["banks"], bank_obj):
        inb = b["inb"]
        mb = MB()
        mb.box(0, L / 2, deck + hh / 2, 2 * hw, L, hh)
        head = mb.finish(f"F140HC_Head_{b['label']}", c_house, [M["alu_cast"]], parent=be)
        cut = MB()
        cut.box(0, L / 2, deck + P["gallery_floor"] + (hh - P["gallery_floor"]) / 2 + 1,
                2 * (hw - 6), L - 16, hh - P["gallery_floor"] + 2)
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
        # cam cover: flange + crowned body, hollow
        mb = MB()
        mb.box(0, L / 2, deck + hh + 3.0, 2 * hw, L, 6.0)
        mb.box(0, L / 2, deck + hh + 6.0 + (P["cover_height"] - 6.0) / 2, 2 * (hw - 12), L - 12,
               P["cover_height"] - 6.0)
        cover = mb.finish(f"F140HC_CamCover_{b['label']}", c_house, [M["rosso"]], parent=be)
        cut = MB()
        cut.box(0, L / 2, deck + hh + (P["cover_height"] - 4.0) / 2 - 1, 2 * (hw - 16), L - 20,
                P["cover_height"] - 2.0)
        bake_boolean(cover, cut.finish("F140HC_cut_cover", c_tmp, [], parent=be))
        covers.append(cover)
        # coils and plugs
        mb = MB()
        pl = MB()
        for c in b["cyls"]:
            ztop = deck + hh + P["cover_height"]
            mb.box(0, c["y"], ztop + 18.0, 30.0, 26.0, 36.0)
            mb.box(0, c["y"] + 18.0, ztop + 26.0, 14.0, 12.0, 12.0)
            mb.cyl(9.0, deck + 70.0, ztop, M=T(0, c["y"], 0), seg=20)
            pl.lathe([(0, deck + 8.0), (2.5, deck + 8.0), (7.0, deck + 12.0), (7.0, deck + 30.0),
                      (8.0, deck + 30.0), (8.0, deck + 40.0), (5.5, deck + 42.0), (5.5, deck + 72.0),
                      (0, deck + 72.0)], 6 * 4, T(0, c["y"], 0))
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
    tc_outline = hull2d(cover_pts)
    mb = MB()
    mb.prism_xz(tc_outline, -45.0, 0.0)
    tcover = mb.finish("F140HC_TimingCover", c_house, [M["alu_cast"]], parent=root)
    cut = MB()
    cut.prism_xz(hull2d(cover_pts + [(x * 0.94, z * 0.94) for x, z in cover_pts]), -41.0, 1.0)
    inner = [(x * 0.93, z * 0.93 + 4) for x, z in tc_outline]
    cut.bm.clear()
    cut.prism_xz(inner, -41.0, 1.0)
    cut.cyl_y(26.0, -60.0, 5.0, seg=32)
    bake_boolean(tcover, cut.finish("F140HC_cut_tc", c_tmp, [], parent=root))

    # dry-sump pan and scavenge pump stack
    mb = MB()
    mb.box(0, L / 2, cb - P["sump_depth"] / 2, 2 * (cw - 10), L - 20, P["sump_depth"])
    sump = mb.finish("F140HC_DrySumpPan", c_house, [M["alu_cast"]], parent=root)
    mb = MB()
    mb.cyl_y(32.0, 60.0, 560.0, cx=-(cw + 18), cz=-70.0, seg=32)
    for y in range(80, 560, 96):
        mb.cyl_y(36.0, y, y + 8.0, cx=-(cw + 18), cz=-70.0, seg=32)
    mb.finish("F140HC_ScavengePumps", c_house, [M["alu_mach"]], parent=root)

    # ---------------- intake ----------------
    mb = MB()
    for b in g["banks"]:
        inb = b["inb"]
        for c in b["cyls"]:
            px, pz = rot_xz(inb * hw, deck + 70.0, b["gamma"])
            Lr = 150.0
            mb.lathe([(21, 0), (24, 0), (24, Lr - 25), (30, Lr - 8), (40, Lr), (37, Lr),
                      (27, Lr - 8), (21, Lr - 25)], 32, T(px, c["y"], pz) @ RY(inb * 10.0), closed=True)
    mb.finish("F140HC_IntakeRunners", c_ind, [M["carbon"]], parent=root)
    mb = MB()
    mb.box(0, 330, 470, 250, 600, 100)
    plen = mb.finish("F140HC_Plenum", c_ind, [M["carbon"]], parent=root)
    cut = MB()
    cut.box(0, 330, 468, 238, 588, 92)
    bake_boolean(plen, cut.finish("F140HC_cut_plen", c_tmp, [], parent=root))
    mb = MB()
    for sx in (-1, 1):                                  # SP3: air enters from the rear
        mb.lathe([(40, 0), (44, 0), (44, 130), (40, 130)], 40,
                 T(sx * 70, 630, 470) @ ROT_Z_TO_Y, closed=True)
    mb.finish("F140HC_AirboxInlets", c_ind, [M["carbon"]], parent=root)

    # ---------------- exhaust ----------------
    for b in g["banks"]:
        inb = b["inb"]
        sx = -inb
        for i, c in enumerate(b["cyls"]):
            p0 = Vector(rot_xz(-inb * hw, deck + 45.0, b["gamma"]))
            d = Vector(rot_xz(-inb * cos(radians(20)), -sin(radians(20)), b["gamma"]))
            pts = [(p0.x, c["y"], p0.y),
                   (p0.x + d.x * 55, c["y"], p0.y + d.y * 55),
                   (sx * 285, c["y"] + 30, 120.0),
                   (sx * 292, c["y"] + 90, 10.0),
                   (sx * (262 + (i % 2) * 18 - 9), 740.0, -10.0 + (i // 2 - 1) * 20)]
            cu = bpy.data.curves.new(f"F140HC_Primary_C{c['num']:02d}", 'CURVE')
            cu.dimensions = '3D'
            cu.bevel_depth = 21 * MM
            cu.bevel_resolution = 3
            sp = cu.splines.new('NURBS')
            sp.points.add(len(pts) - 1)
            for j, p in enumerate(pts):
                sp.points[j].co = (p[0] * MM, p[1] * MM, p[2] * MM, 1)
            sp.order_u = 4
            sp.use_endpoint_u = True
            sp.resolution_u = 16
            cu.materials.append(M["inconel"])
            ob = bpy.data.objects.new(cu.name, cu)
            c_ind.objects.link(ob)
            ob.parent = root
    mb = MB()
    for sx in (-1, 1):
        mb.lathe([(55, 0), (40, 120), (40, 560)], 40, T(sx * 262, 740, -10) @ ROT_Z_TO_Y)
    mb.finish("F140HC_Collectors", c_ind, [M["inconel"]], parent=root)

    # ---------------- gearbox placeholder ----------------
    mb = MB()
    mb.lathe([(150, L), (185, L + 40), (185, L + 120), (170, L + 130)], 48, ROT_Z_TO_Y)
    end = P["envelope_length"] + snout_front
    mb.box(0, (L + 125 + end) / 2, 0, 320, end - L - 125, 340)
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
        ztop = deck + hh + 6.0
        n = int((L - 30) // 52) + 1
        for i in range(n):
            y = 15.0 + i * (L - 30) / (n - 1)
            for sx in (-1, 1):
                bolt(f"CamCover_{b['label']}", 6, 25.0, (sx * (hw - 6.0), y, ztop), parent=be)
        for sx in (-1, 1):
            bolt(f"CamCover_{b['label']}", 6, 25.0, (sx * 40.0, 6.0, ztop), parent=be)
            bolt(f"CamCover_{b['label']}", 6, 25.0, (sx * 40.0, L - 6.0, ztop), parent=be)
        for c in b["cyls"]:
            bolt(f"Coil_{b['label']}", 6, 20.0, (0, c["y"] + 18.0, deck + hh + P["cover_height"] + 32.0),
                 parent=be)
    for y in g["main_y"]:
        for x in (-62.0, -40.0, 40.0, 62.0):
            bolt("MainCaps", 10, 110.0, (x, y, cb), rot=(pi, 0, 0))
    perim = resample_closed([(-(cw - 18), 20.0), ((cw - 18), 20.0), ((cw - 18), L - 20.0),
                             (-(cw - 18), L - 20.0)][::-1], 70.0)
    for x, y in perim:
        bolt("Sump", 6, 25.0, (x, y, cb - P["sump_depth"]), rot=(pi, 0, 0))
    for i in range(14):
        a = 2 * pi * i / 14
        bolt("Bellhousing", 10, 60.0, None, M_=T(176 * cos(a), L + 6.0, 176 * sin(a)) @ ROT_Z_TO_Y)
    for x, z in resample_closed(hull2d([(x * 0.96, z * 0.96) for x, z in tc_outline]), 60.0):
        bolt("TimingCover", 6, 30.0, None, M_=T(x, -45.0, z) @ ROT_Z_TO_NY)

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
    for ob in [block, heads[1], covers[1], tcover, sump, plen,
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
