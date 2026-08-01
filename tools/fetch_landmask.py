# -*- coding: utf-8 -*-
"""100mメッシュの水／陸マスクを作る。

ETOPO(450m)の「標高が負＝水」だけでは、江戸川区・江東区のような市街地まで
水域として扱われてしまう（450m平均が海面下になる、川筋の1セルが隣へ漏れる）。
そこで実際の土地利用で水／陸を判定し直すためのマスクを作る。

出典: 国土数値情報 L03-b 100mメッシュ土地利用（国土交通省, 2016年度）
      https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L03-b.html

出力:
  docs/data/landmask.bin  — 100mメッシュの水域ビットマップ（1bit/メッシュ、北上、行内は西→東）
  docs/data/landmask.json — 上のビットマップの原点・大きさ

判定:
  1100 河川地及び湖沼 / 1400 海浜 / 1500 海水域  -> 水 (1)
  それ以外の区分（建物用地・森林・田 など）        -> 陸 (0)
  L03-b に収録が無いメッシュ                      -> 水 (1)  ※外洋。陸は必ず収録される
"""
import io
import json
import os
import sys
import zipfile

import numpy as np
import requests
import shapefile  # pyshp

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "docs", "data")

VER = "L03-b-16"
URL = "https://nlftp.mlit.go.jp/ksj/gml/data/L03-b/{v}/{v}_{m}-jgd_GML.zip"
# アプリの表示範囲 138.9〜141.0E / 34.82〜35.80N を覆う1次メッシュ
PRIMARY = ["5238", "5239", "5240", "5338", "5339", "5340"]
WATER = {"1100", "1400", "1500"}

# 100mメッシュ格子: 緯度 1/1200度, 経度 1/800度
LAT_DIV, LON_DIV = 1200, 800


def fetch(mesh):
    path = os.path.join(CACHE, "%s_%s.zip" % (VER, mesh))
    if not os.path.exists(path):
        url = URL.format(v=VER, m=mesh)
        print("downloading", url)
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=900)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
    return path


def main():
    meta = json.load(open(os.path.join(OUT, "meta.json")))
    # マスクはメッシュ格子にぴったり載せる（再標本化による半メッシュのズレを避ける）
    x0 = int(np.floor(meta["west"] * LON_DIV))
    y0 = int(np.floor(meta["south"] * LAT_DIV))
    cols = int(np.ceil(meta["east"] * LON_DIV)) - x0
    rows = int(np.ceil(meta["north"] * LAT_DIV)) - y0
    print("mask grid %d x %d (%.1f KB)" % (cols, rows, cols * rows / 8 / 1024))

    # 0=未収録(=外洋として水扱い), 1=水, 2=陸
    kind = np.zeros((rows, cols), dtype=np.uint8)

    for mesh in PRIMARY:
        z = zipfile.ZipFile(fetch(mesh))
        base = "%s_%s" % (VER, mesh)
        r = shapefile.Reader(dbf=io.BytesIO(z.read(base + ".dbf")), encoding="cp932")
        fields = [f[0] for f in r.fields[1:]]
        i_mesh, i_use = fields.index("メッシュ"), fields.index("土地利用種")
        n_in = 0
        for rec in r.iterRecords():
            code = rec[i_mesh]
            # 10桁 = 1次(4) + 2次(2) + 3次(2) + 100m(2)。SW隅のメッシュ番号を直接求める。
            # 1次は緯度2/3度・経度1度、2次はその1/8、3次はさらに1/10、100mはさらに1/10。
            # 100mメッシュ単位（緯度1/1200度・経度1/800度）に直すと重みは 800/100/10/1。
            iy = int(code[0:2]) * 800 + int(code[4]) * 100 + int(code[6]) * 10 + int(code[8])
            ix = ((int(code[2:4]) + 100) * 800 + int(code[5]) * 100
                  + int(code[7]) * 10 + int(code[9]))
            cy, cx = iy - y0, ix - x0
            if 0 <= cy < rows and 0 <= cx < cols:
                kind[rows - 1 - cy, cx] = 1 if rec[i_use] in WATER else 2
                n_in += 1
        print("  %s: %d records, %d in range" % (mesh, r.numRecords, n_in))

    water = kind != 2                       # 未収録(外洋)と水域を「水」とする
    print("水 %.1f%% / 陸 %.1f%% / うち未収録(外洋扱い) %.1f%%"
          % (100 * water.mean(), 100 * (kind == 2).mean(), 100 * (kind == 0).mean()))

    np.packbits(water, axis=None).tofile(os.path.join(OUT, "landmask.bin"))
    with open(os.path.join(OUT, "landmask.json"), "w") as f:
        json.dump({"x0": x0, "y0": y0, "cols": cols, "rows": rows,
                   "latDiv": LAT_DIV, "lonDiv": LON_DIV,
                   "src": "国土数値情報 L03-b 100mメッシュ土地利用 (2016)"}, f)
    print("saved landmask.bin", os.path.getsize(os.path.join(OUT, "landmask.bin")) // 1024, "KB")


if __name__ == "__main__":
    main()
