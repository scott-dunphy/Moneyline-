"""Shared settings for the Manhattan tract-population GIF."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"
PROCESSED = HERE / "data" / "processed"
OUTPUT = HERE / "output"

STATE_FIPS = "36"   # New York
COUNTY_FIPS = "061"  # New York County = Manhattan
NHGIS_PREFIX = "G3600610"  # NHGIS GISJOIN prefix for Manhattan tracts
MAP_CRS = "EPSG:2263"  # NY State Plane Long Island (US ft)
SQFT_PER_SQMI = 5280 ** 2

# 1950-2000 come from the decennial census via NHGIS (the ACS starts in 2005).
DECENNIAL_YEARS = [1950, 1960, 1970, 1980, 1990, 2000]
# ACS 5-year estimates, keyed by final year; the latest release is appended
# automatically by fetch_data.py.
ACS_END_YEARS = [2010, 2014, 2019]

# Counties drawn in gray as geographic context around Manhattan.
CONTEXT_COUNTIES = {
    "36005": "THE BRONX",
    "36047": "BROOKLYN",
    "36081": "QUEENS",
    "34017": "NEW JERSEY",
    "34003": "NEW JERSEY",
}

# Density classes (people per square mile of land) -> sequential blue ramp.
DENSITY_BINS = [0, 10_000, 25_000, 50_000, 75_000, 100_000, 150_000, float("inf")]
DENSITY_LABELS = ["Under 10k", "10k–25k", "25k–50k", "50k–75k", "75k–100k", "100k–150k", "150k+"]
DENSITY_COLORS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
# Tracts below this population are parks, rail yards, etc.
MIN_RESIDENTIAL_POP = 100
NONRESIDENTIAL_COLOR = "#e3e1da"

WATER = "#fcfcfb"
CONTEXT_LAND = "#ecebe7"
INK = "#0b0b0b"
INK_2 = "#52514e"
INK_MUTED = "#8a8984"
HIGHLIGHT = "#2a78d6"
FONT = "Liberation Sans"

# Neighborhood label anchors (lon, lat). Kept fixed across every frame so
# readers can track a place through time.
NEIGHBORHOODS = [
    ("Inwood", -73.9215, 40.8680),
    ("Washington\nHeights", -73.9395, 40.8430),
    ("Hamilton\nHeights", -73.9500, 40.8245),
    ("Harlem", -73.9440, 40.8105),
    ("East\nHarlem", -73.9385, 40.7960),
    ("Morningside\nHeights", -73.9625, 40.8080),
    ("Upper\nWest Side", -73.9760, 40.7870),
    ("Upper\nEast Side", -73.9560, 40.7730),
    ("Central\nPark", -73.9655, 40.7815),
    ("Hell's\nKitchen", -73.9925, 40.7640),
    ("Midtown", -73.9800, 40.7560),
    ("Murray Hill", -73.9770, 40.7480),
    ("Chelsea", -74.0010, 40.7450),
    ("Gramercy", -73.9840, 40.7370),
    ("Greenwich\nVillage", -74.0010, 40.7330),
    ("East\nVillage", -73.9820, 40.7265),
    ("SoHo", -74.0015, 40.7235),
    ("Lower\nEast Side", -73.9840, 40.7150),
    ("Chinatown", -73.9975, 40.7160),
    ("Tribeca", -74.0090, 40.7180),
    ("Financial\nDistrict", -74.0095, 40.7070),
    ("Roosevelt\nIsland", -73.9505, 40.7615),
]
