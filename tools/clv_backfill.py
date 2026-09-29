"""
STEP 2 - Backfill Closing Line Value from football-data.co.uk.

The Betfair export has no closing price, so CLV cannot be computed from it.
football-data.co.uk publishes free per-league season CSVs that DO carry closing
odds; their convention is an extra "C" in the column code, so B365CH is Bet365's
closing home price and PSCH/PSCD/PSCA are Pinnacle's closing 1X2.

Pinnacle's closing line is the sharpest public benchmark in soccer, so it is
preferred wherever present, falling back to the market average.

Scope: CLUB football in the leagues football-data covers. It cannot reach
international fixtures or AFL - those need other sources.

Method
------
1. Parse each Betfair bet into (date, home, away, market, selection).
2. Match to a fixture on date (+/- 1 day, since settlement can cross midnight
   UTC) and fuzzy team names.
3. Read that fixture's CLOSING odds. Opening odds are NEVER silently
   substituted - a wrong benchmark is worse than none.
4. Strip the bookmaker margin, because a bookmaker price includes overround and
   a Betfair price does not; comparing them raw would overstate CLV on every
   single bet.
5. CLV = what you took against the de-vigged closing price.

Usage:
  python clv_backfill.py bets.csv                 # downloads what it needs
  python clv_backfill.py bets.csv --data-dir FOLDER   # use local files
"""
import argparse
import csv
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from difflib import SequenceMatcher

BASE = "https://www.football-data.co.uk"
# main European divisions, then the "extra" worldwide files
MAIN_DIVS = ["E0", "E1", "E2", "E3", "EC", "SC0", "SC1", "SC2", "SC3", "D1", "D2",
             "I1", "I2", "SP1", "SP2", "F1", "F2", "N1", "B1", "P1", "T1", "G1"]
EXTRA = ["ARG", "AUT", "BRA", "CHN", "DNK", "FIN", "IRL", "JPN", "MEX", "NOR",
         "POL", "ROU", "RUS", "SWE", "SWZ", "USA"]

# Closing-odds column candidates, best benchmark first. Pinnacle > market
# average > max > single bookmaker. NOTHING here may be an opening-odds column.
COL_1X2 = {
    "H": ["PSCH", "PCH", "AvgCH", "MaxCH", "B365CH", "BFECH", "WHCH", "VCCH"],
    "D": ["PSCD", "PCD", "AvgCD", "MaxCD", "B365CD", "BFECD", "WHCD", "VCCD"],
    "A": ["PSCA", "PCA", "AvgCA", "MaxCA", "B365CA", "BFECA", "WHCA", "VCCA"],
}
COL_OU25 = {
    "O": ["PC>2.5", "AvgC>2.5", "MaxC>2.5", "B365C>2.5", "BFEC>2.5"],
    "U": ["PC<2.5", "AvgC<2.5", "MaxC<2.5", "B365C<2.5", "BFEC<2.5"],
}
COL_AH = {
    "line": ["AHCh", "PAHh", "AHh"],
    "H": ["PCAHH", "AvgCAHH", "MaxCAHH", "B365CAHH", "BFECAHH"],
    "A": ["PCAHA", "AvgCAHA", "MaxCAHA", "B365CAHA", "BFECAHA"],
}
HOME_COLS = ["HomeTeam", "Home", "HT"]
AWAY_COLS = ["AwayTeam", "Away", "AT"]
DATE_COLS = ["Date"]

NOISE = {"fc", "cf", "sc", "ac", "afc", "cd", "ud", "club", "de", "calcio", "ss",
         "ssc", "as", "us", "if", "bk", "sk", "fk", "cfr", "the", "and"}
ALIAS = {
    "utd": "united", "man": "manchester", "nottm": "nottingham", "wolves":
    "wolverhampton", "ath": "atletico", "atl": "atletico", "st": "saint",
    "spurs": "tottenham", "psg": "paris", "sociedad": "sociedad", "dortmund":
    "dortmund", "leverkusen": "leverkusen", "gladbach": "monchengladbach",
    "m'gladbach": "monchengladbach", "bayern": "bayern", "inter": "inter",
    "sheff": "sheffield", "qpr": "queens park rangers", "wba": "west bromwich",
    "brighton": "brighton", "newcastle": "newcastle",
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def norm_team(name):
    s = strip_accents((name or "").lower())
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    toks = [ALIAS.get(t, t) for t in s.split()]
    toks = [t for t in toks if t not in NOISE and len(t) > 1]
    return " ".join(toks).strip()


def tok_sim(a, b):
    if a == b:
        return 1.0
    # football-data abbreviates by truncation: Nott'm <-> Nottingham
    if len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a)):
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


