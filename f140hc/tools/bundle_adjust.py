"""Joint camera + scale solve across views (first version).

Unknowns: one camera per view (rotation 3, position 3, focal 1), the alternator centre
(free 3D point), and two global scale factors applied to the model's feature coordinates
about the crank axis: k_h for x/y and k_v for z. If k_v comes out clearly different from 1,
the model's vertical proportions below the cam covers are off.

Observations (all from reference_data):
  photo13  : 6 coils, filler cap, cover rear/front bottom corners (cameras/photo13_side_points.json),
             alternator centre (picks_front.json)
  photo11  : crank pulley centre, 4 cover-bottom corners, alternator centre (picks_front.json)
  video114 : 6 coils, filler cap, 6 flange bolts (specs/video_011.4s_topdown.json)

usage: python bundle_adjust.py            (needs numpy + scipy; run from anywhere)
"""
import os, sys, json, math
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation as Rot

HERE = os.path.dirname(os.path.abspath(__file__))
RD = os.path.join(HERE, "..", "reference_data")
ROOT_Z = 0.150

# model geometry needed for feature definitions (mirrors f140hc_build.py P / derive)
DECK, HH, HC, HW = 207.5, 95.0, 70.0, 105.0
Z0 = DECK + HH
PITCH, Y0, OFFSET = 104.0, 62.0, 23.0
HF = -100.0
G = math.radians(32.5)


def bank_to_root(xl, zl, gamma):
    return xl * math.cos(gamma) + zl * math.sin(gamma), -xl * math.sin(gamma) + zl * math.cos(gamma)


def feat_near(kind, i):
    """-X bank (cylinders 1-6, rear-offset) features in root-frame mm."""
    gamma, o = -G, -1.0
    ys = [Y0 + OFFSET + k * PITCH for k in range(6)]
    if kind == "coil":
        x, z = bank_to_root(o * 18.0, Z0 + HC + 13.0, gamma); return (x, ys[i], z)
    if kind == "filler":
        x, z = bank_to_root(o * 8.0, Z0 + HC + 13.0, gamma); return (x, min(ys) - 0.68 * PITCH, z)
    if kind == "flange_bolt":
        x, z = bank_to_root(o * (HW - 3.0 * HW / 82.0), DECK + HH + 7.0 * HC / 42.0, gamma)
        return (x, ys[0] - PITCH / 2 + i * PITCH, z)
    if kind == "cover_bottom_outer":       # i = y value
        x, z = bank_to_root(o * HW, Z0, gamma); return (x, i, z)
    raise ValueError(kind)


def front_corner(side, inner):
    gamma = -G if side < 0 else G
    inb = 1.0 if side < 0 else -1.0
    xl = inb * HW if inner else -inb * HW
    x, z = bank_to_root(xl, Z0, gamma)
    return (x, HF, z)


def load_obs():
    obs = []          # (view, feature-key, model mm or None for the alternator, uv)
    p13 = json.load(open(os.path.join(RD, "cameras", "photo13_side_points.json")))
    U = p13["U"]
    for i in range(6):                     # fit_camera.py order: coils rear -> front
        obs.append(("photo13", ("coil", 5 - i), U[i]))
    obs.append(("photo13", ("filler", 0), U[6]))
    obs.append(("photo13", ("cover_bottom_outer", 685.0), U[7]))
    obs.append(("photo13", ("cover_bottom_outer", -100.0), U[8]))
    pf = json.load(open(os.path.join(RD, "picks_front.json")))
    obs.append(("photo13", ("alternator", 0), pf["photo13_side"]["alternator_centre"]))
    f11 = pf["photo11"]
    obs.append(("photo11", ("crank", 0), f11["crank_pulley_centre"]))
    obs.append(("photo11", ("corner", (-1, False)), f11["left_cover_outer_bottom_corner"]))
    obs.append(("photo11", ("corner", (1, False)), f11["right_cover_outer_bottom_corner"]))
    obs.append(("photo11", ("corner", (-1, True)), f11["left_cover_inner_bottom_corner"]))
    obs.append(("photo11", ("corner", (1, True)), f11["right_cover_inner_bottom_corner"]))
    obs.append(("photo11", ("alternator", 0), f11["alternator_centre"]))
    sp = json.load(open(os.path.join(RD, "specs", "video_011.4s_topdown.json")))
    for kind, i, u, v in sp["points"]:
        obs.append(("video114", (kind, i), [u, v]))
    return obs


