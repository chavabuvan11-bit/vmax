"""Solve any reference photo's camera from hand-picked model features, then render the model
from that camera for a side-by-side.  usage: fit_view.py SPEC.json OUTDIR [samples]
SPEC: {"photo": path, "bank": 0|1, "points": [[feature, index, u, v], ...]}
features: coil k (0-5, front to rear), filler, flange_bolt j (row 0-6, lower outboard flange)"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np, cv2
import bpy
from mathutils import Vector, Matrix
import f140hc_build as F
spec = json.load(open(sys.argv[1])); out = sys.argv[2]
spp = int(sys.argv[3]) if len(sys.argv) > 3 else 48
os.makedirs(out, exist_ok=True)
rep, g = F.build()
P, MM = F.P, F.MM
img = cv2.imread(spec["photo"]); Hh, Ww = img.shape[:2]
b = g["banks"][spec["bank"]]
be = bpy.data.objects[f"F140HC_Bank_{b['label']}"]
bpy.context.view_layer.update()
o = -b["inb"]
hw, deck, hh, Hc = P["head_half_width"], g["deck"], P["head_height"], P["cover_height"]
z0 = deck + hh
ys = [c["y"] for c in b["cyls"]]
def feat(kind, i):
    if kind == "coil": return (o * 18.0, ys[i], z0 + Hc + 13.0)
    if kind == "filler": return (o * 8.0, min(ys) - 0.68 * P["bore_pitch"], z0 + Hc + 13.0)
    if kind == "flange_bolt": return (o * (hw - 5.0), ys[0] - P["bore_pitch"] / 2 + i * P["bore_pitch"], deck + hh + 8.0)
    raise ValueError(kind)
X = np.array([tuple(be.matrix_world @ (Vector(feat(k, i)) * MM)) for k, i, u, v in spec["points"]])
U = np.array([(u, v) for k, i, u, v in spec["points"]], np.float64)
best = None
for lens in np.arange(20, 300, 1.0):
    fx = lens / 36.0 * Ww
    K = np.array([[fx, 0, Ww / 2], [0, fx, Hh / 2], [0, 0, 1]])
    ok, rv, tv = cv2.solvePnP(X, U, K, None, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok: continue
    pr = cv2.projectPoints(X, rv, tv, K, None)[0].reshape(-1, 2)
    e = np.sqrt(((pr - U) ** 2).sum(1))
    if best is None or e.mean() < best[0]: best = (e.mean(), lens, rv, tv, e)
e, lens, rv, tv, err = best
R, _ = cv2.Rodrigues(rv)
Rb = Matrix(R.T.tolist()) @ Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
loc = -R.T @ tv.reshape(3)
print("lens %.0f mm, mean error %.1f px, per point %s" % (lens, e, np.round(err, 1).tolist()))
json.dump(dict(lens=float(lens), loc=loc.tolist(), rot=[list(r) for r in Rb], err=float(e)),
          open(out + "/camera.json", "w"), indent=1)
cam = bpy.data.objects["F140HC_Camera"]; cam.constraints[0].mute = True
cam.matrix_world = Matrix.Translation(Vector(loc.tolist())) @ Rb.to_4x4()
cam.data.lens = float(lens); cam.data.sensor_width = 36.0; cam.data.sensor_fit = 'HORIZONTAL'
cam.data.clip_start = 0.01; cam.data.clip_end = 100
ctrl = bpy.data.objects["F140HC_CONTROL"]; ctrl["cutaway"] = 0; ctrl.update_tag()
for nm in ("Light", "F140HC_Floor"):
    if nm in bpy.data.objects: bpy.data.objects[nm].hide_render = True
scn = bpy.context.scene
scn.render.engine = 'CYCLES'; scn.cycles.device = 'CPU'; scn.cycles.samples = spp; scn.cycles.use_denoising = True
scn.render.resolution_x, scn.render.resolution_y = Ww // 2, Hh // 2
scn.render.filepath = out + "/render.png"; scn.frame_set(1)
bpy.ops.render.render(write_still=True)
rn = cv2.imread(out + "/render.png")
ph = cv2.resize(img, (Ww // 2, Hh // 2))
for (u, v), q in zip(U, cv2.projectPoints(X, rv, tv, np.array([[lens / 36 * Ww, 0, Ww / 2], [0, lens / 36 * Ww, Hh / 2], [0, 0, 1]]), None)[0].reshape(-1, 2)):
    cv2.circle(ph, (int(u / 2), int(v / 2)), 6, (0, 255, 0), 2); cv2.circle(ph, (int(q[0] / 2), int(q[1] / 2)), 3, (255, 0, 255), -1)
cv2.imwrite(out + "/compare.jpg", np.hstack([ph, np.zeros((Hh // 2, 6, 3), np.uint8), rn]))
