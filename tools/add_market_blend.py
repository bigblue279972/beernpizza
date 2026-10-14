#!/usr/bin/env python3
"""Blend the model with the Betfair price before judging a soccer bet (v9 -> v10).

    python tools/add_market_blend.py "FIXTURE DBASE v9.xlsx" "FIXTURE DBASE v10.xlsx"

Standard library only; worksheet XML is edited in place and every other part is
copied byte for byte, so Power Query is untouched.

Why. The pricer flagged a bet whenever the model's chance beat the price by the
buffer -- a RELATIVE margin. Every model is a few points out on every game, and
a few points is a large relative margin on an outsider but a small one on a
favourite, so model error passes the gate far more often at long prices, and the
stake rule then puts the biggest stakes there. A simulation of a fair market
reproduced the user's experience: about 3 in 4 flagged bets on the outsider,
almost none on the favourite, a claimed edge near +20% and a real value near -5%.

What changes, on SOCCER rows 12-31 and the KELLY tab:

- The chance used is  w x model + (1 - w) x (1 / Betfair price).  w is the new
  SETTINGS "Model weight" (B11, 30%).
- No bet above the new SETTINGS "Max price" (B12, 4.00). Blending alone still
  leaves the remaining bets on outsiders, because the model's share of the edge
  grows with the price; the ceiling is what removes them. In the simulation the
  two together flagged nothing in a fair market -- the right answer when the
  model knows nothing the market doesn't.
- REQUIRED PRICE is still "the lowest price worth taking", now solved for the
  blend: the price D at which the blended edge equals the buffer, the larger
  root of  w p g D^2 + (w p (1-g) + (1-w) g - (1+buffer)) D + (1-w)(1-g) = 0,
  g = 1 - commission. The smaller root is always below 1, so for any real
  price "D >= required" is exactly "blended edge >= buffer". At w = 1 it reduces
  to v9's formula.
- EDGE, UNITS, STAKE and KELLY all use the blended chance, so the decision block
  picks each family's best bet on the blended Kelly, unchanged in form.

AFL is left as it is: its line and total markets sit near even money, where the
relative-margin problem is small, and its season is over until March.
"""

import re
import sys
import zipfile
from xml.sax.saxutils import escape

SETTINGS, SOCCER, KELLY, README = (f"xl/worksheets/sheet{n}.xml" for n in (2, 5, 7, 1))
W, MX = "SETTINGS!$B$11", "SETTINGS!$B$12"
BUF, COM, MAXU, UNIT = "SETTINGS!$B$4", "SETTINGS!$B$8", "SETTINGS!$B$5", "SETTINGS!$B$3"
G = f"(1-{COM})"
ROWS = range(12, 32)


def stop(msg):
    sys.exit(f"STOPPED: {msg}\n  Nothing was written.")


def required(p):
    """Lowest price at which the blended edge reaches the buffer (larger root)."""
    a = f"({W}*{p}*{G})"
    b = f"({W}*{p}*(1-{G})+(1-{W})*{G}-(1+{BUF}))"
    c = f"((1-{W})*(1-{G}))"
    return f"IFERROR(IF(OR({p}<=0,{a}<=0),\"\",(-{b}+SQRT({b}^2-4*{a}*{c}))/(2*{a})),\"\")"


def blended_edge(p, d):
    return f"(({W}*{p}+(1-{W})/{d})*(1+({d}-1)*{G})-1)"


def cell_f(ref, s, formula, text=False):
    t = ' t="str"' if text else ""
    return f'<c r="{ref}" s="{s}"{t}><f>{escape(formula)}</f></c>'


def cell_t(ref, s, text):
    return (f'<c r="{ref}" s="{s}" t="inlineStr"><is><t xml:space="preserve">'
            f'{escape(text)}</t></is></c>')


def replace_cell(xml, ref, new):
    m = re.search(r'<c r="%s"[^>]*?(?:/>|>.*?</c>)' % ref, xml, re.S)
    if not m:
        stop(f"cell {ref} not found")
    return xml.replace(m.group(0), new, 1)


def style_of(xml, ref):
    m = re.search(r'<c r="%s"[^>]*?\ss="(\d+)"' % ref, xml)
    return m.group(1) if m else "0"


