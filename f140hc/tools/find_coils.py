"""Locate the six coil boots on the near cam cover in side photo 13."""
import sys, json
import numpy as np, cv2
src, out = sys.argv[1], sys.argv[2]
img = cv2.imread(src)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = [hsv[..., i].astype(int) for i in range(3)]
red = (((H <= 8) | (H >= 170)) & (S > 110) & (V > 90)).astype(np.uint8)
red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
k, lab, st, _ = cv2.connectedComponentsWithStats(red, 8)
cov = (lab == (1 + np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
x, y, w, h = cv2.boundingRect(cov)
dark = ((V < 60) & (S < 120)).astype(np.uint8)
dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
band = np.zeros_like(dark); band[y - 40:y + int(h * 0.45), x:x + w] = 1
k, lab, st, cen = cv2.connectedComponentsWithStats(dark & band, 8)
blobs = [(cen[i][0], cen[i][1], st[i, cv2.CC_STAT_AREA]) for i in range(1, k)
         if 1200 < st[i, cv2.CC_STAT_AREA] < 20000]
blobs.sort()
ov = img.copy()
for bx, by, a in blobs:
    cv2.circle(ov, (int(bx), int(by)), 10, (0, 255, 0), 3)
cv2.imwrite(out + "/coils_found.jpg", cv2.resize(ov, (900, 600)))
print(json.dumps([(round(bx, 1), round(by, 1), int(a)) for bx, by, a in blobs]))
