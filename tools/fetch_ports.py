# -*- coding: utf-8 -*-
# Port name labels: 漁港 (国土数値情報C09, 全国2006) + 港湾 (C02, 2014)
# -> docs/data/ports.json (GeoJSON points, properties: n=name, k=漁港|港湾)
import requests, zipfile, io, os, json, re
import xml.etree.ElementTree as ET

BBOX = (138.90, 34.82, 141.00, 35.80)   # w,s,e,n
OUT = r"C:\Users\kahoo\Downloads\fishing-map\docs\data\ports.json"
URLS = {
    "漁港": "https://nlftp.mlit.go.jp/ksj/gml/data/C09/C09-06/C09-06_GML.zip",
    "港湾": "https://nlftp.mlit.go.jp/ksj/gml/data/C02/C02-14/C02-14_GML.zip",
}
NAME_TAGS = ("fishingPortName", "harborName", "portName", "facilityName")
GML = "{http://www.opengis.net/gml/3.2}"
XLINK = "{http://www.w3.org/1999/xlink}href"

def parse_ksj(xml_bytes):
    txt = xml_bytes.decode("utf-8-sig", errors="replace")
    txt = re.sub(r"^<\?xml[^>]*\?>", "", txt, count=1)
    root = ET.fromstring(txt)
    pts = {}
    for pt in root.iter(f"{GML}Point"):
        gid = pt.get(f"{GML}id")
        pos = pt.find(f"{GML}pos")
        if gid and pos is not None and pos.text:
            a = pos.text.split()
            if len(a) >= 2:
                pts[gid] = (float(a[1]), float(a[0]))  # lon, lat
    feats = []
    tags_seen = set()
    for el in root:
        tag = el.tag.split("}")[-1]
        if tag in ("Dataset",):
            continue
        tags_seen.add(tag)
        name, coord = None, None
        for child in el:
            ctag = child.tag.split("}")[-1]
            if ctag in NAME_TAGS and child.text:
                name = child.text.strip()
            href = child.get(XLINK)
            if href and href.lstrip("#") in pts:
                coord = pts[href.lstrip("#")]
        if name and coord:
            feats.append((name, coord))
    return feats, tags_seen

all_feats, seen = [], set()
for kind, url in URLS.items():
    print("downloading", kind)
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = [n for n in zf.namelist()
             if n.lower().endswith((".xml", ".gml")) and "META" not in n.upper()]
    got = 0
    for n in names:
        feats, tags = parse_ksj(zf.read(n))
        if not feats:
            print("  no features in", n, "tags:", sorted(tags)[:12])
            continue
        for name, (lon, lat) in feats:
            if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
                continue
            disp = name if name.endswith(("港", "漁港")) else name + ("漁港" if kind == "漁港" else "港")
            key = (disp, round(lon, 3), round(lat, 3))
            if key in seen:
                continue
            seen.add(key)
            all_feats.append({"type": "Feature",
                              "properties": {"n": disp, "k": kind},
                              "geometry": {"type": "Point",
                                           "coordinates": [round(lon, 5), round(lat, 5)]}})
            got += 1
    print(f"  -> {got} in bbox")

gj = {"type": "FeatureCollection", "features": all_feats}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(gj, f, ensure_ascii=False, separators=(",", ":"))
print("total", len(all_feats), "->", OUT, os.path.getsize(OUT) // 1024, "KB")
