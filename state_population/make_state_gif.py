"""Animated map of U.S. population by state, 1790 census to latest estimate.

Data (all U.S. Census Bureau)
  1790-1900  "Population of States and Counties of the United States:
             1790-1990" (parsed by parse_1790_1900.py -> data/states_1790_1900.csv)
  1910-2020  2020 Census apportionment file, resident population
  latest     Vintage population estimates (NST-EST), final frame only

  python parse_1790_1900.py   # once
  python make_state_gif.py
"""
import argparse
import io
import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from matplotlib.patches import Rectangle
from PIL import Image
from shapely import affinity

HERE = Path(__file__).resolve().parent
RAW, OUT = HERE / "data" / "raw", HERE / "output"
APPORTIONMENT = "https://www2.census.gov/programs-surveys/decennial/2020/data/apportionment/apportionment.csv"
ESTIMATES = "https://www2.census.gov/programs-surveys/popest/datasets/2020-{y}/state/totals/NST-EST{y}-ALLDATA.csv"
STATES_SHP = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_20m.zip"

W, H, DPI = 1200, 800, 100
BINS = [0, 100_000, 500_000, 1_000_000, 2_500_000, 5_000_000, 10_000_000, 20_000_000, np.inf]
LABELS = ["<100k", "100k", "500k", "1M", "2.5M", "5M", "10M", "20M+"]
COLORS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#104281", "#0d366b"]
SURFACE, NO_DATA, INK, INK_2, MUTED, ACCENT = "#fcfcfb", "#ecebe7", "#0b0b0b", "#52514e", "#8a8984", "#2a78d6"
plt.rcParams.update({"font.family": "Liberation Sans", "text.color": INK})


def fetch(url, name):
    path = RAW / name
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path


def latest_estimates():
    for y in range(2030, 2020, -1):
        try:
            path = fetch(ESTIMATES.format(y=y), f"NST-EST{y}-ALLDATA.csv")
        except requests.HTTPError:
            continue
        df = pd.read_csv(path, encoding="latin-1")
        df = df[df.SUMLEV == 40][["NAME", f"POPESTIMATE{y}"]]
        return y, df.rename(columns={"NAME": "name", f"POPESTIMATE{y}": "population"})
    raise RuntimeError("No state population estimates found.")


def load_population():
    early = pd.read_csv(HERE / "data" / "states_1790_1900.csv")
    ap = pd.read_csv(fetch(APPORTIONMENT, "apportionment.csv"), thousands=",")
    ap = ap[(ap["Geography Type"] == "State") & (ap.Name != "Puerto Rico")]
    census = ap.rename(columns={"Name": "name", "Year": "year", "Resident Population": "population"})
    est_year, est = latest_estimates()
    est["year"] = est_year
    df = pd.concat([early, census[["name", "year", "population"]], est], ignore_index=True)
    df = df[~df.name.isin(["Puerto Rico", "United States"])]
    frames = [{"year": y, "label": str(y), "kind": "Census"} for y in sorted(df.year.unique()) if y != est_year]
    frames.append({"year": est_year, "label": str(est_year), "kind": "Census Bureau estimate"})
    return df, frames


def load_states():
    """Lower 48 in Albers equal-area, with Alaska and Hawaii moved into insets."""
    gdf = gpd.read_file(f"zip://{fetch(STATES_SHP, 'cb_2024_us_state_20m.zip')}")
    gdf = gdf[~gdf.STUSPS.isin(["PR"])].to_crs("EPSG:5070")
    def place(geom, name):
        # Scale, then move the inset's lower-left corner under the Southwest.
        target = {"Alaska": (0.35, -2_300_000, 250_000), "Hawaii": (1.0, -700_000, 250_000)}
        if name not in target:
            return geom
        k, x, y = target[name]
        geom = affinity.scale(geom, k, k, origin="centroid")
        minx, miny, _, _ = geom.bounds
        return affinity.translate(geom, x - minx, y - miny)
    gdf["geometry"] = [place(g, n) for g, n in zip(gdf.geometry, gdf.NAME)]
    return gdf.rename(columns={"NAME": "name"})[["name", "geometry"]]


