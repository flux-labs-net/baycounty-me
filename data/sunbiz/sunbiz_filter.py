#!/usr/bin/env python3
"""
Filter the Sunbiz quarterly corporate data files down to one county (Bay County by default).

Keeps an entity if ANY of these has a ZIP in the county (see counties.py):
  principal address, mailing address, registered agent, or any of the 6 officers.
(Officer matches catch Bay County residents who own entities based elsewhere.)

Usage:
  python3 data/sunbiz/sunbiz_filter.py /path/to/folder/with/cordata/files [--county bay] [--active-only]

The state publishes the quarterly file at https://dos.fl.gov/sunbiz/other-services/data-downloads/ (SFTP, user "Public").
Run it WITHOUT --active-only for the files committed here: dissolved companies are needed to match older gifts.

Reads .txt files and .zip files (no need to unzip). Streams line by line,
so memory use stays small even on 18 GB of input.

Writes data/sunbiz/<county>/entities.csv.gz and officers.csv.gz (the inputs build_sunbiz.py reads):
  entities.csv.gz   one row per entity (parsed, plus which addresses matched the county)
  officers.csv.gz   one row per officer/manager on those entities
"""
import csv
import io
import os
import sys
import gzip
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from counties import county  # noqa: E402

BAY_ZIPS = set()  # set from --county in main()

# (name, start, length) from the official layout; start is 1-based.
FIELDS = [
    ("doc_number", 1, 12), ("name", 13, 192), ("status", 205, 1),
    ("filing_type", 206, 15),
    ("addr1", 221, 42), ("addr2", 263, 42), ("city", 305, 28),
    ("state", 333, 2), ("zip", 335, 10), ("country", 345, 2),
    ("mail_addr1", 347, 42), ("mail_addr2", 389, 42), ("mail_city", 431, 28),
    ("mail_state", 459, 2), ("mail_zip", 461, 10), ("mail_country", 471, 2),
    ("file_date", 473, 8), ("fei", 481, 14), ("more_than_6_officers", 495, 1),
    ("last_txn_date", 496, 8), ("state_country", 504, 2),
    ("report_year_1", 506, 4), ("report_date_1", 511, 8),
    ("report_year_2", 519, 4), ("report_date_2", 524, 8),
    ("report_year_3", 532, 4), ("report_date_3", 537, 8),
    ("ra_name", 545, 42), ("ra_type", 587, 1), ("ra_addr", 588, 42),
    ("ra_city", 630, 28), ("ra_state", 658, 2), ("ra_zip", 660, 9),
]
OFFICER_START = 669      # officer 1 title
OFFICER_LEN = 128        # 4+1+42+42+28+2+9
OFFICER_FIELDS = [("title", 0, 4), ("type", 4, 1), ("name", 5, 42),
                  ("addr", 47, 42), ("city", 89, 28), ("state", 117, 2),
                  ("zip", 119, 9)]
RECORD_LEN = 1440


def zip5(z):
    z = z.strip()
    return z[:5] if len(z) >= 5 else ""


def parse(line):
    line = line.rstrip("\r\n").ljust(RECORD_LEN)
    rec = {n: line[s - 1:s - 1 + l].strip() for n, s, l in FIELDS}
    officers = []
    for i in range(6):
        base = OFFICER_START - 1 + i * OFFICER_LEN
        o = {n: line[base + off:base + off + l].strip()
             for n, off, l in OFFICER_FIELDS}
        if o["name"]:
            o["slot"] = i + 1
            officers.append(o)
    return rec, officers


def bay_matches(rec, officers):
    hits = []
    if zip5(rec["zip"]) in BAY_ZIPS:
        hits.append("principal")
    if zip5(rec["mail_zip"]) in BAY_ZIPS:
        hits.append("mailing")
    if zip5(rec["ra_zip"]) in BAY_ZIPS:
        hits.append("agent")
    if any(zip5(o["zip"]) in BAY_ZIPS for o in officers):
        hits.append("officer")
    return hits


def iter_lines(path):
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue
                with zf.open(member) as fh:
                    for line in io.TextIOWrapper(fh, encoding="latin-1"):
                        yield line
    else:
        with open(path, encoding="latin-1") as fh:
            for line in fh:
                yield line


ENT_COLS = ["doc_number", "name", "status", "filing_type", "addr1", "addr2", "city", "state", "zip", "mail_city", "mail_state",
            "mail_zip", "file_date", "fei", "more_than_6_officers", "last_txn_date", "state_country", "report_year_1",
            "report_date_1", "ra_name", "ra_type", "ra_addr", "ra_city", "ra_state", "ra_zip", "bay_match"]
OFF_COLS = ["doc_number", "slot", "title", "type", "name", "addr", "city", "state", "zip"]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)
    folder = args[0]
    active_only = "--active-only" in sys.argv
    key = sys.argv[sys.argv.index("--county") + 1] if "--county" in sys.argv else "bay"
    BAY_ZIPS.update(county(key)["zips"])
    if key in args:
        args.remove(key)
    files = sorted(
        os.path.join(folder, f) for f in os.listdir(folder)
        if f.lower().endswith((".txt", ".zip")))
    if not files:
        sys.exit(f"No .txt or .zip files found in {folder}")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), key)
    os.makedirs(out_dir, exist_ok=True)
    ent_path = os.path.join(out_dir, "entities.csv.gz")
    off_path = os.path.join(out_dir, "officers.csv.gz")

    total = kept = 0
    with gzip.open(ent_path, "wt", newline="", encoding="utf-8") as ef, \
         gzip.open(off_path, "wt", newline="", encoding="utf-8") as of:
        ew = csv.DictWriter(ef, fieldnames=ENT_COLS, extrasaction="ignore")
        ow = csv.DictWriter(of, fieldnames=OFF_COLS, extrasaction="ignore")
        ew.writeheader()
        ow.writeheader()
        for path in files:
            print(f"Scanning {os.path.basename(path)} ...", flush=True)
            for line in iter_lines(path):
                if not line.strip():
                    continue
                total += 1
                rec, officers = parse(line)
                if active_only and rec["status"] != "A":
                    continue
                hits = bay_matches(rec, officers)
                if not hits:
                    continue
                kept += 1
                rec["bay_match"] = "|".join(hits)
                ew.writerow(rec)
                for o in officers:
                    ow.writerow({"doc_number": rec["doc_number"], **o})
            print(f"  {kept:,} {key} entities so far (of {total:,} scanned)", flush=True)

    print(f"\nDone. {kept:,} entities kept out of {total:,}.")
    print(f"  {ent_path}\n  {off_path}")


if __name__ == "__main__":
    main()
