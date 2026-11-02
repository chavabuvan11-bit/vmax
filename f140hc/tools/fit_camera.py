"""Solve the side photo's camera from known features (PnP), render ID masks from it,
and score model vs photo (IoU per part). Run with the bpy python.
usage: fit_camera.py PHOTO OUTDIR"""
import sys, os, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np, cv2
import bpy
from mathutils import Vector, Matrix
import f140hc_build as F

photo, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
rep, g = F.build()
MM = F.MM
P = F.P
img = cv2.imread(photo)
Hh, Ww = img.shape[:2]

bank = bpy.data.objects["F140HC_Bank_1-6"]          # -X bank faces the side photo
root = bpy.data.objects["F140HC_ROOT"]
bpy.context.view_layer.update()
b0 = g["banks"][0]
o = -b0["inb"]
deck, hh = g["deck"], P["head_height"]
z0 = deck + hh
L = g["length"]
hf, hr = P["head_front"], L + P["head_rear_ext"]

def W_bank(x, y, z):
    return bank.matrix_world @ (Vector((x, y, z)) * MM)

def W_root(x, y, z):
    return root.matrix_world @ (Vector((x, y, z)) * MM)

pts3, pts2 = [], []
coils_px = [(512.9, 465.9), (658.3, 459.3), (799.2, 452.9), (945.0, 457.4), (1084.3, 457.6), (1224.6, 466.8)]
for c, uv in zip(sorted(b0["cyls"], key=lambda c: -c["y"]), coils_px):   # photo: rear on the left
    pts3.append(W_bank(o * 18.0, c["y"], z0 + P["cover_height"] + 13.0)); pts2.append(uv)
y_rear = L + P["head_rear_ext"]
pts3.append(W_bank(o * 8.0, min(c["y"] for c in b0["cyls"]) - 0.68 * P["bore_pitch"], z0 + P["cover_height"] + 13.0)); pts2.append((1322.0, 432.0))   # filler cap
pts3.append(W_bank(o * P["head_half_width"], hr, z0 + 4.0)); pts2.append((416.0, 598.0))            # cover rear-bottom
pts3.append(W_bank(o * P["head_half_width"], hf, z0 + 4.0)); pts2.append((1478.0, 598.0))           # cover front-bottom
X = np.array([tuple(p) for p in pts3], np.float64)
U = np.array(pts2, np.float64)
json.dump(dict(X=X.tolist(), U=U.tolist(), W=Ww, H=Hh), open(out + "/points.json", "w"))

