# Geospatial map examples for real estate

Six original, slide-ready map types built in R from public data. Each PNG is
16:9 at 2400×1350 pixels and carries a footer with its data source, year,
geography and method. Open `index.html` for a contact sheet of all six.

| # | Map type | Place | Data | Script |
|---|---|---|---|---|
| 1 | Choropleth | Twin Cities (7 counties), tracts | ACS 2020–2024 median household income | `R/01_choropleth.R` |
| 2 | Proportional symbols | Twin Cities (7 counties), tracts | ACS 2020–2024 renter households | `R/02_proportional_symbols.R` |
| 3 | Dot density | Hennepin County, MN, tracts | 2020 Census race and ethnicity, 1 dot = 100 people | `R/03_dot_density.R` |
| 4 | Heat map | Minneapolis | **Synthetic** point events, kernel density | `R/04_heat_map.R` |
| 5 | Isochrones | Mall of America, Bloomington, MN | 5/10/15-min drive times + ACS population and households | `R/05_isochrones.R` |
| 6 | Flow map | Into the Phoenix metro | ACS 2016–2020 metro-to-metro migration flows | `R/06_flow_map.R` |

Outputs are in `output/`; citations are in `sources.md`.

## Notes on methods

- **Heat map (4)** uses simulated points, labeled as synthetic on the map. It is
  a kernel-density surface (`MASS::kde2d`), the static equivalent of
  `mapgl::add_heatmap_layer()`. mapgl draws an interactive WebGL map in a
  browser, which does not export to PNG reliably in a headless session.
- **Isochrones (5)** use `mapboxapi::mb_isochrone()` when a Mapbox token is
  available. Without one, the script falls back to the public Valhalla server
  (OpenStreetMap data), and the footer names the engine used. The committed PNG
  was made with Valhalla. Population reached is apportioned from tracts by area.
- **Flow map (6)** draws arcs with `ggplot2::geom_curve`, a reproducible
  static alternative to `mapdeck::add_arc()`, which needs a Mapbox token and a
  browser. 2016–2020 is the latest ACS release with metro-level flows.
- ACS numbers are survey **estimates** with margins of error. Only map 3 uses
  official decennial census counts.

## Setup

### 1. Install R and packages

R 4.3 or later. In R:

```r
install.packages(c("tidycensus", "tigris", "sf", "ggplot2", "ggspatial", "ggrepel",
                   "patchwork", "dplyr", "tidyr", "scales", "ragg", "httr",
                   "jsonlite", "MASS", "mapboxapi"))
```

`sf` needs the GDAL, GEOS and PROJ system libraries. On macOS and Windows the
CRAN binaries include them. On Ubuntu the quickest route is the r2u binary
repository (<https://eddelbuettel.github.io/r2u/>), then
`apt install r-cran-tidycensus r-cran-sf r-cran-ggspatial ...`.

Fonts: the maps use Liberation Sans. If it isn't installed, change `FONT` in
`R/00_common.R` (e.g. to "Arial").

### 2. Get a Census API key (required)

1. Request a free key at <https://api.census.gov/data/key_signup.html>. It arrives by email.
2. Store it in an environment variable. Never paste it into a script.
   - In R, once: `tidycensus::census_api_key("YOUR_KEY", install = TRUE)`, which writes
     `CENSUS_API_KEY` to your `~/.Renviron`. Then restart R.
   - Or in a shell: `export CENSUS_API_KEY=YOUR_KEY`

### 3. Get a Mapbox token (optional, for map 5)

1. Create a free account at <https://account.mapbox.com/> and copy the default public token.
2. Store it as `MAPBOX_PUBLIC_TOKEN`:
   - In R: `mapboxapi::mb_access_token("pk.YOUR_TOKEN", install = TRUE)`, then restart R.
   - Or in a shell: `export MAPBOX_PUBLIC_TOKEN=pk.YOUR_TOKEN`
3. Delete `data/isochrones_moa.rds` if it exists, so the isochrones are re-requested from Mapbox.

Without a token, map 5 still runs using the Valhalla fallback.

## Run

From this folder:

```bash
Rscript run_all.R                 # all six maps, then checks every PNG is >= 2400x1350
Rscript R/03_dot_density.R        # or any single map
```

Downloaded data is cached in `data/` (not committed). Delete it to fetch fresh
data. tigris also caches shapefiles in its own cache folder.
