# 2. Proportional-symbol map: renter-occupied households by census tract,
#    seven-county Twin Cities region, latest ACS 5-year estimates.
#
# Data
#   ACS 5-year table B25003 (tenure), B25003_003 = renter-occupied housing
#   units (one per renter household), via tidycensus::get_acs(geometry = TRUE).
#   API: https://api.census.gov/data/2024/acs/acs5
#   Geometry: TIGER/Line cartographic tracts (tigris), area water (tigris::area_water)
#
# Why symbols: renter households are an absolute count. Shading tract areas by
# a count would make big, sparsely settled tracts look important, so each
# tract gets a circle whose AREA is proportional to its count
# (ggplot2::scale_size_area), placed with sf::st_point_on_surface().

source("R/00_common.R")

renters <- cached("acs_renters_tracts", {
  get_acs(geography = "tract", variables = c(renters = "B25003_003"),
          state = "MN", county = TC_COUNTIES, year = ACS_YEAR,
          survey = "acs5", geometry = TRUE, cb = TRUE) |>
    st_transform(CRS_MN)
})

counties <- tc_counties()
water <- tc_water()
points <- renters |>
  filter(estimate > 0) |>
  st_point_on_surface() |>
  arrange(desc(estimate))              # draw big circles first, small on top
total <- sum(renters$estimate, na.rm = TRUE)

p <- ggplot() +
  geom_sf(data = renters, fill = "#f7f7f5", colour = "#dcdbd6", linewidth = 0.1) +
  geom_sf(data = water, fill = WATER, colour = NA) +
  geom_sf(data = counties, fill = NA, colour = INK_2, linewidth = 0.35) +
  geom_sf(data = points, aes(size = estimate), shape = 21, fill = alpha(ACCENT, 0.55),
          colour = "white", stroke = 0.25) +
  halo_label(counties, aes(label = NAME), fontface = "bold") +
  scale_size_area(max_size = 11, breaks = c(250, 1000, 2000, 4000),
                  labels = comma, name = "Renter households\nper tract") +
  guides(size = guide_legend(override.aes = list(fill = alpha(ACCENT, 0.55), colour = INK_2))) +
  scale_bar() +
  fit_view(counties, ratio = 1.75) +
  labs(
    title = "Renter households by census tract, Twin Cities region",
    subtitle = paste0(
      "Circle area is proportional to each tract's count of renter households (",
      comma(total), " in total). Proportional symbols suit absolute counts:\n",
      "shading whole tracts by a count would exaggerate large rural tracts, so ",
      "use a choropleth only for rates or medians."),
    caption = footer(
      paste0("U.S. Census Bureau, ", ACS_LABEL, ", table B25003, renter-occupied housing ",
             "units (tidycensus::get_acs); TIGER/Line cartographic tracts and area water ",
             "(tigris). ACS figures are survey estimates with margins of error."),
      sprintf("%d–%d", ACS_YEAR - 4, ACS_YEAR),
      "Census tracts, seven-county Twin Cities region",
      "Proportional symbols (circle area ∝ count) at tract interior points, NAD83 / UTM 15N"
    )
  ) +
  theme_map()

save_map(p, "02_proportional_symbols_renters.png")
