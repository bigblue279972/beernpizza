"""
STEP 1 - Pull your settled Betfair bets WITH their market and selection IDs.

Why this exists: the CSV you can download from the Betfair website has no
marketId or selectionId, only free text. Those IDs are the key that lets us
look up the closing price for each bet, which is the one thing Closing Line
Value needs. The API has them - but only for the last 90 days, so this is
time-critical.

It writes two files next to itself:
  betfair_bets_with_ids.csv   - one row per bet, ready for step 2
  betfair_bets_raw.json       - the untouched API response, kept as a backup
                                because the 90-day window cannot be re-opened

Only the Python standard library is used, so there is nothing to pip install.

Your password is never written to disk and never leaves your laptop: it is
typed at the prompt each run, sent straight to Betfair over HTTPS, and
discarded when the script exits.
"""
import csv
import getpass
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "betfair_config.txt")
OUT_CSV = os.path.join(HERE, "betfair_bets_with_ids.csv")
OUT_JSON = os.path.join(HERE, "betfair_bets_raw.json")

LOGIN_URL = "https://identitysso.betfair.com/api/login"
API_URL = "https://api.betfair.com/exchange/betting/json-rpc/v1"
PAGE = 1000            # Betfair's hard page-size limit for listClearedOrders
MAX_DAYS = 90          # Betfair's hard history limit - older bets are gone

CONFIG_TEMPLATE = """# Betfair settings. Edit the two lines below, save, and run the script again.
# Your PASSWORD does NOT go in here - you will be asked for it each time.

APP_KEY = paste-your-app-key-here
USERNAME = your-betfair-username
"""

FIELDS = ["bet_id", "placed", "settled", "market_start", "sport", "event",
          "market", "market_type", "selection", "market_id", "selection_id",
          "handicap", "side", "price_requested", "price_matched",
          "size_settled", "profit", "commission", "outcome"]


def die(msg, *extra):
    print("\n" + "=" * 68)
    print("STOPPED: " + msg)
    for line in extra:
        print("  " + line)
    print("=" * 68)
    sys.exit(1)


def read_config():
    if not os.path.exists(CONFIG):
        with open(CONFIG, "w", encoding="utf-8") as fh:
            fh.write(CONFIG_TEMPLATE)
        die("I have created a settings file for you.",
            f"Open this file: {CONFIG}",
            "Put your App Key and Betfair username in it, save it,",
            "then run this script again.")
    cfg = {}
    with open(CONFIG, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip().upper()] = v.strip()
    app_key, user = cfg.get("APP_KEY", ""), cfg.get("USERNAME", "")
    if not app_key or app_key.startswith("paste-"):
        die("The App Key is still missing from your settings file.",
            f"Open {CONFIG} and paste your App Key after 'APP_KEY ='.")
    if not user or user.startswith("your-"):
        die("Your username is still missing from the settings file.",
            f"Open {CONFIG} and put your Betfair username after 'USERNAME ='.")
    return app_key, user


def post(url, data, headers, form=False):
    body = (urllib.parse.urlencode(data).encode() if form
            else json.dumps(data).encode())
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        die(f"Betfair refused the request (HTTP {e.code}).",
            (e.read().decode()[:300] or "No detail returned."))
    except urllib.error.URLError as e:
        die("Could not reach Betfair. Check your internet connection.", str(e.reason))


