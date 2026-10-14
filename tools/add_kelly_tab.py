#!/usr/bin/env python3
"""Add a KELLY sandbox tab to a patched Fixture Dbase (v8 -> v9).

    python tools/patch_fixture_dbase.py "FIXTURE DBASE v7.xlsx" "FIXTURE DBASE v8.xlsx"
    python tools/add_kelly_tab.py       "FIXTURE DBASE v8.xlsx" "FIXTURE DBASE v9.xlsx"

Standard library only, for the same reason as the patch: the workbook carries
Power Query, which openpyxl drops on save. The new sheet is written as raw XML
and registered in the workbook; every existing part except the four that list
sheets and styles is copied byte for byte.

What the tab is, and is not:

- A calculator for trying bet sizes. One yellow dial -- the Kelly fraction --
  and every stake on the tab follows it.
- Not a change to live staking. STAKE $ on SOCCER and AFL still comes from
  units, exactly as before. The tab reads their decision blocks and shows the
  Kelly stake beside the units stake, so the two can be compared on real bets
  before anything is switched.

Kelly here is the same formula the pricers already use in their KELLY column,
net of commission: f* = (p(1 + b) - 1) / b with b = (price - 1)(1 - commission).
Stakes are gated on the required price, as the pricers are, and capped at
SETTINGS' max units per bet.

The 'chance the bank halves' columns use the standard continuous-time result
for betting a fraction c of full Kelly: the bankroll ever falls to x of its
starting value with probability x^(2/c - 1). Full Kelly halves the bank at some
point about half the time even when the edge is real. The last column assumes
only half the model's edge is real, which turns a fraction c into an effective
2c -- the point of the column.
"""

import re
import sys
import zipfile
from xml.sax.saxutils import escape

SHEET_PART = "xl/worksheets/sheet7.xml"
SHEET_NAME = "KELLY"
FRACTIONS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.33, 0.50, 1.00]


def stop(msg):
    sys.exit(f"STOPPED: {msg}\n  Nothing was written.")


# ------------------------------------------------------------- cells ------

def t(ref, s, text):
    return (f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">'
            f'{escape(text)}</t></is></c>')


def f(ref, s, formula, text=False):
    tt = ' t="str"' if text else ""
    return f'<c r="{ref}" s="{s}"{tt}><f>{escape(formula)}</f></c>'


def n(ref, s, value):
    return f'<c r="{ref}" s="{s}"><v>{value}</v></c>'


def blank(ref, s):
    return f'<c r="{ref}" s="{s}"/>'


# ------------------------------------------------------------- sheet ------

