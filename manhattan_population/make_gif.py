"""Render the Manhattan tract-density animation from data/processed/.

Each year is drawn on its own census-tract boundaries and colored by
population density (people per square mile of land), which stays comparable
even though tract lines are redrawn every decade. Frames hold long enough to
read, with a slow crossfade between years.

  python make_gif.py                 # output/manhattan_population.gif (+ .mp4, stills)
  python make_gif.py --hold 5 --fade 1.5
"""
import argparse
import json

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from PIL import Image
from pyproj import Transformer

from config import (CONTEXT_LAND, DENSITY_BINS, DENSITY_COLORS, DENSITY_LABELS, FONT,
                    HIGHLIGHT, INK, INK_2, INK_MUTED, MAP_CRS, MIN_RESIDENTIAL_POP,
                    NEIGHBORHOODS, NONRESIDENTIAL_COLOR, OUTPUT, PROCESSED, WATER)

W, H, DPI = 1080, 1350, 100
plt.rcParams.update({"font.family": FONT, "text.color": INK})
to_map = Transformer.from_crs("EPSG:4326", MAP_CRS, always_xy=True)

# Map window (lon/lat) sized to the 4:5 frame; Manhattan runs down the middle,
# New Jersey (upper left) and Brooklyn/Queens (lower right) hold the text panels.
LAT_MIN, LAT_MAX, LON_CENTER = 40.6935, 40.8845, -73.962
RIVERS = [("Hudson River", -74.0165, 40.7700, 66), ("East River", -73.9615, 40.7330, 72)]
PLACES = [("NEW JERSEY", -74.0350, 40.7950), ("THE BRONX", -73.9050, 40.8680),
          ("QUEENS", -73.8930, 40.7760)]
HALO = [pe.withStroke(linewidth=3, foreground=WATER)]


def map_extent():
    x0, y0 = to_map.transform(LON_CENTER, LAT_MIN)
    _, y1 = to_map.transform(LON_CENTER, LAT_MAX)
    half_w = (y1 - y0) * W / H / 2
    return x0 - half_w, x0 + half_w, y0, y1


PARK_HATCH = dict(facecolor=NONRESIDENTIAL_COLOR, edgecolor="#c4c1b6", hatch="////", linewidth=0)


def classify(gdf):
    cls = pd.cut(gdf["density"], DENSITY_BINS, right=False, labels=False)
    return np.array(DENSITY_COLORS, dtype=object)[cls.fillna(0).astype(int)]


def draw_panel(fig, x, y, w, h):
    fig.patches.append(Rectangle((x, y), w, h, transform=fig.transFigure, facecolor=WATER,
                                 edgecolor="none", alpha=0.94, zorder=5))


