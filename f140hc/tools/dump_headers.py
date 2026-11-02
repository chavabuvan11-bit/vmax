"""Dump the near-bank header traces, port stubs, collector and radii for tools/solve_header_depth.py.
usage: python tools/dump_headers.py OUT.json   (with the bpy module)"""
import sys, json
sys.path.insert(0, "/home/user/vmax/f140hc")
import bpy
from mathutils import Vector
import f140hc_build as F
F.build()
EX = F.P["exhaust"]
zu0, zv0, zk = EX["tube_zoom"]
out = dict(cam=EX["photo13_cam"], root_z=150.0 + F.P["sump_depth"] - 40.0, tubes={})
for entry in EX["traced_tubes"]:
    ci, depth, trace, bell = entry[:4]
    opt = entry[4] if len(entry) > 4 else {}
    o = None
    for ob in bpy.data.objects:
        if ob.name.startswith("F140HC_Primary_C") and int(ob.name[-2:]) == ci + 1:
            o = ob
    pts = [list((o.matrix_world @ Vector(p.co[:3])) / F.MM) for p in o.data.splines[0].points]
    for p in pts: p[2] -= out["root_z"]
    rad = [p.radius * o.data.bevel_depth / F.MM for p in o.data.splines[0].points]
    out["tubes"][ci] = dict(p0=pts[0], p1=pts[1], collector=pts[-1], radii=rad, merge_into=opt.get("merge_into"),
                            uv=[(zu0 + X / zk, zv0 + Y / zk) for X, Y, r in trace], bell=bell,
                            anchors=EX["tube_anchors"][ci], r=o.data.bevel_depth / F.MM)
json.dump(out, open(sys.argv[-1], "w"), indent=0)
print("cylinder numbers check:", [ob.name for ob in bpy.data.objects if ob.name.startswith("F140HC_Primary_C0")])
