#!/usr/bin/env python3
"""Patch FIXTURE DBASE v7 into v8: kickoff times, capacity, and stale guidance.

    python tools/patch_fixture_dbase.py "FIXTURE DBASE v7.xlsx" "FIXTURE DBASE v8.xlsx"

Standard library only. The workbook carries three Power Query queries
(Results, Ratings, Slate), their connections and a query table. openpyxl does
not round-trip those -- saving through it silently drops the queries -- so this
edits the worksheet XML inside the zip directly and copies every other part
across byte for byte.

What it changes, and why:

1. Kickoff times. FIXTURES column H added a typed-in SETTINGS!B9 ("Hours ahead
   of UK") to the UK kickoff. It was 8.5, which is only right while Adelaide is
   on standard time AND the UK is on summer time. Adelaide moved to daylight
   saving on 4 Oct 2026, so every time shown became an hour early; from 25 Oct,
   when the UK leaves summer time, two hours early. Each fixture now works out
   its own gap from its own date and time (new helper columns J and K), so the
   four clock changes a year need no one to remember them.

2. Capacity. FIXTURES formulas ran to row 166 but SOCCER looked up only to row
   150, so fixtures 147-162 showed but could not be priced, and anything past
   162 vanished without a word. Both now run to row 200 (196 fixtures), and a
   status line in A2 says, in red, when a download does not fit.

3. Guidance that pointed at formula cells. README and FIXTURES A2 told the
   reader to type AFL games into rows 55-60. Those rows hold Slate formulas;
   typing there breaks them for good. AFL already lives at row 201 onwards
   (the AFL pricer looks it up there), so the text now says so.

Refuses to run if the layout is not the one it was written against, rather
than patching the wrong cells.
"""

import re
import sys
import zipfile
from xml.sax.saxutils import escape

FIRST, LAST_OLD, LAST = 5, 166, 200          # FIXTURES formula rows
CAPACITY = LAST - FIRST + 1                   # 196

NS_XLSX_FIX = "xl/worksheets/sheet4.xml"
NS_SETTINGS = "xl/worksheets/sheet2.xml"
NS_SOCCER = "xl/worksheets/sheet5.xml"
NS_README = "xl/worksheets/sheet1.xml"
UNTOUCHABLE = [                                # must come out byte-identical
    "customXml/item1.xml", "xl/connections.xml", "xl/queryTables/queryTable1.xml",
    "xl/tables/table1.xml", "xl/worksheets/sheet3.xml", "xl/metadata.xml",
    "xl/worksheets/sheet6.xml",
]


def stop(msg):
    sys.exit(f"STOPPED: {msg}\n  Nothing was written.")


# ------------------------------------------------------------ formulas ----

D = "INDEX(Slate[Date],ROW()-4)"
T = "INDEX(Slate[Time],ROW()-4)"


def f_uk_kickoff():
    """UK kickoff as a real date-time, parsed exactly as v7's column H did."""
    return (f'IFERROR(DATE(1*MID({D},7,4),1*MID({D},4,2),1*LEFT({D},2))'
            f'+IFERROR(TIMEVALUE({T}),0),"")')


def dst_gap(u):
    """Hours Adelaide is ahead of the UK at UK local date-time `u`.

    UK summer time: last Sunday of March 01:00 to last Sunday of October 01:00,
    in UK clock terms. Adelaide daylight saving: first Sunday of October 02:00
    ACST to first Sunday of April 03:00 ACDT -- both instants are 16:30 UTC on
    the Saturday, i.e. that Sunday minus 7.5 hours in UTC. So the UK test is
    done in UK local time, and the Adelaide test on the UTC instant.
    """
    y = f"YEAR({u})"
    last_sun_mar = f"DATE({y},4,0)-WEEKDAY(DATE({y},4,0))+1"
    last_sun_oct = f"DATE({y},11,0)-WEEKDAY(DATE({y},11,0))+1"
    first_sun_oct = f"DATE({y},10,1)+MOD(8-WEEKDAY(DATE({y},10,1)),7)"
    first_sun_apr = f"DATE({y},4,1)+MOD(8-WEEKDAY(DATE({y},4,1)),7)"
    uk_bst = f"AND({u}>={last_sun_mar}+1/24,{u}<{last_sun_oct}+1/24)"
    utc = f"({u}-IF({uk_bst},1,0)/24)"
    sa_dst = f"OR({utc}>={first_sun_oct}-7.5/24,{utc}<{first_sun_apr}-7.5/24)"
    return f"IF({sa_dst},10.5,9.5)-IF({uk_bst},1,0)"


