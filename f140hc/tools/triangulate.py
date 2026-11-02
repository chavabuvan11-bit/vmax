"""Triangulate landmarks picked in two or more photos with solved cameras.

usage: triangulate.py PICKS.json
PICKS: {"views": {"name": {"camera": cam.json, "size": [W, H]}, ...},
        "landmarks": {"label": {"view_name": [u, v], ...}, ...}}
Prints each landmark in root-frame millimetres (root at world z = 150 mm) and the
reprojection error per view, so a bad pick or a bad camera shows up immediately.
"""
import sys, json, os
import numpy as np
from scipy.optimize import least_squares

ROOT_Z = 0.150


def load_cam(path, size):
    c = json.load(open(path))
    W, H = size
    return dict(R=np.array(c["rot"]), loc=np.array(c["loc"]), f=c["lens"] / 36.0 * W, W=W, H=H)


def project(cam, X):
    pc = cam["R"].T @ (X - cam["loc"])
    return np.array([cam["W"] / 2 + cam["f"] * pc[0] / -pc[2], cam["H"] / 2 - cam["f"] * pc[1] / -pc[2]])


def ray(cam, uv):
    x = (uv[0] - cam["W"] / 2) / cam["f"]
    y = -(uv[1] - cam["H"] / 2) / cam["f"]
    d = cam["R"] @ np.array([x, y, -1.0])
    return cam["loc"], d / np.linalg.norm(d)


def triangulate(cams, obs):
    # closest point to all rays (linear), then refine on reprojection error
    A = np.zeros((3, 3)); b = np.zeros(3)
    for name, uv in obs.items():
        o, d = ray(cams[name], uv)
        P = np.eye(3) - np.outer(d, d)
        A += P; b += P @ o
    X0 = np.linalg.solve(A, b)
    res = least_squares(lambda X: np.concatenate([project(cams[n], X) - np.array(uv) for n, uv in obs.items()]), X0)
    X = res.x
    err = {n: float(np.linalg.norm(project(cams[n], X) - np.array(uv))) for n, uv in obs.items()}
    return X, err


def main():
    spec = json.load(open(sys.argv[1]))
    base = os.path.dirname(os.path.abspath(sys.argv[1]))
    cams = {n: load_cam(v["camera"] if os.path.isabs(v["camera"]) else os.path.join(base, v["camera"]), v["size"])
            for n, v in spec["views"].items()}
    out = {}
    for label, obs in spec["landmarks"].items():
        X, err = triangulate(cams, obs)
        mm = (X - np.array([0, 0, ROOT_Z])) * 1000.0
        out[label] = [round(float(v), 1) for v in mm]
        print("%-16s x %7.1f  y %7.1f  z %7.1f   reproj px: %s" % (
            label, mm[0], mm[1], mm[2], ", ".join("%s %.1f" % (n, e) for n, e in err.items())))
    if len(sys.argv) > 2:
        json.dump(out, open(sys.argv[2], "w"), indent=1)


if __name__ == "__main__":
    main()
