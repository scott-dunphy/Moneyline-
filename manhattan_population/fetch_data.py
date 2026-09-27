"""Download and prepare Manhattan census-tract population, 1950 -> latest ACS.

Sources
  1990-2000  Decennial census straight from the Census Bureau (no IPUMS
             needed): the 1990 PL 94-171 file, the 2000 SF1 via the API, and
             the Bureau's 1990/2000 cartographic tract boundaries.
  1950-2000  With --start 1950: decennial tract counts + historical tract
             boundaries from IPUMS NHGIS (the ACS does not exist before 2005).
             Needs a free IPUMS account registered for NHGIS: set
             IPUMS_API_KEY, or download the extract yourself and pass
             --nhgis-dir.
  2010-now   ACS 5-year estimates (table B01003, total population) from the
             Census Bureau API, on matching-vintage TIGER cartographic tracts.
  Context    TIGER cartographic county boundaries (shoreline-clipped) and
             NYC Planning's 2020 Neighborhood Tabulation Areas.

Every year's tracts are clipped to the same Manhattan shoreline so land area,
and therefore density, is measured consistently across vintages.

Usage
  python fetch_data.py                       # 1990 -> today, Census Bureau only
  python fetch_data.py --start 1950          # 1950 -> today (needs IPUMS_API_KEY)
  python fetch_data.py --start 1950 --nhgis-dir ~/Downloads/nhgis_extract
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
PL1990_URL = "https://www2.census.gov/census_1990/1990_PL94-171/CD7%20-%20CA%20NY/pl9417ny.dbf"
DEC2000_API = "https://api.census.gov/data/2000/dec/sf1"
NTA_URL = "https://data.cityofnewyork.us/api/geospatial/9nt8-h7nd?method=export&format=GeoJSON"

session = requests.Session()
session.mount("https://", requests.adapters.HTTPAdapter(max_retries=requests.adapters.Retry(
    total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=None)))

# Tract-level total-population table for each census, checked against the
# IPUMS metadata API. 1970 publishes no single total at tract level, so its
# Sex-by-Race table is summed.
NHGIS_TABLES = {
    1950: ("1950_tPH_Major", "NT1", "BZ8"),   # Total Population
    1960: ("1960_tPH", "NTSUP2", "CA4"),      # Total Persons
    1970: ("1970_Cnt2", "NT1", "CEB"),        # Sex by Race (summed)
    1980: ("1980_STF1", "NT1A", "C7L"),       # Persons
    1990: ("1990_STF1", "NP1", "ET1"),        # Persons
    2000: ("2000_SF1a", "NP001A", "FL5"),     # Total Population
}


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


def remove_water(gdf, year):
    """Cartographic county outlines run to the state line mid-Hudson; cut out
    TIGER area-water polygons so only land remains."""
    out = []
    for geoid, row in gdf.set_index("GEOID").iterrows():
        path = download(f"{TIGER}/TIGER{year}/AREAWATER/tl_{year}_{geoid}_areawater.zip",
                        RAW / "tiger" / f"tl_{year}_{geoid}_areawater.zip")
        water = gpd.read_file(f"zip://{path}").to_crs(MAP_CRS).union_all()
        out.append({**row.to_dict(), "GEOID": geoid, "geometry": row.geometry.difference(water)})
    return gpd.GeoDataFrame(out, crs=MAP_CRS)


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


def legacy_tracts(year):
    """Census Bureau cartographic tracts for 1990 (NAD27) or 2000 (NAD83)."""
    yy = str(year)[2:]
    url = f"{TIGER}/PREVGENZ/tr/tr{yy}shp/tr{STATE_FIPS}_d{yy}_shp.zip"
    gdf = gpd.read_file(f"zip://{download(url, RAW / 'tiger' / Path(url).name)}")
    gdf = gdf.set_crs("EPSG:4267" if year == 1990 else "EPSG:4269")
    if year == 1990:
        gdf = gdf[gdf["CO"] == COUNTY_FIPS]
        code = gdf["TRACTBASE"] + gdf["TRACTSUF"].fillna("00")
    else:
        gdf = gdf[gdf["COUNTY"] == COUNTY_FIPS]
        code = gdf["TRACT"].str.ljust(6, "0")
    gdf = gdf.assign(GEOID=STATE_FIPS + COUNTY_FIPS + code)
    return gdf.dissolve("GEOID").reset_index()[["GEOID", "geometry"]].to_crs(MAP_CRS)


def census_population(year):
    if year == 1990:
        from dbfread import DBF
        path = download(PL1990_URL, RAW / "census1990" / "pl9417ny.dbf")
        rows = [(r["TRACTBNA"], r["P001_0001"]) for r in DBF(path, load=False)
                if r["SUMLEV"] == "140" and r["STATEFP"] == STATE_FIPS and r["CNTY"] == COUNTY_FIPS]
        df = pd.DataFrame(rows, columns=["tract", "pop"])
    else:
        key = os.environ.get("CENSUS_API_KEY")
        if not key:
            raise RuntimeError("Census 2000 needs CENSUS_API_KEY.")
        r = session.get(DEC2000_API, params={"get": "P001001", "for": "tract:*", "key": key,
                                             "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}"}, timeout=120)
        r.raise_for_status()
        rows = r.json()
        df = pd.DataFrame(rows[1:], columns=rows[0]).rename(columns={"P001001": "pop"})
    df["GEOID"] = STATE_FIPS + COUNTY_FIPS + df["tract"].str.ljust(6, "0")
    df["pop"] = pd.to_numeric(df["pop"])
    return df[["GEOID", "pop"]]


# ---------------------------------------------------------------------- ACS

def summary_file_url(year):
    # Table-based ACS summary files (2021 onward) need no API key.
    return (f"https://www2.census.gov/programs-surveys/acs/summary_file/{year}/"
            f"table-based-SF/data/5YRData/acsdt5y{year}-b01003.dat")


def latest_acs_year():
    for year in range(dt.date.today().year, 2020, -1):
        if session.head(summary_file_url(year), timeout=30).status_code == 200:
            return year
    raise RuntimeError("Could not find an ACS 5-year release on www2.census.gov.")


def acs_population(year):
    if year >= 2021:
        path = download(summary_file_url(year), RAW / "acs" / f"acsdt5y{year}-b01003.dat")
        df = pd.read_csv(path, sep="|", dtype=str)
        df = df[df["GEO_ID"].str.startswith(f"1400000US{STATE_FIPS}{COUNTY_FIPS}")].copy()
        df["GEOID"] = df["GEO_ID"].str[-11:]
        df["pop"] = pd.to_numeric(df["B01003_E001"]).clip(lower=0)
        df["moe"] = pd.to_numeric(df["B01003_M001"], errors="coerce")
        return df[["GEOID", "pop", "moe"]]
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise RuntimeError(f"ACS {year} needs the Census API: set CENSUS_API_KEY "
                           "(free at https://api.census.gov/data/key_signup.html).")
    params = {"get": "B01003_001E,B01003_001M", "for": "tract:*",
              "in": f"state:{STATE_FIPS} county:{COUNTY_FIPS}", "key": key}
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
    """Pair each census's population table with the newest-basis NHGIS tract shapefile."""
    shapefiles = ipums_paged("/metadata/shapefiles", key)
    plan = {}
    for year in DECENNIAL_YEARS:
        dataset, table, code = NHGIS_TABLES[year]
        shp = sorted((s for s in shapefiles if str(s["year"]) == str(year)
                      and s["geographicLevel"].lower() == "census tract"
                      and s["extent"].lower() == "united states"), key=lambda s: s["basis"])
        if not shp:
            raise RuntimeError(f"No NHGIS tract shapefile found for {year}.")
        plan[year] = {"dataset": dataset, "table": table, "code": code, "shapefile": shp[-1]["name"]}
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