def render(frame, frames, layers):
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=WATER)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(WATER)
    ax.set_axis_off()
    x0, x1, y0, y1 = map_extent()
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)

    layers["context"].plot(ax=ax, color=CONTEXT_LAND, edgecolor="none")
    tracts = layers["tracts"][frame["year"]]
    parks = tracts["pop"] < MIN_RESIDENTIAL_POP
    tracts[~parks].plot(ax=ax, color=classify(tracts[~parks]), edgecolor=WATER, linewidth=0.35)
    if parks.any():
        tracts[parks].plot(ax=ax, **PARK_HATCH)
        tracts[parks].boundary.plot(ax=ax, color=WATER, linewidth=0.35)
    if layers.get("neighborhoods") is not None:
        layers["neighborhoods"].boundary.plot(ax=ax, color=INK, linewidth=0.7, alpha=0.35)

    for name, lon, lat, rot in RIVERS:
        ax.text(*to_map.transform(lon, lat), name, rotation=rot, ha="center", va="center",
                fontsize=11, style="italic", color=INK_MUTED, path_effects=HALO)
    for name, lon, lat in PLACES:
        ax.text(*to_map.transform(lon, lat), name, ha="center", va="center", fontsize=11,
                color=INK_MUTED, fontweight="bold", path_effects=HALO)
    for name, lon, lat in NEIGHBORHOODS:
        park = name.startswith("Central")
        ax.text(*to_map.transform(lon, lat), name, ha="center", va="center",
                fontsize=10, linespacing=0.95, color=INK_2 if park else INK,
                style="italic" if park else "normal", fontweight="normal" if park else "bold",
                path_effects=[pe.withStroke(linewidth=2.8, foreground="white")], zorder=4)

    # ---- headline panel (upper left, over New Jersey)
    draw_panel(fig, 0, 0.635, 0.50, 0.365)
    fig.text(0.045, 0.962, "MANHATTAN POPULATION DENSITY BY CENSUS TRACT",
             fontsize=11, fontweight="bold", color=INK_2, zorder=6)
    fig.text(0.045, 0.918, f"Where Manhattanites have lived,\n{frames[0]['label']} to today",
             fontsize=21, fontweight="bold", va="top", linespacing=1.1, zorder=6)
    fig.text(0.045, 0.835, frame["label"], fontsize=68, fontweight="bold", va="top",
             color=HIGHLIGHT, zorder=6)
    fig.text(0.047, 0.738, frame["source"], fontsize=13, color=INK_2, zorder=6)
    fig.text(0.047, 0.702, "Total population", fontsize=12, color=INK_2, zorder=6)
    fig.text(0.047, 0.660, f"{frame['total']:,}", fontsize=26, fontweight="bold", zorder=6)
    base = frames[0]
    if frame is not base:
        pct = (frame["total"] / base["total"] - 1) * 100
        fig.text(0.27, 0.665, f"{pct:+.0f}% vs. {base['label']}".replace("-", "−"),
                 fontsize=14, color=INK_2, zorder=6)

    # ---- legend + timeline panel (lower right, over Brooklyn/Queens)
    draw_panel(fig, 0.60, 0, 0.40, 0.40)
    fig.text(0.625, 0.375, "People per square mile", fontsize=13, fontweight="bold", zorder=6)
    sw_w, sw_h, lx, ly = 0.05, 0.022, 0.625, 0.335
    for i, (color, label) in enumerate(zip(DENSITY_COLORS, DENSITY_LABELS)):
        fig.patches.append(Rectangle((lx + i * sw_w, ly), sw_w - 0.003, sw_h,
                                     transform=fig.transFigure, color=color, zorder=6))
    for i, edge in enumerate(["0", "10k", "25k", "50k", "75k", "100k", "150k"]):
        fig.text(lx + i * sw_w, ly - 0.008, edge, fontsize=9.5, color=INK_2, va="top",
                 ha="left" if i == 0 else "center", zorder=6)
    fig.patches.append(Rectangle((lx, 0.278), 0.025, sw_h, transform=fig.transFigure,
                                 zorder=6, **PARK_HATCH))
    fig.text(lx + 0.033, 0.289, f"Parks & non-residential\n(under {MIN_RESIDENTIAL_POP} residents)",
             fontsize=9.5, color=INK_2, va="center", zorder=6)

    bx = fig.add_axes([0.635, 0.085, 0.335, 0.145], zorder=7)
    bx.set_facecolor("none")
    years = [f["year"] for f in frames]
    idx = frames.index(frame)
    heights = [f["total"] / 1e6 if i <= idx else 0 for i, f in enumerate(frames)]
    colors = [HIGHLIGHT if i == idx else "#c9c8c2" for i in range(len(frames))]
    bx.bar(years, heights, width=3.2, color=colors)
    bx.text(years[idx], heights[idx] + 0.04, f"{frame['total'] / 1e6:.2f}M", ha="center",
            va="bottom", fontsize=10, fontweight="bold")
    bx.set_ylim(0, max(f["total"] for f in frames) / 1e6 * 1.22)
    bx.set_xticks(years, [f"'{str(y)[2:]}" for y in years], fontsize=9, color=INK_2)
    bx.set_yticks([])
    for s in ("top", "right", "left"):
        bx.spines[s].set_visible(False)
    bx.spines["bottom"].set_color(INK_MUTED)
    bx.tick_params(length=0)
    fig.text(0.625, 0.245, "Manhattan total population", fontsize=11, fontweight="bold", zorder=6)

    decennial = ("(1950–2000, via IPUMS NHGIS)" if frames[0]["year"] < 1990
                 else "(1990 PL 94-171, 2000 SF1)")
    fig.text(0.625, 0.016, f"Source: U.S. Census Bureau decennial census\n{decennial} and ACS 5-year\n"
             "estimates (table B01003). Each year is drawn\non its own census-tract boundaries.",
             fontsize=8, color=INK_MUTED, linespacing=1.2, zorder=6)

    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    plt.close(fig)
    return img


