"""Which part does the model show at a photo pixel? Ray-casts from a solved camera.

  python tools/raycast_pick.py CAMERA.json u,v [u,v ...]        single pixels
  python tools/raycast_pick.py CAMERA.json col=U v0 v1 [step]   a vertical scan line (prints changes)
(run with the bpy module; pixel coordinates are in the photo the camera was solved for, 1800 x 1200
unless the camera JSON says otherwise). Prints object name and the hit point in root-frame mm.
"""
import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bpy
from mathutils import Vector, Matrix
import f140hc_build as F


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    cam = json.load(open(args[0]))
    W, H = cam.get("size", (1800, 1200))
    F.build()
    for o in bpy.data.objects:                      # hidden helpers (envelope etc.) would catch rays
        if o.hide_render:
            o.hide_viewport = True
    bpy.context.view_layer.update()
    R, L = Matrix(cam["rot"]), Vector(cam["loc"])
    f = cam["lens"] / 36.0 * W
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    root_z = 150.0 + F.P["sump_depth"] - 40.0

    def cast(u, v):
        d = R @ Vector(((u - W / 2) / f, -(v - H / 2) / f, -1.0))
        d.normalize()
        hit, loc, nor, idx, ob, mx = sc.ray_cast(dg, L, d)
        if not hit:
            return None, None
        return ob.name, (round(loc.x / F.MM), round(loc.y / F.MM), round(loc.z / F.MM - root_z))

    if args[1].startswith("col="):
        u = float(args[1][4:])
        v0, v1 = int(args[2]), int(args[3])
        step = int(args[4]) if len(args) > 4 else 4
        prev = "?"
        for v in range(v0, v1, step):
            name, p = cast(u, v)
            if name != prev:
                print("u %.0f v %d  %s  %s" % (u, v, name, p))
                prev = name
    else:
        for a in args[1:]:
            u, v = map(float, a.split(","))
            name, p = cast(u, v)
            print("u %.0f v %.0f  %s  %s" % (u, v, name, p))


if __name__ == "__main__":
    main()