def _population(df, code):
    cols = [c for c in df.columns if c.startswith(code)]
    if not cols:
        raise RuntimeError(f"No {code}* columns among {list(df.columns)}")
    return df[cols].apply(pd.to_numeric).sum(axis=1)


def nhgis_year(nhgis_dir, year, plan):
    """Return a Manhattan GeoDataFrame (GISJOIN, pop, geometry) for one decennial year."""
    csv_zip = next(Path(nhgis_dir).glob("*_csv.zip"))
    shp_zip = next(Path(nhgis_dir).glob("*_shape.zip"))
    with zipfile.ZipFile(csv_zip) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv") and f"_{year}_tract" in n)
        with z.open(name) as f:
            df = pd.read_csv(f, dtype=str, skiprows=[1], encoding="latin-1")
    df = df[df["GISJOIN"].str.startswith(NHGIS_PREFIX)].copy()
    df["pop"] = _population(df, plan.get(year, {}).get("code") or NHGIS_TABLES[year][2])
    with zipfile.ZipFile(shp_zip) as z:
        inner = next(n for n in z.namelist() if n.endswith(".zip") and f"tract_{year}" in n)
    shp = gpd.read_file(f"zip://{shp_zip}!{inner}")
    shp = shp[shp["GISJOIN"].str.startswith(NHGIS_PREFIX)].to_crs(MAP_CRS)
    return shp[["GISJOIN", "geometry"]].merge(df[["GISJOIN", "pop"]], on="GISJOIN", how="left")