def build_sheet(st_pct2, st_bar):
    """Style ids are v7's own: 1 title, 3 bold label, 4 grey note, 9 header bar,
    10 bordered text, 5/7 yellow inputs (number / percent), 6 number,
    13 percent, 14 bold centred, 15 dollars. st_pct2 is the one added here."""
    rows = {}

    def put(r, cell):
        rows.setdefault(r, []).append(cell)

    def bar(r, label, last="I"):
        put(r, t(f"A{r}", st_bar, label))
        for col in "BCDEFGHI"[: "BCDEFGHI".index(last) + 1]:
            put(r, blank(f"{col}{r}", 9))

    put(1, t("A1", 1, "KELLY CALCULATOR"))
    put(2, t("A2", 4, "A sandbox for trying different bet sizes. Nothing on this tab "
                      "changes STAKE $ on SOCCER or AFL - those still use units."))

    # ---- the dial and the numbers it works from
    put(4, t("A4", 3, "Kelly fraction"))
    put(4, blank("B4", 5))
    put(4, t("C4", 4, "Type a fraction: 1 = full Kelly, 0.5 = half, 0.25 = quarter. "
                      "This is the only place it is set."))
    put(5, t("A5", 3, "Bankroll ($)"))
    put(5, f("B5", 15, "SETTINGS!$B$2"))
    put(5, t("C5", 4, "From SETTINGS."))
    put(6, t("A6", 3, "Your max stake ($)"))
    put(6, f("B6", 15, "SETTINGS!$B$5*SETTINGS!$B$3"))
    put(6, t("C6", 4, "Max units per bet x unit size, from SETTINGS. Every Kelly "
                      "stake is capped here."))
    put(7, t("A7", 3, "Betfair commission"))
    put(7, f("B7", 13, "SETTINGS!$B$8"))
    put(7, t("C7", 4, "From SETTINGS."))

    # ---- one bet, worked through
    bar(9, "TRY A BET")
    put(10, t("A10", 3, "Your chance it wins"))
    put(10, blank("B10", 7))
    put(10, t("C10", 4, "e.g. 55% - copy MODEL % from SOCCER or AFL"))
    put(11, t("A11", 3, "Betfair price"))
    put(11, blank("B11", 5))
    put(11, t("C11", 4, "The back price on Betfair"))
    netb = "($B$11-1)*(1-$B$7)"
    lines = [
        (12, "Fair price", 6, 'IF(B10>0,1/B10,"")', False),
        (13, "Your required price", 6,
         'IF(B10>0,1+((1+SETTINGS!$B$4)/B10-1)/(1-SETTINGS!$B$8),"")', False),
        (14, "Clears your required price?", 14,
         'IF(OR(B10="",B11=""),"",IF(B11>=B13,"YES","NO - no bet"))', True),
        (15, "Edge, after commission", 13,
         f'IF(OR(B10="",B11=""),"",B10*(1+{netb})-1)', False),
        (16, "Full Kelly (% of bankroll)", 13,
         f'IF(OR(B10="",B11="",B11<=1),"",MAX(0,(B10*(1+{netb})-1)/({netb})))', False),
        (17, "Kelly stake at your fraction", 15,
         'IF(OR(B16="",$B$4=""),"",IF(B14<>"YES",0,$B$4*B16*$B$5))', False),
        (18, "...after your max stake cap", 15, 'IF(B17="","",MIN(B17,$B$6))', False),
        (19, "Your usual stake (units)", 15,
         'IF(OR(B10="",B11=""),"",IF(B11<B13,0,MIN(SETTINGS!$B$5,MAX(0,'
         '(B10*(1+(B11-1)*(1-SETTINGS!$B$8))-1)/SETTINGS!$B$4))*SETTINGS!$B$3))', False),
    ]
    for r, label, s, formula, is_text in lines:
        put(r, t(f"A{r}", 10, label))
        put(r, f(f"B{r}", s, formula, text=is_text))
    put(16, f("C16", 4, 'IF(AND(B16<>"",B14<>"YES"),"Shown for interest - the price '
                        'does not clear your required price, so the stake is 0.","")',
              text=True))
    put(17, f("C17", 4, 'IF($B$4="","Type a Kelly fraction in B4 first.","")', text=True))
    put(18, f("C18", 4, 'IF(AND(B17<>"",B17>$B$6),"Capped - Kelly wants more than '
                        'your max stake.","")', text=True))

    # ---- the same bet at every fraction
    bar(21, "COMPARE FRACTIONS - the same bet at different sizes")
    heads = ["Kelly fraction", "Stake $", "% of bankroll", "Expected profit $",
             "Growth per bet", "Bets to double", "Chance it halves",
             "...if half edge real", "Over your max?"]
    for col, h in zip("ABCDEFGHI", heads):
        put(22, t(f"{col}22", 9, h))
    for i, frac in enumerate(FRACTIONS + [None]):
        r = 23 + i
        if frac is None:
            put(r, f(f"A{r}", 6, 'IF($B$4="","",$B$4)'))
        else:
            put(r, n(f"A{r}", 6, frac))
        put(r, f(f"B{r}", 15, f'IF(OR(A{r}="",$B$16="",$B$14<>"YES"),"",A{r}*$B$16*$B$5)'))
        put(r, f(f"C{r}", st_pct2, f'IF(B{r}="","",A{r}*$B$16)'))
        put(r, f(f"D{r}", 15, f'IF(B{r}="","",B{r}*$B$15)'))
        put(r, f(f"E{r}", st_pct2,
                 f'IF(B{r}="","",IFERROR($B$10*LN(1+C{r}*{netb})+(1-$B$10)*LN(1-C{r}),""))'))
        put(r, f(f"F{r}", 6, f'IF(E{r}="","",IF(E{r}<=0,"never",ROUND(LN(2)/E{r},0)))'))
        put(r, f(f"G{r}", st_pct2, f'IF(A{r}="","",IF(A{r}>=2,1,0.5^(2/A{r}-1)))'))
        put(r, f(f"H{r}", st_pct2, f'IF(A{r}="","",IF(A{r}>=1,1,0.5^(1/A{r}-1)))'))
        put(r, f(f"I{r}", 10, f'IF(B{r}="","",IF(B{r}>$B$6,"capped to "&TEXT($B$6,"$0.00"),""))',
                 text=True))
    put(31, t("J31", 4, "<- your fraction"))
    put(32, t("A32", 4, "'Chance it halves' = chance the bank drops to half at some point. "
                        "Neither of those two columns depends on the bet. "
                        "They are a rough guide: many small bets, an edge that holds steady."))

    # ---- the pricers' own best bets, both ways
    bar(34, "TODAY'S BEST BETS - Kelly stake beside your units stake")
    heads = ["Pricer / family", "Best bet", "Model %", "Betfair price", "Full Kelly",
             "Kelly stake $", "After your cap", "Units stake $", "Kelly minus units"]
    for col, h in zip("ABCDEFGHI", heads):
        put(35, t(f"{col}35", 9, h))
    sources = [("SOCCER", 35), ("SOCCER", 36), ("SOCCER", 37), ("AFL", 44), ("AFL", 45)]
    for i, (sheet, sr) in enumerate(sources):
        r = 36 + i
        put(r, f(f"A{r}", 10, f'"{sheet} - "&{sheet}!A{sr}', text=True))
        put(r, f(f"B{r}", 10, f"{sheet}!B{sr}", text=True))
        put(r, f(f"C{r}", 13, f"{sheet}!C{sr}"))
        put(r, f(f"D{r}", 6, f"{sheet}!F{sr}"))
        put(r, f(f"E{r}", 13, f"{sheet}!H{sr}"))
        put(r, f(f"F{r}", 15, f'IF(OR(E{r}="",$B$4=""),"",$B$4*E{r}*$B$5)'))
        put(r, f(f"G{r}", 15, f'IF(F{r}="","",MIN(F{r},$B$6))'))
        put(r, f(f"H{r}", 15, f'IF(E{r}="","",{sheet}!I{sr})'))
        put(r, f(f"I{r}", 15, f'IF(OR(G{r}="",H{r}=""),"",G{r}-H{r})'))
    put(41, t("A41", 3, "TOTAL"))
    for col in "FGH":
        put(41, f(f"{col}41", 15, f"SUM({col}36:{col}40)"))
    put(41, f("I41", 15, 'IF(COUNT(G36:G40)=0,"",G41-H41)', text=False))
    put(42, f("A42", 4, '"SOCCER is on fixture "&SOCCER!$B$3&": "&SOCCER!$B$5&" v "&SOCCER!$B$6'
                        '&"     AFL is on fixture "&AFL!$B$3&": "&AFL!$B$5&" v "&AFL!$B$6',
              text=True))

    # ---- plain English
    put(44, t("A44", 3, "HOW TO READ THIS"))
    notes = [
        "Kelly sizes a bet from your edge: the bigger the edge the model sees, the bigger the bet.",
        "That is also its weak spot. It trusts the model's percentage completely, so if the model "
        "is optimistic, Kelly bets most where the model is most wrong.",
        "The '...if half edge real' column shows that risk. Half Kelly on an edge that "
        "is really half the size is the same as full Kelly.",
        "Full Kelly halves the bank at some point about half the time, even when the edge is real. "
        "Fractions well under 0.5 are the usual choice.",
        "Every stake here is capped at your max stake from SETTINGS. Raising 'Max units per bet' "
        "lets Kelly run further - that is your call, not this tab's.",
        "Kelly stakes are only shown when the price clears your required price, the same gate "
        "the SOCCER and AFL tabs use.",
    ]
    for i, line in enumerate(notes):
        put(45 + i, t(f"A{45 + i}", 4, line))

    body = []
    for r in sorted(rows):
        cells = sorted(rows[r], key=lambda c: _col_index(re.match(r'<c r="([A-Z]+)', c).group(1)))
        body.append(f'<row r="{r}">{"".join(cells)}</row>')

    validation = (
        '<dataValidations count="3">'
        '<dataValidation type="decimal" allowBlank="1" showErrorMessage="1" '
        'errorTitle="Kelly fraction" error="Type a number between 0 and 1, e.g. 0.25." '
        'sqref="B4"><formula1>0</formula1><formula2>1</formula2></dataValidation>'
        '<dataValidation type="decimal" allowBlank="1" showErrorMessage="1" '
        'errorTitle="Chance" error="Type a percentage between 0% and 100%, e.g. 55%." '
        'sqref="B10"><formula1>0</formula1><formula2>1</formula2></dataValidation>'
        '<dataValidation type="decimal" operator="greaterThan" allowBlank="1" '
        'showErrorMessage="1" errorTitle="Betfair price" '
        'error="Betfair prices are above 1, e.g. 2.10." sqref="B11">'
        '<formula1>1</formula1></dataValidation></dataValidations>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetPr><pageSetUpPr fitToPage="1"/></sheetPr>'
        '<dimension ref="A1:J50"/>'
        '<sheetViews><sheetView workbookViewId="0"><selection activeCell="B4" sqref="B4"/>'
        '</sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="14.5"/>'
        '<cols><col min="1" max="1" width="32" customWidth="1"/>'
        '<col min="2" max="2" width="16" customWidth="1"/>'
        '<col min="3" max="6" width="15" customWidth="1"/>'
        '<col min="7" max="8" width="17" customWidth="1"/>'
        '<col min="9" max="9" width="16" customWidth="1"/>'
        '<col min="10" max="10" width="16" customWidth="1"/></cols>'
        f'<sheetData>{"".join(body)}</sheetData>'
        f'{validation}'
        '<pageMargins left="0.5" right="0.5" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
        '<pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"/>'
        '</worksheet>')


