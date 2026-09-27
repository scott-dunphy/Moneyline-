# 1. Choropleth map: median household income by census tract,
#    seven-county Twin Cities region, latest ACS 5-year estimates.
#
# Data
#   ACS 5-year detailed table B19013 (median household income), via
#   tidycensus::get_acs(geography = "tract", geometry = TRUE).
#   API: https://api.census.gov/data/2024/acs/acs5
#   Geometry: TIGER/Line cartographic boundary tracts,
#   https://www2.census.gov/geo/tiger/GENZ2024/shp/ (downloaded by tidycensus/tigris)
#   Water: TIGER/Line AREAWATER via tigris::area_water()
#
# Why a choropleth: median income is already normalized (a per-household
# median), so shading tract areas by it is appropriate. Raw counts are not.

source("R/00_common.R")

income <- cached("acs_income_tracts", {
  get_acs(geography = "tract", variables = c(income = "B19013_001"),
          state = "MN", county = TC_COUNTIES, year = ACS_YEAR,
          survey = "acs5", geometry = TRUE, cb = TRUE) |>
    st_transform(CRS_MN)
})

breaks <- c(0, 50e3, 75e3, 100e3, 125e3, 150e3, Inf)
labels <- c("Under $50k", "$50k\u201375k", "$75k\u2013100k", "$100k\u2013125k", "$125k\u2013150k", "$150k or more")
income <- income |>
  mutate(bin = as.character(cut(estimate, breaks, labels = labels, right = FALSE)),
         bin = factor(coalesce(bin, "No estimate"), levels = c(labels, "No estimate")))

counties <- tc_counties()
water <- tc_water()
region_median <- median(income$estimate, na.rm = TRUE)

p <- ggplot() +
  geom_sf(data = income, aes(fill = bin), colour = "white", linewidth = 0.08) +
  geom_sf(data = water, fill = WATER, colour = NA) +
  geom_sf(data = counties, fill = NA, colour = INK_2, linewidth = 0.35) +
  halo_label(counties, aes(label = NAME), fontface = "bold") +
  scale_fill_manual(values = c(setNames(SEQ_BLUE[c(1, 2, 3, 4, 5, 7)], labels),
                               "No estimate" = NO_DATA),
                    name = "Median household\nincome", drop = FALSE) +
  scale_bar() +
  fit_view(counties, ratio = 1.75) +
  labs(
    title = "Median household income by census tract, Twin Cities region",
    subtitle = sprintf(paste0("Each tract is shaded by its median household income, a normalized ",
                              "measure that suits a choropleth.\nThe median across tracts is %s. ",
                              "Tracts with no estimate are mostly parks, airports and institutions."),
                       dollar(region_median)),
    caption = footer(
      paste0("U.S. Census Bureau, ", ACS_LABEL, ", table B19013 (tidycensus::get_acs); ",
             "TIGER/Line cartographic tracts and area water (tigris). ",
             "ACS figures are survey estimates with margins of error."),
      sprintf("%d\u2013%d", ACS_YEAR - 4, ACS_YEAR),
      "Census tracts, seven-county Twin Cities region (Anoka, Carver, Dakota, Hennepin, Ramsey, Scott, Washington)",
      "Choropleth, six fixed income classes, NAD83 / UTM 15N"
    )
  ) +
  theme_map()

save_map(p, "01_choropleth_median_income.png")
