"""
AFL closing-line backfill, from the free Australia Sports Betting workbook
(aussportsbetting.com/historical_data/afl.xlsx - results plus bookmaker
open/min/max/CLOSE odds, updated weekly).

Covers the three markets that are 104 of the 111 AFL bets in the sample
history: head-to-head, line, and total points.

Two deliberate design choices
-----------------------------
* COLUMN NAMES ARE DETECTED, NOT ASSUMED. The workbook's exact headers could
  not be verified when this was written, so every field is found by pattern
  over the real header row and the mapping is printed for you to check. If a
  needed column is missing it says so and dumps the header, rather than
  guessing and producing confidently wrong CLV.
* A LINE OR TOTAL THAT MOVED IS NOT PRICED. If you took Collingwood -36.5 and
  the market closed at -35.5, those are different bets. Converting between them
  needs an assumed spread of match margins - a number that would have to come
  from the Rulebook, not from me. Such bets are reported with the difference so
  the size of the problem is visible before anyone invents a parameter.

Reads .xlsx with the standard library, so there is nothing to install.

Usage:
  python clv_afl.py ExchangeBets_Settled.csv              # downloads afl.xlsx
  python clv_afl.py ExchangeBets_Settled.csv --xlsx afl.xlsx
  python clv_afl.py --inspect afl.xlsx        # just show me the columns
"""
import argparse
import csv
import os
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

AFL_XLSX = "https://www.aussportsbetting.com/historical_data/afl.xlsx"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# 18 clubs, with every alias Betfair and the workbook are likely to use.
# A fixed league gets an exact lookup - fuzzy matching earns nothing here and
# risks confusing Melbourne with North Melbourne.
CLUBS = {
    "Adelaide": ["adelaide", "adelaide crows", "crows"],
    "Brisbane Lions": ["brisbane", "brisbane lions", "lions"],
    "Carlton": ["carlton", "blues"],
    "Collingwood": ["collingwood", "magpies", "pies"],
    "Essendon": ["essendon", "bombers"],
    "Fremantle": ["fremantle", "dockers", "freo"],
    "Geelong": ["geelong", "geelong cats", "cats"],
    "Gold Coast": ["gold coast", "gold coast suns", "suns"],
    "Greater Western Sydney": ["gws", "gws giants", "greater western sydney",
                               "giants", "gws gnt"],
    "Hawthorn": ["hawthorn", "hawks"],
    "Melbourne": ["melbourne", "demons", "dees"],
    "North Melbourne": ["north melbourne", "kangaroos", "roos", "north"],
    "Port Adelaide": ["port adelaide", "power", "port"],
    "Richmond": ["richmond", "tigers"],
    "St Kilda": ["st kilda", "saints", "st. kilda", "stkilda"],
    "Sydney": ["sydney", "sydney swans", "swans"],
    "West Coast": ["west coast", "west coast eagles", "eagles"],
    "Western Bulldogs": ["western bulldogs", "bulldogs", "footscray"],
}
ALIAS = {a: canon for canon, aliases in CLUBS.items() for a in aliases}


# longest aliases first, so "north melbourne" never collapses to "melbourne"
_ALIAS_BY_LEN = sorted(ALIAS, key=len, reverse=True)


def club(name):
    """Canonical club, tolerating the nickname Betfair sometimes prefixes:
    'SUNS Gold Coast', 'Cats Geelong', 'Crows Adelaide'."""
    n = re.sub(r"[^a-z ]+", " ", (name or "").lower())
    n = re.sub(r"\s+", " ", n).strip()
    if not n:
        return None
    if n in ALIAS:                       # exact first: 'port adelaide' wins
        return ALIAS[n]
    for a in _ALIAS_BY_LEN:              # then the longest whole-word edge
        if n.endswith(" " + a) or n.startswith(a + " "):
            return ALIAS[a]
    return None