def _col_index(letters):
    v = 0
    for ch in letters:
        v = v * 26 + ord(ch) - 64
    return v


# ------------------------------------------------------- registration ------

def add_styles(xml):
    """Two styles v7 lacks: 0.00% on the bordered grid, for small percentages,
    and v7's navy header bar left-aligned, so a long section title is not
    centred off both edges of its cell."""
    m = re.search(r'<cellXfs count="(\d+)">(.*?)</cellXfs>', xml, re.S)
    k = int(m.group(1))
    xf = ('<xf numFmtId="10" fontId="2" fillId="0" borderId="1" xfId="0" '
          'applyNumberFormat="1" applyFont="1" applyBorder="1"/>'
          '<xf numFmtId="0" fontId="7" fillId="3" borderId="1" xfId="0" '
          'applyFont="1" applyFill="1" applyBorder="1"/>')
    return xml.replace(m.group(0), f'<cellXfs count="{k + 2}">{m.group(2)}{xf}</cellXfs>'), k, k + 1


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.split("\n\n")[1])
    src, dst = sys.argv[1], sys.argv[2]
    if src == dst:
        stop("write to a new file; the original is never overwritten.")
    zin = zipfile.ZipFile(src)
    parts = {i.filename: zin.read(i.filename) for i in zin.infolist()}
    get = lambda p: parts[p].decode("utf-8")

    if b"HRS AHEAD (auto)" not in parts.get("xl/worksheets/sheet4.xml", b""):
        stop("this is not a patched v8. Run tools/patch_fixture_dbase.py first.")
    wb = get("xl/workbook.xml")
    if f'name="{SHEET_NAME}"' in wb or SHEET_PART in parts:
        stop(f"the workbook already has a {SHEET_NAME} tab.")

    rels = get("xl/_rels/workbook.xml.rels")
    used = {int(x) for x in re.findall(r'Id="rId(\d+)"', rels)}
    rid = f"rId{max(used) + 1}"
    sheet_id = max(int(x) for x in re.findall(r'sheetId="(\d+)"', wb)) + 1

    styles, st_pct2, st_bar = add_styles(get("xl/styles.xml"))
    changed = {
        "xl/styles.xml": styles,
        "xl/workbook.xml": wb.replace(
            "</sheets>", f'<sheet name="{SHEET_NAME}" sheetId="{sheet_id}" r:id="{rid}"/></sheets>'),
        "xl/_rels/workbook.xml.rels": rels.replace(
            "</Relationships>",
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
            f'officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet7.xml"/></Relationships>'),
        "[Content_Types].xml": get("[Content_Types].xml").replace(
            "</Types>",
            f'<Override PartName="/{SHEET_PART}" ContentType="application/'
            f'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'),
    }
    app = get("docProps/app.xml")
    m = re.search(r'<vt:i4>(\d+)</vt:i4>', app)
    m2 = re.search(r'<TitlesOfParts><vt:vector size="(\d+)" baseType="lpstr">', app)
    if m and m2:
        app = app.replace(m.group(0), f"<vt:i4>{int(m.group(1)) + 1}</vt:i4>", 1)
        app = app.replace(m2.group(0),
                          f'<TitlesOfParts><vt:vector size="{int(m2.group(1)) + 1}" baseType="lpstr">')
        app = app.replace("</vt:vector></TitlesOfParts>",
                          f"<vt:lpstr>{SHEET_NAME}</vt:lpstr></vt:vector></TitlesOfParts>")
        changed["docProps/app.xml"] = app

    readme = get("xl/worksheets/sheet1.xml")
    line = ('<row r="11"><c r="A11" s="2" t="inlineStr"><is><t xml:space="preserve">'
            'KELLY      Try different bet sizes. A sandbox - it does not change SOCCER or '
            'AFL stakes.</t></is></c></row>')
    old11 = re.search(r'<row r="11"[^>]*?(?:/>|>(.*?)</row>)', readme, re.S)
    if old11:
        # v7 keeps row 11 as a spacer: an empty, formatted A11. Anything with a
        # value in it is someone's text and is left alone.
        if re.search(r'<c [^>]*[^/]>', old11.group(1) or ""):
            stop("README row 11 is not blank; refusing to write over it.")
        readme = readme.replace(old11.group(0), line, 1)
    else:
        readme, k = re.subn(r'(<row r="10"[^>]*>.*?</row>)', lambda m: m.group(1) + line,
                            readme, count=1, flags=re.S)
        if k != 1:
            stop("README row 10 not found.")
    changed["xl/worksheets/sheet1.xml"] = readme

    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = changed[info.filename].encode("utf-8") \
                if info.filename in changed else parts[info.filename]
            zout.writestr(info, data)
        zout.writestr(SHEET_PART, build_sheet(st_pct2, st_bar).encode("utf-8"))

    print(f"Wrote {dst}")
    print(f"  new {SHEET_NAME} tab: one yellow dial (B4), a bet to try, a table of "
          f"{len(FRACTIONS)} fractions,")
    print("  and today's SOCCER and AFL best bets with the Kelly stake beside the units stake")
    print("  SOCCER and AFL stakes unchanged; Power Query and DATA copied unchanged")


if __name__ == "__main__":
    main()
