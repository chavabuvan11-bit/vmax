"""Render a crop of a solved photo camera (camera.json) with HDRI lighting, for side-by-side
comparison against the same crop of the photo.
usage: render_section.py CAMJSON OUTPNG ROW0 ROW1 [samples]   (rows in the 1800x1200 photo)"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bpy
from mathutils import Matrix, Vector
import f140hc_build as F
cj, outp, r0, r1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
spp = int(sys.argv[5]) if len(sys.argv) > 5 else 64
F.build()
c = json.load(open(cj))
cam = bpy.data.objects["F140HC_Camera"]
cam.constraints[0].mute = True
cam.matrix_world = Matrix.Translation(Vector(c["loc"])) @ Matrix(c["rot"]).to_4x4()
cam.data.lens = c["lens"]; cam.data.sensor_width = 36.0; cam.data.sensor_fit = 'HORIZONTAL'
cam.data.clip_end = 100.0
ctrl = bpy.data.objects["F140HC_CONTROL"]; ctrl["cutaway"] = 0; ctrl.update_tag()
key = os.environ.get("F140_SOFTBOX")          # "x,y,z,watts,size" in metres: extra overhead softbox
if key:
    kx, ky, kz, kw, ks = map(float, key.split(","))
    ld = bpy.data.lights.new("F140HC_Softbox", 'AREA'); ld.energy = kw; ld.size = ks
    lo = bpy.data.objects.new("F140HC_Softbox", ld); bpy.context.scene.collection.objects.link(lo)
    lo.location = (kx, ky, kz)
    tc = lo.constraints.new('TRACK_TO'); tc.target = bpy.data.objects["F140HC_ROOT"]
for nm in ("Light", "F140HC_Floor"):
    if nm in bpy.data.objects: bpy.data.objects[nm].hide_render = True
scn = bpy.context.scene
scn.render.engine = 'CYCLES'; scn.cycles.device = 'CPU'; scn.cycles.samples = spp
scn.cycles.use_denoising = True
scn.view_settings.view_transform = 'AgX'
try: scn.view_settings.look = os.environ.get('F140_LOOK', 'AgX - Medium High Contrast')
except Exception: pass
scn.render.resolution_x, scn.render.resolution_y = 1800, 1200
scn.render.use_border = True; scn.render.use_crop_to_border = True
scn.render.border_min_x, scn.render.border_max_x = 0.0, 1.0
scn.render.border_min_y, scn.render.border_max_y = 1 - r1 / 1200, 1 - r0 / 1200
scn.render.filepath = outp
scn.frame_set(1)
bpy.ops.render.render(write_still=True)
