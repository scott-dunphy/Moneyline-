# 4. Heat map: kernel density of SYNTHETIC point events in Minneapolis.
#
# Data
#   Point events: simulated in R (set.seed below). They are NOT real
#   311 calls, permits or crimes; they exist only to demonstrate the method.
#   To use real events instead, replace simulate_events() with a public point
#   dataset, e.g. City of Minneapolis Open Data 311 requests
#   (https://opendata.minneapolismn.gov/, feature service "Public_311_2025"),
#   and cite it in the footer.
#   City boundary: TIGER/Line cartographic places (tigris::places),
#   https://www2.census.gov/geo/tiger/GENZ2024/shp/
#   Water: TIGER/Line AREAWATER (tigris::area_water); roads: TIGER/Line
#   primary and secondary roads (tigris::primary_secondary_roads)
#
# Method: a 2-D Gaussian kernel density (MASS::kde2d, 400 m standard
# deviation) scaled to events per square kilometer. This is the static
# equivalent of mapgl::add_heatmap_layer(); mapgl renders an interactive
# WebGL map in a browser, which cannot be exported to PNG reliably in a
# headless session, so the density surface is computed directly in R.
#
# A heat map of events shows EVENT density, not population, need or demand.

source("R/00_common.R")

SIGMA_M <- 400                            # kernel standard deviation, meters
N_EVENTS <- 20000

mpls <- cached("mpls_boundary", {
  places("MN", cb = TRUE, year = ACS_YEAR) |> filter(NAME == "Minneapolis") |> st_transform(CRS_MN)
})

# Simulated events: clusters around a few real activity centers plus a
# uniform background scattered across the city.
simulate_events <- function(boundary, n, seed = 42) {
  set.seed(seed)
  centers <- data.frame(
    lon = c(-93.2700, -93.2277, -93.2600, -93.2980, -93.2470, -93.2890),
    lat = c(44.9760, 44.9740, 44.9485, 44.9990, 44.9900, 44.9500),
    sd_m = c(700, 600, 900, 1100, 800, 700),
    weight = c(0.30, 0.12, 0.20, 0.15, 0.10, 0.13)
  )
  centers_xy <- st_coordinates(st_transform(st_as_sf(centers, coords = c("lon", "lat"), crs = 4326), CRS_MN))
  n_cluster <- round(n * 0.65)
  pick <- sample(nrow(centers), n_cluster, replace = TRUE, prob = centers$weight)
  clustered <- data.frame(x = rnorm(n_cluster, centers_xy[pick, 1], centers$sd_m[pick]),
                          y = rnorm(n_cluster, centers_xy[pick, 2], centers$sd_m[pick]))
  background <- as.data.frame(st_coordinates(st_sample(boundary, n - n_cluster)))
  names(background) <- c("x", "y")
  st_as_sf(rbind(clustered, background), coords = c("x", "y"), crs = CRS_MN) |>
    st_filter(boundary)
}

pts <- simulate_events(mpls, N_EVENTS)
xy <- st_coordinates(pts)

# Kernel density on a 250 x 250 grid; kde2d's h is 4 standard deviations.
bb <- st_bbox(mpls)
kd <- MASS::kde2d(xy[, 1], xy[, 2], h = rep(4 * SIGMA_M, 2), n = 250,
                  lims = c(bb[["xmin"]], bb[["xmax"]], bb[["ymin"]], bb[["ymax"]]))
grid <- expand.grid(x = kd$x, y = kd$y)
grid$density <- as.vector(kd$z) * nrow(xy) * 1e6          # events per km^2
inside <- st_intersects(st_as_sf(grid, coords = c("x", "y"), crs = CRS_MN), mpls, sparse = FALSE)[, 1]
grid <- grid[inside, ]

water <- tc_water("Hennepin", min_km2 = 0.05) |> st_intersection(st_geometry(mpls))
roads <- cached("roads_mn", primary_secondary_roads("MN", year = ACS_YEAR) |> st_transform(CRS_MN)) |>
  st_intersection(st_geometry(mpls))
roads <- roads[st_geometry_type(roads) %in% c("LINESTRING", "MULTILINESTRING"), ]  # drop edge touch points
places_lbl <- st_as_sf(data.frame(
  name = c("Downtown", "University of\nMinnesota", "Lake Street"),
  lon = c(-93.2700, -93.2277, -93.2600), lat = c(44.9760, 44.9740, 44.9485)),
  coords = c("lon", "lat"), crs = 4326) |> st_transform(CRS_MN)

HEAT <- c("#fff4ee", "#fde0d2", "#f9c2a6", "#f39a72", "#eb6834", "#c7501f", "#8f3510")

p <- ggplot() +
  geom_sf(data = mpls, fill = "#fbfbfa", colour = NA) +
  geom_raster(data = grid, aes(x, y, fill = density), interpolate = TRUE) +
  geom_sf(data = water, fill = WATER, colour = NA) +
  geom_sf(data = roads, colour = alpha(INK_2, 0.35), linewidth = 0.3) +
  geom_sf(data = mpls, fill = NA, colour = INK_2, linewidth = 0.4) +
  halo_label(places_lbl, aes(label = name), size = 4, lineheight = 0.9) +
  scale_fill_gradientn(colours = HEAT, labels = comma,
                       name = "Simulated events\nper km² (kernel estimate)") +
  guides(fill = guide_colourbar(barheight = unit(9, "cm"), barwidth = unit(0.6, "cm"))) +
  scale_bar() +
  fit_view(mpls, ratio = 1.75) +
  labs(
    title = "Heat map of point events in Minneapolis (synthetic data)",
    subtitle = sprintf(paste0(
      "Kernel density of %s SIMULATED point events, generated for teaching; they are not real 311 calls, ",
      "permits or crimes.\nA heat map like this shows EVENT density: where events occur, not where ",
      "people live or how much demand exists."), comma(nrow(pts))),
    caption = footer(
      paste0("Simulated point events generated in R (seed 42) for illustration only; ",
             "U.S. Census Bureau TIGER/Line places, area water and primary/secondary roads (tigris)."),
      sprintf("Synthetic events; TIGER/Line %d boundaries", ACS_YEAR),
      "City of Minneapolis (events clipped to city limits)",
      sprintf("Gaussian kernel density (MASS::kde2d), %d m standard deviation, 250 × 250 grid", SIGMA_M)
    )
  ) +
  theme_map()

save_map(p, "04_heat_map_synthetic_events.png")
