"""Re-solve a photo camera with its elevation fixed (PnP is ambiguous when the matched
features are nearly coplanar). Scans elevations, reports the error for each, writes the
camera for the chosen elevation.
usage: solve_camera_constrained.py POINTS.json OUT_CAMERA.json LENS_MM ELEV_DEG"""
import sys, json, math
import numpy as np
from scipy.optimize import least_squares
d = json.load(open(sys.argv[1]))
X, U, W, H = np.array(d["X"]), np.array(d["U"]), d["W"], d["H"]
lens, elev_pick = float(sys.argv[3]), float(sys.argv[4])
f = lens / 36.0 * W
centre = X.mean(0)

def rot(yaw, elev, roll):
    # camera looks along fwd; Blender camera: -Z forward, +Y up
    fwd = np.array([math.cos(elev) * math.cos(yaw), math.cos(elev) * math.sin(yaw), -math.sin(elev)])
    right = np.cross(fwd, [0, 0, 1.0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    c, s_ = math.cos(roll), math.sin(roll)
    right, up = c * right + s_ * up, -s_ * right + c * up
    return np.column_stack([right, up, -fwd])          # columns: cam X, Y, Z in world

def project(params, elev):
    yaw, roll, dist, ox, oz = params
    R = rot(yaw, elev, roll)
    fwd = -R[:, 2]
    loc = centre + np.array([ox, 0, oz]) * 0 - fwd * dist + R[:, 0] * ox + R[:, 1] * oz
    pc = (X - loc) @ R
    return np.column_stack([W / 2 + f * pc[:, 0] / -pc[:, 2], H / 2 - f * pc[:, 1] / -pc[:, 2]]), R, loc

def solve(elev):
    best = None
    for yaw0 in (math.radians(0), math.radians(-5), math.radians(5)):
        x0 = [yaw0, 0.0, f * 0.000737 * 1.0, 0.0, 0.0]
        r = least_squares(lambda p: (project(p, elev)[0] - U).ravel(), x0, method='lm')
        if best is None or r.cost < best.cost: best = r
    e = np.sqrt(((project(best.x, elev)[0] - U) ** 2).sum(1))
    return best.x, e
for el in (0, 5, 10, 15, 20, 30, 45):
    x, e = solve(math.radians(el))
    print("elevation %2d deg: mean reprojection error %.1f px" % (el, e.mean()))
x, e = solve(math.radians(elev_pick))
_, R, loc = project(x, math.radians(elev_pick))
json.dump(dict(lens=lens, loc=loc.tolist(), rot=R.tolist(), err=float(e.mean()), elev=elev_pick),
          open(sys.argv[2], "w"), indent=1)
print("chosen elevation %.0f deg: error %.1f px, per point %s" % (elev_pick, e.mean(), np.round(e, 1).tolist()))
