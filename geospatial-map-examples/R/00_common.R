# Shared settings for the six geospatial map examples.
#
# Packages: tidycensus (Census API), tigris (TIGER/Line geometry), sf,
# ggplot2, ggspatial (scale bars), ragg (PNG device), dplyr, scales.
# Census API key: read from the CENSUS_API_KEY environment variable by
# tidycensus; never write it into a script.

suppressPackageStartupMessages({
  library(tidycensus)
  library(tigris)
  library(sf)
  library(dplyr)
  library(ggplot2)
  library(ggspatial)
  library(scales)
})

# UTF-8 so en dashes and the proportional sign survive text wrapping.
invisible(Sys.setlocale("LC_CTYPE", "C.UTF-8"))
options(tigris_use_cache = TRUE, tigris_class = "sf", timeout = 600)
sf_use_s2(FALSE)

if (Sys.getenv("CENSUS_API_KEY") == "") {
  stop("Set CENSUS_API_KEY first (free key: https://api.census.gov/data/key_signup.html).")
}

# Paths ---------------------------------------------------------------------
# Scripts are run from the geospatial-map-examples folder (see README).
ROOT <- getwd()
if (!file.exists(file.path(ROOT, "R", "00_common.R"))) {
  stop("Run the scripts from the geospatial-map-examples folder, e.g. Rscript R/01_choropleth.R")
}
OUT_DIR <- file.path(ROOT, "output")
DATA_DIR <- file.path(ROOT, "data")
dir.create(OUT_DIR, showWarnings = FALSE)
dir.create(DATA_DIR, showWarnings = FALSE)

# Study area ----------------------------------------------------------------
# The seven-county Twin Cities region (Metropolitan Council planning area).
ACS_YEAR <- 2024                        # latest ACS 5-year release: 2020-2024
ACS_LABEL <- sprintf("ACS %d-%d 5-year estimates", ACS_YEAR - 4, ACS_YEAR)
TC_COUNTIES <- c("Anoka", "Carver", "Dakota", "Hennepin", "Ramsey", "Scott", "Washington")
CRS_MN <- 26915                         # NAD83 / UTM zone 15N (meters)

# Design tokens -------------------------------------------------------------
FONT <- "Liberation Sans"
INK <- "#1f1f1d"
INK_2 <- "#52514e"
INK_MUTED <- "#8a8984"
LINE <- "#b9b8b2"
WATER <- "#e3ebf2"
NO_DATA <- "#efeeea"
SEQ_BLUE <- c("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
ACCENT <- "#2a78d6"

theme_map <- function(base_size = 18) {
  theme_void(base_size = base_size, base_family = FONT) +
    theme(
      plot.background = element_rect(fill = "white", colour = NA),
      panel.background = element_rect(fill = "white", colour = NA),
      plot.title = element_text(face = "bold", size = rel(1.6), colour = INK,
                                margin = margin(b = 6)),
      plot.subtitle = element_text(size = rel(0.95), colour = INK_2, lineheight = 1.15,
                                   margin = margin(b = 14)),
      plot.caption = element_text(size = rel(0.62), colour = INK_2, hjust = 0,
                                  lineheight = 1.25, margin = margin(t = 14)),
      plot.title.position = "plot",
      plot.caption.position = "plot",
      legend.title = element_text(size = rel(0.8), face = "bold", colour = INK,
                                  margin = margin(b = 6)),
      legend.text = element_text(size = rel(0.72), colour = INK_2),
      legend.position = "right",
      legend.justification = c(0, 0.5),
      plot.margin = margin(28, 44, 22, 44)
    )
}

# Footer: data source, year, geography and method, as required on every map.
footer <- function(source, year, geography, method, width = 190) {
  wrap <- function(x) paste(strwrap(x, width = width), collapse = "\n")
  paste0(wrap(paste0("Source: ", source)), "\n",
         wrap(paste0("Year: ", year, "   |   Geography: ", geography, "   |   Method: ", method)))
}

# Expand an sf layer's bounding box to a target width:height ratio so the map
# fills the 16:9 slide instead of shrinking the whole layout toward the center.
fit_view <- function(x, ratio = 1.9, pad = 0.03) {
  bb <- st_bbox(x)
  w <- bb[["xmax"]] - bb[["xmin"]]
  h <- bb[["ymax"]] - bb[["ymin"]]
  cx <- (bb[["xmin"]] + bb[["xmax"]]) / 2
  cy <- (bb[["ymin"]] + bb[["ymax"]]) / 2
  h <- h * (1 + pad)
  w <- max(w * (1 + pad), h * ratio)
  h <- max(h, w / ratio)
  coord_sf(xlim = cx + c(-w, w) / 2, ylim = cy + c(-h, h) / 2, expand = FALSE,
           datum = NA, crs = st_crs(x))
}

# Map labels with a white halo so they read over any fill.
halo_label <- function(data, mapping, size = 4.2, ...) {
  geom_sf_label(data = data, mapping = mapping, family = FONT, size = size, colour = INK,
                fill = alpha("white", 0.75), linewidth = 0, label.r = unit(0.1, "lines"),
                label.padding = unit(0.12, "lines"), ...)
}

scale_bar <- function(location = "bl") {
  annotation_scale(location = location, unit_category = "imperial", style = "ticks",
                   line_col = INK_2, text_col = INK_2, text_family = FONT,
                   text_cex = 1.1, width_hint = 0.2, pad_x = unit(0.4, "cm"),
                   pad_y = unit(0.4, "cm"))
}

save_map <- function(plot, filename) {
  path <- file.path(OUT_DIR, filename)
  # 16 x 9 in at 150 dpi = 2400 x 1350 px.
  ggsave(path, plot, width = 16, height = 9, dpi = 150, device = ragg::agg_png, bg = "white")
  message("wrote ", path)
  invisible(path)
}

# Cached helpers --------------------------------------------------------------
cached <- function(name, expr) {
  path <- file.path(DATA_DIR, paste0(name, ".rds"))
  if (file.exists(path)) return(readRDS(path))
  value <- force(expr)
  saveRDS(value, path)
  value
}

# TIGER/Line cartographic county outlines for the Twin Cities region.
# Source: https://www2.census.gov/geo/tiger/GENZ2024/shp/ via tigris::counties()
tc_counties <- function() {
  cached("tc_counties", {
    counties("MN", cb = TRUE, year = ACS_YEAR) |>
      filter(NAME %in% TC_COUNTIES) |>
      st_transform(CRS_MN)
  })
}

# TIGER/Line area-water polygons (lakes, rivers), largest features only.
# Source: https://www2.census.gov/geo/tiger/TIGER2024/AREAWATER/ via tigris::area_water()
tc_water <- function(counties = TC_COUNTIES, min_km2 = 0.25) {
  cached(paste0("water_", paste(substr(counties, 1, 3), collapse = "")), {
    lapply(counties, \(cty) area_water("MN", cty, year = ACS_YEAR)) |>
      bind_rows() |>
      st_transform(CRS_MN) |>
      mutate(km2 = as.numeric(st_area(geometry)) / 1e6) |>
      filter(km2 >= min_km2)
  })
}
