"""Extract state populations, 1790-1900, from the Census Bureau's
"Population of States and Counties of the United States: 1790-1990"
(Forstall, 1996), Part II tables, using word positions on the OCR'd pages.

Every column is checked: the states must add up to the printed U.S. total,
and 1910/1920 must match the Bureau's machine-readable apportionment file.
Cells where OCR mangled a digit are corrected in FIXES below after checking
them against the page image.
"""
import re
import sys
from pathlib import Path

import pandas as pd
import pymupdf

RAW = Path(__file__).resolve().parent / "data" / "raw"
PDF = RAW / "population-of-states-and-counties-of-the-united-states-1790-1990.pdf"
PAGES = {14: [1850, 1840, 1830, 1820, 1810, 1800, 1790],
         13: [1920, 1910, 1900, 1890, 1880, 1870, 1860]}
STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
          "Delaware", "District of Columbia", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois",
          "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland",
          "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana",
          "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York",
          "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
          "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
          "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"]
# (state, year) -> value, for cells OCR could not read; each checked by eye
# against the scanned page.
FIXES = {
    ("Arizona", 1890): 88_243,  # OCR read 38,243; scan and Arizona county page say 88,243
}
# Cells that are a dash (no count) on the scan but OCR read as specks.
BLANK = {("Nebraska", 1810)}


def ocr_fix(name):
    if name.startswith("District"):  # "District of Columbia"; OCR drops "of"
        return "District of Columbia"
    return {"Califomia": "California"}.get(name, name)


def parse_page(page, years):
    words = page.get_text("words")  # x0, y0, x1, y1, text, block, line, word
    header = {int(w[4]): (w[0] + w[2]) / 2 for w in words if w[4] in {str(y) for y in years}}
    header_y = max(w[1] for w in words if w[4] in {str(y) for y in years})
    num_x_min = min(header.values()) - 60
    rows = {}
    lines = {}
    for w in words:
        if w[1] <= header_y + 5:
            continue
        lines.setdefault(round(w[3] / 3), []).append(w)
    # group words into rows by baseline
    rows_raw = []
    for w in sorted((w for w in words if w[1] > header_y + 5), key=lambda w: (w[3], w[0])):
        if rows_raw and abs(rows_raw[-1][0] - w[3]) < 4:
            rows_raw[-1][1].append(w)
        else:
            rows_raw.append([w[3], [w]])
    for _, ws in rows_raw:
        label = " ".join(w[4] for w in ws if w[2] < num_x_min).strip(" .")
        label = ocr_fix(label)
        if label.upper() == "UNITED STATES":
            label = "United States"
        if label not in STATES + ["United States"]:
            continue
        vals = {}
        for w in ws:
            if w[2] < num_x_min or not any(c.isdigit() for c in w[4]):
                continue
            cx = (w[0] + w[2]) / 2
            year = min(header, key=lambda y: abs(header[y] - cx))
            vals[year] = w[4]
        rows[label] = vals
    return rows


def to_int(s):
    if not re.fullmatch(r"[\d.,]+", s):
        return None
    return int(re.sub(r"[.,]", "", s))


def main():
    doc = pymupdf.open(PDF)
    records, problems = [], []
    for pno, years in PAGES.items():
        rows = parse_page(doc[pno], years)
        missing = set(STATES) - set(rows)
        if missing:
            problems.append(f"page {pno}: rows not found {sorted(missing)}")
        for name, vals in rows.items():
            for year, raw in vals.items():
                if (name, year) in BLANK:
                    continue
                v = FIXES.get((name, year), to_int(raw))
                if v is None:
                    problems.append(f"unreadable {name} {year}: {raw!r}")
                    continue
                records.append({"name": name, "year": year, "population": v})
    df = pd.DataFrame(records).drop_duplicates(["name", "year"])
    for (name, year), v in FIXES.items():
        df = df[~((df.name == name) & (df.year == year))]
        df = pd.concat([df, pd.DataFrame([{"name": name, "year": year, "population": v}])])

    # Check 1: states add up to the printed U.S. total.
    us = df[df.name == "United States"].set_index("year")["population"]
    st = df[df.name != "United States"].groupby("year")["population"].sum()
    for year in sorted(us.index):
        diff = st.get(year, 0) - us[year]
        flag = "OK" if diff == 0 else f"OFF BY {diff:+,}"
        print(f"  {year}: states {st.get(year, 0):>12,}  U.S. {us[year]:>12,}  {flag}")
        if diff:
            problems.append(f"{year} sum off by {diff:+,}")

    # Check 2: 1910 and 1920 agree with the apportionment CSV.
    ap = pd.read_csv(RAW / "apportionment.csv", thousands=",")
    ap = ap[(ap["Geography Type"] == "State") & ap.Year.isin([1910, 1920])
            & (ap.Name != "Puerto Rico")]
    m = ap.merge(df, left_on=["Name", "Year"], right_on=["name", "year"], how="left")
    bad = m[m["Resident Population"] != m["population"]]
    for _, r in bad.iterrows():
        # The 1996 PDF and the 2020 apportionment file differ slightly for
        # Hawaii (later revisions); anything else is a parse error.
        msg = f"{r.Name} {r.Year}: PDF {r.population:,.0f} vs CSV {r['Resident Population']:,}"
        if r.Name == "Hawaii" and abs(r.population - r["Resident Population"]) < 100:
            print(f"  note: {msg}")
        else:
            problems.append(msg)

    if problems:
        print("\nProblems:\n  " + "\n  ".join(problems))
        sys.exit(1)
    out = df[df.year <= 1900].sort_values(["year", "name"])
    out.to_csv(RAW.parent / "states_1790_1900.csv", index=False)
    print(f"\nwrote {len(out)} rows")


if __name__ == "__main__":
    main()
