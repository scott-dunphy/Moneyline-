# 3. Dot-density map: 2020 Census population by race and ethnicity,
#    Hennepin County, Minnesota. 1 dot = 100 people.
#
# Data
#   2020 Census P.L. 94-171 Redistricting Data, table P2 (Hispanic or Latino,
#   and not Hispanic or Latino by race), via
#   tidycensus::get_decennial(sumfile = "pl", year = 2020, geometry = TRUE).
#   API: https://api.census.gov/data/2020/dec/pl
#   Dots: tidycensus::as_dot_density(values_per_dot = 100, erase_water = TRUE),
#   which removes TIGER/Line area water (tigris::erase_water) before placing
#   dots at random inside each tract.
#   City boundary: TIGER/Line cartographic places via tigris::places()
#
# These are official decennial census counts, not ACS estimates. Dot
# positions within a tract are random, so individual dots are not addresses.

source("R/00_common.R")

VARS <- c(total = "P2_001N", hispanic = "P2_002N", white = "P2_005N",
          black = "P2_006N", asian = "P2_008N")
GROUPS <- c(white = "White", black = "Black", hispanic = "Hispanic or Latino",
            asian = "Asian", other = "All other groups, incl. two or more races")
COLORS <- c("White" = "#a3a19a", "Black" = "#2a78d6", "Hispanic or Latino" = "#eb6834",
            "Asian" = "#1baf7a", "All other groups, incl. two or more races" = "#4a3aa7")

race <- cached("dec2020_race_hennepin", {
  get_decennial(geography = "tract", variables = VARS, state = "MN", county = "Hennepin",
                year = 2020, sumfile = "pl", geometry = TRUE, output = "wide") |>
    st_transform(CRS_MN)
})

long <- race |>
  mutate(other = total - hispanic - white - black - asian) |>
  select(GEOID, white, black, hispanic, asian, other) |>
  tidyr::pivot_longer(c(white, black, hispanic, asian, other),
                      names_to = "group", values_to = "value") |>
  mutate(group = factor(GROUPS[group], levels = GROUPS))

set.seed(2020)
dots <- cached("dots_hennepin_100", {
  as_dot_density(long, value = "value", values_per_dot = 100, group = "group",
                 erase_water = TRUE)
})
dots <- dots[sample(nrow(dots)), ]      # shuffle so no group is always drawn on top

county <- tc_counties() |> filter(NAME == "Hennepin")
water <- tc_water("Hennepin", min_km2 = 0.1)
mpls <- cached("mpls_boundary", {
  places("MN", cb = TRUE, year = ACS_YEAR) |> filter(NAME == "Minneapolis") |> st_transform(CRS_MN)
})
shares <- long |> st_drop_geometry() |> group_by(group) |> summarise(n = sum(value)) |>
  mutate(share = n / sum(n))
legend_labels <- setNames(sprintf("%s (%s)", shares$group, percent(shares$share, 0.1)), shares$group)

p <- ggplot() +
  geom_sf(data = county, fill = "#fbfbfa", colour = INK_2, linewidth = 0.35) +
  geom_sf(data = water, fill = WATER, colour = NA) +
  geom_sf(data = dots, aes(colour = group), size = 1.05, stroke = 0, shape = 16, alpha = 0.9) +
  geom_sf(data = mpls, fill = NA, colour = INK, linewidth = 0.45, linetype = "22") +
  halo_label(mpls, aes(label = "Minneapolis"), fontface = "bold", nudge_y = 9000) +
  scale_colour_manual(values = COLORS, labels = legend_labels,
                      name = "1 dot = 100 people\n(share of county population)") +
  guides(colour = guide_legend(override.aes = list(size = 5))) +
  scale_bar() +
  fit_view(county, ratio = 1.75) +
  labs(
    title = "Where 1.28 million people live: Hennepin County by race and ethnicity",
    subtitle = paste0(
      "Each dot is 100 residents, placed at random within their census tract after lakes and ",
      "rivers are erased.\nDot density shows both how many people live in an area and who they are, ",
      "without implying exact locations."),
    caption = footer(
      paste0("U.S. Census Bureau, 2020 Census P.L. 94-171 Redistricting Data, table P2 ",
             "(tidycensus::get_decennial); dots by tidycensus::as_dot_density; TIGER/Line tracts, ",
             "places and area water (tigris). Official 2020 Census counts."),
      "2020 (April 1 census day)",
      "Census tracts, Hennepin County, MN (Minneapolis city limits dashed)",
      "Dot density, 1 dot = 100 people, random placement within tracts, water erased"
    )
  ) +
  theme_map()

save_map(p, "03_dot_density_race_ethnicity.png")
