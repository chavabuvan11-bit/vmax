"""Detect coil boots (dark blobs on the red cover) and flange bolt heads (bright blobs on
the cover's lower edge) in a photo, for camera solving.
usage: find_cover_features.py PHOTO OUT.jpg [coil_band_y0 coil_band_y1]"""
import sys, json
import numpy as np, cv2
src, outp = sys.argv[1], sys.argv[2]
img = cv2.imread(src); Hh, Ww = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = [hsv[..., i].astype(int) for i in range(3)]
red = (((H <= 8) | (H >= 170)) & (S > 110) & (V > 90)).astype(np.uint8)
red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
k, lab, st, cen = cv2.connectedComponentsWithStats(red, 8)
cov = (lab == (1 + np.argmax(st[1:, cv2.CC_STAT_AREA]))).astype(np.uint8)
filled = cov.copy()
cs, _ = cv2.findContours(cov, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
cv2.drawContours(filled, cs, -1, 1, -1)
# coils: dark blobs inside the filled cover region (upper part)
dark = ((V < 70) & (S < 120)).astype(np.uint8) & filled
dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
k, lab2, st2, cen2 = cv2.connectedComponentsWithStats(dark, 8)
coils = sorted([(float(cen2[i][0]), float(cen2[i][1]), int(st2[i, 4])) for i in range(1, k) if st2[i, 4] > 1500])
# bolts: bright, low-saturation small blobs inside the cover region
bright = ((V > 170) & (S < 70)).astype(np.uint8) & filled
bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
k, lab3, st3, cen3 = cv2.connectedComponentsWithStats(bright, 8)
bolts = sorted([(float(cen3[i][0]), float(cen3[i][1]), int(st3[i, 4])) for i in range(1, k) if 40 < st3[i, 4] < 900])
ov = img.copy()
for x, y, a in coils: cv2.circle(ov, (int(x), int(y)), 16, (0, 255, 0), 4)
for x, y, a in bolts: cv2.circle(ov, (int(x), int(y)), 10, (255, 0, 255), 3)
cv2.drawContours(ov, cs, -1, (0, 255, 255), 2)
cv2.imwrite(outp, cv2.resize(ov, (Ww * 3 // 4, Hh * 3 // 4)))
print(json.dumps(dict(coils=coils, bolts=bolts)))
