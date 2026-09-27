# 5. Isochrone map: 5-, 10- and 15-minute drive times from Mall of America,
#    Bloomington, MN, with ACS population and households reached.
#
# Routing
#   Primary: mapboxapi::mb_isochrone(profile = "driving", time = c(5, 10, 15)),
#   Mapbox Isochrone API, https://docs.mapbox.com/api/navigation/isochrone/
#   The token is read ONLY from the MAPBOX_PUBLIC_TOKEN environment variable
#   (mapboxapi's default); it is never written in this script.
#   Fallback when no token is set: the public Valhalla routing server run by
#   FOSSGIS on OpenStreetMap data, https://valhalla1.openstreetmap.de/isochrone
#   (fair-use demo service). The footer names whichever engine produced the map.
#
# Census data
#   ACS 5-year tables B01003 (total population) and B11001 (households), tracts,
#   via tidycensus::get_acs(geometry = TRUE); https://api.census.gov/data/2024/acs/acs5
#   Counts reached are apportioned to each band by tract land area
#   (sf::st_interpolate_aw, extensive = TRUE), which assumes people are spread
#   evenly within each tract: an approximation, not a routed count.

source("R/00_common.R")
suppressPackageStartupMessages(library(patchwork))

SITE <- list(name = "Mall of America", lon = -93.2422, lat = 44.8549)
TIMES <- c(5, 10, 15)

isochrones <- cached("isochrones_moa", {
  token <- Sys.getenv("MAPBOX_PUBLIC_TOKEN")
  if (nzchar(token)) {
    iso <- mapboxapi::mb_isochrone(location = c(SITE$lon, SITE$lat), profile = "driving",
                                   time = TIMES)
    iso$engine <- "Mapbox Isochrone API (mapboxapi::mb_isochrone), driving profile"
  } else {
    body <- list(locations = list(list(lat = SITE$lat, lon = SITE$lon)), costing = "auto",
                 contours = lapply(TIMES, \(t) list(time = t)), polygons = TRUE)
    res <- httr::POST("https://valhalla1.openstreetmap.de/isochrone",
                      body = jsonlite::toJSON(body, auto_unbox = TRUE),
                      httr::content_type_json(), httr::user_agent("geospatial-map-examples (teaching)"))
    httr::stop_for_status(res)
    iso <- read_sf(httr::content(res, as = "text", encoding = "UTF-8"))
    iso$time <- iso$contour
    iso$engine <- "Valhalla isochrone service (FOSSGIS, OpenStreetMap data), auto costing; no Mapbox token was set"
  }
  st_make_valid(iso[, c("time", "engine")])
})
engine <- isochrones$engine[1]
iso <- isochrones |> st_transform(CRS_MN) |> arrange(time)

# Rings: 0-5, 5-10, 10-15 minutes.
rings <- lapply(seq_along(TIMES), function(i) {
  g <- st_geometry(iso)[i]
  if (i > 1) g <- st_difference(g, st_geometry(iso)[i - 1])
  st_sf(band = sprintf("%d–%d min", c(0, TIMES)[i], TIMES[i]), geometry = g)
}) |> bind_rows() |>
  mutate(band = factor(band, levels = band))

tracts <- cached("acs_pop_hh_tracts", {
  get_acs(geography = "tract", variables = c(pop = "B01003_001", hh = "B11001_001"),
          state = "MN", county = TC_COUNTIES, year = ACS_YEAR, survey = "acs5",
          geometry = TRUE, cb = TRUE, output = "wide") |>
    st_transform(CRS_MN) |>
    select(GEOID, pop = popE, hh = hhE)
})

reached <- st_interpolate_aw(tracts[c("pop", "hh")], iso, extensive = TRUE) |>
  st_drop_geometry() |>
  mutate(time = iso$time)

view <- st_buffer(st_as_sfc(st_bbox(iso)), 1500)
water <- tc_water(c("Hennepin", "Dakota", "Ramsey")) |> st_intersection(view)
roads <- cached("roads_mn", primary_secondary_roads("MN", year = ACS_YEAR) |> st_transform(CRS_MN)) |>
  st_intersection(view)
