"""Stack the photo crop over the model render of the same crop.  usage: compare_section.py PHOTO RENDER ROW0 ROW1 OUT"""
import sys
from PIL import Image, ImageDraw
ph, rn, r0, r1, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
a = Image.open(ph).convert("RGB").crop((0, r0, 1800, r1))
b = Image.open(rn).convert("RGB").resize(a.size)
im = Image.new("RGB", (a.width, a.height * 2 + 6), (0, 0, 0))
im.paste(a, (0, 0)); im.paste(b, (0, a.height + 6))
d = ImageDraw.Draw(im)
for y, t in ((0, "REAL (Amalgam 1:4, Ferrari CAD)"), (a.height + 6, "MODEL (same solved camera)")):
    d.rectangle([0, y, 300, y + 22], fill=(0, 0, 0)); d.text((6, y + 5), t, fill=(255, 255, 0))
im.resize((im.width // 2, im.height // 2)).save(out, quality=90); print(out)
