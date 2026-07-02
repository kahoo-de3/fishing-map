# -*- coding: utf-8 -*-
# Fetch bottom sediment (底質) points from MSIL API for the Kanto bbox,
# merge into one GeoJSON used by the web app.
# Uses the public trial subscription key published on portal.msil.go.jp/howtouse
import requests, json, os, time

KEY = "0e83ad5d93214e04abf37c970c32b641"  # trial key (portal.msil.go.jp/howtouse)
BBOX = "138.90,34.82,141.00,35.80"
OUT = r"C:\Users\kahoo\Downloads\fishing-map\docs\data\sediment.json"

# slug candidates per sediment type
TYPES = {
    "砂":     ["sand"],
    "泥・粘土": ["mud-caly"],  # sic: official API slug has this typo
    "石・岩":  ["stone-rock"],
    "礫":     ["gravel", "pebble"],
    "貝殻":    ["shell", "shells"],
    "さんご":  ["coral"],
    "溶岩":    ["lava"],
}

S = requests.Session()
S.headers.update({"Ocp-Apim-Subscription-Key": KEY})

def fetch_all(slug):
    feats, offset = [], 0
    while True:
        params = {
            "f": "geojson", "where": "1=1",
            "geometry": BBOX, "geometryType": "esriGeometryEnvelope",
            "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
            "returnGeometry": "true",
        }
        if offset:
            params["resultOffset"] = offset
        r = S.get(f"https://api.msil.go.jp/{slug}/v2/MapServer/1/query",
                  params=params, timeout=60)
        if r.status_code != 200:
            return None, r.status_code
        j = r.json()
        fs = j.get("features", [])
        feats.extend(fs)
        if j.get("exceededTransferLimit") or (j.get("properties") or {}).get("exceededTransferLimit"):
            offset += 1000
            time.sleep(0.4)
            continue
        return feats, 200

merged = []
for jp, slugs in TYPES.items():
    got = False
    for slug in slugs:
        feats, code = fetch_all(slug)
        if feats is None:
            print(f"{jp}: slug '{slug}' -> HTTP {code}")
            continue
        for f in feats:
            f["properties"] = {"t": jp}
        merged.extend(feats)
        print(f"{jp}: slug '{slug}' -> {len(feats)} points")
        got = True
        break
    if not got:
        print(f"!! {jp}: no working slug found")
    time.sleep(0.4)

gj = {"type": "FeatureCollection", "features": merged}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(gj, f, ensure_ascii=False, separators=(",", ":"))
print("total", len(merged), "->", OUT, os.path.getsize(OUT) // 1024, "KB")
