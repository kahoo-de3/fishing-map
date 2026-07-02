# simple app icon: fish over depth gradient
from PIL import Image, ImageDraw
import os
OUT = r"C:\Users\kahoo\Downloads\fishing-map\docs"

for size in (192, 512):
    img = Image.new("RGBA", (size, size))
    dr = ImageDraw.Draw(img)
    # depth gradient background
    for y in range(size):
        t = y / size
        r = int(200 - 190 * t); g = int(248 - 228 * t); b = int(255 - 165 * t)
        dr.line([(0, y), (size, y)], fill=(r, g, b, 255))
    s = size / 512
    # contour arcs
    for i, ry in enumerate((150, 230, 310, 390)):
        dr.arc([int(-100*s), int(ry*s - 60*s), int(612*s), int(ry*s + 200*s)],
               180, 360, fill=(255, 255, 255, 90), width=max(2, int(6*s)))
    # fish body
    cx, cy = 256 * s, 250 * s
    dr.ellipse([cx-140*s, cy-70*s, cx+110*s, cy+70*s], fill=(20, 50, 90, 255))
    dr.polygon([(cx+90*s, cy), (cx+180*s, cy-70*s), (cx+180*s, cy+70*s)],
               fill=(20, 50, 90, 255))
    dr.ellipse([cx-105*s, cy-30*s, cx-75*s, cy], fill=(255, 255, 255, 255))
    dr.ellipse([cx-98*s, cy-23*s, cx-82*s, cy-7*s], fill=(10, 20, 40, 255))
    img.save(os.path.join(OUT, f"icon-{size}.png"))
print("icons done")
