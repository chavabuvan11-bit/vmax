"""Common-sense checks on the built engine: things that can't happen on a real part.

  python tools/sanity.py            (with the bpy module)   or   blender -b -P tools/sanity.py

  FLOATING      a part that touches nothing (gap to the nearest other part > 3 mm)
  LOOSE END     a tube/pipe end that isn't inside or against another part
  UNSEATED      a bolt whose head isn't sitting on a surface
  BELT          a pulley the belt doesn't wrap
  CLASH         two header primaries passing through each other (outside the merge collector)
Exits non-zero if anything is found, and prints every offender by name.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import f140hc_build as F

GAP = 3.0 * F.MM
SKIP = ("CONTROL", "ROOT", "_Bank_", "Camera", "CamTarget", "Floor", "Envelope", "CUTAWAY",
        "_Key", "_Fill", "_Rim", "Guide_")


def main():
    F.build()
    ctrl = bpy.data.objects["F140HC_CONTROL"]
    ctrl["cutaway"] = 0
    ctrl.update_tag()
    bpy.context.scene.frame_set(1)
    dg = bpy.context.evaluated_depsgraph_get()
    parts = [o for o in bpy.data.objects if o.type in ('MESH', 'CURVE') and o.name.startswith("F140HC_")
             and not any(k in o.name for k in SKIP) and not o.hide_render]
    data = {}
    for o in parts:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        vs = [mw @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
        ev.to_mesh_clear()
        if not vs or not polys:
            continue
        lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        step = max(1, len(vs) // 400)
        data[o.name] = dict(tree=BVHTree.FromPolygons(vs, polys), lo=lo, hi=hi, samples=vs[::step], obj=o)
    names = list(data)

    def near(a, b, pad):
        A, B = data[a], data[b]
        return all(A["lo"][i] - pad <= B["hi"][i] and B["lo"][i] - pad <= A["hi"][i] for i in range(3))

    def nearest_other(p, exclude, pad=0.05, skip_bolts=False):
        best = (1e9, None)
        for n in names:
            if n == exclude or (skip_bolts and "_Bolt_" in n):
                continue
            D = data[n]
            if not all(D["lo"][i] - pad <= p[i] <= D["hi"][i] + pad for i in range(3)):
                continue
            hit = D["tree"].find_nearest(p)
            if hit[0] is not None and hit[3] < best[0]:
                best = (hit[3], n)
        return best

    issues = {"FLOATING": [], "LOOSE END": [], "UNSEATED": [], "BELT": [], "CLASH": []}
    for a in names:
        if "_Bolt_" in a:
            continue
        cands = [b for b in names if b != a and near(a, b, GAP)]
        gap = 1e9
        for b in cands:                                 # both directions: corners vs faces
            for src, dst in ((a, b), (b, a)):
                tree = data[dst]["tree"]
                for v in data[src]["samples"]:
                    hit = tree.find_nearest(v)
                    if hit[0] is not None and hit[3] < gap:
                        gap = hit[3]
            if gap <= GAP:
                break
        if gap > GAP:
            issues["FLOATING"].append("%s (gap %s)" % (a, "none nearby" if gap > 1 else "%.1f mm" % (gap / F.MM)))
    for a in names:                                     # tube ends
        o = data[a]["obj"]
        if o.type != 'CURVE':
            continue
        cu = o.data
        r = cu.bevel_depth
        for sp in cu.splines:
            pts = sp.points if len(sp.points) else sp.bezier_points
            if len(pts) < 2 or "Spring" in a:
                continue
            for end in (pts[0], pts[-1]):
                p = o.matrix_world @ Vector(end.co[:3])
                d, who = nearest_other(p, a)
                if d > r + GAP:
                    issues["LOOSE END"].append("%s end at (%.0f, %.0f, %.0f) mm, nearest %s %.1f mm" % (
                        a, p.x / F.MM, p.y / F.MM, p.z / F.MM, who, d / F.MM))
    for a in names:                                     # bolt heads on a surface
        if "_Bolt_" not in a:
            continue
        o = data[a]["obj"]
        p = o.matrix_world @ Vector((0, 0, 0))
        d, who = nearest_other(p, a, skip_bolts=True)
        if d > 2.0 * F.MM:
            issues["UNSEATED"].append("%s (%.1f mm from %s)" % (a, d / F.MM, who))
    belt = "F140HC_AccessoryBelt"
    if belt in data:
        for n in names:
            if n.endswith("_pulley"):
                gap = min(data[belt]["tree"].find_nearest(v)[3] for v in data[n]["samples"])
                if gap > 2.0 * F.MM:
                    issues["BELT"].append("%s (belt %.1f mm away)" % (n, gap / F.MM))
    prim = [n for n in names if "_Primary_C" in n]
    for i, a in enumerate(prim):                        # primaries must not interpenetrate
        oa = data[a]["obj"]
        end_a = oa.matrix_world @ Vector(oa.data.splines[0].points[-1].co[:3])
        for b in prim[i + 1:]:
            ob_ = data[b]["obj"]
            end_b = ob_.matrix_world @ Vector(ob_.data.splines[0].points[-1].co[:3])
            if not near(a, b, 0.0):
                continue
            hits = data[a]["tree"].overlap(data[b]["tree"])
            if not hits:
                continue
            ev = data[a]["obj"].evaluated_get(dg).to_mesh()
            cen = [data[a]["obj"].matrix_world @ ev.polygons[pa].center for pa, pb in hits]
            data[a]["obj"].evaluated_get(dg).to_mesh_clear()
            bad = [c for c in cen if (c - end_a).length > 0.075 and (c - end_b).length > 0.075]   # merges
            if bad:
                c = bad[0]
                issues["CLASH"].append("%s x %s (%d faces, e.g. at %.0f, %.0f, %.0f mm)" % (
                    a, b, len(bad), c.x / F.MM, c.y / F.MM, c.z / F.MM - 150.0))
    total = 0
    for k, v in issues.items():
        print("%-10s %d" % (k, len(v)))
        for line in v[:60]:
            print("   ", line)
        total += len(v)
    print("SANITY:", "PASS" if total == 0 else "FAIL (%d)" % total)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
