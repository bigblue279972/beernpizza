#!/usr/bin/env python3
"""Write Cliff's own settings into a freshly built Fixture Dbase.

    python tools/apply_my_settings.py "FIXTURE DBASE v9.xlsx" "FIXTURE DBASE v9 (mine).xlsx" \\
        --max-units 3 [--kelly 0.25]

Every workbook the build scripts produce carries v7's defaults -- max 1 unit per
bet, no Kelly fraction -- so a new download silently loses whatever was set by
hand. With a cap of 1 every bet the pricer flags stakes exactly 1 unit, because
a price that clears the required price always has an edge of at least the
buffer; the stake only varies once the cap is above 1. This writes the chosen
values into the yellow input cells and copies every other part byte for byte,
as the other patch scripts do, so Power Query is untouched.
"""

import argparse
import re
import sys
import zipfile

SETTINGS = "xl/worksheets/sheet2.xml"
KELLY = "xl/worksheets/sheet7.xml"


def set_value(xml, ref, value, where):
    m = re.search(r'<c r="%s"([^>]*?)(?:/>|>.*?</c>)' % ref, xml, re.S)
    if not m:
        sys.exit(f"STOPPED: {where} {ref} not found; is this a v9 workbook?")
    if "<f>" in m.group(0):
        sys.exit(f"STOPPED: {where} {ref} holds a formula, not a setting.")
    attrs = re.sub(r'\s+t="[^"]*"', "", m.group(1))
    return xml.replace(m.group(0), f'<c r="{ref}"{attrs}><v>{value}</v></c>', 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--max-units", type=float, help="SETTINGS B5, Max units per bet")
    ap.add_argument("--kelly", type=float, help="KELLY B4, the Kelly fraction")
    a = ap.parse_args()
    if a.src == a.dst:
        sys.exit("STOPPED: write to a new file; the original is never overwritten.")
    if a.max_units is not None and not 0 < a.max_units <= 20:
        sys.exit("STOPPED: --max-units should be between 0 and 20.")
    if a.kelly is not None and not 0 < a.kelly <= 1:
        sys.exit("STOPPED: --kelly should be between 0 and 1.")

    z = zipfile.ZipFile(a.src)
    parts = {i.filename: z.read(i.filename) for i in z.infolist()}
    if a.max_units is not None:
        parts[SETTINGS] = set_value(parts[SETTINGS].decode(), "B5", f"{a.max_units:g}",
                                    "SETTINGS").encode()
    if a.kelly is not None:
        if KELLY not in parts:
            sys.exit("STOPPED: no KELLY tab; build v9 with tools/add_kelly_tab.py first.")
        parts[KELLY] = set_value(parts[KELLY].decode(), "B4", f"{a.kelly:g}", "KELLY").encode()
    with zipfile.ZipFile(a.dst, "w", zipfile.ZIP_DEFLATED) as out:
        for info in z.infolist():
            out.writestr(info, parts[info.filename])
    print(f"Wrote {a.dst}")
    if a.max_units is not None:
        print(f"  SETTINGS Max units per bet = {a.max_units:g}")
    if a.kelly is not None:
        print(f"  KELLY fraction = {a.kelly:g}")


if __name__ == "__main__":
    main()