def insert_cells(xml, row, cells):
    """Add cells to a row in column order, creating the row in row order if needed.

    An existing cell with no content (just formatting) is replaced; one with a
    value or formula stops the run rather than being overwritten.
    """
    col = lambda c: sum((ord(ch) - 64) * 26 ** i for i, ch in
                        enumerate(reversed(re.match(r'<c r="([A-Z]+)', c).group(1))))
    m = re.search(r'<row r="%d"([^>]*?)(?:/>|>(.*?)</row>)' % row, xml, re.S)
    if not m:
        new_row = f'<row r="{row}" spans="1:11">{"".join(sorted(cells, key=col))}</row>'
        for later in re.finditer(r'<row r="(\d+)"', xml):
            if int(later.group(1)) > row:
                return xml[:later.start()] + new_row + xml[later.start():]
        return xml.replace("</sheetData>", new_row + "</sheetData>", 1)
    body = m.group(2) or ""
    have = re.findall(r'<c r="[A-Z]+\d+"(?:[^>]*?/>|[^>]*>.*?</c>)', body, re.S)
    for c in cells:
        ref = re.match(r'<c r="([A-Z]+\d+)"', c).group(1)
        for h in list(have):
            if h.startswith(f'<c r="{ref}"'):
                if h.endswith("/>"):
                    have.remove(h)                       # formatting only: replace it
                else:
                    stop(f"{ref} is not empty; refusing to write over it.")
    allc = sorted(have + list(cells), key=col)
    attrs = re.sub(r'spans="[^"]*"', 'spans="1:11"', m.group(1))
    return xml.replace(m.group(0), f'<row r="{row}"{attrs}>{"".join(allc)}</row>', 1)


# ------------------------------------------------------------- sheets ------

def patch_settings(xml):
    xml = insert_cells(xml, 10, [cell_t("A10", 20, "Market blend")])
    xml = insert_cells(xml, 11, [
        cell_t("A11", 3, "Model weight"),
        '<c r="B11" s="7"><v>0.3</v></c>',
        cell_t("C11", 4, "Share of the chance taken from the model; the rest comes from the "
                         "Betfair price. 30% = 30% model + 70% market. 100% = v9's model only."),
    ])
    xml = insert_cells(xml, 12, [
        cell_t("A12", 3, "Max price"),
        '<c r="B12" s="5"><v>4</v></c>',
        cell_t("C12", 4, "No soccer bet above this price. Long prices are where model error "
                         "looks most like value."),
    ])
    return xml


def patch_soccer(xml):
    if W in xml:
        stop("SOCCER already uses the market blend.")
    for r in ROWS:
        if f'<c r="C{r}"' not in xml:
            stop(f"SOCCER row {r} is not a market row.")
        p, d, c = f"$B{r}", f"$D{r}", f"$C{r}"
        out = f'OR({d}="",{c}="",{d}<{c},{d}>{MX})'
        e = blended_edge(p, d)
        st = lambda col: style_of(xml, f"{col}{r}") if f'<c r="{col}{r}"' in xml \
            else style_of(xml, f"{col}12")
        new = {
            "C": cell_f(f"C{r}", st("C"), required(p)),
            "E": cell_f(f"E{r}", st("E"),
                        f'IF({d}="","",IF({d}>{MX},"no - over "&TEXT({MX},"0.00"),'
                        f'IF(OR({c}="",{d}<{c}),"no","BET")))', text=True),
            "F": cell_f(f"F{r}", st("F"),
                        f"IF({out},0,MIN({MAXU},MAX(0,{e}/{BUF})))"),
            "H": cell_f(f"H{r}", st("H"), f'IF({out},"",{e})'),
            "I": cell_f(f"I{r}", st("I"), f'IF({out},"",{e}/(({d}-1)*{G}))'),
        }
        for col, cell in new.items():
            if f'<c r="{col}{r}"' in xml:
                xml = replace_cell(xml, f"{col}{r}", cell)
            else:
                xml = insert_cells(xml, r, [cell])
    for ref, text in (("H11", "EDGE (blend)"), ("I11", "KELLY (blend)")):
        xml = replace_cell(xml, ref, cell_t(ref, style_of(xml, ref), text))
    note = (f'"Edge, stake and Kelly use "&TEXT({W},"0%")&" model + "&TEXT(1-{W},"0%")'
            f'&" Betfair price. No bets above "&TEXT({MX},"0.00")&". Change both on SETTINGS '
            f'rows 11-12."')
    return insert_cells(xml, 10, [cell_f("A10", 4, note, text=True)])


