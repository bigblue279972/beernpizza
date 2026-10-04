#!/usr/bin/env python3
"""Import a downloaded fixtures file into an Excel fixtures sheet.

Takes whatever the source handed over -- a real CSV, a tab-separated file that
happens to be named .csv, a semicolon file, or an .xlsx -- works out which
column is which, and writes clean rows with **real Excel dates**.

    python tools/fixtures_import.py --inspect downloaded.csv
    python tools/fixtures_import.py downloaded.csv --out "Fixtures.xlsx"
    python tools/fixtures_import.py downloaded.csv --into "Fixture Dbase v7.xlsx"

Design rules, following the rest of this repo:

- **Columns are detected, not assumed**, and `--inspect` prints the mapping and
  writes nothing, so the guess is checked before any file is touched.
- **A day/month order that the file does not prove is reported, not guessed.**
  04/05/2026 is 4 May or 5 April and nothing in the row says which. Every date
  is written as a real Excel date so Excel can never re-read it its own way.
- **The target workbook is never edited in place** unless asked. `--into` copies
  it first and writes to the copy.
- Existing rows are read before appending, so re-importing an overlapping
  download adds only what is new.
"""

import argparse
import csv
import os
import re
import shutil
import sys
from datetime import date, datetime

CANON = ["date", "time", "comp", "home", "away"]
LABEL = {"date": "Date", "time": "Time", "comp": "Competition",
         "home": "Home Team", "away": "Away Team"}

# A header must not be scored as a team/date field just because it starts with
# the right word: 'Home Win Odds' and 'Date Downloaded' are not what we want.
NEVER = re.compile(
    r"odds|price|prob|payout|\bwin\b|\bdraw\b|lose|lost|score|goal|result|"
    r"xg\b|form|rank|rating|\bft\b|\bht\b|updat|download|created|modif|"
    r"\bid\b|url|link|stat", re.I)

HEAD_PAT = {
    "date": [r"^date$", r"match.?date", r"^day$", r"kick.?off.?date",
             r"^ko.?date$", r"^dt$", r"^when$", r"^start(.?date)?$"],
    "time": [r"^time$", r"ko.?time", r"kick.?off(.?time)?$", r"^ko$",
             r"start.?time", r"^local.?time$"],
    "comp": [r"^(league|div|division|competition|comp|country|tournament|"
             r"series|contest)$", r"league.?name", r"comp.*name", r"^event.?type$"],
    "home": [r"^home", r"^h.?team$", r"team.?1$", r"^local$", r"^side.?1$"],
    "away": [r"^away", r"^a.?team$", r"team.?2$", r"^visitor", r"^side.?2$"],
    # one column holding both sides, e.g. 'Arsenal v Chelsea'
    "teams": [r"^(teams?|match|fixture|event|event.?name|game|matchup|"
              r"description)$"],
}

# ' v ', ' vs ', ' - ', ' @ ', ' x ' -- the usual ways two sides get joined.
SPLIT = re.compile(r"\s+(?:v|vs|vs\.|versus|@|x|-|–|—)\s+", re.I)

MONTH_FIX = re.compile(r"\bsept\b", re.I)          # 'Sept' will not parse as %b
ISO_FMT = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]
DMY_FMT = ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y",
           "%d.%m.%y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d %b %y",
           "%d %b", "%a %d %b %Y", "%A %d %B %Y"]
MDY_FMT = ["%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%b %d %Y", "%B %d %Y",
           "%b %d, %Y", "%B %d, %Y", "%a %b %d %Y"]
