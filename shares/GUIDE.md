# Share Investing Starter Guide

> **I'm an AI assistant, not a licensed financial adviser.** This is general information, not personal advice.
> Fees and rules below were researched in October 2026 from comparison sites (Finder, Mozo, SuperGuide).
> The provider websites themselves couldn't be checked from my end, so **confirm every fee on the provider's own site before you sign up**.

## 1. The honest starting point

- **Trading (buying and selling often) is not a sustainable income plan.** ASIC (Australia's market regulator) found that during the 2020 market crash, retail short-term traders mostly bought before prices fell and sold before they rose. Most people who trade often earn less than people who buy a broad fund and leave it.
- **What does work for most people:** *investing*. That means buying a cheap fund that holds hundreds of companies, adding money regularly, and holding it for years.
- **$1,000 won't make an income on its own.** At a ~3.5% yearly payout it pays about **$35 a year (about 67 cents a week)**. Income comes from adding money every month for years, not from picking clever shares.
- **At 60 and 64, your super and the Age Pension matter far more than this $1,000.** Your wife reaches Age Pension age (67) in about 3 years, and shares count towards Centrelink's assets and income tests. Before you put in serious money, book a **free** appointment with the **Financial Information Service (FIS)** at Services Australia (search "Services Australia Financial Information Service" or call 132 300). They are government staff who explain how super, shares and the pension interact. It's free and they don't sell anything.

## 2. The plan (Year 1)

1. **Emergency fund first.** Keep 3–6 months of expenses in a high-interest savings account. Only invest money you won't touch for 5+ years.
2. **One account, one fund.** Buy **one diversified ETF** (an "exchange-traded fund" is a single share that holds hundreds of companies, sometimes plus bonds, bought on the ASX like any share).
3. **Add a fixed amount every month**, the same day each month, regardless of the news.
4. **Never sell because prices fell.** A 20–30% fall at some point is normal and expected.
5. **Review once a year (July).** That's the only time the plan changes.

### Which fund? Compare these yourself and pick ONE

| Fund (ASX code) | What's inside | Yearly fee* | Fits whom |
|---|---|---|---|
| VDHG (Vanguard) | ~90% shares / 10% bonds & cash | ~0.27% | Long horizon, can sit through big falls |
| DHHF (Betashares) | 100% shares | ~0.19% | Same, slightly cheaper, no bonds |
| VDGR (Vanguard) | ~70% shares / 30% bonds | check site | More cautious: smaller falls, lower growth |

*Fees from third-party review sites (2026). Check the fund's page on vanguard.com.au or betashares.com.au.

**My view, given your ages:** a 90–100% shares fund can fall 30–40% in a bad year. If losing $400 of $1,000 would make you sell, a 70/30 fund (VDGR or similar) is the better fit, because the fund you stick with beats the "best" fund you panic out of. **This is a judgment call for you (C1).**

### Which broker? Short list

| Broker | Cost to buy | Ownership | Note |
|---|---|---|---|
| **CMC Invest** | $0 on first buy under $1,000 per stock per day, otherwise ~$11 | CHESS-sponsored | Finder's 2026 award winner |
| **Vanguard Personal Investor** | $0 to buy Vanguard ETFs, $9 to sell | check site | Good if you pick a Vanguard fund |
| **Betashares Direct** | $0 on ASX ETFs, auto-invest from $50 | Custodial (not CHESS) | Easiest for automatic monthly buys |

**Plain English: "CHESS-sponsored"** means the shares are registered in **your name** with the ASX, so if the broker collapses the shares are still yours. **"Custodial"** means the broker holds them for you; usually fine, but one extra layer of risk. For a beginner I'd lean to CHESS-sponsored.

**Rule: brokerage must be under 1% of each order.** $11 on a $1,000 buy = 1.1%, which is too much. That's why $0-brokerage options suit small monthly amounts.

## 3. Setting up (step by step)

1. Decide **whose name** the account goes in. The lower-income earner usually pays less tax on dividends. Ask FIS or your tax agent if unsure.
2. Have ready: driver's licence, Medicare card, bank account details, and your **Tax File Number** (TFN; if you don't give it, 47% tax is held back from dividends).
3. Go to the chosen broker's website, click **Sign up / Open account**, choose **Individual** (or **Joint** for both of you).
4. When asked about dividends, choose **"Reinvest" (DRP)** if offered, or **"Pay to bank"**. Either is fine; just record it.
5. Transfer your $1,000. Fill in the **Pre-Buy Gate** sheet in the spreadsheet. If it says GO, place a **"limit" order** (you set the maximum price; type the current price shown) during market hours (10am–4pm Sydney time, which is 9:30am–3:30pm Adelaide time).
6. Open the confirmation email and copy the figures into the **Transactions** sheet.

## 4. The spreadsheet: `Share_Tracker.xlsx`

**Download and save:**
1. On GitHub, open the `shares` folder, click **Share_Tracker.xlsx**, then click the **Download** button (the down-arrow icon at the top right of the file view).
2. Open File Explorer (yellow folder icon on the taskbar), go to **Documents**, create a folder called `Shares`, and move the file there.
3. Double-click to open in Excel. If a yellow bar says **"Enable Editing"**, click it.

**How it works:** yellow cells are yours to type in, green cells calculate themselves. Start with the **START HERE** tab, then **Settings**.

**The scorecard** (your equivalent of Closing Line Value) is the **Process Scorecard** on the Dashboard: costs under 0.5% of money invested, zero trades that skipped the Gate, mix within 5% of target. Never grade a month by whether the value went up.

**(Optional) to rebuild the file** from the script: install Python from python.org, open the Start menu, type `cmd`, press Enter, then type
`cd Documents\Shares` and press Enter, then `pip install openpyxl` and press Enter, then `python build_tracker.py` and press Enter.

## 5. What I need from you to help further

- **Nothing to log in to.** Never give me (or anyone) your broker password.
- Once you've chosen a broker, tell me which one. Most let you **export trade history as a CSV file**, and I can write an importer so you don't type trades in by hand.
- Your answers to: how much you can add per month, whether you have an emergency fund, and how much of a fall you could sit through without selling.

## Sources
- [Finder: best trading platforms Oct 2026](https://www.finder.com.au/share-trading/best-online-share-trading-platforms)
- [Finder: cheapest brokers 2026](https://www.finder.com.au/share-trading/cheap-stock-brokerage-in-australia)
- [Mozo: best share trading platforms 2026](https://www.mozo.com.au/best/best-share-trading-platforms)
- [Finder: best ETF platforms 2026](https://www.finder.com.au/share-trading/exchange-traded-funds/best-etf-trading-platforms)
- [Finder: Vanguard Personal Investor](https://www.finder.com.au/share-trading/vanguard-share-trading)
- [Peakifi: VDHG vs DHHF](https://peakifi.com/investing/etfs/vdhg-vs-dhhf/)
- [SuperGuide: deeming rates](https://www.superguide.com.au/in-retirement/age-pension-income-test-deeming-rates)
- [SuperGuide: assets test thresholds](https://www.superguide.com.au/accessing-superannuation/age-pension-asset-test-thresholds)
- [Stockhead: ASIC on retail traders](https://stockhead.com.au/?p=64425)
- [Dimensional: dangers of DIY trading](https://www.dimensional.com/au-en/insights/the-dangers-of-diy-trading)
- [Motley Fool: ASX 200 dividend yield](https://www.fool.com.au/2026/02/19/what-happens-if-you-invest-10000-in-asx-shares-and-leave-it-alone-for-20-years/)
