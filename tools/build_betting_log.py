"""
Build the Unleashed betting log workbook (macro-free .xlsx).

Design notes
------------
* NO operational parameter is hardcoded anywhere in this workbook.
  Bank, unit size, commission, stake-tier multipliers and the sample-size
  threshold are blank input cells on the Settings tab, filled by C1 from
  the Rulebook. Where a multiplier is unset the log prints SET MULTIPLIER
  rather than guessing a stake.
* Staking is TIER-weighted, never edge-proportional: Kelly-as-staking-driver
  is a retired concept (SKILL.md house style, Rulebook Section 12.2 scaling
  discipline). A tier multiplier is C1's judgement; the workbook only
  measures whether that judgement tracks CLV.
* Result means "did YOUR BET win", not "did the selection win".
  A winning lay is Result = Win.
* CLV $ = expected profit if the closing price is the true price.
  CLV % = CLV $ / money at risk, so backs and lays are comparable.
* CLV is measured gross of commission (it is a price measure);
  P/L is net of commission.

Columns are addressed through the COL map, never by hardcoded letters, so
inserting a column cannot silently break a downstream formula.

Usage:  python build_betting_log.py <output.xlsx> [--demo]
"""
import os
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side as BSide
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule, CellIsRule
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.comments import Comment

LAST = int(os.environ.get("LOG_ROWS", "1501"))   # last bet row (1500 bets)
SEC_ROW = 11          # Settings: "dropdown lists" banner
NOTE_ROW = 12
LIST_HDR = 14         # Settings: list header row
LIST_1 = 15           # Settings: first list data row
LIST_N = 64           # Settings: last list data row
SPARE = 15            # blank rows left under each list for C1 to extend

FONT = "Arial"
NAVY, TEAL, GREY = "1F3A5F", "0F6E6E", "F2F4F7"
AMBER, GREEN, RED, YELLOW = "FFF3CD", "E3F4E6", "FBE3E3", "FFF2A8"

MONEY = '$#,##0.00;[Red]($#,##0.00)'
MONEY0 = '$#,##0;[Red]($#,##0)'
PCT = '0.0%'
PCTS = '+0.0%;-0.0%;0.0%'
ODDS = '0.00'
DATEF = 'DD/MM/YYYY'
INT = '#,##0'
NUM2 = '0.00'

thin = BSide(style="thin", color="D0D5DD")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)


def title_cell(ws, ref, text, size=14, colour=NAVY):
    ws[ref] = text
    ws[ref].font = Font(name=FONT, size=size, bold=True, color=colour)


def section(ws, ref, text):
    ws[ref] = text
    ws[ref].font = Font(name=FONT, size=11, bold=True, color="FFFFFF")
    ws[ref].fill = PatternFill("solid", fgColor=TEAL)
    ws[ref].alignment = Alignment(horizontal="left", vertical="center")


def label(ws, ref, text, bold=False, italic=False, colour="344054"):
    ws[ref] = text
    ws[ref].font = Font(name=FONT, size=10, bold=bold, italic=italic, color=colour)


def value(ws, ref, formula, fmt=None):
    ws[ref] = formula
    ws[ref].font = Font(name=FONT, size=11, bold=True, color=NAVY)
    ws[ref].alignment = Alignment(horizontal="right")
    if fmt:
        ws[ref].number_format = fmt


def yellow(ws, ref, fmt, note):
    c = ws[ref]
    c.fill = PatternFill("solid", fgColor=YELLOW)
    c.border = BOX
    if fmt:
        c.number_format = fmt
    c.font = Font(name=FONT, size=11, bold=True)
    c.alignment = Alignment(horizontal="center")
    c.comment = Comment(note, "Unleashed Betting Log")


# ---------------------------------------------------------------- columns
# key, header, width, number format, kind
#   in   = typed when the bet is placed      late = filled in afterwards
#   auto = calculated, never typed in        help = calculated, hidden
COLUMNS = [
    ("date",        "Date",            11, DATEF,  "in"),
    ("sport",       "Sport",           12, None,   "in"),
    ("comp",        "Competition",     16, None,   "in"),
    ("event",       "Event",           24, None,   "in"),
    ("selection",   "Selection",       19, None,   "in"),
    ("market",      "Market",          22, None,   "in"),
    ("line",        "Line / Total",    11, NUM2,   "in"),
    ("side",        "Side",             8, None,   "in"),
    ("odds",        "Odds Taken",      10, ODDS,   "in"),
    ("tier",        "Stake Tier",      12, None,   "in"),
    ("mult",        "Multiplier",      10, NUM2,   "auto"),
    ("plan_stake",  "Plan Stake",      12, MONEY0, "auto"),
    ("stake",       "Stake",           10, MONEY0, "in"),
    ("vs_plan",     "Stake vs Plan",   12, PCTS,   "auto"),
    ("fair_odds",   "Fair Odds",       10, ODDS,   "in"),
    ("trigger",     "Trigger",         20, None,   "in"),
    ("gate",        "Gate",             8, None,   "in"),
    ("platform",    "Platform",        16, None,   "in"),
    ("note",        "Note",            26, None,   "in"),
    ("close",       "Closing Odds",    11, ODDS,   "late"),
    ("result",      "Result",          12, None,   "late"),
    ("manual_pl",   "Manual P/L",      11, MONEY,  "late"),
    ("stream",      "Stream",          11, None,   "auto"),
    ("comm",        "Comm %",           8, PCT,    "auto"),
    ("at_risk",     "At Risk",         11, MONEY,  "auto"),
    ("implied",     "Implied %",        9, PCT,    "auto"),
    ("fair_pct",    "Fair %",           9, PCT,    "auto"),
    ("edge",        "Edge %",           9, PCT,    "auto"),
    ("clv_pct",     "CLV %",            9, PCT,    "auto"),
    ("clv",         "CLV $",           10, MONEY,  "auto"),
    ("beat",        "Beat Close",      10, None,   "auto"),
    ("pl",          "P/L",             11, MONEY,  "auto"),
    ("units",       "Units",            8, NUM2,   "auto"),
    ("bank_open",   "Bank Before",     13, MONEY,  "auto"),
    ("bank_close",  "Bank After",      13, MONEY,  "auto"),
    ("status",      "Status",          17, None,   "auto"),
    ("roll_clv",    "Rolling CLV %",   11, PCT,    "auto"),
    ("exp_bank",    "Bank if CLV is right", 13, MONEY, "auto"),
    ("pl_plan",     "P/L at Plan Stake",   13, MONEY, "help"),
    ("pl_matched",  "P/L where a plan exists", 13, MONEY, "help"),
    ("clv_matched", "CLV $ where a plan exists", 13, MONEY, "help"),
    ("clv_plan",    "CLV $ at Plan Stake", 13, MONEY, "help"),
    ("peak",        "Bank peak",       11, MONEY,  "help"),
    ("drawdown",    "Drawdown",        11, MONEY,  "help"),
    ("band",        "Odds Band",       12, None,   "help"),
    ("month",       "Month",           10, None,   "help"),
]
COL = {k: get_column_letter(i) for i, (k, *_r) in enumerate(COLUMNS, start=1)}
IDX = {k: i for i, (k, *_r) in enumerate(COLUMNS, start=1)}


