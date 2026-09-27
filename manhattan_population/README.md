# Manhattan population by census tract, 1950 to today

An animated tract map of Manhattan's population density from the 1950
census through the latest ACS 5-year estimate, with neighborhood labels,
for web publication.

![Manhattan population animation](output/manhattan_population.gif)

## Data

| Years | Source | Boundaries |
|---|---|---|
| 1950, 1960, 1970, 1980, 1990, 2000 | Decennial census tract counts via [IPUMS NHGIS](https://www.nhgis.org) | NHGIS historical tract shapefiles |
| 2006–10, 2010–14, 2015–19, latest | ACS 5-year estimates, table B01003 (total population) | TIGER cartographic tracts of the matching vintage |

The ACS begins in 2005, so the earlier years have to come from the decennial
census. Each year is drawn on its own tract boundaries and clipped to the same
Manhattan shoreline. Tracts are colored by **people per square mile of land**,
which stays comparable even though the tract lines change. Tracts with fewer
than 100 residents (parks, rail yards and similar) are hatched.

## Run it

```bash
pip install -r requirements.txt
export CENSUS_API_KEY=...   # https://api.census.gov/data/key_signup.html
export IPUMS_API_KEY=...    # https://account.ipums.org/api_keys (account must be registered for NHGIS)
python fetch_data.py        # writes data/processed/
python make_gif.py          # writes output/manhattan_population.gif, .mp4, and a PNG per year
```

Instead of an IPUMS key, you can download the NHGIS extract yourself and run
`python fetch_data.py --nhgis-dir <folder with the *_csv.zip and *_shape.zip>`.

Timing flags: `--hold` (seconds per year, default 4.5), `--first-hold` (7),
`--last-hold` (9), `--fade` (crossfade seconds, 1.2).
