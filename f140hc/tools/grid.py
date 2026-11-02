import sys
from PIL import Image, ImageDraw
src, out, step = sys.argv[1], sys.argv[2], int(sys.argv[3])
crop = [int(v) for v in sys.argv[4].split(",")] if len(sys.argv) > 4 else None
im = Image.open(src).convert("RGB")
if crop: im = im.crop(crop)
ox, oy = (crop[0], crop[1]) if crop else (0, 0)
d = ImageDraw.Draw(im)
W, H = im.size
for x in range(0, W, step):
    d.line([(x, 0), (x, H)], fill=(0, 200, 255), width=1)
    d.text((x + 2, 2), str(x + ox), fill=(255, 255, 0))
for y in range(0, H, step):
    d.line([(0, y), (W, y)], fill=(0, 200, 255), width=1)
    d.text((2, y + 2), str(y + oy), fill=(255, 255, 0))
im.save(out, quality=90)
print(out, im.size)