def patch_kelly(xml):
    if "<c r=\"B13\"" not in xml or W in xml:
        stop("KELLY tab is not the v9 one.")
    netb = "($B$11-1)*(1-$B$7)"
    xml = replace_cell(xml, "B13", cell_f("B13", 6, required("B10").replace("$B10", "B10")))
    xml = replace_cell(xml, "B14", cell_f("B14", 14,
        f'IF(OR(B10="",B11=""),"",IF(B11>{MX},"NO - over max price",'
        f'IF(OR(B13="",B11<B13),"NO - no bet","YES")))', text=True))
    xml = replace_cell(xml, "B15", cell_f("B15", 13, f'IF(OR(B10="",B11=""),"",B20*(1+{netb})-1)'))
    xml = replace_cell(xml, "B16", cell_f("B16", 13,
        f'IF(OR(B10="",B11="",B11<=1),"",MAX(0,(B20*(1+{netb})-1)/({netb})))'))
    xml = replace_cell(xml, "B19", cell_f("B19", 15,
        f'IF(OR(B10="",B11=""),"",IF(B14<>"YES",0,MIN({MAXU},MAX(0,B15/{BUF}))*{UNIT}))'))
    xml = replace_cell(xml, "A15", cell_t("A15", 10, "Edge (blend, after commission)"))
    xml = replace_cell(xml, "A16", cell_t("A16", 10, "Full Kelly (blend, % of bankroll)"))
    xml = insert_cells(xml, 20, [
        cell_f("A20", 10, f'"Chance used ("&TEXT({W},"0%")&" model + "&TEXT(1-{W},"0%")&" market)"',
               text=True),
        cell_f("B20", 13, f'IF(OR(B10="",B11=""),"",{W}*B10+(1-{W})/B11)'),
    ])
    # growth per bet must use the chance the stake was sized on
    xml, k = re.subn(r"\$B\$10\*LN\(", "$B$20*LN(", xml)
    xml, k2 = re.subn(r"\(1-\$B\$10\)\*LN\(", "(1-$B$20)*LN(", xml)
    if k != 9 or k2 != 9:
        stop(f"KELLY growth formulas not as expected ({k}, {k2}).")
    return xml


def patch_readme(xml):
    old = re.search(r'<c r="A31"[^>]*?(?:/>|>.*?</c>)', xml, re.S)
    if old:
        xml = xml.replace(old.group(0), cell_t(
            "A31", style_of(xml, "A31"),
            "REQUIRED PRICE  Lowest price worth taking, judged on the model blended with "
            "the Betfair price (SETTINGS rows 11-12). No soccer bet above Max price."), 1)
    return xml


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__.split("\n\n")[1])
    src, dst = sys.argv[1], sys.argv[2]
    if src == dst:
        stop("write to a new file; the original is never overwritten.")
    z = zipfile.ZipFile(src)
    parts = {i.filename: z.read(i.filename) for i in z.infolist()}
    if KELLY not in parts:
        stop("no KELLY tab; build v9 first with tools/add_kelly_tab.py.")
    get = lambda p: parts[p].decode("utf-8")
    changed = {
        SETTINGS: patch_settings(get(SETTINGS)),
        SOCCER: patch_soccer(get(SOCCER)),
        KELLY: patch_kelly(get(KELLY)),
        README: patch_readme(get(README)),
    }
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as out:
        for info in z.infolist():
            out.writestr(info, changed[info.filename].encode("utf-8")
                         if info.filename in changed else parts[info.filename])
    print(f"Wrote {dst}")
    print("  SETTINGS: Model weight 30% (B11), Max price 4.00 (B12)")
    print("  SOCCER rows 12-31: required price, BET?, units, edge and Kelly on the blend")
    print("  KELLY tab: the same rules; AFL, FIXTURES and Power Query unchanged")


if __name__ == "__main__":
    main()
