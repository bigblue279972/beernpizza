#!/usr/bin/env python3
"""Find out why European fixtures are not reaching the Fixture Dbase, and fix it.

    Double-click it, or:  python fixtures_doctor.py

Standard library only. The workbook's Power Query reads European fixtures from
two separate sets of files in its cache folder, and drops a fixture without a
word when either is missing:

    fixtures.csv                 the upcoming games
    mmz4281_2627_E0.csv  etc.    this season's results, which the ratings come from
    mmz4281_2526_E0.csv  etc.    last season's, the same

The other leagues need only one file each (new_JPN.csv and so on), holding both
results and fixtures, which is why they can work while Europe does not.

This replays the workbook's own rules on the files actually in the folder --
the same 15 leagues, today to 4 days ahead, a team must have results in that
league inside 900 days, and the league at least 20 decay-weighted games -- and
reports the first step where the European games disappear. It then offers,
asking first, to download the missing files from football-data.co.uk under the
exact names the workbook expects. Each download is checked before it replaces
anything, and replaced files are kept in cache\\_previous. The new_ files are
never touched.

    python fixtures_doctor.py --check-only     report, change nothing
    python fixtures_doctor.py --cache "D:\\somewhere\\cache"
"""

import argparse
import csv
import io
import math
import os
import shutil
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

# ---- copied from the workbook's Power Query, so the replay matches it ----
CURRENT, PREVIOUS = "2627", "2526"
MAIN_DIVS = ["E0", "E1", "E2", "E3", "SC0", "SC1", "D1", "I1", "SP1", "SP2",
             "F1", "N1", "B1", "P1", "G1"]
NAMES = {"E0": "EPL", "E1": "Championship", "E2": "EFL League One",
         "E3": "EFL League Two", "SC0": "Scottish Premiership",
         "SC1": "Scottish Championship", "D1": "Bundesliga", "I1": "Serie A",
         "SP1": "La Liga", "SP2": "Spain Segunda", "F1": "Ligue 1",
         "N1": "Eredivisie", "B1": "Belgium Pro League",
         "P1": "Portugal Primeira Liga", "G1": "Greece Super League"}
EXTRA = ["JPN", "USA", "BRA", "ARG", "MEX", "CHN"]
DAYS_AHEAD, DAYS_BACK, HALF_LIFE, MIN_DATA = 4, 900, 180, 20
RESULTS_STALE_DAYS = 3        # matches are played every few days; older files miss them

BASE = os.environ.get("FOOTBALL_DATA_BASE", "https://www.football-data.co.uk")
CACHE_GUESSES = [
    Path.home() / "Documents" / "unleashed-pro" / "UNLEASHED BET REQUEST" / "cache",
    Path(r"C:\Users\bigbl\Documents\unleashed-pro\UNLEASHED BET REQUEST\cache"),
]


def say(msg=""):
    print(msg, flush=True)


# ------------------------------------------------------------- reading ----

