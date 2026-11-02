"""Dump the near-bank header traces, port stubs, collector and radii for tools/solve_header_depth.py.
usage: python tools/dump_headers.py OUT.json [--far]   (with the bpy module)
--far dumps the far (+X) bank's photo-04 traces instead (world x positive)."""
import sys, json
sys.path.insert(0, "/home/user/vmax/f140hc")
import bpy
from mathutils import Vector
import f140hc_build as F
F.build()
EX = F.P["exhaust"]
zu0, zv0, zk = EX["tube_zoom"]
FAR = "--far" in sys.argv
out = dict(cam=EX["photo04_cam"] if FAR else EX["photo13_cam"], root_z=150.0 + F.P["sump_depth"] - 40.0,
           tubes={}, far=FAR)
src = [(ci_, 0.0, [(u_, v_, r_ * 2.0) for u_, v_, r_ in tr_], bl_) + tuple(rest_)
       for ci_, tr_, bl_, *rest_ in EX["far_traced_tubes"]] if FAR else EX["traced_tubes"]
for entry in src:
    ci, depth, trace, bell = entry[:4]
    opt = entry[4] if len(entry) > 4 else {}
    o = None
    for ob in bpy.data.objects:
        if ob.name.startswith("F140HC_Primary_C") and int(ob.name[-2:]) == ci + (7 if FAR else 1):
            o = ob
    pts = [list((o.matrix_world @ Vector(p.co[:3])) / F.MM) for p in o.data.splines[0].points]
    for p in pts: p[2] -= out["root_z"]
    rad = [p.radius * o.data.bevel_depth / F.MM for p in o.data.splines[0].points]
    out["tubes"][ci] = dict(p0=pts[0], p1=pts[1], collector=pts[-1], radii=rad, merge_into=opt.get("merge_into"),
                            uv=[(X, Y) if FAR else (zu0 + X / zk, zv0 + Y / zk) for X, Y, r in trace],
                            bell=bell, anchors=(EX["far_tube_anchors"] if FAR else EX["tube_anchors"])[ci],
                            r=o.data.bevel_depth / F.MM)
json.dump(out, open([a for a in sys.argv[1:] if not a.startswith("--")][0], "w"), indent=0)
print("cylinder numbers check:", [ob.name for ob in bpy.data.objects if ob.name.startswith("F140HC_Primary_C0")])
