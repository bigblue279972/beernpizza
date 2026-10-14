"""
Walk-forward backtest of the Fixture Dbase soccer model against Betfair prices.

Does the model find bets the market later agrees with? Six weeks of real bets
answered that for about 300 bets. football-data.co.uk carries, for every game
in the 15 main leagues, Betfair's EARLY price (collected a few days before
kick-off, roughly when the slate is priced) and Betfair's CLOSING price. So the
same question can be asked of thousands of games, free:

  1. Rate every team exactly as the workbook's Power Query does, using only
     results from BEFORE the game (no peeking at the future).
  2. Price the game exactly as the SOCCER tab does (Poisson on the expected
     goals).
  3. Apply the workbook's bet rule at the early Betfair price: model weight,
     buffer, commission, price ceiling, one bet per family, best Kelly wins.
  4. Score each bet by CLV against the closing Betfair price, after
     commission. Win/loss is printed for interest only.

It also measures, over every game including the six worldwide leagues (which
have closing prices only), how much weight the model deserves next to the
market price -- the number that belongs in SETTINGS "Model weight".

Model, copied from the workbook (FIXTURE DBASE v10, Power Query + SOCCER tab):
  weight of a past game  = 0.5 ** (days ago / 180), games up to 900 days back
  main leagues           = the current and previous season files only
  league average goals   = weighted (home + away goals) / weighted games
  home advantage (HGA)   = weighted home goals / weighted away goals
  a league needs 20 weighted games to be rated
  attack  = (GF + 4*avg/2) / (games*avg/2 + 4*avg/2)    (shrink = 4)
  defence = (GA + 4*avg/2) / (games*avg/2 + 4*avg/2)
  exp home = avg * HGA/(1+HGA) * home attack * away defence
  exp away = avg * 1/(1+HGA)   * away attack * home defence
  a team with no games in that league is unrated and its game is skipped
  (the Slate drops it too -- a promoted side's first match is never priced).

Usage:
  python backtest_model.py                       # downloads what it needs
  python backtest_model.py --start 2025-08-01    # first game to test
  python backtest_model.py --weight 0.3 --max-price 4 --buffer 0.10
"""
import argparse
import csv
import math
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clv_backfill import (BASE, LEAGUE_NAMES, devig_power, download,  # noqa: E402
                          fnum, parse_date, price_band)

MAIN_DIVS = ["E0", "E1", "E2", "E3", "SC0", "SC1", "D1", "I1", "SP1", "SP2",
             "F1", "N1", "B1", "P1", "G1"]                   # the workbook's 15
EXTRA = ["JPN", "USA", "BRA", "ARG", "MEX", "CHN"]          # the workbook's 6
HALF_LIFE, DAYS_BACK, SHRINK, MIN_DATA = 180, 900, 4, 20
MAX_GOALS = 12                                              # SETTINGS D11:D23

EARLY_1X2 = [("BFEH", "BFED", "BFEA")]
CLOSE_1X2 = [("BFECH", "BFECD", "BFECA"), ("PSCH", "PSCD", "PSCA"),
             ("AvgCH", "AvgCD", "AvgCA")]
EARLY_OU = [("BFE>2.5", "BFE<2.5")]
CLOSE_OU = [("BFEC>2.5", "BFEC<2.5"), ("PC>2.5", "PC<2.5"), ("AvgC>2.5", "AvgC<2.5")]


# ------------------------------------------------------------------ data
def season_code(d):
    start = d.year if d.month >= 7 else d.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def prev_code(code):
    a = int(code[:2]) - 1
    return f"{a % 100:02d}{(a + 1) % 100:02d}"


def first_full(row, sets):
    for cols in sets:
        vals = [fnum(row.get(c)) for c in cols]
        if all(vals):
            return vals, cols[0]
    return None, None