best = None
lens_range = [float(v) for v in os.environ.get("F140_LENS", "15,400").split(",")]
for lens in np.arange(lens_range[0], lens_range[1] + 0.5, 1.0):
    fx = lens / 36.0 * Ww
    K = np.array([[fx, 0, Ww / 2], [0, fx, Hh / 2], [0, 0, 1]], np.float64)
    ok, rv, tv = cv2.solvePnP(X, U, K, None, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok: continue
    proj, _ = cv2.projectPoints(X, rv, tv, K, None)
    err = np.sqrt(((proj.reshape(-1, 2) - U) ** 2).sum(1))
    if best is None or err.mean() < best[0]:
        best = (err.mean(), lens, rv, tv, err)
e, lens, rv, tv, err = best
print("best lens %.0f mm, mean reprojection error %.1f px" % (lens, e))
print("per-point error px:", np.round(err, 1).tolist())
R, _ = cv2.Rodrigues(rv)
Rb = Matrix(R.T.tolist()) @ Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
loc = -R.T @ tv.reshape(3)
cam = bpy.data.objects["F140HC_Camera"]
cam.constraints[0].mute = True
cam.matrix_world = Matrix.Translation(Vector(loc.tolist())) @ Rb.to_4x4()
cam.data.lens = float(lens)
cam.data.sensor_width = 36.0
cam.data.sensor_fit = 'HORIZONTAL'
json.dump(dict(lens=float(lens), loc=loc.tolist(), rot=[list(r) for r in Rb], err=float(e)),
          open(out + "/camera.json", "w"), indent=1)

# --- ID-mask render: covers red, carbon green, everything else black, background transparent
scn = bpy.context.scene
def emis(name, col):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    o_ = nt.nodes.new("ShaderNodeOutputMaterial"); e_ = nt.nodes.new("ShaderNodeEmission")
    e_.inputs[0].default_value = (*col, 1); nt.links.new(e_.outputs[0], o_.inputs[0])
    return m
m_red, m_grn, m_blk = emis("ID_red", (1, 0, 0)), emis("ID_grn", (0, 1, 0)), emis("ID_blk", (0, 0, 0))
for ob in bpy.data.objects:
    if ob.type not in ('MESH', 'CURVE') or not ob.material_slots: continue
    for sl in ob.material_slots:
        nm = sl.material.name if sl.material else ""
        sl.link = 'OBJECT'
        sl.material = m_red if nm == "F140_Rosso_Crinkle" else m_grn if nm == "F140_Carbon" else m_blk
for nm in ("F140HC_Floor",):
    bpy.data.objects[nm].hide_render = True
if "Light" in bpy.data.objects: bpy.data.objects["Light"].hide_render = True
ctrl = bpy.data.objects["F140HC_CONTROL"]; ctrl["cutaway"] = 0; ctrl.update_tag()
scn.render.engine = 'CYCLES'; scn.cycles.device = 'CPU'; scn.cycles.samples = 1
scn.cycles.use_denoising = False
scn.render.film_transparent = True
scn.view_settings.view_transform = 'Standard'
scn.render.resolution_x, scn.render.resolution_y = Ww // 2, Hh // 2
scn.render.filepath = out + "/idmask.png"
scn.frame_set(1)
bpy.ops.render.render(write_still=True)

# --- compare
idm = cv2.imread(out + "/idmask.png", cv2.IMREAD_UNCHANGED)
mr = ((idm[..., 2] > 128) & (idm[..., 1] < 100) & (idm[..., 3] > 128)).astype(np.uint8)
mg = ((idm[..., 1] > 128) & (idm[..., 2] < 100) & (idm[..., 3] > 128)).astype(np.uint8)
small = cv2.resize(img, (Ww // 2, Hh // 2))
hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
H, S, V = [hsv[..., i].astype(int) for i in range(3)]
pr = (((H <= 8) | (H >= 170)) & (S > 110) & (V > 90)).astype(np.uint8)
pr = cv2.morphologyEx(pr, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
pdk = ((V < 75) & (S < 90)).astype(np.uint8)
pdk = cv2.morphologyEx(pdk, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
k, lab, st, _ = cv2.connectedComponentsWithStats(pdk, 8)
cand = [i for i in range(1, k) if st[i, cv2.CC_STAT_AREA] > 5000]
pid = min(cand, key=lambda i: st[i, cv2.CC_STAT_TOP]); pg = (lab == pid).astype(np.uint8)
# compare only the upper engine (carbon below the covers is other black parts)
cut_row = int(np.nonzero(pr.any(1))[0].max())
for m in (pg, mg): m[cut_row:, :] = 0
def iou(a, b): return (a & b).sum() / max(1, (a | b).sum())
res = dict(cover_iou=float(iou(pr, mr)), pod_iou=float(iou(pg, mg)))
print("IoU covers %.3f  pods %.3f" % (res["cover_iou"], res["pod_iou"]))
ov = small.copy()
for m, col in ((pr, (0, 255, 0)), (pg, (0, 255, 0)), (mr, (255, 0, 255)), (mg, (255, 0, 255))):
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(ov, cs, -1, col, 2)
for (u, v), q in zip(U, cv2.projectPoints(X, rv, tv, np.array([[lens / 36 * Ww, 0, Ww / 2], [0, lens / 36 * Ww, Hh / 2], [0, 0, 1]]), None)[0].reshape(-1, 2)):
    cv2.circle(ov, (int(u / 2), int(v / 2)), 5, (0, 255, 255), 2)
    cv2.circle(ov, (int(q[0] / 2), int(q[1] / 2)), 3, (255, 0, 0), -1)
cv2.putText(ov, "green = real photo   magenta = model   IoU covers %.2f pods %.2f" % (res["cover_iou"], res["pod_iou"]),
            (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
cv2.imwrite(out + "/fit_overlay.jpg", ov)
json.dump(res, open(out + "/iou.json", "w"))