def c(key, row=""):
    """Absolute-column reference, e.g. c('stake', 7) -> $M7"""
    return f"${COL[key]}{row}"


def rng(key):
    """Whole-column data range on the Bet Log, e.g. $M$2:$M$501"""
    return f"${COL[key]}$2:${COL[key]}${LAST}"


def lg(key):
    """Same range, qualified for use from another sheet."""
    return f"'Bet Log'!{rng(key)}"


wb = Workbook()
ws_log = wb.active
ws_log.title = "Bet Log"
ws_dash = wb.create_sheet("Dashboard")
ws_work = wb.create_sheet("Whats Working")
ws_set = wb.create_sheet("Settings")
ws_help = wb.create_sheet("How To Use")

# ================================================================ SETTINGS
title_cell(ws_set, "A1", "SETTINGS")
label(ws_set, "A2",
      "Fill the yellow cells once. Every figure here comes from the Rulebook - "
      "this workbook deliberately contains no numbers of its own.", italic=True)

inputs = [
    ("Starting bank ($)", "B3", MONEY0,
     "Your bankroll at the moment you start this log. Rulebook - bankroll section."),
    ("Unit size ($)", "B4", MONEY0,
     "One unit in dollars. Rulebook - staking section. A Tier multiplier is applied "
     "to this to get the planned stake."),
    ("Betfair commission rate", "B5", PCT,
     "Your actual Betfair rate. Type 5% or 0.05. Taken off winnings only, never off CLV."),
    ("Bookmaker / TAB commission", "B6", PCT,
     "Usually 0%. Type 0 if so - the cell must not be left blank."),
    ("Minimum bets before a verdict", "B7", INT,
     "How many settled-with-closing-price bets a segment needs before the "
     "'Whats Working' tab will call it good or bad. A statistical display "
     "threshold, not a Rulebook parameter. 30 is a common starting point."),
    ("Stake sizing basis", "B8", None,
     "Fixed dollars = every unit is the same dollar amount. "
     "Percent of bank = a unit is a share of the bank as it stands before the bet, "
     "so stakes compound up and cut back down."),
    ("Percent of bank per unit", "B9", PCT,
     "Only used when the basis above is 'Percent of bank'. Rulebook - staking section. "
     "Leave it blank on Fixed dollars."),
]
for i, (ltext, vref, fmt, note) in enumerate(inputs):
    r = 3 + i
    label(ws_set, f"A{r}", ltext, bold=True)
    yellow(ws_set, vref, fmt, note)
    label(ws_set, f"C{r}", note, italic=True, colour="667085")

section(ws_set, f"A{SEC_ROW}",
        "DROPDOWN LISTS - edit freely. Add a row and the dropdown picks it up automatically.")
ws_set.merge_cells(f"A{SEC_ROW}:R{SEC_ROW}")
label(ws_set, f"A{NOTE_ROW}",
      "Commission sits beside its Platform, Stream beside its Trigger, and Multiplier "
      "beside its Stake Tier - keep each pair on the same row. "
      "Leave a Multiplier blank and the log prints SET MULTIPLIER instead of guessing a stake.",
      italic=True, colour="667085")
ws_set.merge_cells(f"A{NOTE_ROW}:R{NOTE_ROW}")