def read_csv(path):
    """Rows as dicts, read the way Power Query does: Windows-1252."""
    raw = Path(path).read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("cp1252", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return [], [], bom
    head = [h.strip() for h in rows[0]]
    out = [dict(zip(head, (c.strip() for c in r))) for r in rows[1:] if any(c.strip() for c in r)]
    return head, out, bom


def parse_date(s):
    """dd/mm/yy or dd/mm/yyyy, as the workbook's ParseDate."""
    p = (s or "").strip().split("/")
    if len(p) != 3:
        return None
    try:
        d, m, y = (int(x) for x in p)
        return date(2000 + y if y < 100 else y, m, d)
    except ValueError:
        return None


def season_file(season, div):
    return f"mmz4281_{season}_{div}.csv"


# -------------------------------------------------------------- replay ----

def replay(cache, today):
    """Walk the workbook's European steps on the real files; count what survives."""
    rep = {"fixtures": None, "bom": False, "seasons": {}, "stale_names": [],
           "per_div": {}, "dropped": [], "latest": None, "results_age": None}
    ages = [(datetime.now() - datetime.fromtimestamp((cache / season_file(CURRENT, d)).stat().st_mtime)).days
            for d in MAIN_DIVS if (cache / season_file(CURRENT, d)).exists()]
    rep["results_age"] = max(ages) if ages else None

    # ratings: which (league, team) pairs have results the workbook would use
    weight_by_div, teams = {}, set()
    for div in MAIN_DIVS:
        for s in (CURRENT, PREVIOUS):
            f = cache / season_file(s, div)
            if not f.exists():
                continue
            head, rows, _ = read_csv(f)
            need = {"Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG"}
            if not need <= set(head):
                rep["seasons"][f.name] = "unreadable (columns missing)"
                continue
            n = 0
            for r in rows:
                if not r.get("HomeTeam") or r.get("FTHG", "") == "":
                    continue
                d = parse_date(r.get("Date"))
                if not d or d > today or (today - d).days > DAYS_BACK:
                    continue
                w = 0.5 ** ((today - d).days / HALF_LIFE)
                weight_by_div[div] = weight_by_div.get(div, 0) + w
                teams.add((div, r["HomeTeam"])); teams.add((div, r["AwayTeam"]))
                n += 1
            rep["seasons"][f.name] = f"{n} results used"
    good_divs = {d for d, w in weight_by_div.items() if w >= MIN_DATA}
    rated = {(d, t) for d, t in teams if d in good_divs}

    # a results file sitting in the cache under the browser's name, not the workbook's
    for div in MAIN_DIVS:
        for f in cache.glob(f"{div}*.csv"):
            if f.stem == div or f.stem.startswith(div + " ("):
                rep["stale_names"].append(f.name)

    fx = cache / "fixtures.csv"
    if not fx.exists():
        return rep
    head, rows, rep["bom"] = read_csv(fx)
    rep["fixtures"] = {"rows": len(rows), "modified": datetime.fromtimestamp(fx.stat().st_mtime)}
    if not {"Div", "Date", "HomeTeam", "AwayTeam"} <= set(head):
        rep["fixtures"]["bad_header"] = head[:6]
        return rep
    last = today + timedelta(days=DAYS_AHEAD)
    for r in rows:
        div = r.get("Div")
        if div not in NAMES or not r.get("HomeTeam"):
            continue
        c = rep["per_div"].setdefault(div, {"listed": 0, "window": 0, "shows": 0})
        c["listed"] += 1
        ko = parse_date(r.get("Date"))
        if ko and (rep["latest"] is None or ko > rep["latest"]):
            rep["latest"] = ko
        if ko is not None and not (today <= ko <= last):
            continue
        c["window"] += 1
        miss = [t for t in (r["HomeTeam"], r["AwayTeam"]) if (div, t) not in rated]
        if miss:
            why = ("no results for this league in the cache" if div not in good_divs
                   else f"no results for {', '.join(miss)} in this league")
            rep["dropped"].append((NAMES[div], r["HomeTeam"], r["AwayTeam"], why))
        else:
            c["shows"] += 1
    return rep


def verdict(rep, today):
    """The first step at which the European games disappear, in plain words."""
    n_seasons = sum(1 for v in rep["seasons"].values() if v.endswith("used"))
    listed = sum(c["listed"] for c in rep["per_div"].values())
    window = sum(c["window"] for c in rep["per_div"].values())
    shows = sum(c["shows"] for c in rep["per_div"].values())
    if rep["fixtures"] is None:
        return "missing_fixtures", "fixtures.csv is not in the cache folder."
    if rep["bom"]:
        return "bom", ("fixtures.csv starts with a hidden marker (a 'BOM') that stops Power "
                       "Query reading its first column.")
    if "bad_header" in rep["fixtures"]:
        return "bad_fixtures", ("fixtures.csv in the cache is not football-data's fixtures file "
                                f"(its first columns are {rep['fixtures']['bad_header']}).")
    if listed == 0:
        return "bad_fixtures", "fixtures.csv has no games for any of your 15 European leagues."
    if window == 0:
        return "stale_fixtures", (f"fixtures.csv is out of date: its latest game is "
                                  f"{rep['latest']:%a %d %b}, and the workbook only shows "
                                  f"{today:%d %b} to {today + timedelta(days=DAYS_AHEAD):%d %b}.")
    if n_seasons == 0:
        return "no_results", ("there are no European results files in the cache, so no European "
                              "team can be rated - and the workbook drops every game it can't rate.")
    if shows == 0:
        return "no_ratings", ("the results files are there but don't cover these teams. They are "
                              "probably old seasons, or the wrong leagues.")
    if rep["results_age"] is not None and rep["results_age"] > RESULTS_STALE_DAYS:
        return "stale_results", (f"{shows} European games will show, but your results files are "
                                 f"{rep['results_age']} days old, so the ratings miss every game "
                                 "played since.")
    return "ok", (f"{shows} European games should show. If v9 still doesn't show them, "
                  "Refresh All didn't finish - run it again.")


def report(rep, today, cache):
    say(f"Cache folder: {cache}")
    say(f"Today (UK date): {today:%a %d %b %Y}   window the workbook shows: "
        f"to {today + timedelta(days=DAYS_AHEAD):%a %d %b}\n")
    fx = rep["fixtures"]
    if fx:
        say(f"fixtures.csv          found, {fx['rows']} games, saved {fx['modified']:%d %b %H:%M}")
    else:
        say("fixtures.csv          MISSING")
    have = {k: v for k, v in rep["seasons"].items()}
    cur = [d for d in MAIN_DIVS if season_file(CURRENT, d) in have]
    prev = [d for d in MAIN_DIVS if season_file(PREVIOUS, d) in have]
    age = rep["results_age"]
    say(f"2026/27 results       {len(cur)} of 15 leagues"
        + ("" if age is None else f", downloaded {age} day{'' if age == 1 else 's'} ago")
        + ("" if len(cur) == 15 else f"  (missing: {', '.join(d for d in MAIN_DIVS if d not in cur)})"))
    say(f"2025/26 results       {len(prev)} of 15 leagues"
        + ("" if len(prev) == 15 else f"  (missing: {', '.join(d for d in MAIN_DIVS if d not in prev)})"))
    if rep["stale_names"]:
        say(f"Wrongly named         {', '.join(sorted(rep['stale_names']))}  "
            "(the workbook can't see these - they need the mmz4281_ name)")
    if rep["per_div"]:
        say("\nLeague                  listed  in window  would show")
        for div in MAIN_DIVS:
            c = rep["per_div"].get(div)
            if c:
                say(f"  {NAMES[div]:<22}{c['listed']:>6}{c['window']:>10}{c['shows']:>11}")
    if rep["dropped"]:
        say("\nDropped, first few:")
        for lg, h, a, why in rep["dropped"][:6]:
            say(f"  {lg}: {h} v {a}  - {why}")
    code, text = verdict(rep, today)
    tag = {"ok": "GOOD: ", "stale_results": "OUT OF DATE: "}.get(code, "PROBLEM: ")
    say("\n" + tag + text)
    return code


# ----------------------------------------------------------- fetching ----

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (fixtures_doctor)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def looks_right(data, div=None):
    """Never replace a good file with an error page: it must be a real data file."""
    text = data.decode("cp1252", errors="replace").lstrip("\ufeff\u00ef\u00bb\u00bf")
    first = text.splitlines()[0] if text else ""
    if not {"Div", "Date", "HomeTeam", "AwayTeam"} <= {h.strip() for h in first.split(",")}:
        return False
    return div is None or any(line.startswith(div + ",") for line in text.splitlines()[1:])


def install(cache, name, data):
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    target = cache / name
    if target.exists():
        if target.read_bytes() == data:
            os.utime(target, None)    # confirmed current today, even with no new games
            return "unchanged"
        keep = cache / "_previous"
        keep.mkdir(exist_ok=True)
        shutil.copy2(target, keep / name)
    target.write_bytes(data)
    return "saved"


def download(cache, want_previous):
    jobs = [("fixtures.csv", f"{BASE}/fixtures.csv", None)]
    jobs += [(season_file(CURRENT, d), f"{BASE}/mmz4281/{CURRENT}/{d}.csv", d) for d in MAIN_DIVS]
    jobs += [(season_file(PREVIOUS, d), f"{BASE}/mmz4281/{PREVIOUS}/{d}.csv", d)
             for d in MAIN_DIVS if d in want_previous]
    ok = failed = 0
    for i, (name, url, div) in enumerate(jobs, 1):
        try:
            data = fetch(url)
        except Exception as e:                                  # noqa: BLE001
            say(f"  {i:>2}/{len(jobs)}  {name:<24} could not download ({e.__class__.__name__})")
            failed += 1
            continue
        if not looks_right(data, div):
            say(f"  {i:>2}/{len(jobs)}  {name:<24} refused - the site sent something that "
                "isn't a fixtures/results file; your old file is kept")
            failed += 1
            continue
        say(f"  {i:>2}/{len(jobs)}  {name:<24} {install(cache, name, data)}")
        ok += 1
        time.sleep(0.4)                                          # be polite to a free site
    return ok, failed


# --------------------------------------------------------------- main -----

def main():
    ap = argparse.ArgumentParser(description="Why are European fixtures missing?")
    ap.add_argument("--cache", help="the workbook's cache folder")
    ap.add_argument("--check-only", action="store_true", help="report, change nothing")
    ap.add_argument("--yes", action="store_true", help="download without asking")
    ap.add_argument("--no-pause", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--today", help=argparse.SUPPRESS)          # testing only
    args = ap.parse_args()
    # Fixture dates are UK dates. Count "today" in UK terms -- Adelaide time less the
    # largest gap, 10.5 hours -- as the workbook does once its one-line fix is in, so
    # a Friday-night UK game is not called yesterday's after Adelaide's midnight.
    today = (date.fromisoformat(args.today) if args.today
             else (datetime.now() - timedelta(hours=10, minutes=30)).date())

    cache = Path(args.cache) if args.cache else next((c for c in CACHE_GUESSES if c.exists()), None)
    try:
        if cache is None or not cache.exists():
            say("STOPPED: can't find the cache folder. Looked in:")
            for c in CACHE_GUESSES:
                say(f"  {c}")
            say('Run it again with  --cache "the folder path"')
            return 2
        code = report(replay(cache, today), today, cache)
        if code == "ok" or args.check_only:
            return 0

        if code in ("missing_fixtures", "bom", "bad_fixtures", "stale_fixtures",
                    "no_results", "no_ratings", "stale_results"):
            have_prev = {d for d in MAIN_DIVS if (cache / season_file(PREVIOUS, d)).exists()}
            n_prev = 15 - len(have_prev)
            say(f"\nI can fix this by downloading fixtures.csv and the 15 current-season results "
                f"files{f', plus {n_prev} missing last-season files' if n_prev else ''} from "
                "football-data.co.uk, saved under the exact names the workbook reads. "
                "Your Japan/USA/Brazil/Argentina/Mexico/China files are not touched.")
            answer = "y" if args.yes else input("Download them now? Type y and press Enter: ").strip().lower()
            if answer != "y":
                say("Nothing downloaded.")
                return 1
            say("")
            ok, failed = download(cache, set(MAIN_DIVS) - have_prev)
            say(f"\n{ok} files saved or already current, {failed} failed.")
            say("Checking again...\n")
            code = report(replay(cache, today), today, cache)
            if code == "ok":
                say("\nNow open FIXTURE DBASE v9 and click Data > Refresh All.")
        return 0 if code == "ok" else 1
    finally:
        if not args.no_pause:
            input("\nPress Enter to close this window.")


if __name__ == "__main__":
    sys.exit(main())