def load_games(paths):
    """Every played game: league, season, date, teams, score, prices."""
    games = []
    for p in paths:
        name = os.path.basename(p)
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as fh:
                rows = list(csv.DictReader(fh))
        except OSError:
            continue
        extra = name.startswith("new_")
        for r in rows:
            d = parse_date(r.get("Date", ""))
            if extra:
                home, away, hg, ag = r.get("Home"), r.get("Away"), r.get("HG"), r.get("AG")
                div = f"{name[4:7]} | {r.get('League', '')}"
                season = None
            else:
                home, away = r.get("HomeTeam"), r.get("AwayTeam")
                hg, ag = r.get("FTHG"), r.get("FTAG")
                div, season = name[5:-4], name[:4]
            try:
                hg, ag = int(float(hg)), int(float(ag))
            except (TypeError, ValueError):
                continue
            if not d or not home or not away:
                continue
            e1, _ = first_full(r, EARLY_1X2)
            c1, cb = first_full(r, CLOSE_1X2)
            eo, _ = first_full(r, EARLY_OU)
            co, _ = first_full(r, CLOSE_OU)
            games.append({"div": div, "season": season, "date": d, "home": home,
                          "away": away, "hg": hg, "ag": ag, "extra": extra,
                          "src": name, "e1x2": e1, "c1x2": c1, "cbench": cb,
                          "eou": eo, "cou": co})
    return games


# -------------------------------------------------------------------- xG
UNDERSTAT = {"E0": "EPL", "SP1": "La_liga", "D1": "Bundesliga", "I1": "Serie_A",
             "F1": "Ligue_1"}


def fetch_understat(league, year, out_dir):
    """One season of Understat results with xG, cached as JSON. Seasons
    finished more than a month ago are not fetched again."""
    import json
    import time
    import urllib.request
    path = os.path.join(out_dir, f"understat_{league}_{year}.json")
    finished = date(year + 1, 7, 1) + timedelta(days=30) < date.today()
    if os.path.exists(path) and (finished or time.time() - os.path.getmtime(path) < 12 * 3600):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    url = f"https://understat.com/getLeagueData/{league}/{year}"
    for wait in (0, 2, 5, 10):
        time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0",
                                                       "X-Requested-With": "XMLHttpRequest"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = json.loads(raw)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            time.sleep(1)
            return data
        except Exception:                                           # noqa: BLE001
            continue
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return None


def attach_xg(games, out_dir, years):
    """Give each big-5 game its Understat xG, matched on date (a day either
    side, since Understat dates are UTC) and team names. Returns
    {div: (matched, games)}."""
    from datetime import datetime
    from clv_backfill import team_sim
    report = {}
    for div, league in UNDERSTAT.items():
        idx = {}
        for y in years:
            data = fetch_understat(league, y, out_dir)
            for m in (data or {}).get("dates", []):
                if not m.get("isResult") or not m.get("xG"):
                    continue
                d = datetime.strptime(m["datetime"][:10], "%Y-%m-%d").date()
                idx.setdefault(d, []).append((m["h"]["title"], m["a"]["title"],
                                              float(m["xG"]["h"]), float(m["xG"]["a"])))
        mine = [g for g in games if g["div"] == div]
        hit = 0
        for g in mine:
            cands = []
            for off in (-1, 0, 1):
                for h, a, hx, ax in idx.get(g["date"] + timedelta(days=off), []):
                    sc = 0.5 * team_sim(g["home"], h) + 0.5 * team_sim(g["away"], a)
                    cands.append((sc, hx, ax))
            cands.sort(reverse=True)
            if cands and cands[0][0] >= 0.6 and (len(cands) == 1 or cands[0][0] - cands[1][0] >= 0.1):
                g["hx"], g["ax"] = cands[0][1], cands[0][2]
                hit += 1
        report[div] = (hit, len(mine))
    return report


# ----------------------------------------------------------------- model
def scored(g, stat):
    """What a past game counts as: its goals (the workbook), its xG, or half
    of each. A game with no xG falls back to its goals."""
    if stat == "goals" or g.get("hx") is None:
        return g["hg"], g["ag"]
    if stat == "xg":
        return g["hx"], g["ax"]
    return (g["hg"] + g["hx"]) / 2, (g["ag"] + g["ax"]) / 2


