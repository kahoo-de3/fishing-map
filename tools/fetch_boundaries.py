# -*- coding: utf-8 -*-
# Coastal municipality boundaries for Tokyo/Chiba/Kanagawa.
# Source: smartnews-smri/japan-topography (国土数値情報N03を簡略化, CC-BY相当・出典明記)
# Output: docs/data/coastal_muni.json  (MultiPolygon per muni + label Point features)
import requests, json, os
from collections import defaultdict

OUT = r"C:\Users\kahoo\Downloads\fishing-map\docs\data\coastal_muni.json"
BASE = ("https://raw.githubusercontent.com/smartnews-smri/japan-topography/"
        "main/data/municipality/geojson/s0010/")
PREFS = {"12": "N03-21_12_210101.json",
         "13": "N03-21_13_210101.json",
         "14": "N03-21_14_210101.json"}

# 海に面している市区町村（政令市は区単位）
COASTAL = {
    # 東京都
    "13": ["大田区", "品川区", "港区", "中央区", "江東区", "江戸川区"],
    # 神奈川県
    "14": ["川崎市川崎区",
           "横浜市鶴見区", "横浜市神奈川区", "横浜市西区", "横浜市中区",
           "横浜市磯子区", "横浜市金沢区",
           "横須賀市", "三浦市", "葉山町", "逗子市", "鎌倉市", "藤沢市",
           "茅ヶ崎市", "平塚市", "大磯町", "二宮町", "小田原市", "真鶴町", "湯河原町"],
    # 千葉県
    "12": ["浦安市", "市川市", "船橋市", "習志野市", "千葉市美浜区", "千葉市中央区",
           "市原市", "袖ケ浦市", "木更津市", "君津市", "富津市", "鋸南町",
           "南房総市", "館山市", "鴨川市", "勝浦市", "御宿町", "いすみ市",
           "一宮町", "長生村", "白子町", "大網白里市", "九十九里町", "山武市",
           "横芝光町", "匝瑳市", "旭市", "銚子市"],
}

def ring_area_centroid(ring):
    """signed area (deg^2) and centroid of a lon/lat ring"""
    a = cx = cy = 0.0
    n = len(ring)
    for i in range(n - 1):
        x0, y0 = ring[i]; x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(a) < 1e-12:
        xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
        return 0.0, (sum(xs) / len(xs), sum(ys) / len(ys))
    a *= 0.5
    return abs(a), (cx / (6 * a), cy / (6 * a))

groups = defaultdict(list)  # key -> list of polygon coordinate arrays
for pref, fname in PREFS.items():
    print("downloading", fname)
    gj = requests.get(BASE + fname, timeout=120).json()
    wanted = set(COASTAL[pref])
    for f in gj["features"]:
        p = f["properties"]
        gun = (p.get("N03_003") or "").strip()
        city = (p.get("N03_004") or "").strip()
        # 政令市は「市名+区名」、それ以外は市区町村名で照合（郡名は除外して照合）
        full = (gun + city) if gun.endswith("市") else city
        if full in wanted:
            geom = f["geometry"]
            polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
                     else geom["coordinates"])
            # label: 政令市の区は区名のみ表示
            groups[(full, city)].extend(polys)

feats = []
for (full, label), polys in groups.items():
    # round coords to 5 decimals (~1m)
    rp = [[[[round(x, 5), round(y, 5)] for x, y in ring] for ring in poly]
          for poly in polys]
    feats.append({"type": "Feature",
                  "properties": {"n": label},
                  "geometry": {"type": "MultiPolygon", "coordinates": rp}})
    # label point = centroid of largest polygon (by exterior ring area)
    best = max(polys, key=lambda poly: ring_area_centroid(poly[0])[0])
    _, (cx, cy) = ring_area_centroid(best[0])
    feats.append({"type": "Feature",
                  "properties": {"n": label, "pt": 1},
                  "geometry": {"type": "Point",
                               "coordinates": [round(cx, 5), round(cy, 5)]}})

missing = []
for pref, names in COASTAL.items():
    for nm in names:
        if not any(k[0] == nm for k in groups):
            missing.append(nm)
print("municipalities:", len(groups), "/ missing:", missing or "none")

gj = {"type": "FeatureCollection", "features": feats}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(gj, f, ensure_ascii=False, separators=(",", ":"))
print("saved", OUT, os.path.getsize(OUT) // 1024, "KB")
