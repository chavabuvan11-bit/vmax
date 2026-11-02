"""Back-project picked pixels from a solved camera onto a model plane (y = const, root mm).
usage: backproject.py CAMERA.json W H Y_PLANE u,v [u,v ...]"""
import sys, json
import numpy as np
cam = json.load(open(sys.argv[1])); W, H = float(sys.argv[2]), float(sys.argv[3]); yp = float(sys.argv[4]) / 1000.0
R = np.array(cam["rot"]); loc = np.array(cam["loc"]); f = cam["lens"] / 36.0 * W
for tok in sys.argv[5:]:
    u, v = map(float, tok.split(","))
    d = R @ np.array([(u - W / 2) / f, -(v - H / 2) / f, -1.0])
    t = (yp - loc[1]) / d[1]
    X = (loc + d * t) * 1000.0
    print("%-12s -> x %7.1f  y %7.1f  z %7.1f" % (tok, X[0], X[1], X[2] - 150.0))
