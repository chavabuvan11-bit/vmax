"""Per-column plan profile of the upper pod and upper cam cover in top-view photo 20.
Output: u (0 = pod rear, 1 = pod tip) vs outer/inner edge offsets from the engine
centreline, as fractions of the cam cover's plan half-width."""
import sys, json
import numpy as np, cv2
d = sys.argv[1]
pods = cv2.imread(d + "/top_pods.png", 0) > 0
cov = cv2.imread(d + "/top_covers.png", 0) > 0
# fill holes in pods (glossy highlights)
pods_u8 = pods.astype(np.uint8)
ff = pods_u8.copy(); h, w = ff.shape
mask = np.zeros((h + 2, w + 2), np.uint8); cv2.floodFill(ff, mask, (0, 0), 1)
pods = (pods_u8 | (1 - ff)).astype(bool)
ys, xs = np.nonzero(pods)
# centre line: mean of the gap between the two pods, per column, over the mid section
mid_rows = []
for x in range(1050, 1450, 5):
    col = np.nonzero(pods[:, x])[0]
    if len(col) < 10: continue
    gaps = np.diff(col)
    k = np.argmax(gaps)
    if gaps[k] > 5: mid_rows.append((col[k] + col[k + 1]) / 2)
cy = float(np.median(mid_rows))
upper = pods.copy(); upper[int(cy):, :] = False
cols = np.nonzero(upper.any(axis=0))[0]
x_rear, x_tip = int(cols.min()), int(cols.max())
cov_up = cov.copy(); cov_up[int(cy):, :] = False
cc = np.nonzero(cov_up.any(axis=0))[0]
# cover plan half-width: robust outer edge over the exposed front section
outer_cov = [cy - np.nonzero(cov_up[:, x])[0].min() for x in range(int(cc.max()) - 180, int(cc.max()) - 40)]
cov_half = float(np.median(outer_cov))
prof = []
for x in range(x_rear, x_tip + 1, 4):
    col = np.nonzero(upper[:, x])[0]
    if len(col) == 0: continue
    prof.append(dict(u=(x - x_rear) / (x_tip - x_rear),
                     outer=(cy - col.min()) / cov_half, inner=(cy - col.max()) / cov_half))
res = dict(centre_row=cy, pod_rear_px=x_rear, pod_tip_px=x_tip, cover_front_px=int(cc.max()),
           cover_half_px=cov_half, profile=prof)
json.dump(res, open(d + "/top_profile.json", "w"), indent=1)
print("centre row %.1f  pod x %d..%d  cover front %d  cover half-width %.1f px" % (cy, x_rear, x_tip, cc.max(), cov_half))
for p in prof[::8]:
    print("u=%.2f outer=%.3f inner=%.3f" % (p["u"], p["outer"], p["inner"]))
