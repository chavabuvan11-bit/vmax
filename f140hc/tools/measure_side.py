"""Side photo 13: pod top profile and extents vs the red cam cover, per column."""
import sys, json
import numpy as np, cv2
src, d = sys.argv[1], sys.argv[2]
img = cv2.imread(src)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = [hsv[..., i].astype(int) for i in range(3)]
red = (((H <= 8) | (H >= 170)) & (S > 110) & (V > 90)).astype(np.uint8)
dark = ((V < 75) & (S < 90)).astype(np.uint8)
red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
dark = cv2.morphologyEx(cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)),
                        cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
k, lab, st, _ = cv2.connectedComponentsWithStats(red, 8)
cov = (lab == (1 + np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
# pod = dark component whose top is highest among large components above the cover
k, lab, st, _ = cv2.connectedComponentsWithStats(dark, 8)
cand = [i for i in range(1, k) if st[i, cv2.CC_STAT_AREA] > 20000]
pid = min(cand, key=lambda i: st[i, cv2.CC_STAT_TOP])
pod = (lab == pid).astype(np.uint8)
cx = np.nonzero(cov.any(axis=0))[0]
c_rear, c_front = int(cx.min()), int(cx.max())
cov_top = {x: int(np.nonzero(cov[:, x])[0].min()) for x in range(c_rear, c_front + 1)}
ctop = float(np.median([cov_top[x] for x in range(c_rear + 100, c_front - 200)]))
px_ = np.nonzero(pod.any(axis=0))[0]
p_rear, p_front = int(px_.min()), int(px_.max())
prof = []
L = c_front - c_rear
for x in range(p_rear, p_front + 1, 6):
    col = np.nonzero(pod[:, x])[0]
    if len(col):
        prof.append(dict(x_cov=(x - c_rear) / L, top_above_cover=(ctop - col.min()) / L,
                         bottom_above_cover=(ctop - col.max()) / L))
ov = img.copy()
for m, col in ((pod, (0, 255, 0)), (cov, (255, 0, 255))):
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(ov, cs, -1, col, 3)
cv2.imwrite(d + "/side_overlay.jpg", ov)
json.dump(dict(cover_rear=c_rear, cover_front=c_front, cover_top_row=ctop, pod_rear=p_rear,
               pod_front=p_front, profile=prof), open(d + "/side_profile.json", "w"), indent=1)
print("cover x %d..%d (len %d) top row %.0f | pod x %d..%d" % (c_rear, c_front, L, ctop, p_rear, p_front))
for p in prof[::10]:
    print("x/Lcov=%.2f top=%.3f bottom=%.3f (fraction of cover length above cover top)" %
          (p["x_cov"], p["top_above_cover"], p["bottom_above_cover"]))
