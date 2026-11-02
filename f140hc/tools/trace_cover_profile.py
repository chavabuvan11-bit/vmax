"""Trace the left cam cover's front-face outline in front photo 11 (near-orthographic,
~244 mm lens) and convert it to bank-local millimetres (x across the bank, z up the bank
axis from the crank centre).  usage: trace_cover_profile.py PHOTO OUTJSON MM_PER_PX"""
import sys, json, math
import numpy as np, cv2
src, outp, mmpx = sys.argv[1], sys.argv[2], float(sys.argv[3])
CRANK = (905.0, 730.0)                 # crank pulley centre in the photo
GAMMA = -32.5                          # left bank
img = cv2.imread(src)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = [hsv[..., i].astype(int) for i in range(3)]
red = (((H <= 8) | (H >= 170)) & (S > 110) & (V > 90)).astype(np.uint8)
red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
red = cv2.morphologyEx(red, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
k, lab, st, cen = cv2.connectedComponentsWithStats(red, 8)
covs = sorted(sorted(range(1, k), key=lambda i: -st[i, cv2.CC_STAT_AREA])[:2], key=lambda i: cen[i][0])
m = (lab == covs[0]).astype(np.uint8)
cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)
hull = cv2.convexHull(c).reshape(-1, 2)
poly = cv2.approxPolyDP(hull.reshape(-1, 1, 2), 4.0, True).reshape(-1, 2)
a = math.radians(-GAMMA)               # world -> bank-local: rotate by -gamma
loc = []
for u, v in poly:
    x, z = (u - CRANK[0]) * mmpx, (CRANK[1] - v) * mmpx
    loc.append((round(x * math.cos(a) + z * math.sin(a), 1), round(-x * math.sin(a) + z * math.cos(a), 1)))
xs = [p[0] for p in loc]; zs = [p[1] for p in loc]
print("bank-local cover outline (mm):", loc)
print("x range %.0f..%.0f (width %.0f)   z range %.0f..%.0f (height %.0f)" %
      (min(xs), max(xs), max(xs) - min(xs), min(zs), max(zs), max(zs) - min(zs)))
json.dump(dict(outline=loc), open(outp, "w"))
ov = img.copy()
cv2.polylines(ov, [poly.reshape(-1, 1, 2)], True, (0, 255, 0), 3)
cv2.imwrite(outp.replace(".json", ".jpg"), cv2.resize(ov[200:900, 450:1350], (900, 700)))