lists = {
    "D": ("Sport", ["AFL", "Soccer", "Horse Racing", "Other"]),
    "E": ("Competition", [
        "AFL", "AFLW", "EPL", "Championship", "League One", "League Two",
        "A-League Men", "A-League Women", "Scottish Premiership", "La Liga",
        "Serie A", "Bundesliga", "Ligue 1", "Eredivisie", "J1 League",
        "K League 1", "MLS", "Brasileirao", "UEFA Champions League", "Other"]),
    "F": ("Market", [
        "Match Odds", "Double Chance", "Both Teams To Score",
        "Over/Under 0.5 Goals", "Over/Under 1.5 Goals", "Over/Under 2.5 Goals",
        "Over/Under 3.5 Goals", "Over/Under 4.5 Goals", "Over/Under 5.5 Goals",
        "Line", "Match Total", "Asian Handicap", "Draw No Bet",
        "Half Time / Full Time", "Correct Score", "Margin",
        "Win (Racing)", "Place (Racing)", "Other"]),
    "G": ("Side", ["Back", "Lay"]),
    "H": ("Result", ["Win", "Half Win", "Lose", "Half Lose", "Void", "Push", "Cashed Out"]),
    "I": ("Platform", ["Betfair Exchange", "Bookmaker", "TAB"]),
    "K": ("Gate", ["PASS", "FAIL"]),
    "L": ("Trigger", ["One Kick Test", "4-Game Win Ceiling", "xG Regression",
                      "Promotion Year 1", "Relegation Year 1", "TAB Instinct", "Other"]),
    "N": ("Stream list", ["Framework", "TAB"]),
    "O": ("Odds band list", ["1.01 - 1.49", "1.50 - 1.99", "2.00 - 2.99",
                             "3.00 - 4.99", "5.00 - 9.99", "10.00 +"]),
    "P": ("Stake Tier", ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Tier 5"]),
    "R": ("Sizing basis", ["Fixed dollars", "Percent of bank"]),
}
for col, (hdr, items) in lists.items():
    h = ws_set[f"{col}{LIST_HDR}"]
    h.value = hdr
    h.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
    h.fill = PatternFill("solid", fgColor=NAVY)
    h.alignment = Alignment(horizontal="center")
    for i, v in enumerate(items):
        cell = ws_set[f"{col}{LIST_1 + i}"]
        cell.value = v
        cell.font = Font(name=FONT, size=10)

for col, hdr in (("J", "Commission"), ("M", "Stream"), ("Q", "Multiplier")):
    h = ws_set[f"{col}{LIST_HDR}"]
    h.value = hdr
    h.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
    h.fill = PatternFill("solid", fgColor="667085")
    h.alignment = Alignment(horizontal="center")

for i, f in enumerate(["=$B$5", "=$B$6", "=$B$6"]):
    cell = ws_set[f"J{LIST_1 + i}"]
    cell.value = f
    cell.number_format = PCT
    cell.font = Font(name=FONT, size=10)

for i, s in enumerate(["Framework", "Framework", "Framework",
                       "Framework", "Framework", "TAB", "Framework"]):
    ws_set[f"M{LIST_1 + i}"] = s
    ws_set[f"M{LIST_1 + i}"].font = Font(name=FONT, size=10)

# Tier multipliers are Rulebook parameters, so they ship BLANK.
for i in range(len(lists["P"][1])):
    yellow(ws_set, f"Q{LIST_1 + i}", NUM2,
           "Multiplier on your unit size for this tier. From the Rulebook - staking "
           "section. Left blank, the log prints SET MULTIPLIER rather than inventing "
           "a stake for you.")

# ranges sized to the list plus spare rows; plain ranges, not dynamic names,
# because OFFSET/COUNTA validation is unreliable in Excel for Android/iOS
LIST_RANGE = {}
for _col, (_hdr, _items) in lists.items():
    LIST_RANGE[_col] = f"Settings!${_col}${LIST_1}:${_col}${LIST_1 + len(_items) - 1 + SPARE}"
    for _r in range(LIST_1 + len(_items), LIST_1 + len(_items) + SPARE):
        cell = ws_set[f"{_col}{_r}"]
        cell.fill = PatternFill("solid", fgColor="F7F9FC")
        cell.border = BOX

dv_basis = DataValidation(type="list", formula1=LIST_RANGE["R"], allow_blank=True)
ws_set.add_data_validation(dv_basis)
dv_basis.add("B8")

for col, w in {"A": 30, "B": 14, "C": 58, "D": 14, "E": 22, "F": 24, "G": 9,
               "H": 12, "I": 18, "J": 12, "K": 9, "L": 22, "M": 13,
               "N": 13, "O": 14, "P": 12, "Q": 12, "R": 17}.items():
    ws_set.column_dimensions[col].width = w

# ================================================================ BET LOG
HDR_FILL = {"in": NAVY, "late": "B54708", "auto": "475467", "help": "98A2B3"}
for i, (key, name, width, fmt, kind) in enumerate(COLUMNS, start=1):
    col = get_column_letter(i)
    cell = ws_log.cell(row=1, column=i, value=name)
    cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
    cell.fill = PatternFill("solid", fgColor=HDR_FILL[kind])
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BOX
    ws_log.column_dimensions[col].width = width
    if kind == "help":
        ws_log.column_dimensions[col].hidden = True
ws_log.row_dimensions[1].height = 30
ws_log.freeze_panes = "B2"   # row 1 + Date: still usable on a phone screen

notes = {
    "date": "Press Ctrl+; to type today's date.\nDark blue headers = you type these when you "
            "place the bet.\nOrange headers = you fill these in later.\nGrey headers = "
            "calculated, never type in them.",
    "tier": "Your confidence tier for this bet. The multiplier beside it on the Settings tab "
            "turns your unit into a planned stake.\nTiers are YOUR judgement. The workbook "
            "does not size bets off your own edge estimate - that amplifies optimism. It "
            "measures instead whether your tiers actually track CLV.",
    "plan_stake": "What the tier says you should stake. Calculated - do not type here.\n"
                  "Reads SET MULTIPLIER until that tier's multiplier is filled in on Settings.",
    "stake": "What you ACTUALLY staked. For a back bet, the amount you put up. For a lay, the "
             "backer's stake - the same number Betfair asks you for. Liability is worked out "
             "for you.",
    "vs_plan": "How far the actual stake sat from the plan. 0% means on plan.",
    "line": "For Line, Match Total and Asian Handicap - type the number you took, "
            "e.g. -12.5 or 165.5. Leave blank for other markets.",
    "result": "Result means DID YOUR BET WIN - not did the selection win.\n"
              "A lay that lands (selection lost) is a Win.",
    "manual_pl": "Only use this for a cash-out or a partly matched bet. Type the real profit "
                 "or loss and it overrides the calculation.",
    "bank_open": "Your bank immediately BEFORE this bet settled.",
    "bank_close": "Your bank immediately AFTER this bet settled.",
}
for key, text in notes.items():
    ws_log[f"{COL[key]}1"].comment = Comment(text, "Unleashed Betting Log")

S = "Settings!"
for r in range(2, LAST + 1):
    p, w0 = r - 1, max(2, r - 19)

    ws_log[f"{COL['stream']}{r}"] = (
        f'=IF({c("trigger", r)}="","",IFERROR(INDEX({S}$M${LIST_1}:$M${LIST_N},'
        f'MATCH({c("trigger", r)},{S}$L${LIST_1}:$L${LIST_N},0)),""))')
    ws_log[f"{COL['comm']}{r}"] = (
        f'=IF({c("platform", r)}="","",IFERROR(INDEX({S}$J${LIST_1}:$J${LIST_N},'
        f'MATCH({c("platform", r)},{S}$I${LIST_1}:$I${LIST_N},0)),0))')
    # a blank multiplier cell indexes to 0, which would silently stake nothing
    _mi = (f'INDEX({S}$Q${LIST_1}:$Q${LIST_N},'
           f'MATCH({c("tier", r)},{S}$P${LIST_1}:$P${LIST_N},0))')
    ws_log[f"{COL['mult']}{r}"] = (
        f'=IF({c("tier", r)}="","",IFERROR(IF({_mi}="","",{_mi}),""))')
    ws_log[f"{COL['plan_stake']}{r}"] = (
        f'=IF({c("tier", r)}="","",'
        f'IF({c("mult", r)}="","SET MULTIPLIER",'
        f'IF({S}$B$8="Percent of bank",'
        f'IF({S}$B$9="","SET PERCENT",{c("bank_open", r)}*{S}$B$9*{c("mult", r)}),'
        f'IF({S}$B$4="","SET UNIT",{S}$B$4*{c("mult", r)}))))')
    ws_log[f"{COL['vs_plan']}{r}"] = (
        f'=IF(OR({c("stake", r)}="",NOT(ISNUMBER({c("plan_stake", r)})),'
        f'{c("plan_stake", r)}=0),"",{c("stake", r)}/{c("plan_stake", r)}-1)')
    ws_log[f"{COL['at_risk']}{r}"] = (
        f'=IF(OR({c("odds", r)}="",{c("stake", r)}=""),"",'
        f'IF({c("side", r)}="Lay",{c("stake", r)}*({c("odds", r)}-1),{c("stake", r)}))')
    ws_log[f"{COL['implied']}{r}"] = f'=IF({c("odds", r)}="","",1/{c("odds", r)})'
    ws_log[f"{COL['fair_pct']}{r}"] = f'=IF({c("fair_odds", r)}="","",1/{c("fair_odds", r)})'
    ws_log[f"{COL['edge']}{r}"] = (
        f'=IF(OR({c("fair_odds", r)}="",{c("odds", r)}="",{c("at_risk", r)}=""),"",IFERROR('
        f'IF({c("side", r)}="Lay",{c("stake", r)}*(1-{c("odds", r)}/{c("fair_odds", r)}),'
        f'{c("stake", r)}*({c("odds", r)}/{c("fair_odds", r)}-1))/{c("at_risk", r)},""))')
    ws_log[f"{COL['clv']}{r}"] = (
        f'=IF(OR({c("close", r)}="",{c("odds", r)}="",{c("stake", r)}=""),"",'
        f'IF({c("side", r)}="Lay",{c("stake", r)}*(1-{c("odds", r)}/{c("close", r)}),'
        f'{c("stake", r)}*({c("odds", r)}/{c("close", r)}-1)))')
    ws_log[f"{COL['clv_pct']}{r}"] = (
        f'=IF(OR({c("clv", r)}="",{c("at_risk", r)}=""),"",'
        f'IFERROR({c("clv", r)}/{c("at_risk", r)},""))')
    ws_log[f"{COL['beat']}{r}"] = (
        f'=IF({c("clv", r)}="","",IF({c("clv", r)}>0,"YES",'
        f'IF({c("clv", r)}<0,"NO","LEVEL")))')
    ws_log[f"{COL['pl']}{r}"] = (
        f'=IF({c("manual_pl", r)}<>"",{c("manual_pl", r)},'
        f'IF({c("result", r)}="","",'
        f'IF(OR({c("result", r)}="Void",{c("result", r)}="Push"),0,'
        f'IF({c("result", r)}="Cashed Out","",'
        f'IF({c("side", r)}="Lay",'
        f'IF({c("result", r)}="Win",{c("stake", r)}*(1-{c("comm", r)}),'
        f'IF({c("result", r)}="Half Win",{c("stake", r)}*0.5*(1-{c("comm", r)}),'
        f'IF({c("result", r)}="Lose",-{c("stake", r)}*({c("odds", r)}-1),'
        f'IF({c("result", r)}="Half Lose",-{c("stake", r)}*({c("odds", r)}-1)*0.5,"")))),'
        f'IF({c("result", r)}="Win",{c("stake", r)}*({c("odds", r)}-1)*(1-{c("comm", r)}),'
        f'IF({c("result", r)}="Half Win",'
        f'{c("stake", r)}*({c("odds", r)}-1)*0.5*(1-{c("comm", r)}),'
        f'IF({c("result", r)}="Lose",-{c("stake", r)},'
        f'IF({c("result", r)}="Half Lose",-{c("stake", r)}*0.5,""))))'
        f')))))')
    ws_log[f"{COL['units']}{r}"] = (
        f'=IF(OR({c("at_risk", r)}="",{S}$B$4=""),"",'
        f'IFERROR({c("at_risk", r)}/{S}$B$4,""))')
    ws_log[f"{COL['bank_open']}{r}"] = (
        f'={S}$B$3' if r == 2 else f'={c("bank_close", p)}')
    ws_log[f"{COL['bank_close']}{r}"] = (
        f'={c("bank_open", r)}+IF(ISNUMBER({c("pl", r)}),{c("pl", r)},0)')
    ws_log[f"{COL['status']}{r}"] = (
        f'=IF({c("date", r)}="","",IF({c("close", r)}="","AWAITING CLOSE",'
        f'IF({c("result", r)}="","AWAITING RESULT","SETTLED")))')
    if r == 2:
        ws_log[f"{COL['roll_clv']}{r}"] = (
            f'=IF(OR({c("date", r)}="",'
            f'COUNT(${COL["clv_pct"]}$2:${COL["clv_pct"]}2)=0),0,'
            f'AVERAGE(${COL["clv_pct"]}$2:${COL["clv_pct"]}2))')
    else:
        ws_log[f"{COL['roll_clv']}{r}"] = (
            f'=IF(OR({c("date", r)}="",'
            f'COUNT(${COL["clv_pct"]}{w0}:${COL["clv_pct"]}{r})=0),{c("roll_clv", p)},'
            f'AVERAGE(${COL["clv_pct"]}{w0}:${COL["clv_pct"]}{r}))')
    ws_log[f"{COL['exp_bank']}{r}"] = (
        (f'={S}$B$3' if r == 2 else f'={c("exp_bank", p)}')
        + f'+IF(ISNUMBER({c("clv", r)}),{c("clv", r)},0)')
    for dst, src in (("pl_plan", "pl"), ("clv_plan", "clv")):
        ws_log[f"{COL[dst]}{r}"] = (
            f'=IF(OR(NOT(ISNUMBER({c(src, r)})),NOT(ISNUMBER({c("plan_stake", r)})),'
            f'NOT(ISNUMBER({c("stake", r)})),{c("stake", r)}=0),"",'
            f'{c(src, r)}*{c("plan_stake", r)}/{c("stake", r)})')
    ws_log[f"{COL['pl_matched']}{r}"] = (
        f'=IF({c("pl_plan", r)}="","",{c("pl", r)})')
    ws_log[f"{COL['clv_matched']}{r}"] = (
        f'=IF({c("clv_plan", r)}="","",{c("clv", r)})')
    ws_log[f"{COL['peak']}{r}"] = (
        f'={c("bank_close", r)}' if r == 2
        else f'=MAX({c("peak", p)},{c("bank_close", r)})')
    ws_log[f"{COL['drawdown']}{r}"] = f'={c("peak", r)}-{c("bank_close", r)}'
    ws_log[f"{COL['band']}{r}"] = (
        f'=IF({c("odds", r)}="","",IF({c("odds", r)}<1.5,"1.01 - 1.49",'
        f'IF({c("odds", r)}<2,"1.50 - 1.99",IF({c("odds", r)}<3,"2.00 - 2.99",'
        f'IF({c("odds", r)}<5,"3.00 - 4.99",IF({c("odds", r)}<10,"5.00 - 9.99",'
        f'"10.00 +"))))))')
    ws_log[f"{COL['month']}{r}"] = f'=IF({c("date", r)}="","",TEXT({c("date", r)},"YYYY-MM"))'

    for i, (key, _n, _w, fmt, kind) in enumerate(COLUMNS, start=1):
        cell = ws_log.cell(row=r, column=i)
        cell.font = Font(name=FONT, size=10)
        if fmt:
            cell.number_format = fmt
        cell.fill = PatternFill("solid", fgColor={
            "in": "FFFFFF", "late": "FFFBF0", "auto": GREY, "help": GREY}[kind])
    for key in ("side", "gate", "beat", "status", "stream", "tier", "vs_plan"):
        ws_log[f"{COL[key]}{r}"].alignment = Alignment(horizontal="center")

# ---- example row, meant to be typed over
example = {"date": "=TODAY()", "sport": "Soccer", "comp": "EPL",
           "event": "Everton v Brentford", "selection": "Over 2.5 Goals",
           "market": "Over/Under 2.5 Goals", "line": 2.5, "side": "Back",
           "odds": 2.46, "tier": "Tier 2", "stake": 50, "fair_odds": 2.20,
           "trigger": "xG Regression", "gate": "PASS", "platform": "Betfair Exchange",
           "note": "EXAMPLE ROW - type your first real bet over the top of it",
           "close": 2.30, "result": "Lose"}
for key, v in example.items():
    cell = ws_log[f"{COL[key]}2"]
    cell.value = v
    cell.fill = PatternFill("solid", fgColor=YELLOW)
    cell.font = Font(name=FONT, size=10, italic=True)
ws_log[f"{COL['date']}2"].number_format = DATEF

# ---- dropdowns
for key, src in (("sport", "D"), ("comp", "E"), ("market", "F"), ("side", "G"),
                 ("trigger", "L"), ("gate", "K"), ("platform", "I"),
                 ("result", "H"), ("tier", "P")):
    dv = DataValidation(type="list", formula1=LIST_RANGE[src], allow_blank=True)
    dv.error = "Pick from the list, or add your entry to the Settings tab first."
    dv.errorTitle = "Not on the list"
    dv.prompt = "Tap the arrow to choose."
    ws_log.add_data_validation(dv)
    dv.add(f"{COL[key]}2:{COL[key]}{LAST}")

# ---- conditional formatting
CF = ws_log.conditional_formatting
CF.add(f"{COL['close']}2:{COL['close']}{LAST}", FormulaRule(
    formula=[f'AND({c("date", 2)}<>"",{c("close", 2)}="")'],
    fill=PatternFill("solid", fgColor=AMBER)))
CF.add(f"{COL['result']}2:{COL['result']}{LAST}", FormulaRule(
    formula=[f'AND({c("date", 2)}<>"",{c("close", 2)}<>"",{c("result", 2)}="")'],
    fill=PatternFill("solid", fgColor=AMBER)))
CF.add(f"{COL['gate']}2:{COL['gate']}{LAST}", CellIsRule(
    operator="equal", formula=['"FAIL"'], fill=PatternFill("solid", fgColor=RED),
    font=Font(name=FONT, size=10, bold=True, color="912018")))
CF.add(f"{COL['beat']}2:{COL['beat']}{LAST}", CellIsRule(
    operator="equal", formula=['"YES"'], fill=PatternFill("solid", fgColor=GREEN),
    font=Font(name=FONT, size=10, bold=True, color="0B6B34")))
CF.add(f"{COL['beat']}2:{COL['beat']}{LAST}", CellIsRule(
    operator="equal", formula=['"NO"'], fill=PatternFill("solid", fgColor=RED),
    font=Font(name=FONT, size=10, bold=True, color="912018")))
for key in ("clv_pct", "vs_plan"):
    CF.add(f"{COL[key]}2:{COL[key]}{LAST}", CellIsRule(
        operator="greaterThan", formula=["0"],
        font=Font(name=FONT, size=10, bold=True, color="0B6B34")))
    CF.add(f"{COL[key]}2:{COL[key]}{LAST}", CellIsRule(
        operator="lessThan", formula=["0"],
        font=Font(name=FONT, size=10, bold=True, color="912018")))
# a stake plan the sheet cannot compute yet should shout, not sit there quietly
CF.add(f"{COL['plan_stake']}2:{COL['plan_stake']}{LAST}", FormulaRule(
    formula=[f'AND(ISTEXT({c("plan_stake", 2)}),{c("plan_stake", 2)}<>"")'],
    fill=PatternFill("solid", fgColor=RED),
    font=Font(name=FONT, size=9, bold=True, color="912018")))
# carried-forward running values on rows with no bet in them
for key in ("bank_open", "bank_close", "roll_clv", "exp_bank"):
    CF.add(f"{COL[key]}2:{COL[key]}{LAST}", FormulaRule(
        formula=[f'{c("date", 2)}=""'], font=Font(name=FONT, size=10, color=GREY)))

ws_log.auto_filter.ref = f"A1:{COL['exp_bank']}{LAST}"

# ================================================================ DASHBOARD
ws_dash.sheet_view.showGridLines = False
title_cell(ws_dash, "B2", "BETTING LOG  -  DASHBOARD", size=18)
ws_dash["B3"] = (
    f'=IF(OR(COUNT({S}$B$3:$B$7)<5,{S}$B$8="",'
    f'AND({S}$B$8="Percent of bank",{S}$B$9="")),'
    f'"SETTINGS INCOMPLETE - open the Settings tab and fill every yellow cell, '
    f'including the stake tier multipliers. Until you do, the money figures below are wrong.",'
    f'"Settings complete.")')
ws_dash["B3"].font = Font(name=FONT, size=10, bold=True, color="B54708")
ws_dash.merge_cells("B3:M3")

blocks = [
    ("MONEY", "B", "C", [
        ("Bets logged", f'=COUNT({lg("date")})', INT),
        ("Bets settled", f'=COUNTA({lg("result")})', INT),
        ("Turnover (money at risk)", f'=SUM({lg("at_risk")})', MONEY0),
        ("Net profit / loss", f'=SUM({lg("pl")})', MONEY),
        ("Return on turnover",
         f'=IFERROR($C$9/SUMIF({lg("result")},"<>",{lg("at_risk")}),"")', PCT),
        ("Bank now", f'={S}$B$3+$C$9', MONEY),
        ("Biggest drawdown", f'=MAX({lg("drawdown")})', MONEY0),
    ]),
    ("CLV SCORECARD  -  the only scorecard", "E", "F", [
        ("Bets with a closing price", f'=COUNT({lg("close")})', INT),
        ("Average CLV %",
         f'=IFERROR(SUM({lg("clv")})/SUMIF({lg("close")},">0",{lg("at_risk")}),"")', PCT),
        ("Beat the close %",
         f'=IFERROR(COUNTIF({lg("beat")},"YES")/(COUNTIF({lg("beat")},"YES")'
         f'+COUNTIF({lg("beat")},"NO")),"")', PCT),
        ("Profit you SHOULD have made",
         f'=SUMIFS({lg("clv")},{lg("result")},"<>",{lg("close")},">0")', MONEY),
        ("Profit you ACTUALLY made",
         f'=SUMIFS({lg("pl")},{lg("result")},"<>",{lg("close")},">0")', MONEY),
        ("Luck (actual minus should)", '=$F$10-$F$9', MONEY),
        ("Is the edge real yet?",
         f'=IF({S}$B$7="","Set the minimum bets figure on Settings",'
         f'IF($F$6<{S}$B$7,"TOO FEW BETS - keep logging",'
         f'IFERROR(IF(AVERAGE({lg("clv_pct")})/(STDEV({lg("clv_pct")})/'
         f'SQRT(COUNT({lg("clv_pct")})))>2,"YES - the CLV edge looks real",'
         f'"NOT PROVEN YET - keep logging"),"")))', None),
    ]),
    ("IS YOUR BET SIZING WORKING?", "H", "I", [
        ("Stake-weighted CLV %", '=$F$7', PCT),
        ("Flat-stake CLV %", f'=IFERROR(AVERAGE({lg("clv_pct")}),"")', PCT),
        ("What your sizing adds", '=IFERROR($I$6-$I$7,"")', PCTS),
        ("CLV $ at the stakes you used", f'=SUM({lg("clv_matched")})', MONEY),
        ("CLV $ if you'd stuck to plan", f'=SUM({lg("clv_plan")})', MONEY),
        ("Off plan, by CLV", '=$I$9-$I$10', MONEY),
        ("Off plan, in money", f'=SUM({lg("pl_matched")})-SUM({lg("pl_plan")})', MONEY),
    ]),
    ("DISCIPLINE & WORKFLOW", "K", "L", [
        ("Waiting on a closing price", '=$C$6-$F$6', INT),
        ("Waiting on a result", '=$C$6-$C$7', INT),
        ("Bets that FAILED the gate", f'=COUNTIF({lg("gate")},"FAIL")', INT),
        ("Their profit / loss", f'=SUMIF({lg("gate")},"FAIL",{lg("pl")})', MONEY),
        ("Framework bets", f'=COUNTIF({lg("stream")},"Framework")', INT),
        ("TAB instinct bets", f'=COUNTIF({lg("stream")},"TAB")', INT),
    ]),
]
for title, lcol, vcol, rows in blocks:
    section(ws_dash, f"{lcol}5", title)
    ws_dash.merge_cells(f"{lcol}5:{vcol}5")
    for i, (lab, f, fmt) in enumerate(rows):
        r = 6 + i
        label(ws_dash, f"{lcol}{r}", lab)
        value(ws_dash, f"{vcol}{r}", f, fmt)
        ws_dash[f"{vcol}{r}"].border = BOX
ws_dash["F12"].alignment = Alignment(horizontal="center")
ws_dash["F12"].font = Font(name=FONT, size=10, bold=True, color=NAVY)

label(ws_dash, "B14",
      "CLV = Closing Line Value: the price you took against the price the market settled on. "
      "Beating the close is the one thing that predicts long-run profit - a bet can lose and "
      "still be a good bet. 'Is the edge real yet' is a standard statistical check "
      "(t > 2, roughly 95% confidence); it is a guide, not proof.", italic=True, colour="667085")
ws_dash.merge_cells("B14:M14")
ws_dash["B14"].alignment = Alignment(wrap_text=True, vertical="top")
ws_dash.row_dimensions[14].height = 26
label(ws_dash, "B15",
      "BET SIZING: stake-weighted CLV counts every dollar you risked; flat-stake CLV counts "
      "every bet the same. If the weighted figure is HIGHER, you are putting more money on "
      "your better bets and your sizing is earning its keep. If it is LOWER, your sizing is "
      "destroying value and the tiers need revisiting. 'Off plan, by CLV' is the process read - "
      "did your deviations land on better-priced bets? 'Off plan, in money' is the outcome, "
      "and like any outcome it carries luck, so trust the CLV line over it.",
      italic=True, colour="667085")
ws_dash.merge_cells("B15:M15")
ws_dash["B15"].alignment = Alignment(wrap_text=True, vertical="top")
ws_dash.row_dimensions[15].height = 40

for col, w in {"A": 3, "B": 27, "C": 15, "D": 3, "E": 27, "F": 31, "G": 3,
               "H": 28, "I": 15, "J": 3, "K": 24, "L": 14, "M": 3}.items():
    ws_dash.column_dimensions[col].width = w
for ref in ("C9", "I8", "I11", "I12"):
    ws_dash.conditional_formatting.add(ref, CellIsRule(
        operator="lessThan", formula=["0"],
        font=Font(name=FONT, size=11, bold=True, color="912018")))
for ref in ("I8", "I11", "I12"):
    ws_dash.conditional_formatting.add(ref, CellIsRule(
        operator="greaterThan", formula=["0"],
        font=Font(name=FONT, size=11, bold=True, color="0B6B34")))

ch1 = LineChart()
ch1.title = "Bank: what you actually made vs what CLV said you should"
ch1.style, ch1.height, ch1.width = 2, 9, 23
ch1.y_axis.title, ch1.x_axis.title = "Bank ($)", "Bet number"
ch1.x_axis.delete = ch1.y_axis.delete = False
ch1.add_data(Reference(ws_log, min_col=IDX["bank_close"], min_row=1, max_row=LAST),
             titles_from_data=True)
ch1.add_data(Reference(ws_log, min_col=IDX["exp_bank"], min_row=1, max_row=LAST),
             titles_from_data=True)
ch1.visible_cells_only = False
ch1.display_blanks = 'gap'
ws_dash.add_chart(ch1, "B17")

ch2 = LineChart()
ch2.title = "Rolling 20-bet average CLV % (above zero is the target)"
ch2.style, ch2.height, ch2.width = 2, 9, 23
ch2.y_axis.title, ch2.x_axis.title = "CLV %", "Bet number"
ch2.x_axis.delete = ch2.y_axis.delete = False
ch2.add_data(Reference(ws_log, min_col=IDX["roll_clv"], min_row=1, max_row=LAST),
             titles_from_data=True)
ch2.visible_cells_only = False
ch2.display_blanks = 'gap'
ws_dash.add_chart(ch2, "B37")

# ================================================================ WHATS WORKING
ws_work.sheet_view.showGridLines = False
title_cell(ws_work, "A1", "WHAT'S WORKING", size=18)
label(ws_work, "A2",
      "Every table is ranked by CLV, not by profit. Read the Verdict column. "
      "TOO FEW BETS means exactly that - do not act on it.", italic=True)

HCOLS = ["Segment", "Bets", "Turnover", "Avg CLV %", "Beat Close %",
         "Should have made", "Actually made", "Return", "Verdict"]
HFMTS = [None, INT, MONEY0, PCT, PCT, MONEY, MONEY, PCT, None]

tables = [
    ("BY TRIGGER  -  which of your tests actually beat the close", "trigger", "L", 22),
    ("BY STAKE TIER  -  are your bigger bets your better bets?", "tier", "P", 7),
    ("BY SPORT", "sport", "D", 6),
    ("BY COMPETITION", "comp", "E", 22),
    ("BY MARKET", "market", "F", 22),
    ("BY STREAM  -  Framework vs TAB instinct", "stream", "N", 4),
    ("BY BACK / LAY", "side", "G", 4),
    ("BY ODDS BAND", "band", "O", 8),
    ("BY PRE-BET GATE  -  what breaking your own rules costs", "gate", "K", 4),
    ("BY MONTH", "month", "MONTH", 24),
]

positions, row = {}, 4
for title, key, src, n in tables:
    cc = lg(key)
    section(ws_work, f"A{row}", title)
    ws_work.merge_cells(f"A{row}:I{row}")
    hr = row + 1
    for i, h in enumerate(HCOLS):
        cell = ws_work.cell(row=hr, column=1 + i, value=h)
        cell.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="475467")
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = BOX
    positions[key] = (hr, n)
    for j in range(n):
        r = hr + 1 + j
        if src == "MONTH":
            if j == 0:
                ws_work[f"L{r}"] = (f'=IF(COUNT({lg("date")})=0,"",'
                                    f'DATE(YEAR(MIN({lg("date")})),'
                                    f'MONTH(MIN({lg("date")})),1))')
            else:
                ws_work[f"L{r}"] = f'=IF($L{r-1}="","",EDATE($L{r-1},1))'
            ws_work[f"A{r}"] = f'=IF($L{r}="","",TEXT($L{r},"YYYY-MM"))'
        else:
            ws_work[f"A{r}"] = (f'=IF({S}${src}${LIST_1 + j}="","",'
                                f'{S}${src}${LIST_1 + j})')
        g = f'IF($A{r}="",""'
        ws_work[f"B{r}"] = f'={g},COUNTIFS({cc},$A{r}))'
        ws_work[f"C{r}"] = f'={g},SUMIFS({lg("at_risk")},{cc},$A{r}))'
        ws_work[f"D{r}"] = (f'={g},IFERROR(SUMIFS({lg("clv")},{cc},$A{r})/'
                            f'SUMIFS({lg("at_risk")},{cc},$A{r},{lg("close")},">0"),""))')
        ws_work[f"E{r}"] = (f'={g},IFERROR(COUNTIFS({cc},$A{r},{lg("beat")},"YES")/'
                            f'(COUNTIFS({cc},$A{r},{lg("beat")},"YES")+'
                            f'COUNTIFS({cc},$A{r},{lg("beat")},"NO")),""))')
        ws_work[f"F{r}"] = f'={g},SUMIFS({lg("clv")},{cc},$A{r}))'
        ws_work[f"G{r}"] = f'={g},SUMIFS({lg("pl")},{cc},$A{r}))'
        ws_work[f"H{r}"] = (f'={g},IFERROR($G{r}/SUMIFS({lg("at_risk")},{cc},$A{r},'
                            f'{lg("result")},"<>"),""))')
        ws_work[f"I{r}"] = (f'={g},IF({S}$B$7="","SET MINIMUM BETS",'
                            f'IF(COUNTIFS({cc},$A{r},{lg("close")},">0")<{S}$B$7,'
                            f'"TOO FEW BETS",IF(AND(ISNUMBER($D{r}),$D{r}>0),"POSITIVE CLV",'
                            f'"NEGATIVE CLV - REVIEW"))))')
        for i, fmt in enumerate(HFMTS):
            cell = ws_work.cell(row=r, column=1 + i)
            cell.font = Font(name=FONT, size=10)
            cell.border = BOX
            if fmt:
                cell.number_format = fmt
        ws_work[f"I{r}"].alignment = Alignment(horizontal="center")
    vr = f"I{hr+1}:I{hr+n}"
    for txt, fill, colour, ital in (
            ("POSITIVE CLV", GREEN, "0B6B34", False),
            ("NEGATIVE CLV - REVIEW", RED, "912018", False),
            ("TOO FEW BETS", GREY, "667085", True)):
        ws_work.conditional_formatting.add(vr, CellIsRule(
            operator="equal", formula=[f'"{txt}"'],
            fill=PatternFill("solid", fgColor=fill),
            font=Font(name=FONT, size=10, bold=not ital, italic=ital, color=colour)))
    ws_work.conditional_formatting.add(f"D{hr+1}:D{hr+n}", CellIsRule(
        operator="lessThan", formula=["0"], font=Font(name=FONT, size=10, color="912018")))
    row = hr + n + 2

