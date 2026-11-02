"""Solve front photo 11's camera from the crank pulley centre and the extreme corners of
both cam-cover front faces, then overlay model vs photo cover outlines and render a
beauty frame from the solved camera.  usage: fit_front.py PHOTO OUTDIR [lens]"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np, cv2
import bpy
from mathutils import Vector, Matrix
import f140hc_build as F

photo, out = sys.argv[1], sys.argv[2]
lens_fixed = float(sys.argv[3]) if len(sys.argv) > 3 else None
os.makedirs(out, exist_ok=True)
rep, g = F.build()
P, MM = F.P, F.MM
img = cv2.imread(photo); Hh, Ww = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = [hsv[..., i].astype(int) for i in range(3)]
red = (((H <= 8) | (H >= 170)) & (S > 110) & (V > 90)).astype(np.uint8)
red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
k, lab, st, cen = cv2.connectedComponentsWithStats(red, 8)
covs = sorted(sorted(range(1, k), key=lambda i: -st[i, cv2.CC_STAT_AREA])[:2], key=lambda i: cen[i][0])

def extremes(mask):
    ys, xs = np.nonzero(mask)
    return [(xs.min(), ys[xs.argmin()]), (xs.max(), ys[xs.argmax()]),
            (xs[ys.argmin()], ys.min()), (xs[ys.argmax()], ys.max())]   # left, right, top, bottom

root = bpy.data.objects["F140HC_ROOT"]
bpy.context.view_layer.update()
hw, hh, Hc, deck = P["head_half_width"], P["head_height"], P["cover_height"], g["deck"]
z0 = deck + hh
kx = hw / 82.0
base = [(-82, 0), (82, 0), (82, 7), (77, 10), (73, 27), (61, 42), (-46, 42), (-62, 38), (-71, 11), (-82, 7)]
pts3, pts2 = [], []
for bi, ci in zip((0, 1), covs):
    b = g["banks"][bi]; o = -b["inb"]
    prof = [F.rot_xz(o * x * kx, z0 + z * Hc / 42.0, b["gamma"]) for x, z in base]
    xs = [p[0] for p in prof]; zs = [p[1] for p in prof]
    ext3 = [prof[int(np.argmin(xs))], prof[int(np.argmax(xs))], prof[int(np.argmax(zs))], prof[int(np.argmin(zs))]]
    for (x3, z3), (u, v) in zip(ext3, extremes(lab == ci)):
        pts3.append(root.matrix_world @ (Vector((x3, P["head_front"], z3)) * MM)); pts2.append((float(u), float(v)))
pts3.append(root.matrix_world @ (Vector((0.0, P["head_front"] - 37.0, 0.0)) * MM)); pts2.append((905.0, 730.0))
X = np.array([tuple(p) for p in pts3]); U = np.array(pts2)
best = None
lenses = [lens_fixed] if lens_fixed else np.arange(30, 400, 2.0)
for lens in lenses:
    fx = lens / 36.0 * Ww
    K = np.array([[fx, 0, Ww / 2], [0, fx, Hh / 2], [0, 0, 1]])
    ok, rv, tv = cv2.solvePnP(X, U, K, None, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok: continue
    pr = cv2.projectPoints(X, rv, tv, K, None)[0].reshape(-1, 2)
    err = np.sqrt(((pr - U) ** 2).sum(1))
    if best is None or err.mean() < best[0]: best = (err.mean(), lens, rv, tv, err, pr)
e, lens, rv, tv, err, pr = best
print("front: lens %.0f mm, mean reprojection error %.1f px" % (lens, e))
print("  per point (L-cover l,r,t,b | R-cover l,r,t,b | crank):", np.round(err, 1).tolist())
R, _ = cv2.Rodrigues(rv)
Rb = Matrix(R.T.tolist()) @ Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
loc = -R.T @ tv.reshape(3)
json.dump(dict(lens=float(lens), loc=loc.tolist(), rot=[list(r) for r in Rb], err=float(e)),
          open(out + "/camera.json", "w"), indent=1)
ov = img.copy()
for (u, v), q in zip(U, pr):
    cv2.circle(ov, (int(u), int(v)), 9, (0, 255, 0), 3)
    cv2.line(ov, (int(u), int(v)), (int(q[0]), int(q[1])), (255, 0, 255), 3)
    cv2.circle(ov, (int(q[0]), int(q[1])), 6, (255, 0, 255), -1)
cv2.imwrite(out + "/front_points.jpg", cv2.resize(ov[150:950, 400:1500], (1100, 800)))
