import sys
from PIL import Image, ImageDraw
ref, ren, out = sys.argv[1], sys.argv[2], sys.argv[3]
a = Image.open(ref).convert("RGB").resize((900, 600))
b = Image.open(ren).convert("RGB").resize((900, 600))
im = Image.new("RGB", (1800, 600))
im.paste(a, (0, 0)); im.paste(b, (900, 0))
d = ImageDraw.Draw(im)
for x, t in ((0, "REAL (Amalgam 1:4, Ferrari CAD)"), (900, "MODEL")):
    d.rectangle([x, 0, x + 270, 22], fill=(0, 0, 0)); d.text((x + 6, 5), t, fill=(255, 255, 0))
im.save(out, quality=88); print(out)