for col, w in {"A": 34, "B": 8, "C": 13, "D": 11, "E": 13,
               "F": 17, "G": 15, "H": 10, "I": 23, "L": 12}.items():
    ws_work.column_dimensions[col].width = w
ws_work.column_dimensions["L"].hidden = True
ws_work.freeze_panes = "B1"

for key, anchor, title in (("trigger", "K4", "Average CLV % by Trigger"),
                           ("tier", "K28", "Average CLV % by Stake Tier")):
    hr, n = positions[key]
    ch = BarChart()
    ch.type = "bar"
    ch.title = title
    ch.height, ch.width = 11, 20
    ch.add_data(Reference(ws_work, min_col=4, min_row=hr, max_row=hr + n),
                titles_from_data=True)
    ch.set_categories(Reference(ws_work, min_col=1, min_row=hr + 1, max_row=hr + n))
    ch.visible_cells_only = False
    ch.display_blanks = 'gap'
    ws_work.add_chart(ch, anchor)

# ================================================================ HOW TO USE
ws_help.sheet_view.showGridLines = False
title_cell(ws_help, "B2", "HOW TO USE THIS BETTING LOG", size=18)

steps = [
    ("SET IT UP  -  once, on the laptop", None),
    ("1.", "Save this file into OneDrive, not your Documents folder. Open File Explorer, "
           "click OneDrive in the left-hand list, and drop the file in there. That is what "
           "makes the phone and the laptop show the same file."),
    ("2.", "Open the Settings tab (along the bottom) and fill the seven yellow cells at the "
           "top from the Rulebook. Type 0 for bookmaker commission rather than leaving it "
           "empty."),
    ("3.", "Stake sizing basis: choose 'Fixed dollars' if a unit is always the same dollar "
           "amount. Choose 'Percent of bank' if a unit is a share of your bank, so stakes "
           "grow as the bank grows and shrink when it falls. Only fill the percent cell if "
           "you chose the second one."),
    ("4.", "Scroll down to the Stake Tier list and fill the yellow Multiplier beside each "
           "tier from the Rulebook. A multiplier of 2 means that tier stakes two units. "
           "Rename the tiers to whatever you actually call them. Leave a multiplier blank "
           "and the log will print SET MULTIPLIER in red rather than guess a stake."),
    ("5.", "Still on Settings, add your own competitions and triggers on the blank rows "
           "under each list. The dropdowns update on their own."),
    ("6.", "On your phone, install Microsoft Excel from the app store, sign in with the same "
           "Microsoft account, and open the file from OneDrive. Do this once and it stays "
           "there."),
    ("", ""),
    ("LOG A BET  -  about 25 seconds", None),
    ("7.", "Open the Bet Log tab and go to the first empty row. Row 2 is an example - type "
           "your first real bet straight over the top of it."),
    ("8.", "Date: press Ctrl and the semicolon key together on the laptop. On the phone, "
           "type it."),
    ("9.", "Work left to right. Any cell with a small arrow is a dropdown - on the laptop "
           "press Alt and the down arrow to open it, on the phone tap the arrow. Press Tab "
           "to move to the next cell."),
    ("10.", "Pick your Stake Tier and the grey Plan Stake column immediately shows what that "
            "tier says to bet. Type what you ACTUALLY staked in the Stake column next to it. "
            "Stake vs Plan then shows how far off the plan you went - 0% means on plan."),
    ("11.", "Line / Total is only for Line, Match Total and Asian Handicap bets. Type the "
            "number you took, like -12.5 or 165.5. Leave it empty otherwise."),
    ("12.", "Stake means the amount you put up for a back bet, and the backer's stake for a "
            "lay - the same number Betfair asks you for. The sheet works out your liability "
            "itself."),
    ("13.", "Then stop. The three orange columns are for later."),
    ("", ""),
    ("FINISH THE BET OFF  -  do these in one batch", None),
    ("14.", "Closing Odds: the price the market settled at. Racing - use the Betfair SP. "
            "AFL and soccer - use the last price matched right on the jump or kick-off. "
            "Cells still needing one glow amber, so they are easy to find."),
    ("15.", "Result: this means DID YOUR BET WIN, not did the team win. A lay that comes off "
            "is a Win."),
    ("16.", "Manual P/L: only touch this if you cashed out or were partly matched. Type the "
            "real profit or loss and it overrides everything else."),
    ("", ""),
    ("READ IT", None),
    ("17.", "Dashboard tab: 'Profit you should have made' against 'Profit you actually made' "
            "is the gap that tells you whether a bad month was bad process or bad luck."),
    ("18.", "The bet sizing block is the new one. If stake-weighted CLV is HIGHER than "
            "flat-stake CLV, you are putting more money on your better bets and the "
            "weighting is earning its keep. If it is LOWER, your tiers are pointed the "
            "wrong way and are costing you money."),
    ("19.", "What's Working tab: ten tables, all ranked on CLV rather than profit. "
            "'By Stake Tier' is the one that proves or disproves your weighting. The Verdict "
            "column is the whole point. TOO FEW BETS means do not act on it yet - that "
            "warning is there to stop you killing a good angle after nine bets."),
    ("20.", "Grey columns on the Bet Log calculate themselves. Never type in them. If you do, "
            "that row's numbers go wrong and nothing will warn you."),
    ("", ""),
    ("IF YOU NEED MORE ROOM", None),
    ("21.", "The log holds 500 bets. To add more, click the row number of the last row, "
            "copy it, then paste into the rows underneath."),
]
r = 4
for num, text in steps:
    if text is None:
        section(ws_help, f"B{r}", num)
        ws_help.merge_cells(f"B{r}:F{r}")
        r += 1
        continue
    if num == "":
        r += 1
        continue
    label(ws_help, f"B{r}", num, bold=True, colour=TEAL)
    ws_help[f"B{r}"].alignment = Alignment(vertical="top")
    ws_help[f"C{r}"] = text
    ws_help[f"C{r}"].font = Font(name=FONT, size=10)
    ws_help[f"C{r}"].alignment = Alignment(wrap_text=True, vertical="top")
    ws_help.merge_cells(f"C{r}:F{r}")
    ws_help.row_dimensions[r].height = max(15, 13 * (len(text) // 95 + 1))
    r += 1

r += 1
section(ws_help, f"B{r}", "WHAT THE SHEET WORKS OUT FOR YOU")
ws_help.merge_cells(f"B{r}:F{r}")
r += 1
defs = [
    ("Plan Stake", "What your tier multiplier says to bet. Your unit times the multiplier, "
                   "or a share of your bank times the multiplier if you chose that basis."),
    ("Stake vs Plan", "How far your actual stake sat from the plan. Green is above plan, "
                      "red below. Zero is on plan."),
    ("At Risk", "What the bet can actually cost you. Your stake on a back, your liability "
                "on a lay."),
    ("Bank Before / After", "Your bank immediately before and immediately after that bet "
                            "settled, so every row shows its own opening and closing balance."),
    ("CLV %", "Your edge against the closing price, per dollar at risk. Above zero is a good "
              "bet, whatever the result was."),
    ("CLV $", "The profit that edge is worth in dollars. Add the column up and it is what you "
              "should have made if the closing price is the true price."),
    ("Beat Close", "YES or NO. The percentage of YES answers is the single most honest number "
                   "in this workbook."),
    ("P/L", "Real profit or loss, with Betfair commission already taken off winnings. "
            "Commission is never taken off CLV - CLV measures the price, not the payout."),
    ("Edge %", "What YOUR model said the edge was, if you filled in Fair Odds. Compare it "
               "against CLV % - if your model claims an edge the market never agrees with, "
               "the model is the problem."),
]
for term, meaning in defs:
    label(ws_help, f"B{r}", term, bold=True)
    ws_help[f"B{r}"].alignment = Alignment(vertical="top")
    ws_help[f"C{r}"] = meaning
    ws_help[f"C{r}"].font = Font(name=FONT, size=10)
    ws_help[f"C{r}"].alignment = Alignment(wrap_text=True, vertical="top")
    ws_help.merge_cells(f"C{r}:F{r}")
    ws_help.row_dimensions[r].height = max(15, 13 * (len(meaning) // 95 + 1))
    r += 1

r += 1
label(ws_help, f"B{r}",
      "This workbook contains no figures of its own. Bank, unit size, commission, the stake "
      "tier multipliers and the minimum sample size all live on the Settings tab, because the "
      "Rulebook is the only place a parameter belongs. Stakes are weighted by YOUR tier, never "
      "sized off your own edge estimate - that would amplify an optimistic model rather than "
      "check it.", italic=True, colour="667085")
ws_help.merge_cells(f"B{r}:F{r}")
ws_help.row_dimensions[r].height = 45

for col, w in {"A": 3, "B": 22, "C": 40, "D": 20, "E": 20, "F": 20}.items():
    ws_help.column_dimensions[col].width = w

# ================================================================ page setup
for ws in (ws_log, ws_dash, ws_work, ws_set, ws_help):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.sheet_view.zoomScale = 100
ws_log.print_title_rows = "1:1"

# ================================================================ demo data
if "--demo" in sys.argv:
    import random
    from datetime import date, timedelta
    random.seed(11)
    NDEMO = int(os.environ.get("DEMO_N", "45"))

    ws_set["B3"], ws_set["B4"] = 2000, 25
    ws_set["B5"], ws_set["B6"], ws_set["B7"] = 0.05, 0, 30
    ws_set["B8"], ws_set["B9"] = "Fixed dollars", None
    for i, m in enumerate([0.5, 1.0, 1.5, 2.0, 3.0]):
        ws_set[f"Q{LIST_1 + i}"] = m

    comps = {"AFL": ["AFL"], "Soccer": ["EPL", "Championship", "A-League Men", "Serie A"],
             "Horse Racing": ["Other"]}
    mkts = {"AFL": ["Match Odds", "Line", "Match Total"],
            "Soccer": ["Match Odds", "Over/Under 2.5 Goals", "Both Teams To Score",
                       "Double Chance", "Over/Under 1.5 Goals"],
            "Horse Racing": ["Win (Racing)", "Place (Racing)"]}
    # each trigger carries a real CLV edge; the log has to find them
    trig = {"One Kick Test": 0.030, "4-Game Win Ceiling": 0.045, "xG Regression": 0.055,
            "Promotion Year 1": 0.020, "Relegation Year 1": -0.025, "TAB Instinct": -0.040}
    d0 = date(2026, 5, 2)
    for i in range(NDEMO):
        r = 2 + i
        sp = random.choice(["AFL", "Soccer", "Soccer", "Horse Racing"])
        tg = random.choice(list(trig))
        side = "Lay" if random.random() < 0.22 else "Back"
        close = round(random.uniform(1.6, 6.5), 2)
        edge = trig[tg] + random.gauss(0, 0.045)
        taken = max(1.05, round(close * (1 + edge) if side == "Back"
                                else close * (1 - edge), 2))
        # tier tracks the edge imperfectly, the way real confidence does
        score = edge + random.gauss(0, 0.035)
        ti = min(4, max(0, int((score + 0.055) / 0.028)))
        mult = [0.5, 1.0, 1.5, 2.0, 3.0][ti]
        plan = 25 * mult
        stake = plan * random.choice([1, 1, 1, 1, 1, 1.5, 0.5])
        p_true = 1 / close
        won = random.random() < p_true
        res = ("Win" if won else "Lose") if side == "Back" else ("Lose" if won else "Win")
        if random.random() < 0.05:
            res = "Void"
        vals = {
            "date": d0 + timedelta(days=i * 3 + random.randint(0, 2)),
            "sport": sp, "comp": random.choice(comps[sp]), "event": f"Fixture {i+1}",
            "selection": f"Selection {i+1}", "market": random.choice(mkts[sp]),
            "side": side, "odds": taken, "tier": f"Tier {ti + 1}", "stake": stake,
            "fair_odds": round(close * (1 + random.gauss(0, 0.03)), 2),
            "trigger": tg, "gate": "FAIL" if random.random() < 0.07 else "PASS",
            "platform": "Betfair Exchange" if random.random() < 0.85 else "Bookmaker",
            "note": "", "close": close, "result": res,
        }
        if i >= NDEMO - 3:                  # a few still open, to show the amber states
            vals["close"], vals["result"] = "", ""
        elif i >= NDEMO - 5:
            vals["result"] = ""
        for key, v in vals.items():
            cell = ws_log[f"{COL[key]}{r}"]
            cell.value = v if v != "" else None
            cell.font = Font(name=FONT, size=10)
            cell.fill = PatternFill("solid", fgColor="FFFFFF")
            if key == "date":
                cell.number_format = DATEF
        ws_log[f"{COL['line']}{r}"] = 2.5 if "Over/Under" in str(vals["market"]) else None

# ================================================================ save
wb.active = 0
out = sys.argv[1] if len(sys.argv) > 1 else "Betting Log.xlsx"
wb.save(out)
print(f"written: {out}")