TIME_RE = re.compile(r"^\s*(\d{1,2})[:.](\d{2})(?::\d{2})?\s*(am|pm)?\s*$", re.I)
NUM_DATE_RE = re.compile(r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\s*$")


# ------------------------------------------------------- competitions ----
# Source files name the league with a short code. These are the readable
# names written in its place. Two things to know about this table:
#
#   - It is a starting point, not gospel. Several of these leagues carry a
#     sponsor's name or have been renamed in recent years, so the right
#     label is partly a matter of preference.
#   - Nothing here is hardcoded in the sense that matters: `--write-lookup`
#     dumps the lot to competitions.csv, which is read back on every later
#     run and overrides whatever is below. Edit that file in Excel rather
#     than this one.
#
# Names are plain ASCII on purpose: a CSV edited in Excel on Windows is
# saved as cp1252, and an accented character makes a round trip through
# that badly.
COMP_NAMES = {
    # football-data.co.uk main divisions
    "E0": "England Premier League",
    "E1": "England Championship",
    "E2": "England League One",
    "E3": "England League Two",
    "EC": "England National League",
    "SC0": "Scotland Premiership",
    "SC1": "Scotland Championship",
    "SC2": "Scotland League One",
    "SC3": "Scotland League Two",
    "D1": "Germany Bundesliga",
    "D2": "Germany 2. Bundesliga",
    "I1": "Italy Serie A",
    "I2": "Italy Serie B",
    "SP1": "Spain La Liga",
    "SP2": "Spain Segunda Division",
    "F1": "France Ligue 1",
    "F2": "France Ligue 2",
    "N1": "Netherlands Eredivisie",
    "B1": "Belgium Pro League",
    "P1": "Portugal Primeira Liga",
    "T1": "Turkey Super Lig",
    "G1": "Greece Super League",
    # football-data.co.uk worldwide "extra" files
    "ARG": "Argentina Liga Profesional",
    "AUT": "Austria Bundesliga",
    "BRA": "Brazil Serie A",
    "CHN": "China Super League",
    "DNK": "Denmark Superliga",
    "FIN": "Finland Veikkausliiga",
    "IRL": "Ireland Premier Division",
    "JPN": "Japan J1 League",
    "MEX": "Mexico Liga MX",
    "NOR": "Norway Eliteserien",
    "POL": "Poland Ekstraklasa",
    "ROU": "Romania Liga I",
    "RUS": "Russia Premier League",
    "SWE": "Sweden Allsvenskan",
    "SWZ": "Switzerland Super League",
    "USA": "USA Major League Soccer",
}
LOOKUP_FILE = "competitions.csv"

# A short all-caps token with no spaces is a code waiting to be translated.
# 'Chinese Super League' is already readable and is left alone, so it is not
# reported as missing.
CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,5}$")


def looks_like_code(v):
    return bool(CODE_RE.match((v or "").strip()))


def load_comp_names(path=None):
    """Built-in names, overridden and extended by competitions.csv if present."""
    names = dict(COMP_NAMES)
    path = path or LOOKUP_FILE
    if not os.path.exists(path):
        return names, None
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for n, row in enumerate(csv.reader(fh), start=1):
            if len(row) < 2:
                continue
            code, name = row[0].strip(), row[1].strip()
            if not code or not name or code.lower() in ("code", "competition"):
                continue                      # header row, or a half-filled line
            names[code.upper()] = name
    return names, path


def write_comp_lookup(path):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["Code", "Readable Name"])
        for code in sorted(COMP_NAMES, key=lambda c: (COMP_NAMES[c], c)):
            w.writerow([code, COMP_NAMES[code]])
    return len(COMP_NAMES)


def readable_comp(value, names):
    """Return (name to write, code that had no name or None)."""
    v = (value or "").strip()
    if not v:
        return "", None
    hit = names.get(v.upper())
    if hit:
        return hit, None
    return v, (v if looks_like_code(v) else None)


# ---------------------------------------------------------------- reading ----

def sniff_delim(sample):
    """Pick the delimiter by which one carves the sample into the most columns.

    The failure this exists for: a tab-separated file named .csv, which Excel
    drops whole into column A.
    """
    best, best_cols = ",", 0
    for d in ["\t", ";", ",", "|"]:
        counts = [line.count(d) for line in sample if line.strip()]
        if not counts:
            continue
        # a real delimiter appears the same number of times on most lines
        mode = max(set(counts), key=counts.count)
        if mode == 0:
            continue
        agree = counts.count(mode) / len(counts)
        if agree >= 0.7 and mode + 1 > best_cols:
            best, best_cols = d, mode + 1
    return best


