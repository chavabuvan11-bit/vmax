"""Front photo 11: cam cover cross-sections (red) and pod envelope (dark) in px."""
import sys, json
import numpy as np, cv2
src, d = sys.argv[1], sys.argv[2]
img = cv2.imread(src)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = [hsv[..., i].astype(int) for i in range(3)]
red = (((H <= 8) | (H >= 170)) & (S > 110) & (V > 90)).astype(np.uint8)
red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
k, lab, st, cen = cv2.connectedComponentsWithStats(red, 8)
big = sorted(range(1, k), key=lambda i: -st[i, cv2.CC_STAT_AREA])[:2]
covs = sorted(big, key=lambda i: cen[i][0])
dark = ((V < 70) & (S < 90)).astype(np.uint8)
dark = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
top_red = min(st[i, cv2.CC_STAT_TOP] for i in covs)
band = np.zeros_like(dark); band[:top_red + 40, :] = 1
k2, lab2, st2, _ = cv2.connectedComponentsWithStats(dark & band, 8)
pod_ids = [i for i in range(1, k2) if st2[i, cv2.CC_STAT_AREA] > 3000]
pods = np.isin(lab2, pod_ids).astype(np.uint8)
res = {}
for name, i in zip(("left", "right"), covs):
    x, y, w, h, a = [int(v) for v in st[i]]
    m = (lab == i)
    tops = [int(np.nonzero(m[:, xx])[0].min()) for xx in range(x, x + w)]
    bots = [int(np.nonzero(m[:, xx])[0].max()) for xx in range(x, x + w)]
    res[name] = dict(bbox=[x, y, w, h], top_profile=tops[::4], bottom_profile=bots[::4])
ys, xs = np.nonzero(pods)
res["pods_bbox"] = [int(xs.min()), int(ys.min()), int(xs.max() - xs.min()), int(ys.max() - ys.min())]
cols = range(xs.min(), xs.max() + 1)
res["pods_top"] = [(int(c), int(np.nonzero(pods[:, c])[0].min())) for c in cols if pods[:, c].any()][::6]
ov = img.copy()
for m, col in (((np.isin(lab, covs)).astype(np.uint8), (255, 0, 255)), (pods, (0, 255, 0))):
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(ov, cs, -1, col, 2)
cv2.imwrite(d + "/front_overlay.jpg", cv2.resize(ov[200:800, 450:1350], (900, 600)))
json.dump(res, open(d + "/front.json", "w"))
for nm in ("left", "right"):
    print(nm, "cover bbox (x,y,w,h):", res[nm]["bbox"])
print("pods bbox:", res["pods_bbox"])
print("pods top (col,row):", res["pods_top"][::4])