def f_gap(r):
    return f'IF($J{r}="","",{dst_gap(f"$J{r}")})'


def f_kickoff_adl(r):
    """v7's display, now adding the fixture's own gap instead of SETTINGS!B9.

    A blank source time is shown as 'time TBC' rather than as midnight UK
    plus the gap, which v7 rendered as a confident-looking 9:30 AM.
    """
    return (f'IFERROR(IF($J{r}="",NA(),IF({T}="",'
            f'TEXT($J{r},"ddd d mmm")&" UK, time TBC",'
            f'TEXT(ROUND(($J{r}+$K{r}/24)*1440,0)/1440,"ddd d mmm  h:mm AM/PM"))),'
            f'IFERROR({D}&" "&{T},""))')


def f_status():
    n = "COUNTA(Slate[League])"
    return (f'IF({n}=0,"No fixtures loaded - Data tab, click Refresh All.",'
            f'IF({n}>{CAPACITY},"WARNING: "&{n}&" fixtures downloaded but only '
            f'{CAPACITY} fit - the rest are NOT shown.",'
            f'IF(MAX($J${FIRST}:$J${LAST})<TODAY()-1,'
            f'"OUT OF DATE: these fixtures have been played - Data tab, click Refresh All.",'
            f'{n}&" fixtures loaded. Rows {FIRST}-{LAST} fill themselves - do not type in '
            f'them. Type AFL games in row 201 onwards.")))')


SLATE_COL = {"C": "League", "D": "HomeTeam", "E": "AwayTeam",
             "F": "ExpHome", "G": "ExpAway"}


# --------------------------------------------------------------- cells ----

def c_array(ref, style, formula):
    """A single-cell dynamic-array formula, mirroring how v7 stores them."""
    return (f'<c r="{ref}" s="{style}" cm="1"><f t="array" ref="{ref}">'
            f'{escape(formula)}</f></c>')


def c_plain(ref, style, formula, text=False):
    t = ' t="str"' if text else ""
    return f'<c r="{ref}" s="{style}"{t}><f>{escape(formula)}</f></c>'


def c_text(ref, style, text):
    return (f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
            f'{escape(text)}</t></is></c>')


# -------------------------------------------------------------- styles ----

def patch_styles(xml):
    """Add: a UK date-time format, two grey helper styles, one red warning."""
    m = re.search(r'<numFmts count="(\d+)">(.*?)</numFmts>', xml, re.S)
    if not m:
        stop("styles.xml has no numFmts block.")
    ids = [int(i) for i in re.findall(r'numFmtId="(\d+)"', m.group(2))]
    fmt_id = max(ids + [163]) + 1
    xml = xml.replace(m.group(0),
                      f'<numFmts count="{int(m.group(1)) + 1}">{m.group(2)}'
                      f'<numFmt numFmtId="{fmt_id}" formatCode="ddd d mmm hh:mm"/></numFmts>')

    m = re.search(r'<cellXfs count="(\d+)">(.*?)</cellXfs>', xml, re.S)
    n = int(m.group(1))
    # font 4 is v7's own italic grey 9pt note font; border 1 is its grid.
    add = (f'<xf numFmtId="{fmt_id}" fontId="4" fillId="0" borderId="1" xfId="0" '
           'applyNumberFormat="1" applyFont="1" applyBorder="1"/>'
           '<xf numFmtId="167" fontId="4" fillId="0" borderId="1" xfId="0" '
           'applyNumberFormat="1" applyFont="1" applyBorder="1"/>')
    xml = xml.replace(m.group(0),
                      f'<cellXfs count="{n + 2}">{m.group(2)}{add}</cellXfs>')
    st_uk, st_gap = n, n + 1

    m = re.search(r'<dxfs count="(\d+)"\s*/>|<dxfs count="(\d+)">(.*?)</dxfs>', xml, re.S)
    if not m:
        stop("styles.xml has no dxfs block.")
    red = '<dxf><font><b/><color rgb="FFC00000"/></font></dxf>'
    if m.group(1) is not None:
        dxf_id = int(m.group(1))
        xml = xml.replace(m.group(0), f'<dxfs count="{dxf_id + 1}">{red}</dxfs>')
    else:
        dxf_id = int(m.group(2))
        xml = xml.replace(m.group(0),
                          f'<dxfs count="{dxf_id + 1}">{m.group(3)}{red}</dxfs>')
    return xml, st_uk, st_gap, dxf_id


