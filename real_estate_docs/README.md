# Fictitious Real Estate Document Collection (1,000 originals + 130 duplicates)

A deliberately messy folder of 1,000 invented real estate documents for an
"use AI to organise this" exercise.

* `documents/` – **give students only this folder.** One flat folder, 1,130 PDFs (1,000 originals + 130 hidden duplicates),
  1–15 pages each (8,026 pages total). File names are meaningless
  (`scan_20230815_0931.pdf`, `IMG_4821.pdf`, `download (12).pdf`, …), so the files
  can only be organised by reading them.
* `instructor_answer_key/` – **do not share.** `answer_key.csv` maps every file to its
  property, property type, document type, category, date, page count and a suggested
  target path; `properties.csv` lists the 130 properties; `duplicate_key.csv` lists every duplicate file and the original it copies.
* `add_duplicates.py` – adds the duplicates (run once after generating; `generate_documents.py` resets the folder).
* `generate_documents.py` – regenerates everything (`python3 generate_documents.py --seed N`).
  Requires `reportlab`.

## What's inside
* 130 invented properties across 12 property types (multifamily, office, industrial, retail,
  self storage, hotel, senior housing, medical office, student housing, mixed-use, data center,
  single-family rental).
* 27 document types (offering memorandums, PSAs, appraisals, Phase I ESAs, leases, rent rolls,
  T-12s, loan agreements, insurance certificates, tax bills, vendor contracts, …).
* Every property has 5–8 different document types and ~7–8 documents; recurring types
  (rent rolls, T-12s, quarterly reports, tax bills, insurance, leases) appear several times
  with different dates.
* Running page headers vary: ~70% name the property, ~20% show only the street, ~10% show
  neither – so multi-page documents sometimes have to be classified from their first page or body text.
* Every page carries a "fictitious sample document" footer. All people, companies and
  figures are made up.

## Duplicates
130 extra files are copies of 118 of the originals, saved under different names (some look like
`IMG_3559 (1).pdf` / `Copy of ...`, others are completely unrelated names). Twelve originals have two copies.
* **exact** (70) – byte-identical, so a file hash finds them
* **rewritten** (30) – same pages and text but re-saved, so hashes differ and students must compare content
* **stamped** (30) – same document with a RECEIVED / DRAFT / COPY stamp added; text differs slightly

Ask students to identify the duplicate sets, choose which copy to keep, and explain how they decided.

## Suggested exercise
Have students use an AI tool to read the PDFs and produce a structure such as

```
<Property Type>/<Property Name>/<Category>/<YYYY-MM-DD> - <Document Type>.pdf
```

then score against `answer_key.csv` (`suggested_folder`, `suggested_filename`). Good discussion
points: properties with several documents of the same type, undated or multi-page documents,
and how to handle uncertain classifications.