def team_sim(a, b):
    """Similarity that refuses to be fooled by a shared non-distinctive word.

    'Manchester City' and 'Manchester United' share a long token, which a plain
    string ratio scores at 0.81 - high enough to match the wrong fixture. Each
    token is paired with its best partner instead, and the WORST pairing gets
    half the weight, so one badly-mismatched word sinks the score."""
    a, b = norm_team(a), norm_team(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = a.split(), b.split()
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    best = [max(tok_sim(t, u) for u in long_) for t in short]
    mean, worst = sum(best) / len(best), min(best)
    score = 0.5 * mean + 0.5 * worst
    # a gentle penalty for one name carrying extra words (Zulte-Waregem/Waregem)
    return score * (len(short) / len(long_)) ** 0.25


def pick(header, candidates):
    for c in candidates:
        if c in header:
            return c
    return None


def fnum(v):
    try:
        f = float(str(v).strip())
        return f if f > 1.0 else None
    except (TypeError, ValueError):
        return None


def devig(odds):
    """Proportional de-vig: strip the bookmaker's margin from a full market.

    A bookmaker's prices imply probabilities summing to more than 1. Betfair's
    do not. Comparing a Betfair price to a raw bookmaker closing price would
    therefore show phantom CLV on every bet, so the margin comes out first."""
    probs = [1.0 / o for o in odds]
    total = sum(probs)
    if total <= 0:
        return None, None
    return [p / total for p in probs], total - 1.0


# ---------------------------------------------------------------- bet parsing
OU_RE = re.compile(r"\s+(Over|Under)\s+([\d.]+)\s+Goals$", re.I)
YESNO_RE = re.compile(r"\s+(Yes|No)$", re.I)
DC_RE = re.compile(r"\s+(Home or Draw|Draw or Away|Home or Away)$", re.I)
SCORE_RE = re.compile(r"\s+\d+\s*-\s*\d+$")
HCP_RE = re.compile(r"\s+(.+?)\s+([+-][\d.]+)$")


def split_event_selection(head, market):
    """Betfair glues the selection onto the event: 'Panama v Croatia Croatia'.

    Returns (home, away, selection) or None when the shape is not recognised."""
    m = (market or "").lower()
    head = head.strip()

    def split_away_selection(right, home):
        """right is 'AWAY SELECTION' with no delimiter. Try every split point
        and keep the one where the selection best matches a real team."""
        words = right.split()
        best, best_score = None, 0.0
        for i in range(1, len(words)):
            away, sel = " ".join(words[:i]), " ".join(words[i:])
            score = max(team_sim(sel, home), team_sim(sel, away))
            if score > best_score:
                best, best_score = (away, sel), score
        return best if best_score >= 0.75 else None

    if "over/under" in m and (mt := OU_RE.search(head)):
        sel = mt.group(0).strip()
        rest = head[:mt.start()]
    elif "both teams to score" in m and (mt := YESNO_RE.search(head)):
        sel, rest = mt.group(1), head[:mt.start()]
    elif "double chance" in m and (mt := DC_RE.search(head)):
        sel, rest = mt.group(1), head[:mt.start()]
    elif ("correct score" in m or "half time score" in m) and (mt := SCORE_RE.search(head)):
        sel, rest = mt.group(0).strip(), head[:mt.start()]
    elif re.search(r"\s[+-]?[\d.]+$", head) and (
            "handicap" in m or "total" in m or re.search(r"[+-][\d.]+$", head)):
        mt = re.search(r"\s([+-]?[\d.]+)$", head)
        number, stem = mt.group(1), head[:mt.start()].strip()
        if " v " not in stem:
            return None
        left, right = stem.split(" v ", 1)
        if re.search(r"\b(Over|Under)$", right, re.I):      # AFL Total Points
            cut = right.rfind(" ")
            return left.strip(), right[:cut].strip(), f"{right[cut:].strip()} {number}"
        sp = split_away_selection(right, left)
        if not sp:
            return None
        return left.strip(), sp[0], f"{sp[1]} {number}"
    else:
        # Match Odds / Draw no Bet / To Qualify: selection is a team or the draw
        if " v " not in head:
            return None
        left, right = head.split(" v ", 1)
        if right.lower().endswith("the draw"):
            return left.strip(), right[:-len("the draw")].strip(), "The Draw"
        sp = split_away_selection(right, left)
        if sp:
            return left.strip(), sp[0], sp[1]
        return None

    if " v " not in rest:
        return None
    home, away = rest.split(" v ", 1)
    return home.strip(), away.strip(), sel


# ------------------------------------------------------------- football-data
def season_codes(dates):
    """European seasons straddle the year: a June 2026 game is season 2025/26."""
    codes = set()
    for d in dates:
        start = d.year if d.month >= 7 else d.year - 1
        codes.add(f"{start % 100:02d}{(start + 1) % 100:02d}")
    return sorted(codes)


def candidate_urls(dates):
    urls = []
    for s in season_codes(dates):
        for d in MAIN_DIVS:
            urls.append((f"{BASE}/mmz4281/{s}/{d}.csv", f"{s}_{d}.csv"))
    for e in EXTRA:
        urls.append((f"{BASE}/new/{e}.csv", f"new_{e}.csv"))
    return urls


def download(urls, out_dir, verbose=True):
    os.makedirs(out_dir, exist_ok=True)
    got, missing = [], []
    for url, name in urls:
        dest = os.path.join(out_dir, name)
        if os.path.exists(dest) and os.path.getsize(dest) > 200:
            got.append(dest)
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            if len(data) < 200:
                missing.append((name, "empty"))
                continue
            with open(dest, "wb") as fh:
                fh.write(data)
            got.append(dest)
            if verbose:
                print(f"   downloaded {name} ({len(data)//1024} KB)")
        except urllib.error.HTTPError as e:
            missing.append((name, f"HTTP {e.code}"))
        except Exception as e:                                  # noqa: BLE001
            missing.append((name, type(e).__name__))
    return got, missing


def parse_date(s):
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def load_fixtures(paths):
    """Read every football-data CSV into fixtures, noting which closing-odds
    columns each file actually had. Files with no closing odds are reported
    rather than quietly falling back to opening prices."""
    fixtures, files_report = [], []
    for p in paths:
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as fh:
                rows = list(csv.DictReader(fh))
        except OSError:
            continue
        if not rows:
            continue
        header = set(rows[0].keys())
        cols = {
            "date": pick(header, DATE_COLS), "home": pick(header, HOME_COLS),
            "away": pick(header, AWAY_COLS),
            "h": pick(header, COL_1X2["H"]), "d": pick(header, COL_1X2["D"]),
            "a": pick(header, COL_1X2["A"]),
            "o25": pick(header, COL_OU25["O"]), "u25": pick(header, COL_OU25["U"]),
            "ahl": pick(header, COL_AH["line"]), "ahh": pick(header, COL_AH["H"]),
            "aha": pick(header, COL_AH["A"]),
        }
        files_report.append((os.path.basename(p), len(rows), cols))
        if not (cols["date"] and cols["home"] and cols["away"]):
            continue
        for r in rows:
            d = parse_date(r.get(cols["date"], ""))
            if not d or not r.get(cols["home"]):
                continue
            fixtures.append({
                "date": d, "home": r[cols["home"]], "away": r[cols["away"]],
                "src": os.path.basename(p),
                "h": fnum(r.get(cols["h"])) if cols["h"] else None,
                "d": fnum(r.get(cols["d"])) if cols["d"] else None,
                "a": fnum(r.get(cols["a"])) if cols["a"] else None,
                "o25": fnum(r.get(cols["o25"])) if cols["o25"] else None,
                "u25": fnum(r.get(cols["u25"])) if cols["u25"] else None,
                "ahl": r.get(cols["ahl"]) if cols["ahl"] else None,
                "ahh": fnum(r.get(cols["ahh"])) if cols["ahh"] else None,
                "aha": fnum(r.get(cols["aha"])) if cols["aha"] else None,
                "cols": cols,
            })
    return fixtures, files_report


# ------------------------------------------------------------------ matching
def index_by_date(fixtures):
    idx = {}
    for f in fixtures:
        idx.setdefault(f["date"], []).append(f)
    return idx


def best_fixture(idx, day, home, away, tol=1):
    """Settlement can cross midnight UTC, so look a day either side."""
    cands = []
    for off in range(-tol, tol + 1):
        for f in idx.get(day + timedelta(days=off), []):
            s = 0.5 * team_sim(home, f["home"]) + 0.5 * team_sim(away, f["away"])
            cands.append((s, f))
    if not cands:
        return None, 0.0, 0.0
    cands.sort(key=lambda x: -x[0])
    best, runner = cands[0], (cands[1] if len(cands) > 1 else (0.0, None))
    return best[1], best[0], best[0] - runner[0]


def fair_price(fx, market, selection, home, away):
    """Return (fair_closing_odds, raw_closing_odds, overround, note)."""
    m = (market or "").lower()
    sel = (selection or "").strip()

    if "match odds" in m or "draw no bet" in m or "to qualify" in m:
        if not (fx["h"] and fx["d"] and fx["a"]):
            return None, None, None, "no closing 1X2"
        probs, over = devig([fx["h"], fx["d"], fx["a"]])
        if sel.lower() in ("the draw", "draw"):
            p, raw = probs[1], fx["d"]
        elif team_sim(sel, home) >= team_sim(sel, away):
            p, raw = probs[0], fx["h"]
        else:
            p, raw = probs[2], fx["a"]
        if "draw no bet" in m or "to qualify" in m:
            return None, None, None, "market not covered"
        return 1.0 / p, raw, over, ""

    if "double chance" in m:
        if not (fx["h"] and fx["d"] and fx["a"]):
            return None, None, None, "no closing 1X2"
        probs, over = devig([fx["h"], fx["d"], fx["a"]])
        s = sel.lower()
        if s == "home or draw":
            p = probs[0] + probs[1]
        elif s == "draw or away":
            p = probs[1] + probs[2]
        elif s == "home or away":
            p = probs[0] + probs[2]
        else:
            return None, None, None, "unknown double chance leg"
        return 1.0 / p, None, over, "derived from closing 1X2"

    if "over/under 2.5" in m:
        if not (fx["o25"] and fx["u25"]):
            return None, None, None, "no closing O/U 2.5"
        probs, over = devig([fx["o25"], fx["u25"]])
        if sel.lower().startswith("over"):
            return 1.0 / probs[0], fx["o25"], over, ""
        return 1.0 / probs[1], fx["u25"], over, ""

    if "over/under" in m:
        return None, None, None, "only the 2.5 line is published"
    if "both teams to score" in m:
        return None, None, None, "BTTS not published"
    if "handicap" in m:
        if not (fx["ahh"] and fx["aha"] and fx["ahl"]):
            return None, None, None, "no closing Asian handicap"
        mt = re.search(r"([+-]?[\d.]+)$", sel)
        try:
            want, have = float(mt.group(1)), float(str(fx["ahl"]).strip())
        except (AttributeError, ValueError):
            return None, None, None, "handicap line unreadable"
        probs, over = devig([fx["ahh"], fx["aha"]])
        on_home = team_sim(sel.rsplit(" ", 1)[0], home) >= team_sim(sel.rsplit(" ", 1)[0], away)
        if abs(want - (have if on_home else -have)) > 1e-6:
            return None, None, None, f"line differs (bet {want}, close {have})"
        return (1.0 / probs[0] if on_home else 1.0 / probs[1],
                fx["ahh"] if on_home else fx["aha"], over, "")
    return None, None, None, "market not covered"


def clv_of(side, odds_taken, stake, fair):
    at_risk = stake if side.upper() == "BACK" else stake * (odds_taken - 1)
    if side.upper() == "BACK":
        dollars = stake * (odds_taken / fair - 1)
    else:
        dollars = stake * (1 - odds_taken / fair)
    return dollars, (dollars / at_risk if at_risk else None), at_risk


# ---------------------------------------------------------------------- main
OUT_FIELDS = ["settled", "home", "away", "market", "selection", "side",
              "odds_taken", "stake", "at_risk", "profit", "fixture", "fd_home",
              "fd_away", "close_raw", "close_fair", "overround", "clv_pct",
              "clv_dollar", "beat_close", "match_score", "status", "note"]
MIN_SCORE, MIN_MARGIN = 0.80, 0.05


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bets", help="Betfair ExchangeBets Settled CSV")
    ap.add_argument("--data-dir", default="footballdata",
                    help="where league CSVs live / are downloaded to")
    ap.add_argument("--no-download", action="store_true",
                    help="use only files already in --data-dir")
    ap.add_argument("--out", default="clv_backfill.csv")
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from betfair_analyse import parse as parse_bets

    bets = parse_bets(args.bets)
    dates = [b["settled"].date() for b in bets]
    print(f"{len(bets)} bets, {min(dates)} to {max(dates)}")

    if args.no_download:
        paths = [os.path.join(args.data_dir, f) for f in sorted(os.listdir(args.data_dir))
                 if f.lower().endswith(".csv")] if os.path.isdir(args.data_dir) else []
        missing = []
    else:
        print(f"\nFetching league files into {args.data_dir}/ ...")
        paths, missing = download(candidate_urls(dates), args.data_dir)
    print(f"   {len(paths)} league files available, {len(missing)} unavailable")

    fixtures, files_report = load_fixtures(paths)
    with_close = sum(1 for f in fixtures if f["h"])
    print(f"   {len(fixtures)} fixtures parsed, {with_close} with closing 1X2")
    used = {c["h"] for _n, _r, c in files_report if c.get("h")}
    print(f"   closing 1X2 column used: {', '.join(sorted(x for x in used if x)) or 'NONE FOUND'}")
    if not with_close:
        print("\n   WARNING: no closing-odds columns found in any file.")
        print("   Opening odds are deliberately NOT substituted - they would give")
        print("   a wrong benchmark and silently wrong CLV. Check the column names")
        print("   in one downloaded file against football-data.co.uk/notes.txt.")

    idx = index_by_date(fixtures)
    rows, stats = [], {}

    def bump(k):
        stats[k] = stats.get(k, 0) + 1

    for b in bets:
        parts = split_event_selection(b["head"], b["market"])
        base = {"settled": b["settled"].date().isoformat(), "market": b["market"],
                "side": b["side"], "odds_taken": b["odds"], "stake": b["stake"],
                "profit": b["pl"], "home": "", "away": "", "selection": "",
                "fixture": "", "fd_home": "", "fd_away": "", "close_raw": "",
                "close_fair": "", "overround": "", "clv_pct": "", "clv_dollar": "",
                "beat_close": "", "match_score": "", "note": ""}
        if not parts:
            base["status"] = "UNPARSEABLE"
            bump("UNPARSEABLE"); rows.append(base); continue
        home, away, sel = parts
        base.update(home=home, away=away, selection=sel)

        fx, score, margin = best_fixture(idx, b["settled"].date(), home, away)
        if not fx or score < MIN_SCORE:
            base["status"] = "NO FIXTURE"
            base["match_score"] = f"{score:.2f}"
            bump("NO FIXTURE"); rows.append(base); continue
        if margin < MIN_MARGIN:
            base["status"] = "AMBIGUOUS MATCH"
            base["match_score"] = f"{score:.2f}"
            bump("AMBIGUOUS MATCH"); rows.append(base); continue

        base.update(fixture=fx["src"], fd_home=fx["home"], fd_away=fx["away"],
                    match_score=f"{score:.2f}")
        fair, raw, over, note = fair_price(fx, b["market"], sel, home, away)
        base["note"] = note
        if not fair:
            base["status"] = "NO CLOSING PRICE"
            bump(f"NO CLOSING PRICE: {note}"); rows.append(base); continue

        dollars, pct, at_risk = clv_of(b["side"], b["odds"], b["stake"], fair)
        base.update(status="OK", close_fair=round(fair, 4),
                    close_raw=(raw or ""), overround=(round(over, 4) if over else ""),
                    clv_dollar=round(dollars, 4),
                    clv_pct=(round(pct, 6) if pct is not None else ""),
                    at_risk=round(at_risk, 2),
                    beat_close="YES" if dollars > 0 else "NO")
        bump("OK"); rows.append(base)

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_FIELDS, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

    ok = [r for r in rows if r["status"] == "OK"]
    print("\n" + "=" * 66)
    print(f"{len(ok)} of {len(bets)} bets got a real closing price "
          f"({len(ok)/len(bets):.0%})")
    for k, v in sorted(stats.items(), key=lambda x: -x[1]):
        if k != "OK":
            print(f"   {v:>4}  {k}")
    if ok:
        risk = sum(r["at_risk"] for r in ok)
        clv = sum(r["clv_dollar"] for r in ok)
        beat = sum(1 for r in ok if r["beat_close"] == "YES")
        pnl = sum(r["profit"] for r in ok)
        print(f"\n   turnover on those      ${risk:,.2f}")
        print(f"   CLV                    ${clv:,.2f}  ({clv/risk:+.2%})")
        print(f"   beat the close         {beat}/{len(ok)} = {beat/len(ok):.1%}")
        print(f"   actual P/L on them     ${pnl:,.2f}  (gross of commission)")
        print(f"   luck (actual - CLV)    ${pnl-clv:,.2f}")
    print(f"\n   written: {args.out}")
    print("=" * 66)


if __name__ == "__main__":
    main()
