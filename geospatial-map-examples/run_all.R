# Rebuild all six maps and check the outputs.
#   cd geospatial-map-examples
#   Rscript run_all.R
# Needs CENSUS_API_KEY (and optionally MAPBOX_PUBLIC_TOKEN) in the environment.

scripts <- c("R/01_choropleth.R", "R/02_proportional_symbols.R", "R/03_dot_density.R",
             "R/04_heat_map.R", "R/05_isochrones.R", "R/06_flow_map.R")
outputs <- c("01_choropleth_median_income.png", "02_proportional_symbols_renters.png",
             "03_dot_density_race_ethnicity.png", "04_heat_map_synthetic_events.png",
             "05_isochrones_mall_of_america.png", "06_flow_map_phoenix_inmigration.png")

# Run each script in its own R process so one failure cannot affect another.
status <- vapply(scripts, function(s) {
  message("\n== ", s)
  system2(file.path(R.home("bin"), "Rscript"), s) == 0
}, logical(1))

png_size <- function(path) {
  con <- file(path, "rb"); on.exit(close(con))
  header <- readBin(con, "raw", 24)
  c(width = sum(as.integer(header[17:20]) * 256^(3:0)),
    height = sum(as.integer(header[21:24]) * 256^(3:0)))
}

cat("\nResults\n")
ok <- TRUE
for (i in seq_along(outputs)) {
  path <- file.path("output", outputs[i])
  if (!status[i] || !file.exists(path)) {
    cat(sprintf("  FAIL  %s\n", outputs[i])); ok <- FALSE; next
  }
  d <- png_size(path)
  good <- d[["width"]] >= 2400 && d[["height"]] >= 1350 && abs(d[["width"]] / d[["height"]] - 16 / 9) < 0.01
  cat(sprintf("  %s  %s  %d x %d\n", if (good) "OK  " else "SIZE", outputs[i], d[["width"]], d[["height"]]))
  ok <- ok && good
}
if (!file.exists("index.html")) { cat("  FAIL  index.html missing\n"); ok <- FALSE } else cat("  OK    index.html\n")
if (!ok) quit(status = 1)