SIZES = {"photo13": (1800, 1200), "photo11": (1800, 1200), "video114": (1920, 1080)}
INIT = {"photo13": "photo13_side_camera.json", "video114": "video_011.4s_topdown_camera.json"}


def model_point(key, kh, kv, alt):
    kind, i = key
    if kind == "alternator":
        return np.array(alt)
    if kind == "crank":
        p = (0.0, -137.0, 0.0)
    elif kind == "corner":
        p = front_corner(*i)
    else:
        p = feat_near(kind, i)
    return np.array([p[0] * kh, p[1] * kh, p[2] * kv])


def project(cam, Xmm, W, H):
    rv, t, lens = cam[:3], cam[3:6], cam[6]
    R = Rot.from_rotvec(rv).as_matrix()          # Blender camera axes in world (columns)
    Xw = Xmm / 1000.0 + np.array([0, 0, ROOT_Z])
    pc = R.T @ (Xw - t)
    f = lens / 36.0 * W
    return np.array([W / 2 + f * pc[0] / -pc[2], H / 2 - f * pc[1] / -pc[2]])


def init_cam(view):
    if view in INIT:
        c = json.load(open(os.path.join(RD, "cameras", INIT[view])))
        return np.concatenate([Rot.from_matrix(np.array(c["rot"])).as_rotvec(), c["loc"], [c["lens"]]])
    # photo11: level camera 5 m in front of the engine, looking +Y
    R = np.column_stack([[1, 0, 0], [0, 0, 1], [0, -1, 0]])     # cam X=world X, cam Y=world Z, cam Z=-world Y
    return np.concatenate([Rot.from_matrix(R).as_rotvec(), [0.0, -5.0, 0.35], [250.0]])


def main():
    obs = load_obs()
    views = sorted({o[0] for o in obs})
    x0 = [1.0, 1.0] + [-250.0, -110.0, 60.0]
    for v in views:
        x0 += list(init_cam(v))
    x0 = np.array(x0, float)

    def resid(x):
        kh, kv, alt = x[0], x[1], x[2:5]
        cams = {v: x[5 + 7 * j: 12 + 7 * j] for j, v in enumerate(views)}
        r = []
        for v, key, uv in obs:
            W, H = SIZES[v]
            r.extend(project(cams[v], model_point(key, kh, kv, alt), W, H) - np.array(uv))
        r.append((x[0] - 1.0) * 20.0)                      # weak priors keep scales sane
        r.append((x[1] - 1.0) * 20.0)
        return np.array(r)

    lo = np.full_like(x0, -np.inf); hi = np.full_like(x0, np.inf)
    lo[0:2], hi[0:2] = 0.6, 1.5
    for j in range(len(views)):
        lo[5 + 7 * j + 6], hi[5 + 7 * j + 6] = 20.0, 600.0
    res = least_squares(resid, x0, bounds=(lo, hi), x_scale='jac', max_nfev=4000)
    x = res.x
    rr = resid(x)[:-2].reshape(-1, 2)
    print("k_h (x/y scale) %.3f   k_v (z scale) %.3f" % (x[0], x[1]))
    print("alternator centre (root mm): x %.0f  y %.0f  z %.0f" % tuple(x[2:5]))
    for j, v in enumerate(views):
        idx = [i for i, o in enumerate(obs) if o[0] == v]
        e = np.linalg.norm(rr[idx], axis=1)
        print("%-9s lens %.0f mm  mean err %.1f px  max %.1f px" % (v, x[5 + 7 * j + 6], e.mean(), e.max()))
    json.dump(dict(k_h=float(x[0]), k_v=float(x[1]), alternator=[float(v) for v in x[2:5]]),
              open(os.path.join(RD, "measurements", "bundle_adjust_v1.json"), "w"), indent=1)
    for j, v in enumerate(views):                      # save jointly solved cameras
        c = x[5 + 7 * j: 12 + 7 * j]
        R = Rot.from_rotvec(c[:3]).as_matrix()
        json.dump(dict(lens=float(c[6]), loc=[float(t) for t in c[3:6]], rot=R.tolist()),
                  open(os.path.join(RD, "cameras", "ba_%s_camera.json" % v), "w"), indent=1)


if __name__ == "__main__":
    main()
