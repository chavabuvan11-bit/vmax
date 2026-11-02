"""Iteratively fit the pod height table and length to side photo 13 from a solved camera.
usage: fit_pod.py PHOTO CAMJSON OUTDIR ITER"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np, cv2
import bpy
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view
import f140hc_build as F

photo, cj, out, iters = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
os.makedirs(out, exist_ok=True)
MMPX = 104.0 / 70.5                   # mm per half-res pixel (coil pitch ruler)
img = cv2.resize(cv2.imread(photo), (900, 600))
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = [hsv[..., i].astype(int) for i in range(3)]
pdk = cv2.morphologyEx(((V < 75) & (S < 90)).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
k, lab, st, _ = cv2.connectedComponentsWithStats(pdk, 8)
cand = [i for i in range(1, k) if st[i, cv2.CC_STAT_AREA] > 5000]
pg = (lab == min(cand, key=lambda i: st[i, cv2.CC_STAT_TOP])).astype(np.uint8)
def top_rows(m):
    return {x: int(np.nonzero(m[:, x])[0].min()) for x in range(m.shape[1]) if m[:, x].any()}
photo_top = top_rows(pg)
pcols = sorted(photo_top)
c = json.load(open(cj))

def render_mask():
    F.build()
    cam = bpy.data.objects["F140HC_Camera"]; cam.constraints[0].mute = True
    cam.matrix_world = Matrix.Translation(Vector(c["loc"])) @ Matrix(c["rot"]).to_4x4()
    cam.data.lens = c["lens"]; cam.data.sensor_width = 36.0; cam.data.sensor_fit = 'HORIZONTAL'
    scn = bpy.context.scene
    grn = bpy.data.materials.new("ID_g"); grn.use_nodes = True
    nt = grn.node_tree; nt.nodes.clear()
    o_ = nt.nodes.new("ShaderNodeOutputMaterial"); e_ = nt.nodes.new("ShaderNodeEmission")
    e_.inputs[0].default_value = (0, 1, 0, 1); nt.links.new(e_.outputs[0], o_.inputs[0])
    for ob in bpy.data.objects:     # render only the pods
        if ob.type in ('MESH', 'CURVE'):
            ob.hide_render = not ob.name.startswith("F140HC_IntakePod")
            if not ob.hide_render:
                for sl in ob.material_slots: sl.link = 'OBJECT'; sl.material = grn
    if "Light" in bpy.data.objects: bpy.data.objects["Light"].hide_render = True
    scn.render.engine = 'CYCLES'; scn.cycles.samples = 1; scn.cycles.use_denoising = False
    scn.render.film_transparent = True; scn.view_settings.view_transform = 'Standard'
    scn.render.resolution_x, scn.render.resolution_y = 900, 600
    scn.render.filepath = out + "/pod_mask.png"; scn.frame_set(1)
    bpy.ops.render.render(write_still=True)
    m = cv2.imread(out + "/pod_mask.png", cv2.IMREAD_UNCHANGED)
    return ((m[..., 3] > 128) & (m[..., 1] > 128)).astype(np.uint8), cam, scn

P = F.P
for it in range(iters):
    mg, cam, scn = render_mask()
    model_top = top_rows(mg)
    mcols = sorted(model_top)
    # pod length: compare front-most columns
    d_front = (max(pcols) - max(mcols)) * MMPX
    d_rear = (min(pcols) - min(mcols)) * MMPX
    # per-u height correction at each table sample
    g = F.derive()
    L = g["length"]; hr = L + P["head_rear_ext"]; hf = P["head_front"]
    y_rear = hr; y_tip = y_rear - P["pod_length_frac"] * (hr - hf)
    root = bpy.data.objects["F140HC_ROOT"]
    newh, report = [], []
    for u, h in P["pod_height"]:
        y = y_rear - u * (y_rear - y_tip)
        p3 = root.matrix_world @ (Vector((-130.0, y, P["pod_base_z"] + h)) * F.MM)
        ndc = world_to_camera_view(scn, cam, p3)
        col = int(round(ndc.x * 900))
        if col in photo_top and col in model_top and u < P["pod_nose_start"]:
            dz = (model_top[col] - photo_top[col]) * MMPX
            newh.append((u, round(h + 0.85 * dz, 1))); report.append((u, col, round(dz, 1)))
        else:
            newh.append((u, h)); report.append((u, col, None))
    print("iter", it, "front gap %.0f mm, rear gap %.0f mm" % (d_front, d_rear))
    print("  height corrections (u, column, dz mm):", report)
    P["pod_height"] = newh
    span = hr - hf
    P["pod_length_frac"] = round(min(1.0, P["pod_length_frac"] + 0.85 * d_front / span), 3)
print("FINAL pod_height =", P["pod_height"])
print("FINAL pod_length_frac =", P["pod_length_frac"])
ov = img.copy()
for m, col in ((pg, (0, 255, 0)), (mg, (255, 0, 255))):
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(ov, cs, -1, col, 2)
cv2.imwrite(out + "/pod_fit_overlay.jpg", ov)
json.dump(dict(pod_height=P["pod_height"], pod_length_frac=P["pod_length_frac"]), open(out + "/pod_fit.json", "w"))
