# 6. Flow map: largest U.S. origin metros for movers into the
#    Phoenix-Mesa-Chandler, AZ metro area, ACS 2016-2020 migration flows.
#
# Data
#   ACS 5-year metro-to-metro migration flows via
#   tidycensus::get_flows(geography = "metropolitan statistical area", msa = 38060, year = 2020).
#   API: https://api.census.gov/data/2020/acs/flows
#   2016-2020 is the latest ACS release with metro-level flows; later
#   releases publish county-level flows only.
#   Metro and state shapes: TIGER/Line cartographic CBSA and state boundaries
#   (tigris::core_based_statistical_areas, tigris::states), https://www2.census.gov/geo/tiger/GENZ2020/shp/
#
# Method: arcs from each origin metro's interior point to Phoenix, drawn with
# ggplot2::geom_curve; line width is proportional to estimated movers. This is
# a static, reproducible alternative to mapdeck::add_arc(), which renders an
# interactive Mapbox WebGL map that needs a token and cannot export a PNG
# reliably in a headless session.
#
# ACS flows count people aged 1+ who lived in the origin metro one year earlier,
# averaged over the 5-year period. They are estimates with margins of error.

source("R/00_common.R")
suppressPackageStartupMessages(library(ggrepel))

FLOW_YEAR <- 2020
DEST_GEOID <- "38060"
TOP_N <- 15
CRS_US <- 5070                            # NAD83 / Conus Albers

flows <- cached("flows_phoenix_2020", {
  get_flows(geography = "metropolitan statistical area", msa = DEST_GEOID, year = FLOW_YEAR)
})

metros <- cached("cbsa_2020", {
  core_based_statistical_areas(cb = TRUE, year = FLOW_YEAR) |> st_transform(CRS_US)
})
states48 <- cached("states48_2020", {
  states(cb = TRUE, year = FLOW_YEAR) |>
    filter(!STUSPS %in% c("AK", "HI", "PR", "VI", "GU", "MP", "AS")) |>
    st_transform(CRS_US)
})

anchor <- function(geoids) {
  pts <- metros |> filter(GEOID %in% geoids) |> st_point_on_surface()
  cbind(GEOID = pts$GEOID, as.data.frame(st_coordinates(pts)))
}

top <- flows |>
  filter(variable == "MOVEDIN", !is.na(GEOID2), GEOID2 != DEST_GEOID) |>
  arrange(desc(estimate)) |>
  inner_join(anchor(unique(flows$GEOID2)), by = c("GEOID2" = "GEOID")) |>
  filter(X > st_bbox(states48)[["xmin"]], X < st_bbox(states48)[["xmax"]]) |>  # lower 48 only
  slice_head(n = TOP_N) |>
  mutate(short = sub("^([^-,]+).*?, ([A-Z]{2}).*$", "\\1, \\2", FULL2_NAME),
         label = sprintf("%s  %s", short, comma(estimate)))
dest <- anchor(DEST_GEOID)
labels_df <- bind_rows(
  top |> st_drop_geometry() |> transmute(X, Y, label, face = "plain", size = 4.2),
  dest |> transmute(X, Y, label = "Phoenix metro", face = "bold", size = 5.4)
)
total_in <- flows |> filter(variable == "MOVEDIN", !is.na(GEOID2)) |> pull(estimate) |> sum()

p <- ggplot() +
  geom_sf(data = states48, fill = "#f3f2ef", colour = "white", linewidth = 0.5) +
  geom_curve(data = top, aes(x = X, y = Y, xend = dest$X, yend = dest$Y, linewidth = estimate),
             colour = alpha(ACCENT, 0.6), curvature = 0.28, lineend = "round") +
  geom_point(data = top, aes(X, Y), shape = 21, size = 2.6, fill = "white", colour = ACCENT, stroke = 1) +
  geom_point(data = dest, aes(X, Y), shape = 21, size = 6, fill = "#eb6834", colour = "white", stroke = 1.3) +
  # One repel layer for every label, including Phoenix, so none collide.
  geom_text_repel(data = labels_df, aes(X, Y, label = label, fontface = face, size = size),
                  family = FONT, colour = INK, bg.color = "white", bg.r = 0.12, seed = 7,
                  min.segment.length = 0.3, segment.colour = INK_MUTED, box.padding = 0.45,
                  max.overlaps = Inf, show.legend = FALSE) +
  scale_size_identity() +
  scale_linewidth(range = c(0.6, 7), limits = c(2000, 15000), breaks = c(2500, 5000, 10000, 15000),
                  labels = comma, name = "Estimated movers\nper year") +
  guides(linewidth = guide_legend(keywidth = unit(1.6, "cm"),
                                  override.aes = list(colour = alpha(ACCENT, 0.6)))) +
  scale_bar("bl") +
  coord_sf(crs = CRS_US, datum = NA, expand = FALSE,
           xlim = c(-2.45e6, 2.3e6), ylim = c(0.25e6, 3.25e6)) +
  labs(
    title = "Where new Phoenix-area residents moved from",
    subtitle = sprintf(paste0(
      "The %d largest U.S. origin metros for people moving into the Phoenix-Mesa-Chandler metro area, ",
      "ACS 2016–2020.\nArc width is proportional to estimated movers per year. All domestic ",
      "metro-to-metro inflows total about %s people a year."), TOP_N, comma(round(total_in, -3))),
    caption = footer(
      paste0("U.S. Census Bureau, American Community Survey 2016-2020 5-year migration flows ",
             "(tidycensus::get_flows); TIGER/Line cartographic CBSA and state boundaries (tigris). ",
             "Estimates of residents aged 1+ who lived in the origin metro one year earlier; ",
             "margins of error apply, largest for small flows."),
      "2016–2020 (latest ACS release with metro-level flows)",
      "Metropolitan statistical areas, contiguous United States",
      "Flow map; curved arcs (ggplot2::geom_curve) with width ∝ estimated movers, NAD83 / Conus Albers"
    )
  ) +
  theme_map()

save_map(p, "06_flow_map_phoenix_inmigration.png")