# Header patterns, most specific first. Every odds field must be a CLOSING one.
WANT = {
    "date":      [r"^date$", r"^match date$"],
    "home":      [r"^home team$", r"^home$"],
    "away":      [r"^away team$", r"^away$"],
    "h2h_home":  [r"^home odds close$", r"^home close$", r"^home odds$"],
    "h2h_away":  [r"^away odds close$", r"^away close$", r"^away odds$"],
    "line_home": [r"^home line close$", r"^home line$", r"^line close$"],
    "line_away": [r"^away line close$", r"^away line$"],
    "lodds_home": [r"^home line odds close$", r"^home line odds$"],
    "lodds_away": [r"^away line odds close$", r"^away line odds$"],
    "total":     [r"^total score close$", r"^total close$", r"^total score$",
                  r"^total points close$"],
    "over":      [r"^over line odds close$", r"^over odds close$",
                  r"^over line odds$", r"^over odds$"],
    "under":     [r"^under line odds close$", r"^under odds close$",
                  r"^under line odds$", r"^under odds$"],
}
NEVER = re.compile(r"\b(open|min|max)\b", re.I)   # never benchmark on these


def detect(header):
    """Map each needed field to a real column, refusing open/min/max odds."""
    found, used = {}, set()
    for field, pats in WANT.items():
        odds_field = field not in ("date", "home", "away")
        for pat in pats:
            for h in header:
                if h in used or not h:
                    continue
                if odds_field and NEVER.search(h):
                    continue
                if re.match(pat, h.strip(), re.I):
                    found[field] = h
                    used.add(h)
                    break
            if field in found:
                break
    return found


# ------------------------------------------------------------- xlsx reading
def col_letters(ref):
    return "".join(ch for ch in ref if ch.isalpha())


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_xlsx(path):
    """Minimal .xlsx reader - a workbook is a zip of XML, so no dependency
    is needed just to read one sheet of numbers and names."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
        sheets = sorted(n for n in z.namelist()
                        if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        if not sheets:
            raise ValueError("no worksheet found inside the workbook")
        root = ET.fromstring(z.read(sheets[0]))
        rows = []
        for r in root.iter(f"{NS}row"):
            cells = {}
            for c in r.findall(f"{NS}c"):
                idx = col_index(col_letters(c.get("r", "A1")))
                t = c.get("t")
                if t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{NS}t"))
                else:
                    v = c.find(f"{NS}v")
                    if v is None or v.text is None:
                        continue
                    if t == "s":
                        i = int(v.text)
                        val = shared[i] if 0 <= i < len(shared) else ""
                    else:
                        val = v.text
                cells[idx] = val
            if cells:
                rows.append(cells)
    if not rows:
        return [], []
    width = max(max(r) for r in rows if r) + 1
    header = [str(rows[0].get(i, "")).strip() for i in range(width)]
    out = []
    for r in rows[1:]:
        out.append({header[i]: r.get(i) for i in range(width) if header[i]})
    return header, out


def as_date(v):
    if v is None:
        return None
    s = str(v).strip()
    try:                                  # Excel stores dates as a day count
        f = float(s)
        if 20000 < f < 80000:
            return (datetime(1899, 12, 30) + timedelta(days=int(f))).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%Y-%m-%dT%H:%M:%S",
                "%d %b %Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s[:len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    return None


def as_num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ pricing
def fair_afl(fx, market, selection, home, away, cols):
    """Return (fair_odds, raw_odds, overround, note)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from clv_backfill import devig
    m = (market or "").lower()
    sel_club = club(re.sub(r"\s*[+-]?[\d.]+$", "", selection or "").strip())

    if "match odds" in m:
        h, a = fx.get("h2h_home"), fx.get("h2h_away")
        if not (h and a):
            return None, None, None, "no closing head-to-head price"
        probs, over = devig([h, a])
        if sel_club == home:
            return 1 / probs[0], h, over, ""
        if sel_club == away:
            return 1 / probs[1], a, over, ""
        return None, None, None, f"selection '{selection}' is neither club"

    if "handicap" in m:
        lh, oh, oa = fx.get("line_home"), fx.get("lodds_home"), fx.get("lodds_away")
        if lh is None or not (oh and oa):
            return None, None, None, "no closing line or line odds"
        mt = re.search(r"([+-]?[\d.]+)$", (selection or "").strip())
        if not mt:
            return None, None, None, "bet line unreadable"
        bet_line = float(mt.group(1))
        la = fx.get("line_away")
        book = lh if sel_club == home else (la if la is not None else -lh)
        if sel_club not in (home, away):
            return None, None, None, f"selection '{selection}' is neither club"
        if abs(bet_line - book) > 1e-6:
            return None, None, None, f"line moved (bet {bet_line:+}, close {book:+})"
        probs, over = devig([oh, oa])
        return ((1 / probs[0], oh, over, "") if sel_club == home
                else (1 / probs[1], oa, over, ""))

    if "total points" in m:
        tot, o, u = fx.get("total"), fx.get("over"), fx.get("under")
        if tot is None or not (o and u):
            return None, None, None, "no closing total or total odds"
        mt = re.search(r"([+-]?[\d.]+)$", (selection or "").strip())
        if not mt:
            return None, None, None, "bet total unreadable"
        bet_tot = abs(float(mt.group(1)))
        if abs(bet_tot - tot) > 1e-6:
            return None, None, None, f"total moved (bet {bet_tot}, close {tot})"
        probs, over = devig([o, u])
        if re.match(r"\s*over", selection or "", re.I):
            return 1 / probs[0], o, over, ""
        return 1 / probs[1], u, over, ""

    return None, None, None, "market not covered"