def read_table(path):
    """Return (rows, note). rows is a list of lists of strings."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError:
            sys.exit("STOPPED: reading .xlsx needs openpyxl.\n"
                     "  Run:  pip install openpyxl")
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = []
        for r in ws.iter_rows(values_only=True):
            rows.append(["" if v is None else
                         (v.strftime("%Y-%m-%d") if isinstance(v, (datetime, date))
                          else str(v).strip())
                         for v in r])
        wb.close()
        return rows, f"read sheet '{ws.title}' of {os.path.basename(path)}"

    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        text = fh.read()
    lines = text.splitlines()
    delim = sniff_delim(lines[:40])
    rows = [[c.strip() for c in r]
            for r in csv.reader(lines, delimiter=delim)]
    name = {"\t": "tab", ";": "semicolon", ",": "comma", "|": "pipe"}[delim]
    return rows, f"read as {name}-separated text"


# -------------------------------------------------------------- detection ----

def score_header(h, key):
    h = (h or "").strip()
    if not h:
        return 0
    flat = re.sub(r"[^a-z0-9 ]+", " ", h.lower()).strip()
    tight = flat.replace(" ", "")
    if key in ("home", "away", "teams", "date") and NEVER.search(h):
        return 0
    for i, pat in enumerate(HEAD_PAT[key]):
        if re.search(pat, flat) or re.search(pat, tight):
            return 100 - i          # earlier pattern is the stronger claim
    return 0


def find_header_row(rows):
    """The first row in the first few that names at least two fields."""
    for i, row in enumerate(rows[:10]):
        hits = sum(1 for k in list(CANON) + ["teams"]
                   if any(score_header(c, k) for c in row))
        if hits >= 2:
            return i
    return None


def map_columns(header):
    """{canonical field -> column index}, each column claimed only once."""
    claims = []
    for key in list(CANON) + ["teams"]:
        for j, h in enumerate(header):
            s = score_header(h, key)
            if s:
                claims.append((s, key, j))
    claims.sort(reverse=True)
    out, used = {}, set()
    for _s, key, j in claims:
        if key in out or j in used:
            continue
        out[key], _ = j, used.add(j)
    return out


def guess_by_content(rows):
    """No usable header row: find the date and time columns from the values."""
    width = max(len(r) for r in rows)
    out = {}
    for j in range(width):
        col = [r[j] if j < len(r) else "" for r in rows]
        vals = [v for v in col if v.strip()]
        if not vals:
            continue
        if "date" not in out and sum(1 for v in vals if looks_like_date(v)) >= 0.7 * len(vals):
            out["date"] = j
        elif "time" not in out and sum(1 for v in vals if TIME_RE.match(v)) >= 0.7 * len(vals):
            out["time"] = j
        elif "teams" not in out and sum(1 for v in vals if SPLIT.search(v)) >= 0.7 * len(vals):
            out["teams"] = j
    return out


def looks_like_date(v):
    if NUM_DATE_RE.match(v or ""):
        return True
    for fmt in ISO_FMT + DMY_FMT + MDY_FMT:
        try:
            datetime.strptime(MONTH_FIX.sub("Sep", v or ""), fmt)
            return True
        except ValueError:
            pass
    return False


# ----------------------------------------------------------------- dates -----

def date_order_evidence(values):
    """How many rows prove day-first, and how many prove month-first."""
    dmy = mdy = 0
    for v in values:
        m = NUM_DATE_RE.match(v or "")
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if a > 12:
            dmy += 1
        if b > 12:
            mdy += 1
    return dmy, mdy


def parse_date(v, order, default_year=None):
    v = MONTH_FIX.sub("Sep", (v or "").strip())
    if not v:
        return None
    for fmt in ISO_FMT:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    m = NUM_DATE_RE.match(v)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        d, mo = (a, b) if order == "dmy" else (b, a)
        if a > 12:                      # the row itself settles it
            d, mo = a, b
        elif b > 12:
            d, mo = b, a
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    pref = DMY_FMT + MDY_FMT if order == "dmy" else MDY_FMT + DMY_FMT
    for fmt in pref:
        try:
            got = datetime.strptime(v, fmt).date()
            if "%Y" not in fmt and "%y" not in fmt:
                got = got.replace(year=default_year or date.today().year)
            return got
        except ValueError:
            pass
    return None


def parse_time(v):
    m = TIME_RE.match(v or "")
    if not m:
        return ""
    h, mi, ap = int(m.group(1)), m.group(2), (m.group(3) or "").lower()
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return f"{h:02d}:{mi}" if 0 <= h <= 23 else ""


# ------------------------------------------------------------------ rows -----

def rows_word(n):
    return "1 row" if n == 1 else f"{n} rows"


def norm_team(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def build_rows(rows, header_row, cmap, order, comp_names=None):
    """Turn the raw table into fixture dicts, plus a list of skipped rows."""
    body = rows[header_row + 1:] if header_row is not None else rows
    out, skipped, unknown = [], [], {}
    for n, raw in enumerate(body, start=(header_row or 0) + 2):
        if not any((c or "").strip() for c in raw):
            continue

        def cell(key):
            j = cmap.get(key)
            return (raw[j].strip() if j is not None and j < len(raw) else "")

        d = parse_date(cell("date"), order)
        home, away = cell("home"), cell("away")
        if not (home and away) and "teams" in cmap:
            parts = SPLIT.split(cell("teams"), maxsplit=1)
            if len(parts) == 2:
                home, away = parts[0].strip(), parts[1].strip()
        if not d or not home or not away:
            why = ("no readable date" if not d else "no two team names")
            skipped.append((n, why, " | ".join(raw[:5])))
            continue
        comp = cell("comp")
        if comp_names is not None:
            comp, missing = readable_comp(comp, comp_names)
            if missing:
                unknown[missing] = unknown.get(missing, 0) + 1
        out.append({"date": d, "time": parse_time(cell("time")),
                    "comp": comp, "home": home, "away": away})
    return out, skipped, unknown


def key_of(f):
    return (f["date"].isoformat(), norm_team(f["home"]), norm_team(f["away"]))


# ---------------------------------------------------------------- writing ----

def new_workbook(path, fixtures):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Fixtures"
    head = [LABEL[k] for k in CANON]
    ws.append(head)
    fill = PatternFill("solid", fgColor="1F3864")
    for j in range(1, len(head) + 1):
        c = ws.cell(row=1, column=j)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = fill
        c.alignment = Alignment(horizontal="center")
    for f in fixtures:
        ws.append([f["date"], f["time"], f["comp"], f["home"], f["away"]])
    for r in range(2, len(fixtures) + 2):
        ws.cell(row=r, column=1).number_format = "dd/mm/yyyy"
    for j, w in enumerate([12, 8, 26, 24, 24], start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "A2"
    if fixtures:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(head))}{len(fixtures) + 1}"
    wb.save(path)


def header_row_of(ws, limit=10):
    """Row number of the header in an existing sheet, or None.

    Not assumed to be row 1: a workbook built by hand often carries a title
    or a blank line above its headings.
    """
    best, best_hits = None, 0
    for r in range(1, min(ws.max_row, limit) + 1):
        header = [str(c.value or "") for c in ws[r]]
        hits = len(map_columns(header))
        if hits > best_hits:
            best, best_hits = r, hits
    return best if best_hits >= 2 else None


def append_into(src, out, fixtures, sheet_name, comp_names=None,
                rename_existing=False):
    """Copy the target workbook, then append onto its own existing layout."""
    from openpyxl import load_workbook
    if os.path.abspath(src) != os.path.abspath(out):
        shutil.copyfile(src, out)
    wb = load_workbook(out)

    # Pick the sheet whose header row names the most fixture fields.
    if sheet_name:
        if sheet_name not in wb.sheetnames:
            sys.exit(f"STOPPED: no sheet named '{sheet_name}'. "
                     f"Sheets: {', '.join(wb.sheetnames)}")
        ws = wb[sheet_name]
    else:
        best, best_hits = None, 0
        for name in wb.sheetnames:
            cand = wb[name]
            hr = header_row_of(cand)
            hits = (len(map_columns([str(c.value or "") for c in cand[hr]]))
                    if hr else 0)
            if hits > best_hits:
                best, best_hits = cand, hits
        if best is None:
            sys.exit("STOPPED: could not find a fixtures sheet in that workbook.\n"
                     "  Name it with --sheet, e.g.  --sheet Fixtures")
        ws = best

    hrow = header_row_of(ws)
    if hrow is None:
        sys.exit(f"STOPPED: sheet '{ws.title}' has no row of column headings "
                 "that names a date and two teams.")
    header = [str(c.value or "") for c in ws[hrow]]
    tmap = map_columns(header)
    if "date" not in tmap:
        sys.exit(f"STOPPED: sheet '{ws.title}' has no Date column "
                 f"in row {hrow}.")

    # Existing rows, so an overlapping download does not duplicate.
    have, last = set(), hrow
    for r in range(hrow + 1, ws.max_row + 1):
        def tcell(key):
            j = tmap.get(key)
            return ws.cell(row=r, column=j + 1).value if j is not None else None
        dv, hv, av = tcell("date"), tcell("home"), tcell("away")
        if not (hv and av) and "teams" in tmap:
            parts = SPLIT.split(str(tcell("teams") or ""), maxsplit=1)
            if len(parts) == 2:
                hv, av = parts
        if dv is None and not hv:
            continue
        last = r
        if isinstance(dv, datetime):
            dv = dv.date()
        elif isinstance(dv, str):
            dv = parse_date(dv, "dmy")
        if dv and hv and av:
            have.add((dv.isoformat(), norm_team(str(hv)), norm_team(str(av))))

    added, dupes = 0, 0
    for f in fixtures:
        if key_of(f) in have:
            dupes += 1
            continue
        last += 1
        for key, j in tmap.items():
            if key == "teams":
                ws.cell(row=last, column=j + 1,
                        value=f"{f['home']} v {f['away']}")
            elif key in f:
                ws.cell(row=last, column=j + 1, value=f[key])
        ws.cell(row=last, column=tmap["date"] + 1).number_format = "dd/mm/yyyy"
        have.add(key_of(f))
        added += 1

    # Rows that were already in the sheet keep whatever competition value
    # they were written with. Left alone, the column ends up half codes and
    # half names, which is worse than either -- so this translates them too,
    # on request.
    renamed = 0
    if rename_existing and comp_names and "comp" in tmap:
        for r in range(hrow + 1, last + 1):
            cell = ws.cell(row=r, column=tmap["comp"] + 1)
            was = cell.value
            if not isinstance(was, str) or not was.strip():
                continue
            now, _missing = readable_comp(was, comp_names)
            if now != was:
                cell.value = now
                renamed += 1

    wb.save(out)
    unfilled = [h for j, h in enumerate(header)
                if h and j not in tmap.values()]
    return ws.title, hrow, added, dupes, unfilled, renamed


# ------------------------------------------------------------------ main -----

def main():
    ap = argparse.ArgumentParser(
        description="Import a downloaded fixtures file into an Excel sheet.")
    ap.add_argument("source", nargs="*", help="downloaded file(s): csv/txt/xlsx")
    ap.add_argument("--inspect", action="store_true",
                    help="show the detected columns and write nothing")
    ap.add_argument("--out", help="workbook to write (default 'Fixtures.xlsx')")
    ap.add_argument("--into", help="existing workbook to append into (copied first)")
    ap.add_argument("--sheet", help="sheet name inside --into")
    ap.add_argument("--in-place", action="store_true",
                    help="write back over --into instead of a copy")
    ap.add_argument("--date-order", choices=["dmy", "mdy"],
                    help="force day-first or month-first when the file is ambiguous")
    ap.add_argument("--keep-codes", action="store_true",
                    help="leave competition codes as they are, do not translate")
    ap.add_argument("--comp-names", metavar="FILE",
                    help=f"competition lookup to use (default {LOOKUP_FILE})")
    ap.add_argument("--write-lookup", action="store_true",
                    help=f"write {LOOKUP_FILE} with the built-in names, to edit")
    ap.add_argument("--rename-existing", action="store_true",
                    help="with --into, also translate codes already in the sheet")
    args = ap.parse_args()

    if args.write_lookup:
        target = args.comp_names or LOOKUP_FILE
        if os.path.exists(target):
            sys.exit(f"STOPPED: {target} already exists. Delete or rename it "
                     "first -- this would overwrite your edits.")
        n = write_comp_lookup(target)
        print(f"Wrote {target} with {n} competitions.\n"
              "  Open it in Excel, change any name you like, add your own rows,\n"
              "  and save it as CSV in this folder. Every later run reads it.")
        if not args.source:
            return
    elif not args.source:
        ap.error("name at least one file to import, "
                 "or use --write-lookup on its own")

    comp_names, lookup_used = (None, None) if args.keep_codes else \
        load_comp_names(args.comp_names)

    all_fx, seen, unknown_all = [], set(), {}
    for path in args.source:
        if not os.path.exists(path):
            sys.exit(f"STOPPED: cannot find {path}")
        rows, note = read_table(path)
        rows = [r for r in rows if any((c or "").strip() for c in r)]
        if not rows:
            print(f"{path}: empty, skipped")
            continue

        hrow = find_header_row(rows)
        if hrow is None:
            cmap, how = guess_by_content(rows), "by content (no header row found)"
        else:
            cmap, how = map_columns(rows[hrow]), f"from header row {hrow + 1}"
            if "date" not in cmap or not ({"home", "away"} <= set(cmap) or "teams" in cmap):
                extra = guess_by_content(rows[hrow + 1:])
                for k, v in extra.items():
                    cmap.setdefault(k, v)
                how += " + by content"

        print(f"\n=== {os.path.basename(path)} ===")
        print(f"  {note}; {len(rows)} non-empty rows; columns {how}")
        head = rows[hrow] if hrow is not None else []
        for key in list(CANON) + ["teams"]:
            j = cmap.get(key)
            if j is None:
                flag = "  (not found)" if key in ("date", "comp", "time") else ""
                if key in ("home", "away") and "teams" in cmap:
                    flag = "  (taken from the combined column)"
                print(f"  {key:<6} -> -{flag}")
            else:
                name = head[j] if j < len(head) else f"column {j + 1}"
                print(f"  {key:<6} -> {name!r}  (column {j + 1})")

        if "date" not in cmap:
            print("  !! no date column, nothing imported from this file")
            continue

        dcol = [r[cmap['date']] if cmap['date'] < len(r) else ""
                for r in (rows[hrow + 1:] if hrow is not None else rows)]
        dmy, mdy = date_order_evidence(dcol)
        if dmy and mdy:
            sys.exit("STOPPED: the dates in this file disagree with each other "
                     f"({rows_word(dmy)} day-first, "
                     f"{rows_word(mdy)} month-first).\n"
                     "  Fix the file, or split it and import each part with "
                     "--date-order.")
        if args.date_order:
            order, src = args.date_order, "you set it"
        elif dmy:
            order, src = "dmy", (f"proven by {rows_word(dmy)} "
                                 "with a day above 12")
        elif mdy:
            order, src = "mdy", (f"proven by {rows_word(mdy)} "
                                 "with a month above 12")
        else:
            order, src = "dmy", "ASSUMED, nothing in the file proves it"
        print(f"  date order: {order.upper()}  ({src})")
        if src.startswith("ASSUMED"):
            print("  !! check one date against the source website before you "
                  "trust these. Override with --date-order mdy if it is wrong.")

        fx, skipped, unknown = build_rows(rows, hrow, cmap, order, comp_names)
        for code, n in unknown.items():
            unknown_all[code] = unknown_all.get(code, 0) + n
        print(f"  usable fixtures: {len(fx)}; unusable rows: {len(skipped)}")
        for n, why, preview in skipped[:5]:
            print(f"    row {n}: {why} -- {preview[:70]}")
        if len(skipped) > 5:
            print(f"    ... and {len(skipped) - 5} more")
        if fx:
            print(f"  date range: {min(f['date'] for f in fx)} "
                  f"to {max(f['date'] for f in fx)}")
            for f in fx[:3]:
                print(f"    {f['date']}  {f['time'] or '--:--'}  "
                      f"{f['comp'] or '(no competition)'}  "
                      f"{f['home']} v {f['away']}")

        for f in fx:
            k = key_of(f)
            if k not in seen:
                seen.add(k)
                all_fx.append(f)

    if not all_fx:
        sys.exit("\nNothing usable found. Run with --inspect and check the "
                 "column mapping above.")

    all_fx.sort(key=lambda f: (f["date"], f["time"] or "99:99",
                               f["comp"], f["home"]))
    print(f"\n{len(all_fx)} fixtures ready (duplicates across files removed).")

    if comp_names is None:
        print("competition names: left as codes (--keep-codes).")
    else:
        named = sum(1 for f in all_fx
                    if f["comp"] and f["comp"] not in unknown_all)
        src = f"built-in names + {lookup_used}" if lookup_used else "built-in names"
        print(f"competition names: {named} of {len(all_fx)} readable ({src}).")
        if unknown_all:
            worst = sorted(unknown_all.items(), key=lambda kv: -kv[1])
            print("  no readable name for these codes, left exactly as they were:")
            for code, n in worst[:12]:
                print(f"    {code:<8} {n} fixture{'' if n == 1 else 's'}")
            if len(worst) > 12:
                print(f"    ... and {len(worst) - 12} more")
            print(f"  to name them: add a row to {lookup_used or LOOKUP_FILE}"
                  + ("" if lookup_used else " (--write-lookup creates it)"))

    if args.inspect:
        print("--inspect: nothing written. Re-run without --inspect to write.")
        return

    try:
        import openpyxl  # noqa: F401
    except ImportError:
        sys.exit("STOPPED: writing Excel needs openpyxl.\n"
                 "  Run:  pip install openpyxl")

    if args.into:
        if not os.path.exists(args.into):
            sys.exit(f"STOPPED: cannot find {args.into}")
        if args.in_place:
            out = args.into
        else:
            base, ext = os.path.splitext(args.into)
            out = args.out or f"{base} updated{ext}"
        sheet, hrow, added, dupes, unfilled, renamed = append_into(
            args.into, out, all_fx, args.sheet, comp_names,
            args.rename_existing)
        print(f"Wrote {out}")
        print(f"  sheet '{sheet}' (headings on row {hrow}): "
              f"{added} fixtures added, {dupes} already there and left alone")
        if args.rename_existing:
            print(f"  {renamed} competition "
                  f"{'name' if renamed == 1 else 'names'} rewritten on rows "
                  "that were already in the sheet")
        elif comp_names and added:
            print("  rows already in the sheet keep their old competition "
                  "values; --rename-existing translates those too")
        if unfilled:
            print("  columns it could not fill (left blank, nothing overwritten): "
                  + ", ".join(unfilled[:8])
                  + (" ..." if len(unfilled) > 8 else ""))
        if not args.in_place:
            print(f"  your original {args.into} was not touched")
    else:
        out = args.out or "Fixtures.xlsx"
        new_workbook(out, all_fx)
        print(f"Wrote {out} ({len(all_fx)} fixtures, dates as real Excel dates)")


if __name__ == "__main__":
    main()
