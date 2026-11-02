"""
Build the F140HC and check that the internals actually work.

  blender -b -P verify.py -- [--render OUT_DIR]
  python verify.py [--render OUT_DIR]          (with the `bpy` pip module)

Checks, over one full 720-degree cycle:
  1. every driver is a Blender simple expression (no Auto Run Python needed)
  2. every rod big-end stays centred on its crankpin
  3. each piston reaches TDC (r + l) at its firing angle and BDC (l - r) 180 deg later
  4. valve lift from the driver equals the cam lobe radius under the follower
  5. no valve face ever drops into its piston crown
  6. no piston skirt reaches the counterweight swing radius
"""
import os
import sys
import math
from math import radians, degrees, atan2, sin, pi

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import f140hc_build as F  # noqa: E402

MM = F.MM


def setp(ctrl, **kw):
    """Set control properties and tag the object so drivers see the new values."""
    for k, v in kw.items():
        ctrl[k] = v
    ctrl.update_tag()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    report, g = F.build()
    scn = bpy.context.scene
    ctrl = bpy.data.objects["F140HC_CONTROL"]
    r, l = g["r"], g["l"]
    fails = []

    # 1. drivers
    n_drv, bad = 0, []
    for ob in bpy.data.objects:
        ad = ob.animation_data
        if not ad:
            continue
        for fc in ad.drivers:
            n_drv += 1
            if not fc.driver.is_simple_expression:
                bad.append((ob.name, fc.data_path))
    print(f"[1] drivers: {n_drv}, not simple: {len(bad)}")
    if bad:
        fails.append(f"non-simple drivers: {bad[:5]}")

    crank = bpy.data.objects["F140HC_Crankshaft"]
    rods = {o["cyl"]: o for o in bpy.data.objects if o.name.startswith("F140HC_Rod_")}
    pistons = {o["cyl"]: o for o in bpy.data.objects if o.name.startswith("F140HC_Piston_")}
    valves = [o for o in bpy.data.objects if o.name.startswith("F140HC_Valve_")]
    cams = {}
    for o in bpy.data.objects:
        if o.name.startswith("F140HC_Cam_"):
            _, _, kind, bank = o.name.split("_", 3)
            cams[(kind, bank)] = o

    pin_local = {}
    for b in g["banks"]:
        for c in b["cyls"]:
            k = c["k"]
            px, pz = F.rot_xz(0.0, r, F.PIN_PHASE[k])
            pin_local[c["num"]] = Vector((px * MM, g["pin_y"][k] * MM, pz * MM))

    setp(ctrl, deg_per_frame=1.0, offset_deg=0.0)
    worst_pin = 0.0
    worst_cam = 0.0
    min_clear = {}
    min_cw = [1e9]
    tdc_err = 0.0
    for f in range(0, 720, 2):
        scn.frame_set(f)
        cinv = crank.matrix_world.inverted()
        for n, rod in rods.items():
            # big-end centre in crank space: must sit on the pin axis, inside the pin length
            big = cinv @ (rod.matrix_world @ Vector((0, 0, -l * MM)))
            pin = pin_local[n]
            radial = math.hypot(big.x - pin.x, big.z - pin.z) / MM
            along = abs(big.y - pin.y) / MM
            spill = max(0.0, along + F.P["rod_width"] / 2 - F.P["pin_length"] / 2)
            worst_pin = max(worst_pin, radial, spill)
        for v in valves:
            lift = -v.location.z / MM
            guide = v.parent
            bank = "1-6" if v["cyl"] <= 6 else "7-12"
            cam = cams[(v["kind"], bank)]
            down_w = (guide.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
            down_c = cam.matrix_world.to_3x3().inverted() @ down_w
            a = atan2(down_c.x, down_c.z)
            vv = g["valves"][v["kind"]]
            geo = F.lobe_radius(a, v["lobe_delta"], vv) - F.P["cam_base_radius"]
            worst_cam = max(worst_cam, abs(geo - lift))
            # valve face lowest point vs piston crown peak, in the bank frame
            bank_ob = guide.parent
            inv = bank_ob.matrix_world.inverted()
            face_c = inv @ (v.matrix_world @ Vector((0, 0, -v["valve_len"] * MM)))
            low = face_c.z / MM - v["face_radius"] * abs(sin(radians(v["lean_deg"])))
            pis = pistons[v["cyl"]]
            crown = pis.location.z / MM + F.P["comp_height"] + F.P["crown_dome"]
            key = v["cyl"]
            min_clear[key] = min(min_clear.get(key, 1e9), low - crown)
        for n, pis in pistons.items():       # skirt vs counterweight swing (conservative)
            skirt = pis.location.z / MM - F.P["piston_skirt"]
            min_cw[0] = min(min_cw[0], skirt - F.P["counterweight_radius"])
    setp(ctrl, deg_per_frame=0.0)        # crank angle = offset_deg only
    tick = 1000
    for n, pis in pistons.items():
        fire = pis["theta_fire"]
        for ang, want in ((fire, r + l), (fire + 180.0, l - r)):
            setp(ctrl, offset_deg=ang)
            tick += 1
            scn.frame_set(tick)               # new frame forces driver re-evaluation
            tdc_err = max(tdc_err, abs(pis.location.z / MM - want))
    setp(ctrl, offset_deg=0.0, deg_per_frame=6.0)
    print(f"[2] worst rod big-end to crankpin error: {worst_pin:.4f} mm")
    print(f"[3] worst TDC/BDC height error: {tdc_err:.4f} mm")
    print(f"[4] worst cam-lobe vs valve-lift mismatch: {worst_cam:.4f} mm")
    mc = min(min_clear.values())
    print(f"[5] minimum valve-to-piston clearance: {mc:.2f} mm "
          f"(cyl {min(min_clear, key=min_clear.get)})")
    print(f"[6] minimum piston-skirt to counterweight clearance: {min_cw[0]:.2f} mm")
    print("    firing order:", "-".join(map(str, report["firing_order"])))
    print("    fasteners:", report["bolt_total"], report["bolts"])
    if worst_pin > 0.01:
        fails.append("rod big-end leaves crankpin")
    if tdc_err > 0.01:
        fails.append("TDC/BDC height wrong")
    if worst_cam > 0.05:
        fails.append("cam lobe and valve lift disagree")
    if mc <= 0.0:
        fails.append("valve hits piston")
    if min_cw[0] <= 0.0:
        fails.append("piston skirt hits counterweight")

    if "--render" in argv:
        out = argv[argv.index("--render") + 1]
        os.makedirs(out, exist_ok=True)
        scn.render.engine = 'CYCLES'
        scn.cycles.device = 'CPU'
        scn.cycles.samples = int(os.environ.get("F140_SAMPLES", "48"))
        try:
            scn.cycles.use_denoising = True
        except Exception:
            pass
        scn.render.resolution_x, scn.render.resolution_y = 1280, 720
        scn.render.image_settings.file_format = 'PNG'
        for name in ("Light",):                 # Blender's startup lamp skews the exposure
            if name in bpy.data.objects:
                bpy.data.objects[name].hide_render = True
        cam = bpy.data.objects["F140HC_Camera"]
        track = cam.constraints[0]
        rz = scn.objects["F140HC_ROOT"].location.z
        # name: (location, rotation or None for track-to, lens, cutaway, frame, resolution)
        shots = {
            "cutaway_34": ((1.55, -0.95, 1.25), None, 40, 1, 1, (1280, 720)),
            "cutaway_side": ((1.9, 0.33, 0.55), None, 40, 1, 31, (1280, 720)),
            "closed_34": ((-1.5, -1.0, 1.3), None, 40, 0, 1, (1280, 720)),
            "front_internals": ((0.0, -1.7, 0.45), None, 40, 1, 16, (1280, 720)),
            # matched to Amalgam photo 13 (side, -X) and photo 20 (top, front to the right)
            "ref_side": ((-3.4, 0.30, rz + 0.30), (radians(90), 0, radians(-90)), 85, 0, 1, (1200, 800)),
            "ref_top": ((0.0, 0.66, 5.2), (0, 0, radians(-90)), 70, 0, 1, (1200, 800)),
            "ref_front": ((0.0, -4.2, rz + 0.11), (radians(90), 0, 0), 100, 0, 1, (1200, 800)),
        }
        want = argv[argv.index("--shots") + 1].split(",") if "--shots" in argv else list(shots)
        for name in want:
            loc, rot, lens, cut, frame, res = shots[name]
            setp(ctrl, cutaway=cut)
            scn.render.resolution_x, scn.render.resolution_y = res
            cam.location = loc
            cam.data.lens = lens
            track.mute = rot is not None
            if rot is not None:
                cam.rotation_euler = rot
            scn.frame_set(frame)
            scn.render.filepath = os.path.join(out, name + ".png")
            bpy.ops.render.render(write_still=True)
            print("rendered", scn.render.filepath)
        track.mute = False
        setp(ctrl, cutaway=1)

    if fails:
        print("FAIL:", "; ".join(fails))
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
