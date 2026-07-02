# ETOPO 2022 (15 arc-second) tile download + local subset
# Region: Tokyo / Chiba / Kanagawa coast
import requests, numpy as np, netCDF4, os

BBOX = dict(west=138.90, east=141.00, south=34.82, north=35.80)
DATA = r"C:\Users\kahoo\Downloads\fishing-map\data"
TILE = os.path.join(DATA, "ETOPO_N45E135_surface.nc")

url = ("https://www.ngdc.noaa.gov/thredds/fileServer/global/ETOPO2022/15s/"
       "15s_surface_elev_netcdf/ETOPO_2022_v1_15s_N45E135_surface.nc")

if not os.path.exists(TILE):
    print("downloading tile ...")
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    with open(TILE, "wb") as f:
        f.write(r.content)
    print("saved", len(r.content), "bytes")

ds = netCDF4.Dataset(TILE)
print(ds.variables.keys())
lat = ds.variables["lat"][:]
lon = ds.variables["lon"][:]
print("lat range", lat.min(), lat.max(), "n=", len(lat))
print("lon range", lon.min(), lon.max(), "n=", len(lon))

yi = np.where((lat >= BBOX["south"]) & (lat <= BBOX["north"]))[0]
xi = np.where((lon >= BBOX["west"]) & (lon <= BBOX["east"]))[0]
z = ds.variables["z"][yi.min():yi.max()+1, xi.min():xi.max()+1]
sublat = lat[yi.min():yi.max()+1]
sublon = lon[xi.min():xi.max()+1]
print("subset shape", z.shape)
print("depth stats: min", float(z.min()), "max", float(z.max()))

np.savez_compressed(os.path.join(DATA, "kanto_depth.npz"),
                    z=np.asarray(z, dtype=np.float32),
                    lat=np.asarray(sublat), lon=np.asarray(sublon))
print("saved kanto_depth.npz")