# ------------------------------------------------------------ FIXTURES ----

ROW_RE = re.compile(r'<row r="(\d+)"([^>]*?)(?:/>|>(.*?)</row>)', re.S)


def patch_fixtures(xml, st_uk, st_gap, dxf_id):
    for need in (escape('IFERROR(INDEX(Slate[League],ROW()-4),"")'),
                 "SETTINGS!$B$9/24", '<c r="A201"', '<dimension ref="A1:I206"/>'):
        if need not in xml:
            stop(f"FIXTURES does not look like v7 (missing {need!r}).")

    rows = {int(m.group(1)): m for m in ROW_RE.finditer(xml)}
    for r in range(FIRST, LAST_OLD + 1):
        if r not in rows or f'<c r="H{r}"' not in rows[r].group(0):
            stop(f"FIXTURES row {r} is not the formula row v7 has there.")
    for r in range(LAST_OLD + 1, LAST + 1):
        if r in rows and re.search(r'<c r="[A-Z]+\d+"[^>]*>', rows[r].group(0)):
            stop(f"FIXTURES row {r} has content; refusing to write over it.")

    def rebuilt(r):
        m = rows[r]
        attrs = re.sub(r'spans="[^"]*"', 'spans="1:11"', m.group(2))
        body = m.group(3) or ""
        if r == 2:
            body = c_plain("A2", 4, f_status(), text=True)
        elif r == 4:
            body += (c_text("J4", 9, "UK KICKOFF (auto)") +
                     c_text("K4", 9, "HRS AHEAD (auto)"))
        elif FIRST <= r <= LAST_OLD:
            body = re.sub(r'<c r="H%d"[^>]*?(?:/>|>.*?</c>)' % r,
                          c_array(f"H{r}", 10, f_kickoff_adl(r)), body, flags=re.S)
            body += c_array(f"J{r}", st_uk, f_uk_kickoff())
            body += c_plain(f"K{r}", st_gap, f_gap(r))
        return f'<row r="{r}"{attrs}>{body}</row>'

    def new_row(r):
        cells = [c_plain(f"A{r}", 2, f"A{r - 1}+1"),
                 c_plain(f"B{r}", 10, f'IF(C{r}="","","SOC")', text=True)]
        for col, field in SLATE_COL.items():
            style = 6 if col in "FG" else 10
            cells.append(c_array(f"{col}{r}", style,
                                 f'IFERROR(INDEX(Slate[{field}],ROW()-4),"")'))
        cells.append(c_array(f"H{r}", 10, f_kickoff_adl(r)))
        cells.append(c_array(f"J{r}", st_uk, f_uk_kickoff()))
        cells.append(c_plain(f"K{r}", st_gap, f_gap(r)))
        return (f'<row r="{r}" spans="1:11" x14ac:dyDescent="0.35">'
                f'{"".join(cells)}</row>')

    head, sheet_data, tail = re.match(r'(.*<sheetData>)(.*)(</sheetData>.*)', xml, re.S).groups()
    out = []
    for m in ROW_RE.finditer(sheet_data):
        r = int(m.group(1))
        out.append(rebuilt(r) if r in (2, 4) or FIRST <= r <= LAST_OLD else m.group(0))
        if r == LAST_OLD:
            out.extend(new_row(n) for n in range(LAST_OLD + 1, LAST + 1))
    # rows LAST_OLD+1..LAST that existed only as empty shells are now superseded
    out = [x for x in out if not (re.match(r'<row r="(\d+)"', x) and
           LAST_OLD < int(re.match(r'<row r="(\d+)"', x).group(1)) <= LAST and
           'spans="1:11"' not in x)]

    head = head.replace('<dimension ref="A1:I206"/>', '<dimension ref="A1:K206"/>')
    head = head.replace(
        '<col min="8" max="8" width="18" customWidth="1"/></cols>',
        '<col min="8" max="8" width="18" customWidth="1"/>'
        '<col min="10" max="10" width="17" customWidth="1"/>'
        '<col min="11" max="11" width="17" customWidth="1"/></cols>')
    # anything but the normal "N fixtures loaded" line is a warning: red, bold
    rule = escape('NOT(ISNUMBER(SEARCH("fixtures loaded",$A$2)))')
    cf = (f'<conditionalFormatting sqref="A2"><cfRule type="expression" '
          f'dxfId="{dxf_id}" priority="1"><formula>{rule}</formula></cfRule>'
          f'</conditionalFormatting>')
    tail = tail.replace("</sheetData>", "</sheetData>" + cf, 1)
    return head + "".join(out) + tail


