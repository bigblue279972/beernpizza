"""Builds Share_Tracker.xlsx - a beginner long-term investing tracker (Excel, Windows).

Run:  python build_tracker.py   (creates Share_Tracker.xlsx next to this script)
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

OUT = Path(__file__).with_name("Share_Tracker.xlsx")

HEAD = PatternFill("solid", fgColor="1F3864")
HEAD_FONT = Font(bold=True, color="FFFFFF")
INPUT = PatternFill("solid", fgColor="FFF2CC")   # yellow = you type here
CALC = PatternFill("solid", fgColor="E2EFDA")    # green = calculated, don't touch
GOOD = PatternFill("solid", fgColor="C6EFCE")
BAD = PatternFill("solid", fgColor="FFC7CE")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
MONEY = '"$"#,##0.00;[Red]-"$"#,##0.00'
PCT = "0.00%"
ROWS = 500  # rows pre-formatted for data entry


def header(ws, row, titles, widths=None):
    for i, t in enumerate(titles, start=1):
        c = ws.cell(row=row, column=i, value=t)
        c.fill, c.font, c.alignment, c.border = HEAD, HEAD_FONT, Alignment(wrap_text=True, vertical="center"), BOX
    if widths:
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[ws.cell(row=row, column=i).column_letter].width = w
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = Font(bold=True, size=16, color="1F3864")
    if sub:
        ws["A2"] = sub
        ws["A2"].font = Font(italic=True, color="595959")


wb = Workbook()

# ---------------------------------------------------------------- START HERE
ws = wb.active
ws.title = "START HERE"
title(ws, "Share Tracker - read this first",
      "Not financial advice. Built by an AI assistant, not a licensed financial adviser.")
ws.column_dimensions["A"].width = 120
lines = [
    "",
    "COLOURS",
    "  Yellow cells = you type here.   Green cells = calculated automatically - don't type over them.",
    "",
    "THE 5 SHEETS YOU USE",
    "  1. Settings      - fill in once (your names, brokerage cost, target mix). Change only after a planned review.",
    "  2. Pre-Buy Gate  - fill in BEFORE every buy or sell. If the result says STOP, you don't place the order.",
    "  3. Transactions  - one row for every buy or sell, copied from your broker's confirmation email.",
    "  4. Dividends     - one row for every dividend/distribution paid (they arrive in your bank account or as extra units).",
    "  5. Prices        - once a month (e.g. first Sunday), type today's price for each fund you own.",
    "",
    "THE 2 SHEETS YOU READ",
    "  Holdings   - what you own, what it cost, what it's worth, and whether your mix has drifted from target.",
    "  Dashboard  - the scorecard. The number that matters is 'You vs doing nothing clever' (see below).",
    "",
    "THE SCORECARD (this is your Closing Line Value for shares)",
    "  In betting, CLV tells you if your process beats the market, regardless of one result.",
    "  In investing the equivalent is: did my portfolio, after ALL fees, keep up with simply holding the benchmark fund?",
    "  Never judge a month by whether the value went up or down - markets fall 10-20% regularly and that is normal.",
    "  Judge the process: (a) costs kept under 1% of each purchase, (b) every trade passed the Gate, (c) mix stays near target.",
    "",
    "THE RULES (write them on paper too)",
    "  R1. No buying or selling outside the monthly routine, except the yearly rebalance.",
    "  R2. Never sell because the market dropped. Falls are expected; selling locks in the loss.",
    "  R3. No single company shares, tips, forums, crypto, CFDs, options or 'trading courses' in Year 1.",
    "  R4. Only invest money you won't need for at least 5 years. Keep an emergency fund in a savings account first.",
    "  R5. Every order must pass the Pre-Buy Gate. Brokerage must be under 1% of the order.",
    "",
    "MONTHLY ROUTINE (about 15 minutes)",
    "  1. Prices sheet: type the latest price for each fund (from your broker app).",
    "  2. If you're adding money this month: fill the Pre-Buy Gate, then buy, then log it in Transactions.",
    "  3. Log any dividends received in Dividends.",
    "  4. Look at the Dashboard. Do nothing else.",
    "",
    "TAX TIME (July)",
    "  Your broker/fund sends an 'AMMA' or 'Annual Tax Statement' for each ETF. Give those to your tax agent or enter them in myTax.",
    "  The Dividends sheet totals cash + franking credits per financial year as a cross-check.",
]
for i, line in enumerate(lines, start=3):
    c = ws.cell(row=i, column=1, value=line)
    if line and not line.startswith("  "):
        c.font = Font(bold=True, color="1F3864")

# ---------------------------------------------------------------- Settings
st = wb.create_sheet("Settings")
title(st, "Settings", "Fill in once. Yellow cells only.")
st.column_dimensions["A"].width = 42
st.column_dimensions["B"].width = 18
st.column_dimensions["C"].width = 70
settings = [
    ("Account holder name(s)", "", "As shown on the broker account."),
    ("Broker", "", "e.g. CMC Invest / Vanguard Personal Investor / Betashares Direct."),
    ("Start date", None, "Date of your first deposit (DD/MM/YYYY)."),
    ("Typical brokerage per trade ($)", 0, "From your broker's pricing page. Used by the Gate."),
    ("Max brokerage as % of an order", 0.01, "1% rule. Don't change this unless you know why."),
    ("Planned monthly contribution ($)", 0, "What you can add each month without touching emergency money."),
    ("Emergency fund held in savings ($)", 0, "Cash you can reach in 1 day. Aim for 3-6 months of expenses."),
    ("Marginal tax rate of account holder", 0.16, "Used for rough after-tax estimates only. Check your own bracket."),
    ("Benchmark fund ticker", "VDHG", "The single fund you compare yourself against (see Dashboard)."),
]
for r, (k, v, note) in enumerate(settings, start=4):
    st.cell(row=r, column=1, value=k).font = Font(bold=True)
    c = st.cell(row=r, column=2, value=v)
    c.fill, c.border = INPUT, BOX
    st.cell(row=r, column=3, value=note).alignment = WRAP
st["B6"].number_format = "DD/MM/YYYY"
st["B7"].number_format = MONEY
st["B8"].number_format = PCT
st["B9"].number_format = MONEY
st["B10"].number_format = MONEY
st["B11"].number_format = PCT

st["A14"] = "TARGET MIX (must add up to 100%)"
st["A14"].font = Font(bold=True, color="1F3864")
for col, t in zip("ABC", ["Ticker (ASX code)", "Target %", "What it is"]):
    c = st[f"{col}15"]
    c.value, c.fill, c.font, c.border = t, HEAD, HEAD_FONT, BOX
targets = [("VDHG", 1.0, "Example only - one diversified fund. Replace with your chosen fund(s).")]
for r in range(16, 26):
    for col in "ABC":
        st[f"{col}{r}"].fill, st[f"{col}{r}"].border = INPUT, BOX
    st[f"B{r}"].number_format = "0%"
for r, (t, p, d) in enumerate(targets, start=16):
    st[f"A{r}"], st[f"B{r}"], st[f"C{r}"] = t, p, d
st["A26"] = "Total (must be 100%)"
st["A26"].font = Font(bold=True)
st["B26"] = "=SUM(B16:B25)"
st["B26"].number_format = "0%"
st["B26"].fill = CALC
st.conditional_formatting.add("B26", FormulaRule(formula=["ROUND(B26,4)<>1"], fill=BAD))
st.conditional_formatting.add("B26", FormulaRule(formula=["ROUND(B26,4)=1"], fill=GOOD))

# ---------------------------------------------------------------- Pre-Buy Gate
g = wb.create_sheet("Pre-Buy Gate")
title(g, "Pre-Buy Gate", "Fill in before EVERY order. Answer honestly. If any line fails, the answer is STOP.")
g.column_dimensions["A"].width = 70
g.column_dimensions["B"].width = 16
g.column_dimensions["C"].width = 14
g.column_dimensions["D"].width = 60
for col, t in zip("ABCD", ["Check", "Your answer", "Pass?", "Why it matters"]):
    c = g[f"{col}4"]
    c.value, c.fill, c.font, c.border = t, HEAD, HEAD_FONT, BOX
g["A5"], g["D5"] = "Order: Buy or Sell?", "Sells need an extra reason - see row 13."
g["A6"], g["D6"] = "Ticker (ASX code)", "Must be on your Target Mix list in Settings."
g["A7"], g["D7"] = "Order size ($, before brokerage)", ""
g["A8"], g["D8"] = "Is the ticker in my Target Mix?", "No new ideas mid-stream. Change the plan at a review, not on impulse."
g["A9"], g["D9"] = "Brokerage as % of the order", "Above 1%, fees eat the return. Save up and buy less often instead."
g["A10"], g["D10"] = "Emergency fund in place? (Y/N)", "Never invest money you might need next year."
g["A11"], g["D11"] = "Will I leave this money for 5+ years? (Y/N)", "Shares can fall 30%+ and take years to recover."
g["A12"], g["D12"] = "Is this part of my monthly routine or yearly rebalance? (Y/N)", "Unplanned trades are where beginners lose money."
g["A13"], g["D13"] = "If SELLING: is it for rebalancing or a planned need, NOT because prices fell? (Y/N/NA)", "Panic selling is the #1 wealth destroyer."
g["A14"], g["D14"] = "Did a tip, forum, ad or news story prompt this? (Y/N)", "If yes, wait 7 days and come back."
for r in range(5, 15):
    for col in "ABCD":
        g[f"{col}{r}"].border = BOX
        g[f"{col}{r}"].alignment = WRAP
for r in (5, 6, 7, 10, 11, 12, 13, 14):
    g[f"B{r}"].fill = INPUT
g["B7"].number_format = MONEY
g["B8"] = '=IF(B6="","",IF(COUNTIF(Settings!A16:A25,B6)>0,"Yes","No"))'
g["B9"] = '=IF(N(B7)=0,"",Settings!B7/B7)'
g["B9"].number_format = PCT
for r in (8, 9):
    g[f"B{r}"].fill = CALC
g["C8"] = '=IF(B8="","",IF(B8="Yes","PASS","FAIL"))'
g["C9"] = '=IF(B9="","",IF(B9<=Settings!B8,"PASS","FAIL"))'
g["C10"] = '=IF(B10="","",IF(UPPER(B10)="Y","PASS","FAIL"))'
g["C11"] = '=IF(B11="","",IF(UPPER(B11)="Y","PASS","FAIL"))'
g["C12"] = '=IF(B12="","",IF(UPPER(B12)="Y","PASS","FAIL"))'
g["C13"] = '=IF(B13="","",IF(OR(UPPER(B13)="Y",AND(UPPER(B13)="NA",UPPER(B5)="BUY")),"PASS","FAIL"))'
g["C14"] = '=IF(B14="","",IF(UPPER(B14)="N","PASS","FAIL"))'
for r in range(8, 15):
    g[f"C{r}"].fill = CALC
    g[f"C{r}"].font = Font(bold=True)
g.conditional_formatting.add("C8:C14", CellIsRule(operator="equal", formula=['"PASS"'], fill=GOOD))
g.conditional_formatting.add("C8:C14", CellIsRule(operator="equal", formula=['"FAIL"'], fill=BAD))
g["A16"] = "GATE RESULT"
g["A16"].font = Font(bold=True, size=14)
g["B16"] = ('=IF(COUNTBLANK(B5:B14)>0,"Fill in every yellow cell",'
            'IF(COUNTIF(C8:C14,"FAIL")>0,"STOP - do not place this order","GO - place order, then log it"))')
g.merge_cells("B16:D16")
g["B16"].font = Font(bold=True, size=14)
g.conditional_formatting.add("B16", FormulaRule(formula=['LEFT($B$16,4)="STOP"'], fill=BAD))
g.conditional_formatting.add("B16", FormulaRule(formula=['LEFT($B$16,2)="GO"'], fill=GOOD))
g["A18"] = "After each order, clear the yellow cells (select them, press Delete) so it's fresh next time."
g["A18"].font = Font(italic=True, color="595959")
yn = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
ynna = DataValidation(type="list", formula1='"Y,N,NA"', allow_blank=True)
bs = DataValidation(type="list", formula1='"Buy,Sell"', allow_blank=True)
g.add_data_validation(yn)
g.add_data_validation(ynna)
g.add_data_validation(bs)
for ref in ("B10", "B11", "B12", "B14"):
    yn.add(ref)
ynna.add("B13")
bs.add("B5")

# ---------------------------------------------------------------- Transactions
t = wb.create_sheet("Transactions")
title(t, "Transactions", "One row per buy or sell. Copy figures from the broker's trade confirmation.")
header(t, 4, ["Date", "Ticker", "Buy/Sell", "Units", "Price per unit ($)", "Brokerage ($)",
              "Cash out(-) / in(+) ($)", "Brokerage % of order", "Gate passed? (Y/N)", "Notes / reason"],
       [13, 10, 10, 10, 16, 13, 20, 14, 12, 50])
tv = DataValidation(type="list", formula1='"Buy,Sell"', allow_blank=True)
gv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
t.add_data_validation(tv)
t.add_data_validation(gv)
for r in range(5, 5 + ROWS):
    for col in "ABCDEFIJ":
        t[f"{col}{r}"].fill = INPUT
    t[f"A{r}"].number_format = "DD/MM/YYYY"
    t[f"E{r}"].number_format = "$#,##0.0000"
    t[f"F{r}"].number_format = MONEY
    # Buys are cash out (negative), sells cash in (positive); brokerage always costs you.
    t[f"G{r}"] = f'=IF(OR(C{r}="",D{r}=""),"",IF(C{r}="Buy",-(D{r}*E{r}+F{r}),D{r}*E{r}-F{r}))'
    t[f"G{r}"].number_format = MONEY
    t[f"H{r}"] = f'=IF(OR(D{r}="",E{r}="",D{r}*E{r}=0),"",F{r}/(D{r}*E{r}))'
    t[f"H{r}"].number_format = PCT
    t[f"G{r}"].fill = t[f"H{r}"].fill = CALC
    tv.add(f"C{r}")
    gv.add(f"I{r}")
last = 4 + ROWS
t.conditional_formatting.add(f"H5:H{last}", FormulaRule(formula=[f'AND(H5<>"",H5>Settings!$B$8)'], fill=BAD))
t.conditional_formatting.add(f"I5:I{last}", CellIsRule(operator="equal", formula=['"N"'], fill=BAD))

# ---------------------------------------------------------------- Dividends
d = wb.create_sheet("Dividends")
title(d, "Dividends & Distributions",
      "One row per payment. Franking % is on the distribution statement (ETFs often 0-80%).")
header(d, 4, ["Pay date", "Ticker", "Cash received ($)", "Franked % (0-100%)", "Franking credit ($)",
              "Reinvested? (Y/N)", "Units received if reinvested", "Financial year", "Notes"],
       [13, 10, 16, 16, 16, 13, 16, 13, 40])
dv = DataValidation(type="list", formula1='"Y,N"', allow_blank=True)
d.add_data_validation(dv)
for r in range(5, 5 + ROWS):
    for col in "ABCDFGI":
        d[f"{col}{r}"].fill = INPUT
    d[f"A{r}"].number_format = "DD/MM/YYYY"
    d[f"C{r}"].number_format = MONEY
    d[f"D{r}"].number_format = "0%"
    # Franking credit = franked portion x 30/70 (company tax rate 30%).
    d[f"E{r}"] = f'=IF(C{r}="","",C{r}*N(D{r})*30/70)'
    d[f"E{r}"].number_format = MONEY
    # Australian financial year label: Jul 2026-Jun 2027 = "FY2027".
    d[f"H{r}"] = f'=IF(A{r}="","","FY"&(YEAR(A{r})+IF(MONTH(A{r})>=7,1,0)))'
    d[f"E{r}"].fill = d[f"H{r}"].fill = CALC
    dv.add(f"F{r}")

# ---------------------------------------------------------------- Prices
p = wb.create_sheet("Prices")
title(p, "Latest prices", "Update monthly. Ticker list should match Settings > Target Mix.")
header(p, 4, ["Ticker", "Latest price ($)", "Price date"], [12, 16, 14])
for r in range(5, 25):
    for col in "ABC":
        p[f"{col}{r}"].fill = INPUT
    p[f"B{r}"].number_format = "$#,##0.0000"
    p[f"C{r}"].number_format = "DD/MM/YYYY"
p["A5"] = "VDHG"

# ---------------------------------------------------------------- Holdings
h = wb.create_sheet("Holdings")
title(h, "Holdings", "All calculated. Tickers come from Settings > Target Mix.")
header(h, 4, ["Ticker", "Units held", "Total cost incl. brokerage ($)", "Average cost / unit ($)",
              "Latest price ($)", "Market value ($)", "Gain/loss ($)", "Gain/loss %",
              "Actual % of portfolio", "Target %", "Drift (actual - target)"],
       [10, 11, 18, 15, 13, 15, 15, 11, 13, 10, 14])
TX = f"Transactions!$B$5:$B${last}"
for i, r in enumerate(range(5, 15)):
    s = 16 + i
    h[f"A{r}"] = f'=IF(Settings!A{s}="","",Settings!A{s})'
    h[f"B{r}"] = (f'=IF(A{r}="","",SUMIFS(Transactions!$D$5:$D${last},{TX},A{r},Transactions!$C$5:$C${last},"Buy")'
                  f'-SUMIFS(Transactions!$D$5:$D${last},{TX},A{r},Transactions!$C$5:$C${last},"Sell"))')
    # Cost base: average-cost method; a sell removes cost in proportion to units sold.
    buys_cost = f'-SUMIFS(Transactions!$G$5:$G${last},{TX},A{r},Transactions!$C$5:$C${last},"Buy")'
    buys_units = f'SUMIFS(Transactions!$D$5:$D${last},{TX},A{r},Transactions!$C$5:$C${last},"Buy")'
    h[f"C{r}"] = f'=IF(A{r}="","",IF({buys_units}=0,0,({buys_cost})*B{r}/{buys_units}))'
    h[f"D{r}"] = f'=IF(OR(A{r}="",N(B{r})=0),"",C{r}/B{r})'
    h[f"E{r}"] = f'=IF(A{r}="","",IFERROR(VLOOKUP(A{r},Prices!$A$5:$B$24,2,FALSE),""))'
    h[f"F{r}"] = f'=IF(OR(A{r}="",E{r}=""),"",B{r}*E{r})'
    h[f"G{r}"] = f'=IF(F{r}="","",F{r}-C{r})'
    h[f"H{r}"] = f'=IF(OR(G{r}="",N(C{r})=0),"",G{r}/C{r})'
    h[f"I{r}"] = f'=IF(OR(F{r}="",N($F$16)=0),"",F{r}/$F$16)'
    h[f"J{r}"] = f'=IF(A{r}="","",Settings!B{s})'
    h[f"K{r}"] = f'=IF(I{r}="","",I{r}-J{r})'
    for col, fmt in zip("BCDEFGHIJK", ["0.####", MONEY, "$#,##0.0000", "$#,##0.0000", MONEY, MONEY,
                                       PCT, PCT, "0%", PCT]):
        h[f"{col}{r}"].number_format = fmt
    for col in "ABCDEFGHIJK":
        h[f"{col}{r}"].fill, h[f"{col}{r}"].border = CALC, BOX
h["A16"] = "TOTAL"
h["A16"].font = Font(bold=True)
h["C16"] = "=SUM(C5:C14)"
h["F16"] = "=SUM(F5:F14)"
h["G16"] = "=F16-C16"
h["H16"] = '=IF(C16=0,"",G16/C16)'
for col, fmt in zip("CFGH", [MONEY, MONEY, MONEY, PCT]):
    h[f"{col}16"].number_format = fmt
    h[f"{col}16"].font = Font(bold=True)
h.conditional_formatting.add("K5:K14", FormulaRule(formula=['AND(K5<>"",ABS(K5)>0.05)'], fill=BAD))
h["A18"] = "Red drift = more than 5 percentage points off target. Fix it at the yearly rebalance by directing new money to the underweight fund (cheaper than selling)."
h["A18"].font = Font(italic=True, color="595959")

# ---------------------------------------------------------------- Dashboard
db = wb.create_sheet("Dashboard", 1)
title(db, "Dashboard", "Read-only. Judge the PROCESS, not this month's price.")
db.column_dimensions["A"].width = 52
db.column_dimensions["B"].width = 20
db.column_dimensions["C"].width = 70
rows = [
    ("MONEY", None, None, None),
    ("Total cash put in (buys incl. brokerage)", f'=-SUMIF(Transactions!$C$5:$C${last},"Buy",Transactions!$G$5:$G${last})', MONEY, ""),
    ("Total cash taken out (sells after brokerage)", f'=SUMIF(Transactions!$C$5:$C${last},"Sell",Transactions!$G$5:$G${last})', MONEY, ""),
    ("Current market value", "=Holdings!F16", MONEY, "Only as fresh as your last Prices update."),
    ("Dividends received (cash)", f"=SUM(Dividends!$C$5:$C${last})", MONEY, "Includes reinvested amounts."),
    ("Franking credits earned", f"=SUM(Dividends!$E$5:$E${last})", MONEY, "A tax credit, claimed at tax time. Can be refunded if your tax is low."),
    ("Total gain (value + money out + dividends - money in)", "=B7+B6+B8-B5", MONEY, "Includes dividends, so this is your true total return in dollars."),
    ("Total gain % on money put in", '=IF(B5=0,"",B10/B5)', PCT, ""),
    (None, None, None, None),
    ("PROCESS SCORECARD (this is what you grade yourself on)", None, None, None),
    ("Total brokerage paid", f"=SUM(Transactions!$F$5:$F${last})", MONEY, ""),
    ("Brokerage as % of all money invested", '=IF(B5=0,"",B14/B5)', PCT, "Target: under 0.5% overall. Above 1% = trading too often in small amounts."),
    ("Number of trades", f'=COUNTIF(Transactions!$C$5:$C${last},"Buy")+COUNTIF(Transactions!$C$5:$C${last},"Sell")', "0", ""),
    ("Trades that did NOT pass the Gate", f'=COUNTIF(Transactions!$I$5:$I${last},"N")', "0", "Target: 0. Every one of these is a process failure even if it made money."),
    ("Sells", f'=COUNTIF(Transactions!$C$5:$C${last},"Sell")', "0", "In Years 1-3 this should be 0 or 1 (rebalance only)."),
    ("Largest drift from target mix", "=MAX(MAX(Holdings!K5:K14),-MIN(Holdings!K5:K14))", PCT, "Under 5% is fine."),
    (None, None, None, None),
    ("REALITY CHECK - what 'income' this produces", None, None, None),
    ("Value x 3.5% (rough yearly distribution estimate)", "=B7*0.035", MONEY, "ASX 200 cash yield has recently been ~3.3-3.5%. Diversified ETFs often lower. An estimate, not a promise."),
    ("Per week", "=B22/52", MONEY, "This is why contributions matter far more than picking."),
]
for i, (label, formula, fmt, note) in enumerate(rows, start=4):
    if label is None:
        continue
    a = db.cell(row=i, column=1, value=label)
    if formula is None:
        a.font = Font(bold=True, color="1F3864", size=12)
        continue
    b = db.cell(row=i, column=2, value=formula)
    b.number_format, b.fill, b.border = fmt, CALC, BOX
    db.cell(row=i, column=3, value=note).alignment = WRAP
db.conditional_formatting.add("B15", FormulaRule(formula=['AND(B15<>"",B15>0.01)'], fill=BAD))
db.conditional_formatting.add("B15", FormulaRule(formula=['AND(B15<>"",B15<=0.005)'], fill=GOOD))
db.conditional_formatting.add("B17", CellIsRule(operator="greaterThan", formula=["0"], fill=BAD))
db.conditional_formatting.add("B17", CellIsRule(operator="equal", formula=["0"], fill=GOOD))
db["A26"] = ("Reinvested dividends (DRP): enter the payment in Dividends AND the new units in Transactions as a Buy "
             "with brokerage 0 and price = cash / units. The gain line stays correct; 'Total cash put in' will then include "
             "reinvested money as well as your own deposits.")
db["A26"].alignment = WRAP
db.merge_cells("A26:C28")
db.row_dimensions[26].height = 30

wb.save(OUT)
print(f"Saved {OUT}")
