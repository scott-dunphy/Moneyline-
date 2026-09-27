"""Download and prepare Manhattan census-tract population, 1950 -> latest ACS.

Sources
  1950-2000  Decennial census tract counts + historical tract boundaries from
             IPUMS NHGIS (the ACS does not exist before 2005). Needs a free
             IPUMS account: either set IPUMS_API_KEY, or log in at
             nhgis.org, download the extract yourself and pass --nhgis-dir.
  2010-now   ACS 5-year estimates (table B01003, total population) from the
             Census Bureau API, on matching-vintage TIGER cartographic tracts.
  Context    TIGER cartographic county boundaries (shoreline-clipped) and
             NYC Planning's 2020 Neighborhood Tabulation Areas.

Every year's tracts are clipped to the same Manhattan shoreline so land area,
and therefore density, is measured consistently across vintages.

Usage
  python fetch_data.py                       # everything (needs IPUMS_API_KEY)
  python fetch_data.py --nhgis-dir ~/Downloads/nhgis_extract
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from config import (ACS_END_YEARS, CONTEXT_COUNTIES, COUNTY_FIPS, DECENNIAL_YEARS,
                    MAP_CRS, NHGIS_PREFIX, PROCESSED, RAW, SQFT_PER_SQMI, STATE_FIPS)

ACS_API = "https://api.census.gov/data/{year}/acs/acs5"
TIGER = "https://www2.census.gov/geo/tiger"
IPUMS = "https://api.ipums.org"
NTA_URL = "https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd?method=export&format=GeoJSON"

session = requests.Session()


def download(url, dest, headers=None):
    dest = Path(dest)
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}")
    with session.get(url, headers=headers, timeout=600, stream=True) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    return dest


# ---------------------------------------------------------------- geography

def county_shapes(year):
    path = download(f"{TIGER}/GENZ{year}/shp/cb_{year}_us_county_500k.zip",
                    RAW / "tiger" / f"cb_{year}_us_county_500k.zip")
    gdf = gpd.read_file(f"zip://{path}")
    gdf["GEOID"] = gdf["STATEFP"] + gdf["COUNTYFP"]
    return gdf.to_crs(MAP_CRS)


def tiger_tracts(year):
    """Cartographic-boundary tracts for Manhattan matching an ACS vintage."""
    if year == 2010:
        url = f"{TIGER}/GENZ2010/gz_2010_{STATE_FIPS}_140_00_500k.zip"
    else:
        url = f"{TIGER}/GENZ{year}/shp/cb_{year}_{STATE_FIPS}_tract_500k.zip"
    path = download(url, RAW / "tiger" / Path(url).name)
    gdf = gpd.read_file(f"zip://{path}")
    if "GEOID" not in gdf:
        gdf["GEOID"] = gdf["GEO_ID"].str[-11:]
    gdf = gdf[gdf["GEOID"].str.startswith(STATE_FIPS + COUNTY_FIPS)]
    return gdf[["GEOID", "geometry"]].to_crs(MAP_CRS)


# ---------------------------------------------------------------------- ACS

def acs_released(year):
    try:
        r = session.get(ACS_API.format(year=year), params={"get": "NAME", "for": "us:1"}, timeout=30)
        return r.status_code == 200 and r.text.lstrip().startswith("[")
    except requests.RequestException:
        return False


def latest_acs_year():
    for year in range(dt.date.today().year, 2009, -1):
        if acs_released(year):
            return year
    raise RuntimeError("Could not reach the Census API to find the latest ACS release.")


def acs_population(year):
    params = {"get": "B01003_001E,B01003_001M", "for": "tract:*",
              "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}"}
    if os.environ.get("CENSUS_API_KEY"):
        params["key"] = os.environ["CENSUS_API_KEY"]
    r = session.get(ACS_API.format(year=year), params=params, timeout=120)
    r.raise_for_status()
    rows = r.json()
    df = pd.DataFrame(rows[1:], columns=rows[0])
    df["GEOID"] = df["state"] + df["county"] + df["tract"]
    df["pop"] = pd.to_numeric(df["B01003_001E"]).clip(lower=0)
    df["moe"] = pd.to_numeric(df["B01003_001M"], errors="coerce")
    return df[["GEOID", "pop", "moe"]]


# -------------------------------------------------------------------- NHGIS

def ipums(method, path, key, params=None, **kw):
    params = {"collection": "nhgis", "version": 2, **(params or {})}
    r = session.request(method, IPUMS + path, headers={"Authorization": key},
                        params=params, timeout=120, **kw)
    r.raise_for_status()
    return r.json()


def ipums_paged(path, key):
    out, page = [], 1
    while True:
        j = ipums("GET", path, key, params={"pageNumber": page, "pageSize": 2500})
        out += j["data"]
        if not (j.get("links") or {}).get("nextPage"):
            return out
        page += 1


def discover_nhgis(key):
    """Find, for each decennial year, a tract-level total-population table and
    the matching tract shapefile, using the IPUMS metadata API."""
    datasets = ipums_paged("/metadata/datasets", key)
    shapefiles = ipums_paged("/metadata/shapefiles", key)
    plan = {}
    for year in DECENNIAL_YEARS:
        choice = None
        for ds in (d for d in datasets if d["name"].startswith(f"{year}_")):
            meta = ipums("GET", f"/metadata/datasets/{ds['name']}", key)
            if not any(g["name"] == "tract" for g in meta.get("geogLevels", [])):
                continue
            for t in meta.get("dataTables", []):
                if t["description"].strip().lower() == "total population":
                    choice = (ds["name"], t["name"], t["nhgisCode"])
                    break
            if choice:
                break
        if not choice:
            raise RuntimeError(f"No tract-level 'Total Population' table found for {year}.")
        shp = [s for s in shapefiles if str(s["year"]) == str(year)
               and s["geographicLevel"].lower() == "census tract"
               and s["extent"].lower() == "united states"]
        if not shp:
            raise RuntimeError(f"No NHGIS tract shapefile found for {year}.")
        shp.sort(key=lambda s: s["basis"])  # newest TIGER basis last
        plan[year] = {"dataset": choice[0], "table": choice[1], "code": choice[2],
                      "shapefile": shp[-1]["name"]}
        print(f"  {year}: {plan[year]}")
    return plan


def request_nhgis_extract(key):
    dest = RAW / "nhgis"
    plan_path = dest / "plan.json"
    if plan_path.exists() and list(dest.glob("*_csv.zip")) and list(dest.glob("*_shape.zip")):
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    plan = discover_nhgis(key)
    plan_path.write_text(json.dumps(plan, indent=2))
    body = {
        "datasets": {p["dataset"]: {"dataTables": [p["table"]], "geogLevels": ["tract"]}
                     for p in plan.values()},
        "shapefiles": [p["shapefile"] for p in plan.values()],
        "dataFormat": "csv_header",
        "breakdownAndDataTypeLayout": "single_file",
        "description": "Manhattan tract population 1950-2000",
    }
    number = ipums("POST", "/extracts", key, json=body)["number"]
    print(f"  submitted NHGIS extract #{number}; waiting for IPUMS to build it...")
    while True:
        ext = ipums("GET", f"/extracts/{number}", key)
        if ext["status"] == "completed":
            break
        if ext["status"] == "failed":
            raise RuntimeError(f"NHGIS extract failed: {ext.get('errors')}")
        time.sleep(20)
    links = ext["downloadLinks"]
    download(links["tableData"]["url"], dest / f"nhgis{number:04d}_csv.zip", {"Authorization": key})
    download(links["gisData"]["url"], dest / f"nhgis{number:04d}_shape.zip", {"Authorization": key})
    return dest


def _pop_column(df, code=None):
    if code and f"{code}001" in df:
        return f"{code}001"
    geo_cols = {"GISJOIN", "YEAR", "STATE", "STATEA", "COUNTY", "COUNTYA", "TRACTA",
                "NAME", "AREANAME", "PRETRACTA", "POSTTRCTA", "CTY_SUBA", "PLACEA", "SMSAA"}
    candidates = [c for c in df.columns if c not in geo_cols and c.endswith("001")]
    if len(candidates) != 1:
        raise RuntimeError(f"Can't identify the population column among {list(df.columns)}")
    return candidates[0]


def nhgis_year(nhgis_dir, year, plan):
    """Return a Manhattan GeoDataFrame (GISJOIN, pop, geometry) for one decennial year."""
    csv_zip = next(Path(nhgis_dir).glob("*_csv.zip"))
    shp_zip = next(Path(nhgis_dir).glob("*_shape.zip"))
    with zipfile.ZipFile(csv_zip) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv") and f"_{year}_tract" in n)
        with z.open(name) as f:
            df = pd.read_csv(f, dtype=str, skiprows=[1], encoding="latin-1")
    df = df[df["GISJOIN"].str.startswith(NHGIS_PREFIX)].copy()
    df["pop"] = pd.to_numeric(df[_pop_column(df, plan.get(year, {}).get("code"))])
    with zipfile.ZipFile(shp_zip) as z:
        inner = next(n for n in z.namelist() if n.endswith(".zip") and f"tract_{year}" in n)
    shp = gpd.read_file(f"zip://{shp_zip}!{inner}")
    shp = shp[shp["GISJOIN"].str.startswith(NHGIS_PREFIX)].to_crs(MAP_CRS)
    return shp[["GISJOIN", "geometry"]].merge(df[["GISJOIN", "pop"]], on="GISJOIN", how="left")


# ------------------------------------------------------------------- output

def finish(gdf, manhattan_land):
    gdf = gpd.clip(gdf, manhattan_land)
    gdf = gdf[~gdf.geometry.is_empty].copy()
    gdf["pop"] = gdf["pop"].fillna(0)
    gdf["area_sqmi"] = gdf.geometry.area / SQFT_PER_SQMI
    gdf["density"] = gdf["pop"] / gdf["area_sqmi"]
    return gdf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nhgis-dir", help="Folder with a manually downloaded NHGIS extract "
                    "(the *_csv.zip and *_shape.zip files)")
    ap.add_argument("--skip-decennial", action="store_true", help="Only fetch ACS years")
    args = ap.parse_args()
    PROCESSED.mkdir(parents=True, exist_ok=True)

    print("Finding latest ACS 5-year release...")
    latest = latest_acs_year()
    acs_years = sorted(set(ACS_END_YEARS + [latest]))
    print(f"  latest is {latest - 4}-{latest}")

    counties = county_shapes(latest)
    manhattan_land = counties[counties["GEOID"] == STATE_FIPS + COUNTY_FIPS][["geometry"]]
    context = counties[counties["GEOID"].isin(CONTEXT_COUNTIES)].copy()
    context["label"] = context["GEOID"].map(CONTEXT_COUNTIES)
    context[["GEOID", "label", "geometry"]].to_file(PROCESSED / "context.gpkg")
    manhattan_land.to_file(PROCESSED / "manhattan_land.gpkg")

    try:
        nta = gpd.read_file(download(NTA_URL, RAW / "nyc" / "nta2020.geojson")).to_crs(MAP_CRS)
        name_col = next(c for c in ("ntaname", "NTAName", "nta_name") if c in nta)
        boro = next(c for c in ("boroname", "BoroName") if c in nta)
        nta = nta[nta[boro] == "Manhattan"].rename(columns={name_col: "name"})
        nta[["name", "geometry"]].to_file(PROCESSED / "neighborhoods.gpkg")
    except Exception as e:  # labels still render from config without the outlines
        print(f"  warning: neighborhood boundaries unavailable ({e})")

    frames = []
    if not args.skip_decennial:
        nhgis_dir = args.nhgis_dir
        if not nhgis_dir:
            key = os.environ.get("IPUMS_API_KEY")
            if not key:
                sys.exit("1950-2000 tract data needs NHGIS: set IPUMS_API_KEY or pass --nhgis-dir.")
            nhgis_dir = request_nhgis_extract(key)
        plan_path = Path(nhgis_dir) / "plan.json"
        plan = {int(k): v for k, v in json.loads(plan_path.read_text()).items()} if plan_path.exists() else {}
        for year in DECENNIAL_YEARS:
            print(f"Decennial {year}...")
            gdf = finish(nhgis_year(nhgis_dir, year, plan), manhattan_land)
            gdf.rename(columns={"GISJOIN": "tract_id"}).to_file(PROCESSED / f"tracts_{year}.gpkg")
            frames.append({"year": year, "label": str(year), "source": "Decennial Census",
                           "total": int(gdf["pop"].sum()), "tracts": len(gdf)})

    for year in acs_years:
        print(f"ACS {year - 4}-{year}...")
        gdf = tiger_tracts(year).merge(acs_population(year), on="GEOID", how="left")
        gdf = finish(gdf, manhattan_land)
        gdf.rename(columns={"GEOID": "tract_id"}).to_file(PROCESSED / f"tracts_{year}.gpkg")
        frames.append({"year": year, "label": f"{year - 4}–{str(year)[2:]}",
                       "source": "ACS 5-year estimate",
                       "total": int(gdf["pop"].sum()), "tracts": len(gdf)})

    (PROCESSED / "frames.json").write_text(json.dumps(frames, indent=2, ensure_ascii=False))
    pd.DataFrame(frames).to_csv(PROCESSED / "manhattan_totals.csv", index=False)
    print("\nManhattan totals:")
    for f in frames:
        print(f"  {f['label']:>8}  {f['total']:>10,}  ({f['tracts']} tracts, {f['source']})")


if __name__ == "__main__":
    main()
