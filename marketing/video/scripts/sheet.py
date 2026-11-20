"""Planche-contact des images clés : python scripts/sheet.py out/sheet.jpg img1 img2 ..."""

import sys

from PIL import Image, ImageDraw

out, files = sys.argv[1], sys.argv[2:]
ims = [Image.open(f) for f in files]
w, h = ims[0].size
cols = 2
rows = (len(ims) + cols - 1) // cols
sheet = Image.new("RGB", (cols * w + (cols - 1) * 8, rows * h + (rows - 1) * 8), "white")
for i, (f, im) in enumerate(zip(files, ims, strict=True)):
    x, y = (i % cols) * (w + 8), (i // cols) * (h + 8)
    sheet.paste(im, (x, y))
    ImageDraw.Draw(sheet).text((x + 8, y + 6), f.split("/")[-1], fill="yellow")
sheet.save(out, quality=85)