# ------------------------------------------------------ other sheets ------

def patch_settings(xml):
    old = '<c r="B9" s="21"><v>8.5</v></c>'
    if old not in xml:
        stop("SETTINGS B9 is not the 8.5 input v7 has there.")
    note = ("Automatic now. Each fixture works out its own gap from its own date "
            "(Adelaide and UK daylight saving), see FIXTURES column K. This cell "
            "only shows today's. Do not type here.")
    # style 12 is v7's plain 0.00 number: no yellow, because it is not an input
    return xml.replace(old, c_plain("B9", 12, dst_gap("(TODAY()+0.5)")) +
                       c_text("C9", 4, note))


def patch_soccer(xml):
    n = 0
    for col in "CDEFG":
        old, new = f"FIXTURES!${col}$5:${col}$150", f"FIXTURES!${col}$5:${col}${LAST}"
        if old not in xml:
            stop(f"SOCCER does not look up {old} as v7 does.")
        n += xml.count(old)
        xml = xml.replace(old, new)
    return xml, n


def patch_readme(xml):
    lines = {
        8: "FIXTURES   Rows 5-200 fill themselves from DATA. Row 201 onwards is yours "
           "to type in (AFL).",
        25: "Power Query covers soccer only. For AFL, type the game into FIXTURES row "
            "201 onwards",
        27: "Row 201 already has Geelong v Carlton in it as an example.",
    }
    for r, text in lines.items():
        m = re.search(r'<c r="A%d" s="(\d+)" t="s"><v>\d+</v></c>' % r, xml)
        if not m:
            stop(f"README A{r} is not the text cell v7 has there.")
        xml = xml.replace(m.group(0), c_text(f"A{r}", m.group(1), text))
    return xml


# ---------------------------------------------------------------- main ----

def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.split("\n\n")[1])
    src, dst = sys.argv[1], sys.argv[2]
    if src == dst:
        stop("write to a new file; the original is never overwritten.")
    zin = zipfile.ZipFile(src)
    parts = {i.filename: zin.read(i.filename) for i in zin.infolist()}
    for p in UNTOUCHABLE + [NS_XLSX_FIX, NS_SETTINGS, NS_SOCCER, NS_README]:
        if p not in parts:
            stop(f"{p} is missing; this is not the v7 layout.")

    get = lambda p: parts[p].decode("utf-8")
    styles, st_uk, st_gap, dxf_id = patch_styles(get("xl/styles.xml"))
    changed = {
        "xl/styles.xml": styles,
        NS_XLSX_FIX: patch_fixtures(get(NS_XLSX_FIX), st_uk, st_gap, dxf_id),
        NS_SETTINGS: patch_settings(get(NS_SETTINGS)),
        NS_README: patch_readme(get(NS_README)),
    }
    changed[NS_SOCCER], n_soccer = patch_soccer(get(NS_SOCCER))

    # Recalculate everything on open, and drop the calc chain: it lists the
    # old formula cells, and Excel rebuilds it silently when it is absent.
    wb = get("xl/workbook.xml")
    if 'fullCalcOnLoad="1"' not in wb:
        wb = re.sub(r'<calcPr ', '<calcPr fullCalcOnLoad="1" ', wb, count=1)
    changed["xl/workbook.xml"] = wb
    changed["[Content_Types].xml"] = re.sub(
        r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", get("[Content_Types].xml"))
    changed["xl/_rels/workbook.xml.rels"] = re.sub(
        r'<Relationship [^>]*Target="calcChain.xml"[^>]*/>', "",
        get("xl/_rels/workbook.xml.rels"))

    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename == "xl/calcChain.xml":
                continue
            data = changed[info.filename].encode("utf-8") \
                if info.filename in changed else parts[info.filename]
            zout.writestr(info, data)

    print(f"Wrote {dst}")
    print(f"  FIXTURES: rows {FIRST}-{LAST} ({CAPACITY} fixtures), kickoff times "
          "now follow daylight saving at both ends")
    print(f"  SOCCER: {n_soccer} lookups extended to row {LAST}")
    print("  SETTINGS B9: automatic, no longer typed in")
    print("  README and FIXTURES A2: AFL now pointed at row 201, not formula rows")
    print("  Power Query, connections and the DATA table copied unchanged")


if __name__ == "__main__":
    main()