# ------------------------------------------------------------------- output

def finish(gdf, manhattan_land):
    gdf = gpd.clip(gdf, manhattan_land)
    gdf = gdf[~gdf.geometry.is_empty].copy()
    # Drop slivers where generalized tract lines overlap the detailed shoreline,
    # keeping each tract's largest piece.
    parts = gdf.explode(index_parts=False).reset_index(drop=True)
    parts["_a"] = parts.geometry.area
    id_col = gdf.columns[0]
    keep = (parts["_a"] >= 60_000) | (parts["_a"] == parts.groupby(id_col)["_a"].transform("max"))
    gdf = parts[keep].dissolve(id_col, aggfunc="first").reset_index().drop(columns="_a")
    gdf["pop"] = gdf["pop"].fillna(0)
    gdf["area_sqmi"] = gdf.geometry.area / SQFT_PER_SQMI
    gdf["density"] = gdf["pop"] / gdf["area_sqmi"]
    return gdf


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nhgis-dir", help="Folder with a manually downloaded NHGIS extract "
                    "(the *_csv.zip and *_shape.zip files)")
    ap.add_argument("--start", type=int, choices=[1950, 1990], default=1990,
                    help="1990 uses Census Bureau files only; 1950 needs IPUMS NHGIS")
    ap.add_argument("--skip-decennial", action="store_true", help="Only fetch ACS years")
    args = ap.parse_args()
    PROCESSED.mkdir(parents=True, exist_ok=True)

    print("Finding latest ACS 5-year release...")
    latest = latest_acs_year()
    acs_years = sorted(set(ACS_END_YEARS + [latest]))
    print(f"  latest is {latest - 4}-{latest}")

    counties = county_shapes(latest)
    counties = remove_water(counties[counties["GEOID"].isin([STATE_FIPS + COUNTY_FIPS, *CONTEXT_COUNTIES])], latest)
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
    if not args.skip_decennial and args.start == 1990:
        for year in (1990, 2000):
            print(f"Decennial {year} (Census Bureau)...")
            pop = census_population(year)
            gdf = legacy_tracts(year).merge(pop, on="GEOID", how="left")
            unmatched = gdf["pop"].isna().sum()
            if unmatched:
                print(f"  warning: {unmatched} tract shapes had no population record")
            gdf = finish(gdf, manhattan_land)
            gdf.rename(columns={"GEOID": "tract_id"}).to_file(PROCESSED / f"tracts_{year}.gpkg")
            # Totals come from the population records so that people with no
            # mappable tract (1990 "crews of vessels", tract .99) still count.
            frames.append({"year": year, "label": str(year), "source": "Decennial Census",
                           "total": int(pop["pop"].sum()), "tracts": len(gdf)})
    elif not args.skip_decennial:
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
        try:
            pop = acs_population(year)
        except RuntimeError as e:
            print(f"  skipped: {e}")
            continue
        gdf = tiger_tracts(year).merge(pop, on="GEOID", how="left")
        gdf = finish(gdf, manhattan_land)
        gdf.rename(columns={"GEOID": "tract_id"}).to_file(PROCESSED / f"tracts_{year}.gpkg")
        frames.append({"year": year, "label": f"{year - 4}–{str(year)[2:]}",
                       "source": "ACS 5-year estimate",
                       "total": int(pop["pop"].sum()), "tracts": len(gdf)})

    (PROCESSED / "frames.json").write_text(json.dumps(frames, indent=2, ensure_ascii=False))
    pd.DataFrame(frames).to_csv(PROCESSED / "manhattan_totals.csv", index=False)
    print("\nManhattan totals:")
    for f in frames:
        print(f"  {f['label']:>8}  {f['total']:>10,}  ({f['tracts']} tracts, {f['source']})")


if __name__ == "__main__":
    main()
