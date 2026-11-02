"""Beauty render from a solved photo camera (camera.json). usage: render_fit.py CAMJSON OUTPNG [cutaway]"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import bpy
from mathutils import Matrix, Vector
import f140hc_build as F
cj, outp = sys.argv[1], sys.argv[2]
cut = int(sys.argv[3]) if len(sys.argv) > 3 else 0
F.build()
c = json.load(open(cj))
cam = bpy.data.objects["F140HC_Camera"]
cam.constraints[0].mute = True
cam.matrix_world = Matrix.Translation(Vector(c["loc"])) @ Matrix(c["rot"]).to_4x4()
cam.data.lens = c["lens"]; cam.data.sensor_width = 36.0; cam.data.sensor_fit = 'HORIZONTAL'
ctrl = bpy.data.objects["F140HC_CONTROL"]; ctrl["cutaway"] = cut; ctrl.update_tag()
if "Light" in bpy.data.objects: bpy.data.objects["Light"].hide_render = True
scn = bpy.context.scene
scn.render.engine = 'CYCLES'; scn.cycles.device = 'CPU'; scn.cycles.samples = 20
scn.render.resolution_x, scn.render.resolution_y = 900, 600
scn.render.filepath = outp
scn.frame_set(1)
bpy.ops.render.render(write_still=True)
