import sys, glob, os
from PIL import Image, ImageDraw
src, out, cols, w = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
files = sorted(glob.glob(os.path.join(src, "*.jpg")))
sel = sys.argv[5].split(",") if len(sys.argv) > 5 else None
if sel: files = [f for f in files if os.path.basename(f)[:2] in sel]
ims = [Image.open(f).convert("RGB") for f in files]
h = int(w * 2 / 3)
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w, rows * h), (30, 30, 30))
d = ImageDraw.Draw(sheet)
for i, (f, im) in enumerate(zip(files, ims)):
    im = im.resize((w, h))
    x, y = (i % cols) * w, (i // cols) * h
    sheet.paste(im, (x, y))
    d.rectangle([x, y, x + 34, y + 20], fill=(0, 0, 0))
    d.text((x + 6, y + 4), os.path.basename(f)[:2], fill=(255, 255, 0))
sheet.save(out, quality=88)
print(out, sheet.size)