def render(frame, frames, states, pop, totals):
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=SURFACE)
    ax = fig.add_axes([0.0, 0.14, 0.80, 0.72])
    ax.set_axis_off()
    year_pop = pop[pop.year == frame["year"]].set_index("name")["population"]
    s = states.assign(population=states["name"].map(year_pop))
    have = s.population.notna() & (s.population > 0)
    s[~have].plot(ax=ax, color=NO_DATA, edgecolor="white", linewidth=0.6)
    cls = pd.cut(s.loc[have, "population"], BINS, right=False, labels=False).astype(int)
    s[have].plot(ax=ax, color=[COLORS[i] for i in cls], edgecolor="white", linewidth=0.6)
    ax.set_aspect("equal")

    fig.text(0.035, 0.935, "U.S. population by state", fontsize=24, fontweight="bold")
    fig.text(0.035, 0.892, f"Every census from {frames[0]['label']}, plus the latest "
             f"Census Bureau estimate ({frames[-1]['label']})", fontsize=13, color=INK_2)
    fig.text(0.965, 0.915, frame["label"], fontsize=54, fontweight="bold", color=ACCENT, ha="right")
    fig.text(0.965, 0.878, frame["kind"], fontsize=12, color=INK_2, ha="right")

    # legend
    lx, ly, sw = 0.035, 0.075, 0.052
    fig.text(lx, ly + 0.035, "Population", fontsize=11, fontweight="bold")
    for i, (c, lab) in enumerate(zip(COLORS, LABELS)):
        fig.patches.append(Rectangle((lx + i * sw, ly), sw - 0.003, 0.022, transform=fig.transFigure, color=c))
        fig.text(lx + i * sw, ly - 0.008, lab, fontsize=9, color=INK_2, va="top")
    nx = lx + len(COLORS) * sw + 0.02
    fig.patches.append(Rectangle((nx, ly), 0.022, 0.022, transform=fig.transFigure, color=NO_DATA))
    fig.text(nx + 0.028, ly + 0.011, "Not yet counted", fontsize=9, color=INK_2, va="center")

    # national total, drawn up to the current frame
    bx = fig.add_axes([0.745, 0.06, 0.22, 0.14])
    bx.set_facecolor("none")
    idx = frames.index(frame)
    ys = [f["year"] for f in frames]
    bx.plot(ys[: idx + 1], [totals[y] / 1e6 for y in ys[: idx + 1]], color=ACCENT, linewidth=2)
    bx.plot(ys[idx], totals[ys[idx]] / 1e6, "o", color=ACCENT, markersize=6)
    bx.set_xlim(ys[0] - 5, ys[-1] + 5)
    bx.set_ylim(0, max(totals.values()) / 1e6 * 1.1)
    bx.set_xticks([1800, 1900, 2000], ["1800", "1900", "2000"], fontsize=8, color=INK_2)
    bx.set_yticks([])
    for sp in ("top", "right", "left"):
        bx.spines[sp].set_visible(False)
    bx.spines["bottom"].set_color(MUTED)
    bx.tick_params(length=0)
    fig.text(0.745, 0.23, f"U.S. total: {totals[frame['year']]:,}", fontsize=11, fontweight="bold")

    fig.text(0.035, 0.012, "Source: U.S. Census Bureau — Population of States and Counties of the U.S., "
             "1790–1990; 2020 Census apportionment data; Vintage population estimates. "
             "Current state boundaries shown.", fontsize=8, color=MUTED)
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    plt.close(fig)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=float, default=0.9)
    ap.add_argument("--first-hold", type=float, default=2.0)
    ap.add_argument("--last-hold", type=float, default=4.0)
    args = ap.parse_args()

    pop, frames = load_population()
    states = load_states()
    totals = pop.groupby("year")["population"].sum().astype(int).to_dict()
    OUT.mkdir(exist_ok=True)
    pop.to_csv(HERE / "data" / "state_population_1790_latest.csv", index=False)

    imgs = []
    for f in frames:
        imgs.append(render(f, frames, states, pop, totals))
    Image.fromarray(imgs[-1]).save(OUT / f"states_{frames[-1]['year']}.png")
    Image.fromarray(imgs[0]).save(OUT / f"states_{frames[0]['year']}.png")

    holds = [args.first_hold] + [args.hold] * (len(imgs) - 2) + [args.last_hold]
    sample = Image.fromarray(np.concatenate([imgs[0], imgs[len(imgs) // 2], imgs[-1]], axis=1))
    palette = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    gif = [Image.fromarray(i).quantize(palette=palette, dither=Image.Dither.NONE) for i in imgs]
    out = OUT / "state_population.gif"
    gif[0].save(out, save_all=True, append_images=gif[1:], loop=0,
                duration=[round(h * 1000) for h in holds])
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(imgs)} frames, {sum(holds):.0f}s loop)")


if __name__ == "__main__":
    main()