roads <- roads[st_geometry_type(roads) %in% c("LINESTRING", "MULTILINESTRING"), ]
tracts_view <- st_intersection(tracts, view)
site <- st_transform(st_as_sf(as.data.frame(SITE), coords = c("lon", "lat"), crs = 4326), CRS_MN)

BAND_FILL <- c("#256abf", "#6da7ec", "#cde2fb")

map <- ggplot() +
  geom_sf(data = tracts_view, fill = "white", colour = "#dcdbd6", linewidth = 0.15) +
  geom_sf(data = rings, aes(fill = band), colour = "white", linewidth = 0.4, alpha = 0.75) +
  geom_sf(data = water, fill = WATER, colour = NA) +
  geom_sf(data = roads, colour = alpha(INK_2, 0.45), linewidth = 0.35) +
  geom_sf(data = site, shape = 21, size = 5, fill = "#eb6834", colour = "white", stroke = 1.2) +
  halo_label(site, aes(label = name), fontface = "bold", nudge_y = -1300) +
  scale_fill_manual(values = BAND_FILL, name = "Drive time") +
  scale_bar() +
  fit_view(st_sf(geometry = view), ratio = 1.25, pad = 0) +
  theme_map() +
  theme(legend.position = "inside", legend.position.inside = c(0.02, 0.97),
        legend.justification = c(0, 1),
        legend.background = element_rect(fill = alpha("white", 0.85), colour = NA),
        plot.margin = margin(0, 10, 0, 0))

table_df <- reached |>
  transmute(label = sprintf("Within %d min", time), pop = comma(round(pop, -2)),
            hh = comma(round(hh, -2)))
tbl <- ggplot() +
  annotate("text", x = 0, y = 4.2, label = "Reached within each drive time",
           hjust = 0, family = FONT, fontface = "bold", size = 7, colour = INK) +
  annotate("text", x = c(0, 1.55, 2.55), y = 3.4, label = c("", "Population", "Households"),
           hjust = c(0, 1, 1), family = FONT, fontface = "bold", size = 5.2, colour = INK_2) +
  annotate("text", x = 0, y = 3 - seq_len(nrow(table_df)) * 0.75 + 0.35, label = table_df$label,
           hjust = 0, family = FONT, size = 5.6, colour = INK) +
  annotate("text", x = 1.55, y = 3 - seq_len(nrow(table_df)) * 0.75 + 0.35, label = table_df$pop,
           hjust = 1, family = FONT, size = 5.6, colour = INK) +
  annotate("text", x = 2.55, y = 3 - seq_len(nrow(table_df)) * 0.75 + 0.35, label = table_df$hh,
           hjust = 1, family = FONT, size = 5.6, colour = INK) +
  annotate("text", x = 0, y = -0.2, hjust = 0, vjust = 1, family = FONT, size = 4.2,
           colour = INK_2, lineheight = 1.2,
           label = paste0("Counts are cumulative and rounded to 100.\nTract totals are split ",
                          "across bands by land area,\nassuming residents are spread evenly ",
                          "within\neach tract. Drive times assume typical\ntraffic-free ",
                          "conditions for the routing engine.")) +
  coord_cartesian(xlim = c(0, 2.7), ylim = c(-1.6, 4.5), clip = "off") +
  theme_void()

p <- (map | tbl) + plot_layout(widths = c(2.2, 1)) +
  plot_annotation(
    title = "How many people live within a short drive of Mall of America?",
    subtitle = paste0("5-, 10- and 15-minute driving isochrones from Mall of America, Bloomington, MN, ",
                      "over census tracts.\nTrade-area analysis like this sizes the population and ",
                      "households a retail site can reach."),
    caption = footer(
      paste0("Isochrones: ", engine, ". U.S. Census Bureau, ", ACS_LABEL,
             ", tables B01003 and B11001 (tidycensus::get_acs); TIGER/Line tracts, area water and ",
             "roads (tigris). ACS figures are survey estimates with margins of error."),
      sprintf("ACS %d–%d; routing retrieved at run time", ACS_YEAR - 4, ACS_YEAR),
      "Census tracts in Hennepin, Dakota and nearby counties, MN",
      "Drive-time isochrones; area-weighted apportionment of tract counts (sf::st_interpolate_aw)"
    ),
    theme = theme_map()
  )

save_map(p, "05_isochrones_mall_of_america.png")
