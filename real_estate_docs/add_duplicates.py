#!/usr/bin/env python3
"""
Add duplicate documents (under different file names) to the generated collection.

Reads instructor_answer_key/answer_key.csv, copies ~130 originals into documents/ under
new loose names and writes instructor_answer_key/duplicate_key.csv.

Duplicate kinds
  exact     - byte-identical copy, different file name
  rewritten - same pages and text, re-saved (different bytes / metadata / hash)
  stamped   - same document with a RECEIVED / DRAFT / COPY / SCANNED stamp added
A few originals are duplicated twice (a group of three files).

Usage: python3 add_duplicates.py [--seed 7] [--exact 70] [--rewritten 30] [--stamped 30]
Run once, after generate_documents.py (which resets the documents folder).
"""
import argparse, csv, io, os, random, shutil
import datetime as dt
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "documents")
KEY = os.path.join(HERE, "instructor_answer_key")

def new_name(orig, d, R, taken):
    stem = orig[:-4]
    pats = [lambda: f"{stem} (1).pdf", lambda: f"{stem} - Copy.pdf", lambda: f"Copy of {stem}.pdf", lambda: f"{stem}_v2.pdf",
            lambda: f"{stem}-final.pdf", lambda: f"{stem} (2).pdf",
            lambda: f"scan_{d:%Y%m%d}_{R.randint(700, 1900):04d}.pdf", lambda: f"IMG_{R.randint(1000, 9999)}.pdf",
            lambda: f"Document ({R.randint(1, 400)}).pdf", lambda: f"doc_{R.randrange(16**6):06x}.pdf",
            lambda: f"attachment_{R.randint(1, 9999)}.pdf", lambda: f"New Scan {R.randint(1, 900)}.pdf",
            lambda: f"file{R.randint(10000, 99999)}.pdf", lambda: f"untitled{R.randint(1, 999)}.pdf"]
    while True:
        n = R.choice(pats)()
        if n.lower() not in taken:
            taken.add(n.lower()); return n

def rewrite(src, dst, R):
    r = PdfReader(src); w = PdfWriter()
    for p in r.pages:
        w.add_page(p)
    w.add_metadata({"/Title": f"Scan {R.randint(100, 999)}", "/Producer": R.choice(["Print to PDF", "Scanner Pro", "PDF Merge Tool"])})
    w.compress_identical_objects()
    with open(dst, "wb") as f:
        w.write(f)

def stamp(src, dst, R, date):
    text = R.choice([f"RECEIVED {date:%m/%d/%Y}", "DRAFT", "COPY", "SCANNED COPY", "FILE COPY", f"REVIEWED {date:%m/%d}"])
    col = R.choice([colors.HexColor("#b00020"), colors.HexColor("#1a4fa0"), colors.HexColor("#2b7a2b")])
    r = PdfReader(src); w = PdfWriter()
    for i, p in enumerate(r.pages):
        if i == 0 or R.random() < 0.3:
            buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=letter)
            c.saveState(); c.setFillColor(col); c.setStrokeColor(col); c.setFont("Helvetica-Bold", 20)
            c.translate(R.randint(330, 420), R.randint(660, 700)); c.rotate(R.randint(-12, 12))
            tw = c.stringWidth(text, "Helvetica-Bold", 20)
            c.rect(-6, -6, tw + 12, 30, stroke=1, fill=0); c.drawString(0, 2, text); c.restoreState(); c.save(); buf.seek(0)
            p.merge_page(PdfReader(buf).pages[0])
        w.add_page(p)
    with open(dst, "wb") as f:
        w.write(f)
    return text

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--exact", type=int, default=70)
    ap.add_argument("--rewritten", type=int, default=30)
    ap.add_argument("--stamped", type=int, default=30)
    a = ap.parse_args()
    R = random.Random(a.seed)
    rows = list(csv.DictReader(open(os.path.join(KEY, "answer_key.csv"))))
    taken = {f.lower() for f in os.listdir(DOCS)}
    kinds = ["exact"] * a.exact + ["rewritten"] * a.rewritten + ["stamped"] * a.stamped
    R.shuffle(kinds)
    n_orig = len(kinds) - 12                       # 12 originals are duplicated twice
    originals = R.sample(rows, n_orig)
    originals += R.sample(originals, 12)           # second copies of 12 of them
    out = []
    for kind, o in zip(kinds, originals):
        d = dt.date.fromisoformat(o["document_date"])
        name = new_name(o["filename"], d, R, taken)
        src, dst = os.path.join(DOCS, o["filename"]), os.path.join(DOCS, name)
        note = ""
        if kind == "exact":
            shutil.copyfile(src, dst)
        elif kind == "rewritten":
            rewrite(src, dst, R)
        else:
            note = stamp(src, dst, R, d + dt.timedelta(days=R.randint(1, 40)))
        out.append(dict(filename=name, duplicate_of=o["filename"], duplicate_kind=kind, stamp_text=note,
                        property_name=o["property_name"], document_type=o["document_type"], pages=o["pages"]))
    out.sort(key=lambda r: (r["duplicate_of"], r["filename"]))
    with open(os.path.join(KEY, "duplicate_key.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    print(f"added {len(out)} duplicate files; documents folder now has {len(os.listdir(DOCS))} files")

if __name__ == "__main__":
    main()
