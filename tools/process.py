# Generate map overlay (depth colors + contour lines + slope highlight)
# and a binary depth grid for tap-lookup, from kanto_depth.npz
import numpy as np, json, os
from scipy import ndimage
from PIL import Image

DATA = r"C:\Users\kahoo\Downloads\fishing-map\data"
OUT = r"C:\Users\kahoo\Downloads\fishing-map\docs"
os.makedirs(OUT, exist_ok=True)
os.makedirs(os.path.join(OUT, "data"), exist_ok=True)

d = np.load(os.path.join(DATA, "kanto_depth.npz"))
z = d["z"]          # (nlat, nlon), meters, negative = below sea level
lat = d["lat"]      # ascending
lon = d["lon"]
nlat, nlon = z.shape
south, north = float(lat.min()), float(lat.max())
west, east = float(lon.min()), float(lon.max())
print("grid", z.shape, "bbox", west, south, east, north)

# ---------------- depth grid for tap lookup (original resolution) ----------
# int16 decimeters of depth (positive down); 32767 = land
depth = -z  # positive = depth in m
grid = np.where(depth > 0, np.clip(depth * 10, 1, 32000), 32767).astype(np.int16)
# store north-up (row 0 = north)
grid_nu = grid[::-1, :]
grid_nu.tofile(os.path.join(OUT, "data", "depth.bin"))

meta = dict(west=west, east=east, south=south, north=north,
            nlon=int(nlon), nlat=int(nlat))
with open(os.path.join(OUT, "data", "meta.json"), "w") as f:
    json.dump(meta, f)

# ---------------- upsample for smooth rendering ----------------------------
ZOOM = 8
zf = ndimage.zoom(z.astype(np.float64), ZOOM, order=3)   # bicubic
H, W = zf.shape
# latitudes of upsampled rows (linear in degrees, ascending)
lat_hi = np.linspace(south, north, H)

# ---------------- reproject rows to Web Mercator spacing -------------------
def merc(phi_deg):
    phi = np.radians(phi_deg)
    return np.log(np.tan(np.pi / 4 + phi / 2))

y_top, y_bot = merc(north), merc(south)
# target rows: linear in mercator y from north (row 0) to south (row H-1)
y_rows = np.linspace(y_top, y_bot, H)
# convert each target mercator y back to latitude
lat_rows = np.degrees(2 * np.arctan(np.exp(y_rows)) - np.pi / 2)
# sample zf at those latitudes (zf row index: lat ascending)
row_idx = (lat_rows - south) / (north - south) * (H - 1)
zi = np.clip(row_idx, 0, H - 1)
i0 = np.floor(zi).astype(int); i1 = np.minimum(i0 + 1, H - 1)
w1 = (zi - i0)[:, None]
zm = zf[i0, :] * (1 - w1) + zf[i1, :] * w1   # mercator-spaced, row0=north
dep = -zm  # positive = depth

# ---------------- color mapping --------------------------------------------
# fishing-oriented palette: shallow cyan -> deep navy
stops = [   # depth_m, (r,g,b)
    (0.0,   (200, 248, 255)),
    (2.0,   (150, 235, 250)),
    (5.0,   (100, 220, 245)),
    (10.0,  (60, 200, 240)),
    (15.0,  (40, 180, 235)),
    (20.0,  (30, 160, 225)),
    (30.0,  (25, 135, 210)),
    (50.0,  (20, 105, 185)),
    (100.0, (18, 78, 155)),
    (200.0, (15, 55, 120)),
    (500.0, (12, 35, 90)),
    (1500.0,(8, 20, 60)),
    (3500.0,(4, 10, 35)),
]
sd = np.array([s[0] for s in stops])
sc = np.array([s[1] for s in stops], dtype=np.float64)
dc = np.clip(dep, 0, 3500)
rgb = np.zeros((H, W, 3))
for ch in range(3):
    rgb[:, :, ch] = np.interp(dc, sd, sc[:, ch])