def login(app_key, username, password):
    out = post(LOGIN_URL, {"username": username, "password": password},
               {"X-Application": app_key,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"}, form=True)
    if out.get("status") != "SUCCESS":
        reason = out.get("error") or out.get("loginStatus") or out.get("status")
        hints = {
            "INVALID_USERNAME_OR_PASSWORD": "Check the username in your settings file and retype the password.",
            "INVALID_APP_KEY": "The App Key is wrong. Copy it again from developer.betfair.com.",
            "ACCOUNT_NOW_LOCKED": "Betfair has locked the account. Log in on the website to clear it.",
            "PENDING_AUTH": "Your account needs verifying on the Betfair website first.",
            "TWO_FACTOR_AUTH_REQUIRED": "Two-factor auth is on. Betfair support can advise on API access.",
        }
        die(f"Betfair would not log you in ({reason}).",
            hints.get(str(reason), "Log in on the Betfair website first, then try again."))
    return out["token"]


def call(app_key, token, method, params):
    payload = [{"jsonrpc": "2.0", "method": f"SportsAPING/v1.0/{method}",
                "params": params, "id": 1}]
    out = post(API_URL, payload,
               {"X-Application": app_key, "X-Authentication": token,
                "Content-Type": "application/json", "Accept": "application/json"})
    first = out[0] if isinstance(out, list) else out
    if "error" in first:
        err = first["error"]
        detail = (err.get("data", {}).get("APINGException", {}).get("errorCode")
                  or err.get("message", "unknown"))
        if detail == "INVALID_APP_KEY":
            die("Betfair rejected the App Key for data requests.",
                "A Delayed App Key should work here. If it does not, email",
                "automation@betfair.com.au - do NOT pay for a Live key first.")
        die(f"Betfair returned an error: {detail}")
    return first["result"]


def fetch(app_key, token, days):
    now = datetime.now(timezone.utc)
    rng = {"from": (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "to": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    print(f"Asking Betfair for settled bets from {rng['from'][:10]} to {rng['to'][:10]}...")
    orders, start = [], 0
    while True:
        res = call(app_key, token, "listClearedOrders", {
            "betStatus": "SETTLED", "groupBy": "BET",
            "settledDateRange": rng, "includeItemDescription": True,
            "fromRecord": start, "recordCount": PAGE})
        batch = res.get("clearedOrders", [])
        orders.extend(batch)
        print(f"   ...{len(orders)} bets so far")
        if not res.get("moreAvailable") or not batch:
            break
        start += len(batch)
    return orders


def flatten(o):
    d = o.get("itemDescription") or {}
    return {
        "bet_id": o.get("betId"), "placed": o.get("placedDate"),
        "settled": o.get("settledDate"), "market_start": d.get("marketStartTime"),
        "sport": d.get("eventTypeDesc"), "event": d.get("eventDesc"),
        "market": d.get("marketDesc"), "market_type": o.get("marketType") or d.get("marketType"),
        "selection": d.get("runnerDesc"), "market_id": o.get("marketId"),
        "selection_id": o.get("selectionId"), "handicap": o.get("handicap"),
        "side": o.get("side"), "price_requested": o.get("priceRequested"),
        "price_matched": o.get("priceMatched"), "size_settled": o.get("sizeSettled"),
        "profit": o.get("profit"), "commission": o.get("commission"),
        "outcome": o.get("betOutcome"),
    }


def main():
    days = MAX_DAYS
    for a in sys.argv[1:]:
        if a.startswith("--days="):
            days = min(MAX_DAYS, max(1, int(a.split("=", 1)[1])))

    app_key, username = read_config()
    print(f"Logging in as {username} ...")
    password = getpass.getpass("Betfair password (typing stays hidden): ")
    token = login(app_key, username, password)
    del password
    print("Logged in.\n")

    orders = fetch(app_key, token, days)
    if not orders:
        die("Betfair returned no settled bets for that period.",
            "If you know there were bets, they may be older than 90 days,",
            "which is Betfair's hard limit - those cannot be recovered.")

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(orders, fh, indent=1)
    rows = [flatten(o) for o in orders]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    have_ids = sum(1 for r in rows if r["market_id"] and r["selection_id"])
    dates = sorted(r["settled"][:10] for r in rows if r["settled"])
    profit = sum(r["profit"] or 0 for r in rows)
    comm = sum(r["commission"] or 0 for r in rows)
    print("\n" + "=" * 68)
    print(f"SAVED {len(rows)} bets")
    print(f"  with market + selection IDs : {have_ids}  <-- these can get CLV")
    if dates:
        print(f"  oldest settled              : {dates[0]}")
        print(f"  newest settled              : {dates[-1]}")
    print(f"  profit as Betfair reports it: {profit:,.2f}")
    print(f"  commission reported         : {comm:,.2f}")
    print(f"\n  {OUT_CSV}")
    print(f"  {OUT_JSON}")
    print("\nSend me the CSV and I will build step 2.")
    print("=" * 68)


if __name__ == "__main__":
    main()
