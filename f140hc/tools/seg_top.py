"""Segment Amalgam top view (photo 20): red cam covers and black carbon pods.
Outputs masks, a contour overlay for inspection, and per-column edge profiles."""
import sys, json
import numpy as np, cv2

src, outdir = sys.argv[1], sys.argv[2]
img = cv2.imread(src)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)

red = (((H <= 8) | (H >= 170)) & (S > 110) & (V > 90)).astype(np.uint8)
dark = ((V < 70) & (S < 90)).astype(np.uint8)

def clean(m, k_open, k_close):
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((k_open, k_open), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((k_close, k_close), np.uint8))
    return m

red = clean(red, 3, 9)
dark = clean(dark, 5, 15)

# keep the big components only
def biggest(m, n):
    k, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    order = np.argsort(-st[1:, cv2.CC_STAT_AREA])[:n] + 1
    out = np.zeros_like(m)
    for i in order:
        out[lab == i] = 1
    return out, [tuple(int(v) for v in st[i]) for i in order]

pods, pod_stats = biggest(dark, 2)
covers, cov_stats = biggest(red, 2)

ov = img.copy()
for m, col in ((pods, (0, 255, 0)), (covers, (255, 0, 255))):
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(ov, cs, -1, col, 2)
cv2.imwrite(outdir + "/top_overlay.jpg", ov)
cv2.imwrite(outdir + "/top_pods.png", pods * 255)
cv2.imwrite(outdir + "/top_covers.png", covers * 255)
print("pods", pod_stats)
print("covers", cov_stats)