def ratings_for(history, today, stat="goals"):
    """The workbook's Ratings query, run on games played before `today`."""
    nw = hgw = agw = 0.0
    team = {}
    for g in history:
        days = (today - g["date"]).days
        if days <= 0 or days > DAYS_BACK:
            continue
        w = 0.5 ** (days / HALF_LIFE)
        hs, as_ = scored(g, stat)
        nw += w
        hgw += hs * w
        agw += as_ * w
        for t, gf, ga in ((g["home"], hs, as_), (g["away"], as_, hs)):
            s = team.setdefault(t, [0.0, 0.0, 0.0])
            s[0] += w
            s[1] += gf * w
            s[2] += ga * w
    if nw < MIN_DATA:
        return None
    avg = (hgw + agw) / nw
    hga = 1.0 if agw <= 0 else hgw / agw
    half = avg / 2
    rated = {t: ((gf + SHRINK * half) / (n * half + SHRINK * half),
                 (ga + SHRINK * half) / (n * half + SHRINK * half))
             for t, (n, gf, ga) in team.items()}
    return avg, hga, rated


def poisson(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def price_game(xh, xa):
    """The SOCCER tab's percentages (rows 12-14 and 24-25)."""
    ph = [poisson(k, xh) for k in range(MAX_GOALS + 1)]
    pa = [poisson(k, xa) for k in range(MAX_GOALS + 1)]
    cum_a = [sum(pa[:k + 1]) for k in range(MAX_GOALS + 1)]
    home = sum(ph[k] * cum_a[k - 1] for k in range(1, MAX_GOALS + 1))
    draw = sum(ph[k] * pa[k] for k in range(MAX_GOALS + 1))
    tot = xh + xa
    under = sum(poisson(k, tot) for k in range(3))
    return {"H": home, "D": draw, "A": 1 - home - draw, "O": 1 - under, "U": under}


def model_probs(games, start, stat="goals", divs=None):
    """Walk forward: each game is priced from ratings built on earlier games."""
    by_div = {}
    for g in games:
        if divs is None or g["div"] in divs:
            by_div.setdefault(g["div"], []).append(g)
    priced = []
    for div, gs in by_div.items():
        gs.sort(key=lambda g: g["date"])
        cache = {}
        for g in gs:
            if g["date"] < start:
                continue
            key = (g["date"], g["season"])
            if key not in cache:
                if g["extra"]:
                    hist = gs
                else:      # the workbook loads the current and previous season only
                    keep = {g["season"], prev_code(g["season"])}
                    hist = [h for h in gs if h["season"] in keep]
                cache[key] = ratings_for(hist, g["date"], stat)
            r = cache[key]
            if not r:
                continue
            avg, hga, rated = r
            if g["home"] not in rated or g["away"] not in rated:
                continue                                    # unrated: Slate drops it
            (h_att, h_def), (a_att, a_def) = rated[g["home"]], rated[g["away"]]
            xh = avg * (hga / (1 + hga)) * h_att * a_def
            xa = avg * (1 / (1 + hga)) * a_att * h_def
            g2 = dict(g, xh=xh, xa=xa, p=price_game(xh, xa))
            priced.append(g2)
    return priced


# ------------------------------------------------------------- bet rule
def blended_edge(p, price, w, comm):
    """SOCCER column H: blend the model with the price, net of commission."""
    return (w * p + (1 - w) / price) * (1 + (price - 1) * (1 - comm)) - 1


def selections(g):
    """Every priced selection in the Result and Goals families, at the early
    Betfair price. Double chance has no Betfair column, so it is priced as
    backing both outcomes in Match Odds (what a dutch there pays)."""
    out = []
    p = g["p"]
    if g["e1x2"] and g["c1x2"]:
        eh, ed, ea = g["e1x2"]
        fair_c = devig_power(g["c1x2"])[0]
        for sel, prob, price, pc in (
                ("Home", p["H"], eh, fair_c[0]), ("Draw", p["D"], ed, fair_c[1]),
                ("Away", p["A"], ea, fair_c[2]),
                ("Home or Draw", p["H"] + p["D"], 1 / (1 / eh + 1 / ed), fair_c[0] + fair_c[1]),
                ("Draw or Away", p["D"] + p["A"], 1 / (1 / ed + 1 / ea), fair_c[1] + fair_c[2]),
                ("Home or Away", p["H"] + p["A"], 1 / (1 / eh + 1 / ea), fair_c[0] + fair_c[2])):
            won = {"Home": g["hg"] > g["ag"], "Draw": g["hg"] == g["ag"],
                   "Away": g["hg"] < g["ag"]}
            win = any(won[s] for s in sel.replace(" or ", "|").split("|"))
            out.append(("Result", "Match Odds" if " or " not in sel else "Double Chance",
                        sel, prob, price, pc, win))
    if g["eou"] and g["cou"]:
        eo, eu = g["eou"]
        fair_c = devig_power(g["cou"])[0]
        total = g["hg"] + g["ag"]
        out.append(("Goals", "Over/Under 2.5", "Over 2.5", p["O"], eo, fair_c[0], total > 2))
        out.append(("Goals", "Over/Under 2.5", "Under 2.5", p["U"], eu, fair_c[1], total < 3))
    return out


def run_rule(priced, w, buf, comm, max_price):
    """One bet per family per game: the best Kelly among those that clear."""
    bets = []
    for g in priced:
        best = {}
        for fam, market, sel, prob, price, p_close, win in selections(g):
            if price > max_price or price <= 1:
                continue
            e = blended_edge(prob, price, w, comm)
            if e < buf:                       # same as price >= the required price
                continue
            kelly = e / ((price - 1) * (1 - comm))
            if fam not in best or kelly > best[fam][0]:
                best[fam] = (kelly, market, sel, prob, price, p_close, win, e)
        for fam, (kelly, market, sel, prob, price, p_close, win, e) in best.items():
            clv = price * p_close - 1                       # vs the fair closing price
            comm_cost = comm * p_close * (price - 1)        # expected commission
            bets.append({"date": g["date"].isoformat(), "league": LEAGUE_NAMES.get(g["div"], g["div"]),
                         "home": g["home"], "away": g["away"], "market": market,
                         "selection": sel, "model_p": round(prob, 4),
                         "early_price": round(price, 3), "close_fair": round(1 / p_close, 3),
                         "edge_claimed": round(e, 4), "clv": round(clv, 4),
                         "clv_after_comm": round(clv - comm_cost, 4), "won": win,
                         "pl_net": round((price - 1) * (1 - comm) if win else -1.0, 4)})
    return bets


def every_selection(priced, comm):
    """The random-bet baseline: every selection in every game, as if backed.
    Early prices in thin leagues carry a wide spread, so even a coin-flip
    pick loses CLV there; a rule has to beat THIS, not zero."""
    out = []
    for g in priced:
        for fam, market, sel, prob, price, p_close, win in selections(g):
            clv = price * p_close - 1
            out.append({"league": LEAGUE_NAMES.get(g["div"], g["div"]), "market": market,
                        "early_price": price, "edge_claimed": blended_edge(prob, price, 1, comm),
                        "clv": clv, "clv_after_comm": clv - comm * p_close * (price - 1),
                        "won": win, "pl_net": (price - 1) * (1 - comm) if win else -1.0})
    return out


# -------------------------------------------------------------- reports
def summary_line(label, bets, base=None):
    if not bets:
        print(f"   {label:<34} no bets")
        return
    n = len(bets)
    clv = sum(b["clv"] for b in bets) / n
    after = sum(b["clv_after_comm"] for b in bets) / n
    beat = sum(1 for b in bets if b["clv"] > 0) / n
    roi = sum(b["pl_net"] for b in bets) / n
    sd = (sum((b["clv_after_comm"] - after) ** 2 for b in bets) / max(n - 1, 1)) ** 0.5
    se = sd / n ** 0.5
    claimed = sum(b["edge_claimed"] for b in bets) / n
    price = sum(b["early_price"] for b in bets) / n
    rnd = ""
    if base:
        b_clv = sum(b["clv"] for b in base) / len(base)
        rnd = f"  {b_clv:>+6.1%}  {clv - b_clv:>+6.1%}"
    print(f"   {label:<34} {n:>5}  {price:>5.2f}  {claimed:>+7.1%}  {clv:>+6.1%}  "
          f"{after:>+7.1%} (+/-{1.96 * se:.1%})  {beat:>4.0%}  {roi:>+6.1%}{rnd}")


def header(title, base=False):
    extra = f"  {'random':>6}  {'vs rnd':>6}" if base else ""
    print(f"\n   {title:<34} {'bets':>5}  {'price':>5}  {'claimed':>7}  {'CLV':>6}  "
          f"{'after comm.':>18}  {'beat':>4}  {'ROI':>6}{extra}")


def breakdown(title, bets, key, order=None, base=None):
    groups, bgroups = {}, {}
    for b in bets:
        groups.setdefault(key(b), []).append(b)
    for b in base or []:
        bgroups.setdefault(key(b), []).append(b)
    header(title, base is not None)
    for k in (order or sorted(groups, key=lambda k: -len(groups[k]))):
        if k in groups:
            summary_line(str(k)[:34], groups[k], bgroups.get(k) if base is not None else None)


def log_loss_weight(priced, which):
    """How much weight the model deserves beside the market: the blend
    w*model + (1-w)*market that best predicted what actually happened."""
    rows = []
    for g in priced:
        prices = g["c1x2"] if which == "close" else g["e1x2"]
        if not prices:
            continue
        mkt = devig_power(prices)[0]
        res = 0 if g["hg"] > g["ag"] else (1 if g["hg"] == g["ag"] else 2)
        rows.append(([g["p"]["H"], g["p"]["D"], g["p"]["A"]][res], mkt[res]))
    if not rows:
        return None
    best = None
    table = []
    for i in range(0, 21):
        w = i / 20
        ll = -sum(math.log(max(w * m + (1 - w) * k, 1e-12)) for m, k in rows) / len(rows)
        table.append((w, ll))
        if best is None or ll < best[1]:
            best = (w, ll)
    return len(rows), best, dict(table)


def model_log_loss(priced):
    """How well the model alone predicted 1X2 results (lower is better)."""
    tot = 0.0
    for g in priced:
        res = "H" if g["hg"] > g["ag"] else ("D" if g["hg"] == g["ag"] else "A")
        tot -= math.log(max(g["p"][res], 1e-12))
    return tot / len(priced)


def xg_section(games, start, a):
    """Same games, same rule, three ways of rating teams: goals (the
    workbook), xG, and half of each. Fixed in advance, so nothing here is
    tuned to the answer."""
    print("\n" + "=" * 92)
    print("3. WOULD xG-BASED RATINGS DO BETTER?  (Understat xG, England/Spain/")
    print("   Germany/Italy/France top divisions only - the leagues it covers)")
    years = sorted({int("20" + c[:2]) for c in
                    {season_code(start - timedelta(days=400)), season_code(date.today())}})
    years = list(range(years[0], years[-1] + 1))
    rep = attach_xg(games, a.data_dir, years)
    for div, (hit, n) in rep.items():
        print(f"   {LEAGUE_NAMES[div]:<26} xG found for {hit} of {n} games")
    divs = set(UNDERSTAT)
    runs = {stat: model_probs(games, start, stat, divs) for stat in ("goals", "xg", "mix")}
    keys = set.intersection(*[{(g["div"], g["date"], g["home"]) for g in r} for r in runs.values()])
    for stat in runs:
        runs[stat] = [g for g in runs[stat] if (g["div"], g["date"], g["home"]) in keys]
    print(f"   compared on the same {len(keys)} games\n")
    print(f"   {'RATINGS BUILT ON':<22} {'model log-loss':>14} {'weight vs early':>16} "
          f"{'gain':>6} {'weight vs close':>16} {'gain':>6}")
    for stat, label in (("goals", "goals (the workbook)"), ("xg", "xG"), ("mix", "half goals, half xG")):
        r = runs[stat]
        cells = []
        for which in ("early", "close"):
            res = log_loss_weight(r, which)
            if res:
                n, (w, ll), tab = res
                cells.append(f"{w:>16.2f} {(tab[0.0] - ll) * n:>6.1f}")
            else:
                cells.append(f"{'-':>16} {'-':>6}")
        print(f"   {label:<22} {model_log_loss(r):>14.4f} {cells[0]} {cells[1]}")
    print("   Lower log-loss = better forecasts. The market alone scores about")
    mk = []
    for g in runs["goals"]:
        if g["c1x2"]:
            res = 0 if g["hg"] > g["ag"] else (1 if g["hg"] == g["ag"] else 2)
            mk.append(-math.log(devig_power(g["c1x2"])[0][res]))
    if mk:
        print(f"   {sum(mk) / len(mk):.4f} on these games at the close.")

    base = every_selection(runs["goals"], a.commission)
    header("BET RULE, v9 (model only)", True)
    summary_line("every selection (random baseline)", base, base)
    for stat, label in (("goals", "goals (the workbook)"), ("xg", "xG"), ("mix", "half goals, half xG")):
        summary_line(label, run_rule(runs[stat], 1.0, a.buffer, a.commission, 1e9), base)
    header(f"BET RULE, {a.weight:.0%} model, max {a.max_price:.2f}", True)
    for stat, label in (("goals", "goals (the workbook)"), ("xg", "xG"), ("mix", "half goals, half xG")):
        summary_line(label, run_rule(runs[stat], a.weight, a.buffer, a.commission, a.max_price),
                     base)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", default="2025-08-01", help="first game to test (YYYY-MM-DD)")
    ap.add_argument("--weight", type=float, default=0.3, help="SETTINGS Model weight")
    ap.add_argument("--max-price", type=float, default=4.0, help="SETTINGS Max price")
    ap.add_argument("--buffer", type=float, default=0.10, help="SETTINGS Buffer")
    ap.add_argument("--commission", type=float, default=0.06, help="SETTINGS Betfair commission")
    ap.add_argument("--data-dir", default="footballdata")
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--out", default="backtest_bets.csv")
    ap.add_argument("--no-xg", action="store_true", help="skip the xG comparison")
    a = ap.parse_args()
    start = date.fromisoformat(a.start)

    seasons = sorted({season_code(start - timedelta(days=400)), season_code(start)} |
                     {season_code(date.today())} |
                     {season_code(start + timedelta(days=365 * k)) for k in range(4)
                      if start + timedelta(days=365 * k) <= date.today()})
    urls = [(f"{BASE}/mmz4281/{s}/{d}.csv", f"{s}_{d}.csv") for s in seasons for d in MAIN_DIVS]
    urls += [(f"{BASE}/new/{e}.csv", f"new_{e}.csv") for e in EXTRA]
    if a.no_download:
        paths = [os.path.join(a.data_dir, n) for _u, n in urls
                 if os.path.exists(os.path.join(a.data_dir, n))]
        missing = []
    else:
        print(f"Fetching league files into {a.data_dir}/ ...")
        paths, missing = download(urls, a.data_dir)
    print(f"   {len(paths)} files, {len(missing)} unavailable")
    for name, why in missing:
        print(f"      {name}: {why}")

    games = load_games(paths)
    print(f"   {len(games)} played games loaded; testing from {start}")
    priced = model_probs(games, start)
    main_g = [g for g in priced if not g["extra"]]
    print(f"   {len(priced)} games priced by the model "
          f"({len(main_g)} in the 15 main leagues, {len(priced) - len(main_g)} worldwide)")
    print(f"   {sum(1 for g in main_g if g['e1x2'] and g['c1x2'])} with early and closing "
          f"Betfair 1X2, {sum(1 for g in main_g if g['eou'] and g['cou'])} with O/U 2.5")

    print("\n" + "=" * 92)
    print("1. HOW MUCH SHOULD THE MODEL BE TRUSTED NEXT TO THE MARKET?")
    print("   Blend w*model + (1-w)*market; the w that best predicted actual results.")
    for which, label in (("early", "vs the early Betfair price (what you bet at)"),
                         ("close", "vs the closing price")):
        for scope, gs in (("15 main leagues", main_g),
                          ("worldwide 6", [g for g in priced if g["extra"]])):
            r = log_loss_weight(gs, which)
            if not r:
                continue
            n, (w, ll), tab = r
            gain = (tab[0.0] - ll) * n
            print(f"   {label:<46} {scope:<16} {n:>6} games   best weight {w:.2f}"
                  f"   (log-score gain over market alone: {gain:.1f})")
    print("   A best weight of 0.00 means the model adds nothing the market does not")
    print("   already know. A gain under about 3 is within chance.")

    print("\n" + "=" * 92)
    print("2. THE BET RULE, AT THE EARLY BETFAIR PRICE, SCORED BY CLV")
    print("   One unit per bet. 'claimed' = the edge the workbook said the bet had.")
    print("   'after comm.' must be positive; the +/- is a 95% range. ROI is luck-heavy.")
    print("   'random' is the CLV of backing every selection in the same group: early")
    print("   prices in thin leagues carry a wide spread, so the bar is not zero.")
    print("   'vs rnd' above zero means the rule picks better than chance.")
    variants = [
        ("v9: model only, no ceiling", 1.0, 1e9),
        ("v10 defaults: 30% model, max 4.00", 0.3, 4.0),
        (f"yours: {a.weight:.0%} model, max {a.max_price:.2f}", a.weight, a.max_price),
        ("model only, max 4.00", 1.0, 4.0),
        ("50% model, max 4.00", 0.5, 4.0),
        ("10% model, max 4.00", 0.1, 4.0),
    ]
    base = every_selection(main_g, a.commission)
    header("VARIANT", True)
    summary_line("every selection (random baseline)", base, base)
    results = {}
    seen = set()
    for label, w, mx in variants:
        if (w, mx) in seen:
            continue
        seen.add((w, mx))
        bets = run_rule(main_g, w, a.buffer, a.commission, mx)
        results[label] = bets
        summary_line(label, bets, base)

    for label in ("v9: model only, no ceiling", f"yours: {a.weight:.0%} model, max {a.max_price:.2f}"):
        bets = results.get(label) or results.get("v10 defaults: 30% model, max 4.00")
        if not bets:
            continue
        print("\n" + "-" * 92)
        print(f"   BREAKDOWN - {label}")
        breakdown("MARKET", bets, lambda b: b["market"], base=base)
        breakdown("PRICE TAKEN", bets, lambda b: price_band(b["early_price"]),
                  ["under 1.50", "1.50-1.99", "2.00-2.99", "3.00-4.99", "5.00 and up"], base)
        breakdown("EDGE THE WORKBOOK CLAIMED", bets,
                  lambda b: ("10-15%" if b["edge_claimed"] < .15 else
                             "15-25%" if b["edge_claimed"] < .25 else
                             "25-50%" if b["edge_claimed"] < .5 else "50% and up"),
                  ["10-15%", "15-25%", "25-50%", "50% and up"])
        breakdown("LEAGUE", bets, lambda b: b["league"], base=base)

    if not a.no_xg:
        xg_section(games, start, a)

    allb = [dict(b, variant=k) for k, bs in results.items() for b in bs]
    if allb:
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(allb[0].keys()))
            w.writeheader()
            w.writerows(allb)
        print(f"\n   every simulated bet written to {a.out}")
    print("=" * 92)


if __name__ == "__main__":
    main()