# ---------------------------------------------------------------------- main
OUT = ["settled", "home", "away", "market", "selection", "side", "odds_taken",
       "stake", "at_risk", "profit", "fx_date", "fx_home", "fx_away",
       "close_raw", "close_fair", "overround", "clv_pct", "clv_dollar",
       "beat_close", "status", "note"]


def load_fixtures(path, verbose=True):
    header, rows = read_xlsx(path)
    cols = detect(header)
    if verbose:
        print(f"   {len(rows)} rows, {len(header)} columns")
        print("   column mapping detected:")
        for f in WANT:
            print(f"      {f:<11} -> {cols.get(f) or '*** NOT FOUND ***'}")
    need = ["date", "home", "away"]
    if any(f not in cols for f in need):
        print("\n   Could not find the date/team columns. Full header row:")
        print("   " + " | ".join(h for h in header if h))
        return None, cols, header
    fixtures = {}
    for r in rows:
        d = as_date(r.get(cols["date"]))
        h, a = club(r.get(cols["home"])), club(r.get(cols["away"]))
        if not (d and h and a):
            continue
        fx = {"date": d, "home": h, "away": a,
              "raw_home": r.get(cols["home"]), "raw_away": r.get(cols["away"])}
        for f in WANT:
            if f in ("date", "home", "away"):
                continue
            fx[f] = as_num(r.get(cols[f])) if f in cols else None
        fixtures.setdefault((d, h, a), fx)
    return fixtures, cols, header


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bets", nargs="?", help="Betfair ExchangeBets Settled CSV")
    ap.add_argument("--xlsx", default="afl.xlsx")
    ap.add_argument("--inspect", metavar="FILE", help="just show the columns and exit")
    ap.add_argument("--out", default="clv_afl.csv")
    args = ap.parse_args()

    if args.inspect:
        header, rows = read_xlsx(args.inspect)
        print(f"{len(rows)} data rows, {len(header)} columns\n")
        print("HEADER:")
        for i, h in enumerate(header):
            if h:
                print(f"   {i:>3}  {h}")
        print("\nFIRST 2 ROWS:")
        for r in rows[:2]:
            print("   " + " | ".join(f"{k}={v}" for k, v in list(r.items())[:14]))
        print("\nDETECTED MAPPING:")
        for f, c in detect(header).items():
            print(f"   {f:<11} -> {c}")
        return

    if not args.bets:
        ap.error("give me the Betfair CSV, or use --inspect FILE")

    if not os.path.exists(args.xlsx):
        print(f"Downloading {AFL_XLSX} ...")
        try:
            req = urllib.request.Request(AFL_XLSX, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                open(args.xlsx, "wb").write(resp.read())
            print(f"   saved {args.xlsx} ({os.path.getsize(args.xlsx)//1024} KB)")
        except Exception as e:                                   # noqa: BLE001
            print(f"   download failed ({type(e).__name__}). Open this in your browser")
            print(f"   and save it next to this script, then run again:\n   {AFL_XLSX}")
            sys.exit(1)

    print(f"\nReading {args.xlsx}")
    fixtures, cols, header = load_fixtures(args.xlsx)
    if fixtures is None:
        sys.exit(1)
    print(f"   {len(fixtures)} AFL fixtures with both clubs recognised")

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from betfair_analyse import parse as parse_bets
    from clv_backfill import split_event_selection, clv_of

    bets = parse_bets(args.bets)
    rows, stats = [], {}

    def bump(k):
        stats[k] = stats.get(k, 0) + 1

    for b in bets:
        parts = split_event_selection(b["head"], b["market"])
        if not parts:
            continue
        home, away, sel = parts
        ch, ca = club(home), club(away)
        if not (ch and ca):
            continue                       # not an AFL fixture
        base = {"settled": b["settled"].date().isoformat(), "home": home,
                "away": away, "market": b["market"], "selection": sel,
                "side": b["side"], "odds_taken": b["odds"], "stake": b["stake"],
                "profit": b["pl"], "fx_date": "", "fx_home": "", "fx_away": "",
                "close_raw": "", "close_fair": "", "overround": "", "at_risk": "",
                "clv_pct": "", "clv_dollar": "", "beat_close": "", "note": ""}
        fx = None
        for off in (0, -1, 1, -2):         # AFL is often late night AEST -> UTC slip
            fx = fixtures.get((b["settled"].date() + timedelta(days=off), ch, ca))
            if fx:
                break
        if not fx:
            base["status"] = "NO FIXTURE"
            bump("NO FIXTURE"); rows.append(base); continue
        base.update(fx_date=fx["date"].isoformat(), fx_home=fx["raw_home"],
                    fx_away=fx["raw_away"])
        fair, raw, over, note = fair_afl(fx, b["market"], sel, ch, ca, cols)
        base["note"] = note
        if not fair:
            base["status"] = "NO CLOSING PRICE"
            bump(re.sub(r"[-\d.+]+", "N", note) if "moved" in note else note)
            rows.append(base); continue
        dollars, pct, at_risk = clv_of(b["side"], b["odds"], b["stake"], fair)
        base.update(status="OK", close_fair=round(fair, 4), close_raw=raw,
                    overround=(round(over, 4) if over else ""),
                    at_risk=round(at_risk, 2), clv_dollar=round(dollars, 4),
                    clv_pct=(round(pct, 6) if pct is not None else ""),
                    beat_close="YES" if dollars > 0 else "NO")
        bump("OK"); rows.append(base)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    ok = [r for r in rows if r["status"] == "OK"]
    print("\n" + "=" * 66)
    print(f"{len(rows)} AFL bets found, {len(ok)} priced against the close "
          f"({len(ok)/len(rows):.0%})" if rows else "no AFL bets found")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        if k != "OK":
            print(f"   {v:>4}  {k}")
    if ok:
        risk = sum(r["at_risk"] for r in ok)
        clv = sum(r["clv_dollar"] for r in ok)
        beat = sum(1 for r in ok if r["beat_close"] == "YES")
        pnl = sum(r["profit"] for r in ok)
        print(f"\n   turnover on those   ${risk:,.2f}")
        print(f"   CLV                 ${clv:,.2f}  ({clv/risk:+.2%})")
        print(f"   beat the close      {beat}/{len(ok)} = {beat/len(ok):.1%}")
        print(f"   actual P/L          ${pnl:,.2f}  (gross of commission)")
        print(f"   luck                ${pnl-clv:,.2f}")
    print(f"\n   written: {args.out}")
    print("=" * 66)


if __name__ == "__main__":
    main()