def load():
    frames = sorted(json.loads((PROCESSED / "frames.json").read_text()), key=lambda f: f["year"])
    layers = {"context": gpd.read_file(PROCESSED / "context.gpkg"),
              "tracts": {f["year"]: gpd.read_file(PROCESSED / f"tracts_{f['year']}.gpkg")
                         for f in frames}}
    nta = PROCESSED / "neighborhoods.gpkg"
    layers["neighborhoods"] = gpd.read_file(nta) if nta.exists() else None
    return frames, layers


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hold", type=float, default=2.5, help="seconds on each year")
    ap.add_argument("--first-hold", type=float, default=4.0, help="seconds on the opening year")
    ap.add_argument("--last-hold", type=float, default=5.0, help="seconds on the final year")
    ap.add_argument("--fade", type=float, default=0.6, help="seconds of crossfade between years")
    ap.add_argument("--fade-steps", type=int, default=4)
    ap.add_argument("--no-mp4", action="store_true")
    args = ap.parse_args()

    frames, layers = load()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stills = []
    for f in frames:
        print(f"rendering {f['label']}")
        stills.append(render(f, frames, layers))
        Image.fromarray(stills[-1]).save(OUTPUT / f"manhattan_{f['year']}.png")

    seq = []  # (image, seconds)
    for i, img in enumerate(stills):
        hold = args.first_hold if i == 0 else args.last_hold if i == len(stills) - 1 else args.hold
        seq.append((img, hold))
        if i + 1 < len(stills):
            nxt = stills[i + 1]
            for s in range(1, args.fade_steps + 1):
                t = s / (args.fade_steps + 1)
                t = t * t * (3 - 2 * t)  # ease in/out
                blend = (img * (1 - t) + nxt * t).astype(np.uint8)
                seq.append((blend, args.fade / args.fade_steps))

    # One shared palette so colors don't shimmer between frames.
    sample = Image.fromarray(np.concatenate([s[:, ::2] for s in stills[::max(1, len(stills) // 4)]], axis=1))
    palette = sample.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    gif = [Image.fromarray(img).quantize(palette=palette, dither=Image.Dither.NONE) for img, _ in seq]
    out = OUTPUT / "manhattan_population.gif"
    gif[0].save(out, save_all=True, append_images=gif[1:], loop=0,
                duration=[round(sec * 1000) for _, sec in seq], optimize=False)
    total = sum(sec for _, sec in seq)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {total:.0f}s loop)")

    if not args.no_mp4:
        import imageio.v2 as imageio
        fps = 10
        mp4 = OUTPUT / "manhattan_population.mp4"
        with imageio.get_writer(mp4, fps=fps, codec="libx264", quality=8,
                                macro_block_size=2, pixelformat="yuv420p") as w:
            for img, sec in seq:
                for _ in range(max(1, round(sec * fps))):
                    w.append_data(img)
        print(f"wrote {mp4} ({mp4.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
