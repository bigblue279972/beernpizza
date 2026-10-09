"""Analyse a Betfair 'ExchangeBets Settled' CSV export."""
import csv, re, math, statistics, sys
from collections import defaultdict
from datetime import datetime

MON = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
       "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}


def num(s):
    s = (s or "").strip().replace(",", "")
    if s in ("", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def pdate(s):
    d, t = s.split(" ")
    dd, mon, yy = d.split("-")
    return datetime(2000 + int(yy), MON[mon[:3].lower()], int(dd),
                    *[int(x) for x in t.split(":")])


def parse(path):
    """Description is 'Event Selection-Market | Betfair Bet ID ...'.
    The market is after the LAST hyphen before the pipe - splitting on the
    first one mangles every hyphenated club name (Zulte-Waregem, Red Bull)."""
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for d in csv.DictReader(fh):
            d = {k.strip(): (v.strip() if isinstance(v, str) else v)
                 for k, v in d.items()}
            desc = d["Description"].split("| Betfair Bet ID")[0].strip()
            if "-" in desc:
                head, market = desc.rsplit("-", 1)
            else:
                head, market = desc, "??"
            rows.append(dict(
                settled=pdate(d["Settled"]), placed=pdate(d["Placed"]),
                side=d["Type"], odds=num(d["Odds"]), stake=num(d["Stake (AUD)"]),
                liability=num(d["Liability (AUD)"]), pl=num(d["Profit/Loss"]),
                status=d["Status"], market=market.strip(), head=head.strip()))
    rows.sort(key=lambda r: r["settled"])
    return rows


def band(o):
    return ("1.01-1.49" if o < 1.5 else "1.50-1.99" if o < 2 else
            "2.00-2.99" if o < 3 else "3.00-4.99" if o < 5 else
            "5.00-9.99" if o < 10 else "10.00+")


def table(rows, keyfn, title, order=None):
    agg = defaultdict(lambda: [0, 0.0, 0.0, 0])
    for r in rows:
        a = agg[keyfn(r)]
        a[0] += 1; a[1] += r["stake"]; a[2] += r["pl"]; a[3] += (r["pl"] > 0)
    print(f"\n{title}")
    print(f"{'':<26}{'Bets':>5}{'Turnover':>11}{'P/L':>10}{'ROI':>9}{'Strike':>8}")
    keys = order or sorted(agg, key=lambda k: -agg[k][2])
    for k in keys:
        if k not in agg:
            continue
        c_, s_, p_, w_ = agg[k]
        print(f"{k[:25]:<26}{c_:>5}{s_:>11,.0f}{p_:>10,.2f}"
              f"{p_/s_ if s_ else 0:>9.1%}{w_/c_:>8.0%}")
    return agg


if __name__ == "__main__":
    R = parse(sys.argv[1])
    stake = sum(r["stake"] for r in R)
    pl = sum(r["pl"] for r in R)
    gross_win = sum(r["pl"] for r in R if r["pl"] > 0)
    rets = [r["pl"] / r["stake"] for r in R]
    mean, sd, n = statistics.mean(rets), statistics.stdev(rets), len(rets)
    t = mean / (sd / math.sqrt(n))

    print("=" * 72)
    print(f"{len(R)} settled bets   {min(r['settled'] for r in R):%d %b %Y} "
          f"to {max(r['settled'] for r in R):%d %b %Y}")
    print("=" * 72)
    print(f"Turnover ${stake:,.2f}   P/L (gross) ${pl:,.2f}   ROI {pl/stake:+.2%}")
    for rate in (0.02, 0.05, 0.07):
        net = pl - rate * gross_win
        print(f"   net at {rate:.0%} commission  ${net:>8,.2f}  ROI {net/stake:>+7.2%}")
    print(f"\nt-statistic on per-bet return: {t:.2f} "
          f"({'significant' if abs(t) > 2 else 'NOT significant'})")
    se = sd / math.sqrt(n)
    print(f"95% range for the true ROI: {mean-1.96*se:+.1%} to {mean+1.96*se:+.1%}")

    # how concentrated is the profit?
    print("\nPROFIT CONCENTRATION")
    by_win = sorted(R, key=lambda r: -r["pl"])
    for k in (1, 3, 5, 10, 20):
        share = sum(r["pl"] for r in by_win[:k]) / pl
        print(f"   top {k:>2} bets = {share:>6.1%} of all profit")
    long_ = [r for r in R if r["odds"] >= 10]
    rest = [r for r in R if r["odds"] < 10]
    print(f"   bets at 10.00+ : {len(long_):>3} bets, ${sum(r['pl'] for r in long_):>8,.2f} "
          f"({sum(r['pl'] for r in long_)/pl:.0%} of profit)")
    rs, rp = sum(r["stake"] for r in rest), sum(r["pl"] for r in rest)
    rgw = sum(r["pl"] for r in rest if r["pl"] > 0)
    print(f"   everything else: {len(rest):>3} bets, ${rp:>8,.2f}  ROI {rp/rs:+.2%} gross"
          f"  |  {(rp-0.05*rgw)/rs:+.2%} net at 5%")

    table(R, lambda r: r["market"], "BY MARKET")
    table(R, lambda r: band(r["odds"]), "BY ODDS BAND",
          order=["1.01-1.49","1.50-1.99","2.00-2.99","3.00-4.99","5.00-9.99","10.00+"])
    table(R, lambda r: f"{r['settled']:%Y-%m}", "BY MONTH",
          order=sorted({f"{r['settled']:%Y-%m}" for r in R}))