water = dep > 0
alpha = np.where(water, 185, 0).astype(np.float64)  # ~0.73 opacity over water

# ---------------- contour lines --------------------------------------------
levels = [2, 5, 10, 15, 20, 30, 50, 100, 200, 500, 1000, 2000]
line = np.zeros((H, W), dtype=bool)
for lv in levels:
    m = dep >= lv
    edge = m & ~ndimage.binary_erosion(m, iterations=2)
    line |= (edge & water)
# darken lines
lc = np.array([10, 60, 110], dtype=np.float64)
for ch in range(3):
    rgb[:, :, ch] = np.where(line, rgb[:, :, ch] * 0.45 + lc[ch] * 0.55, rgb[:, :, ch])
alpha = np.where(line, 235, alpha)

# ---------------- slope highlight (kakeagari) -------------------------------
# gradient on the UPSAMPLED smooth surface -> smooth band edges at high zoom
latc = (south + north) / 2
mlat = 111320.0
mlon = 111320.0 * np.cos(np.radians(latc))
dy_hi = (lat[1] - lat[0]) * mlat / ZOOM
dx_hi = (lon[1] - lon[0]) * mlon / ZOOM
zf_s = ndimage.gaussian_filter(zf, sigma=ZOOM * 0.6)
gy, gx = np.gradient(-zf_s, dy_hi, dx_hi)
slope_hi = np.hypot(gx, gy)                   # tan(slope)
slope_hi[(-zf) <= 0] = 0
# re-space rows to mercator like zm
slope_m = slope_hi[i0, :] * (1 - w1) + slope_hi[i1, :] * w1

# thresholds: gentle->steep : yellow -> orange -> red
th = [(0.035, (255, 210, 80), 0.40, 130),
      (0.07,  (255, 140, 40), 0.62, 175),
      (0.12,  (235, 40, 30),  0.78, 215)]
for t, col, a, av in th:
    m = (slope_m >= t) & water
    for ch in range(3):
        rgb[:, :, ch] = np.where(m, rgb[:, :, ch] * (1 - a) + col[ch] * a, rgb[:, :, ch])
    alpha = np.where(m, np.maximum(alpha, av), alpha)

# ---------------- save PNG --------------------------------------------------
img = np.dstack([rgb.astype(np.uint8), alpha.astype(np.uint8)])
Image.fromarray(img, "RGBA").save(os.path.join(OUT, "data", "overlay.png"), optimize=True)
print("overlay.png", img.shape)

# slope-only overlay (so kakeagari can be toggled separately)
rgb2 = np.zeros((H, W, 3))
alpha2 = np.zeros((H, W))
for t, col, a, av in th:
    m = (slope_m >= t) & water
    for ch in range(3):
        rgb2[:, :, ch] = np.where(m, col[ch], rgb2[:, :, ch])
    alpha2 = np.where(m, av + 25, alpha2)
img2 = np.dstack([rgb2.astype(np.uint8), alpha2.astype(np.uint8)])
Image.fromarray(img2, "RGBA").save(os.path.join(OUT, "data", "slope.png"), optimize=True)

# depth-only overlay (colors + contours, no slope)
rgb3 = np.zeros((H, W, 3))
for ch in range(3):
    rgb3[:, :, ch] = np.interp(dc, sd, sc[:, ch])
alpha3 = np.where(water, 185, 0).astype(np.float64)
for ch in range(3):
    rgb3[:, :, ch] = np.where(line, rgb3[:, :, ch] * 0.45 + lc[ch] * 0.55, rgb3[:, :, ch])
alpha3 = np.where(line, 235, alpha3)
img3 = np.dstack([rgb3.astype(np.uint8), alpha3.astype(np.uint8)])
Image.fromarray(img3, "RGBA").save(os.path.join(OUT, "data", "depth_only.png"), optimize=True)

sizes = {f: os.path.getsize(os.path.join(OUT, 'data', f)) // 1024
         for f in ["overlay.png", "slope.png", "depth_only.png", "depth.bin"]}
print("sizes KB:", sizes)
