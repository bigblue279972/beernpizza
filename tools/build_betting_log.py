"""
Build the Unleashed betting log workbook (macro-free .xlsx).

Design notes
------------
* NO operational parameter is hardcoded anywhere in this workbook.
  Bank, unit size, commission and the sample-size threshold are blank
  yellow input cells on the Settings tab, filled by C1 from the Rulebook.
* Result means "did YOUR BET win", not "did the selection win".
  A winning lay is Result = Win.
* CLV $ = expected profit if the closing price is the true price.
  CLV % = CLV $ / money at risk, so backs and lays are comparable.
* CLV is measured gross of commission (it is a price measure);
  P/L is net of commission.

Usage:  python build_betting_log.py <output.xlsx>
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

LAST = 501          # last bet row (500 bets)
LIST_LAST = 62      # last row of the editable dropdown lists on Settings

# ---------------------------------------------------------------- styling
FONT = "Arial"
NAVY = "1F3A5F"
TEAL = "0F6E6E"
GREY = "F2F4F7"
AMBER = "FFF3CD"
GREEN = "E3F4E6"
RED = "FBE3E3"
YELLOW = "FFF2A8"

MONEY = '$#,##0.00;[Red]($#,##0.00)'
MONEY0 = '$#,##0;[Red]($#,##0)'
PCT = '0.0%'
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


def value(ws, ref, formula, fmt=None, bold=True, size=11):
    ws[ref] = formula
    ws[ref].font = Font(name=FONT, size=size, bold=bold, color=NAVY)
    ws[ref].alignment = Alignment(horizontal="right")
    if fmt:
        ws[ref].number_format = fmt


# ================================================================ workbook
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
      "this workbook deliberately contains no numbers of its own.",
      italic=True)

inputs = [
    ("A3", "Starting bank ($)", "B3", MONEY0,
     "Your bankroll at the moment you start this log. Rulebook - bankroll section."),
    ("A4", "Unit size ($)", "B4", MONEY0,
     "One unit in dollars. Rulebook - staking section. Used only to show stakes in units."),
    ("A5", "Betfair commission rate", "B5", PCT,
     "Your actual Betfair rate. Type 5% or 0.05. Taken off winnings only, never off CLV."),
    ("A6", "Bookmaker / TAB commission", "B6", PCT,
     "Usually 0%. Type 0 if so - the cell must not be left blank."),
    ("A7", "Minimum bets before a verdict", "B7", INT,
     "How many settled-with-closing-price bets a segment needs before the "
     "'Whats Working' tab will call it good or bad. A statistical display "
     "threshold, not a Rulebook parameter. 30 is a common starting point."),
]
for lref, ltext, vref, fmt, note in inputs:
    label(ws_set, lref, ltext, bold=True)
    c = ws_set[vref]
    c.fill = PatternFill("solid", fgColor=YELLOW)
    c.border = BOX
    c.number_format = fmt
    c.font = Font(name=FONT, size=11, bold=True)
    c.alignment = Alignment(horizontal="center")
    c.comment = Comment(note, "Unleashed Betting Log")
    ws_set[lref.replace("A", "C")] = note
    ws_set[lref.replace("A", "C")].font = Font(name=FONT, size=9, italic=True, color="667085")

section(ws_set, "A10", "DROPDOWN LISTS - edit freely. Add a row and the dropdown picks it up automatically.")
ws_set.merge_cells("A10:O10")

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
}
for col, (hdr, items) in lists.items():
    h = ws_set[f"{col}12"]
    h.value = hdr
    h.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
    h.fill = PatternFill("solid", fgColor=NAVY)
    h.alignment = Alignment(horizontal="center")
    for i, v in enumerate(items):
        c = ws_set[f"{col}{13 + i}"]
        c.value = v
        c.font = Font(name=FONT, size=10)

# paired columns: commission per platform, stream per trigger
for col, hdr in (("J", "Commission"), ("M", "Stream")):
    h = ws_set[f"{col}12"]
    h.value = hdr
    h.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
    h.fill = PatternFill("solid", fgColor="667085")
    h.alignment = Alignment(horizontal="center")

for i, f in enumerate(["=$B$5", "=$B$6", "=$B$6"]):
    c = ws_set[f"J{13 + i}"]
    c.value = f
    c.number_format = PCT
    c.font = Font(name=FONT, size=10)

for i, s in enumerate(["Framework", "Framework", "Framework",
                       "Framework", "Framework", "TAB", "Framework"]):
    ws_set[f"M{13 + i}"] = s
    ws_set[f"M{13 + i}"].font = Font(name=FONT, size=10)

label(ws_set, "A12", "Paired columns:", bold=True)
label(ws_set, "A13", "Commission sits beside its Platform.", italic=True)
label(ws_set, "A14", "Stream sits beside its Trigger.", italic=True)
label(ws_set, "A15", "Keep each pair on the same row.", italic=True)

for col, w in {"A": 30, "B": 14, "C": 62, "D": 14, "E": 22, "F": 24, "G": 9,
               "H": 12, "I": 18, "J": 12, "K": 9, "L": 22, "M": 13,
               "N": 13, "O": 14}.items():
    ws_set.column_dimensions[col].width = w

# Plain range references for the dropdowns.
# Deliberately NOT dynamic named ranges (OFFSET/COUNTA): those are unreliable in
# Excel for Android/iOS, and this workbook has to work on a phone. Each range is
# sized to the current list plus SPARE blank rows so lists stay editable.
SPARE = 15
LIST_RANGE = {}
for _col, (_hdr, _items) in lists.items():
    LIST_RANGE[_col] = f"Settings!${_col}$13:${_col}${13 + len(_items) - 1 + SPARE}"
    # shade the spare rows so it is obvious where new entries go
    for _r in range(13 + len(_items), 13 + len(_items) + SPARE):
        _c = ws_set[f"{_col}{_r}"]
        _c.fill = PatternFill("solid", fgColor="F7F9FC")
        _c.border = BOX

# ================================================================ BET LOG
headers = [
    ("Date", 11, DATEF, "in"), ("Sport", 12, None, "in"), ("Competition", 16, None, "in"),
    ("Event", 26, None, "in"), ("Selection", 20, None, "in"), ("Market", 22, None, "in"),
    ("Line / Total", 11, NUM2, "in"), ("Side", 8, None, "in"),
    ("Odds Taken", 10, ODDS, "in"), ("Stake", 10, MONEY0, "in"),
    ("Fair Odds", 10, ODDS, "in"), ("Trigger", 20, None, "in"),
    ("Gate", 8, None, "in"), ("Platform", 16, None, "in"), ("Note", 30, None, "in"),
    ("Closing Odds", 11, ODDS, "late"), ("Result", 12, None, "late"),
    ("Manual P/L", 11, MONEY, "late"),
    ("Stream", 11, None, "auto"), ("Comm %", 8, PCT, "auto"),
    ("At Risk", 11, MONEY, "auto"), ("Implied %", 9, PCT, "auto"),
    ("Fair %", 9, PCT, "auto"), ("Edge %", 9, PCT, "auto"),
    ("CLV %", 9, PCT, "auto"), ("CLV $", 10, MONEY, "auto"),
    ("Beat Close", 10, None, "auto"), ("P/L", 11, MONEY, "auto"),
    ("Units", 8, NUM2, "auto"), ("Running Bank", 13, MONEY, "auto"),
    ("Status", 17, None, "auto"),
    ("Rolling CLV %", 11, PCT, "auto"), ("Bank if CLV is right", 13, MONEY, "auto"),
    ("Drawdown", 11, MONEY, "help"), ("Odds Band", 12, None, "help"),
    ("Month", 10, None, "help"),
]
HDR_FILL = {"in": NAVY, "late": "B54708", "auto": "475467", "help": "98A2B3"}

for i, (name, width, fmt, kind) in enumerate(headers, start=1):
    col = get_column_letter(i)
    c = ws_log.cell(row=1, column=i, value=name)
    c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=HDR_FILL[kind])
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = BOX
    ws_log.column_dimensions[col].width = width
    if kind == "help":
        ws_log.column_dimensions[col].hidden = True

ws_log.row_dimensions[1].height = 30
ws_log.freeze_panes = "B2"  # row 1 + Date column: usable on a phone screen

ws_log["A1"].comment = Comment(
    "Press Ctrl+; to type today's date.\n"
    "Dark blue headers = you type these when you place the bet.\n"
    "Orange headers = you fill these in later.\n"
    "Grey headers = calculated, never type in them.", "Unleashed Betting Log")
ws_log["Q1"].comment = Comment(
    "Result means DID YOUR BET WIN - not did the selection win.\n"
    "A lay that lands (selection lost) is a Win.", "Unleashed Betting Log")
ws_log["R1"].comment = Comment(
    "Only use this for a cash-out or a partly matched bet. "
    "Type the real profit or loss and it overrides the calculation.",
    "Unleashed Betting Log")
ws_log["G1"].comment = Comment(
    "For Line, Match Total and Asian Handicap - type the number you took, "
    "e.g. -12.5 or 165.5. Leave blank for other markets.", "Unleashed Betting Log")

# ---- formulas, row by row
for r in range(2, LAST + 1):
    p = r - 1  # previous row
    w0 = max(2, r - 19)  # 20-bet rolling window start

    ws_log[f"S{r}"] = (f'=IF($L{r}="","",IFERROR(INDEX(Settings!$M$13:$M${LIST_LAST},'
                      f'MATCH($L{r},Settings!$L$13:$L${LIST_LAST},0)),""))')
    ws_log[f"T{r}"] = (f'=IF($N{r}="","",IFERROR(INDEX(Settings!$J$13:$J${LIST_LAST},'
                      f'MATCH($N{r},Settings!$I$13:$I${LIST_LAST},0)),0))')
    ws_log[f"U{r}"] = (f'=IF(OR($I{r}="",$J{r}=""),"",'
                       f'IF($H{r}="Lay",$J{r}*($I{r}-1),$J{r}))')
    ws_log[f"V{r}"] = f'=IF($I{r}="","",1/$I{r})'
    ws_log[f"W{r}"] = f'=IF($K{r}="","",1/$K{r})'
    ws_log[f"X{r}"] = (f'=IF(OR($K{r}="",$I{r}="",$U{r}=""),"",IFERROR('
                       f'IF($H{r}="Lay",$J{r}*(1-$I{r}/$K{r}),$J{r}*($I{r}/$K{r}-1))/$U{r},""))')
    ws_log[f"Z{r}"] = (f'=IF(OR($P{r}="",$I{r}="",$J{r}=""),"",'
                       f'IF($H{r}="Lay",$J{r}*(1-$I{r}/$P{r}),$J{r}*($I{r}/$P{r}-1)))')
    ws_log[f"Y{r}"] = f'=IF(OR($Z{r}="",$U{r}=""),"",IFERROR($Z{r}/$U{r},""))'
    ws_log[f"AA{r}"] = f'=IF($Z{r}="","",IF($Z{r}>0,"YES",IF($Z{r}<0,"NO","LEVEL")))'
    ws_log[f"AB{r}"] = (
        f'=IF($R{r}<>"",$R{r},'
        f'IF($Q{r}="","",'
        f'IF(OR($Q{r}="Void",$Q{r}="Push"),0,'
        f'IF($Q{r}="Cashed Out","",'
        f'IF($H{r}="Lay",'
        f'IF($Q{r}="Win",$J{r}*(1-$T{r}),'
        f'IF($Q{r}="Half Win",$J{r}*0.5*(1-$T{r}),'
        f'IF($Q{r}="Lose",-$J{r}*($I{r}-1),'
        f'IF($Q{r}="Half Lose",-$J{r}*($I{r}-1)*0.5,"")))),'
        f'IF($Q{r}="Win",$J{r}*($I{r}-1)*(1-$T{r}),'
        f'IF($Q{r}="Half Win",$J{r}*($I{r}-1)*0.5*(1-$T{r}),'
        f'IF($Q{r}="Lose",-$J{r},'
        f'IF($Q{r}="Half Lose",-$J{r}*0.5,""))))'
        f')))))')
    ws_log[f"AC{r}"] = f'=IF(OR($U{r}="",Settings!$B$4=""),"",IFERROR($U{r}/Settings!$B$4,""))'
    ws_log[f"AD{r}"] = f'=Settings!$B$3+SUM($AB$2:$AB{r})'
    ws_log[f"AE{r}"] = (f'=IF($A{r}="","",IF($P{r}="","AWAITING CLOSE",'
                        f'IF($Q{r}="","AWAITING RESULT","SETTLED")))')
    if r == 2:
        ws_log[f"AF{r}"] = '=IF(COUNT($Y$2:$Y2)=0,0,AVERAGE($Y$2:$Y2))'
    else:
        ws_log[f"AF{r}"] = (f'=IF(COUNT($Y{w0}:$Y{r})=0,$AF{p},AVERAGE($Y{w0}:$Y{r}))')
    ws_log[f"AG{r}"] = f'=Settings!$B$3+SUM($Z$2:$Z{r})'
    ws_log[f"AH{r}"] = f'=MAX($AD$2:$AD{r})-$AD{r}'
    ws_log[f"AI{r}"] = (f'=IF($I{r}="","",IF($I{r}<1.5,"1.01 - 1.49",'
                        f'IF($I{r}<2,"1.50 - 1.99",IF($I{r}<3,"2.00 - 2.99",'
                        f'IF($I{r}<5,"3.00 - 4.99",IF($I{r}<10,"5.00 - 9.99","10.00 +"))))))')
    ws_log[f"AJ{r}"] = f'=IF($A{r}="","",TEXT($A{r},"YYYY-MM"))'

    for i, (_n, _w, fmt, kind) in enumerate(headers, start=1):
        c = ws_log.cell(row=r, column=i)
        c.font = Font(name=FONT, size=10)
        if fmt:
            c.number_format = fmt
        if kind == "in":
            c.fill = PatternFill("solid", fgColor="FFFFFF")
        elif kind == "late":
            c.fill = PatternFill("solid", fgColor="FFFBF0")
        elif kind == "auto":
            c.fill = PatternFill("solid", fgColor=GREY)
    for col in ("H", "M", "AA", "AE", "S"):
        ws_log[f"{col}{r}"].alignment = Alignment(horizontal="center")

# ---- example row, meant to be typed over
example = {"A": "=TODAY()", "B": "Soccer", "C": "EPL", "D": "Everton v Brentford",
           "E": "Over 2.5 Goals", "F": "Over/Under 2.5 Goals", "G": 2.5, "H": "Back",
           "I": 2.46, "J": 50, "K": 2.20, "L": "xG Regression", "M": "PASS",
           "N": "Betfair Exchange", "O": "EXAMPLE ROW - type your first real bet over the top of it",
           "P": 2.30, "Q": "Lose"}
for col, v in example.items():
    c = ws_log[f"{col}2"]
    c.value = v
    c.fill = PatternFill("solid", fgColor=YELLOW)
    c.font = Font(name=FONT, size=10, italic=True)
ws_log["A2"].number_format = DATEF

# ---- dropdowns
dvs = [("B", "D"), ("C", "E"), ("F", "F"), ("H", "G"),
       ("L", "L"), ("M", "K"), ("N", "I"), ("Q", "H")]
for col, src in dvs:
    dv = DataValidation(type="list", formula1=LIST_RANGE[src], allow_blank=True)
    dv.error = "Pick from the list, or add your entry to the Settings tab first."
    dv.errorTitle = "Not on the list"
    dv.prompt = "Tap the arrow to choose."
    ws_log.add_data_validation(dv)
    dv.add(f"{col}2:{col}{LAST}")

# ---- conditional formatting
rng_all = f"A2:AE{LAST}"
ws_log.conditional_formatting.add(
    f"P2:P{LAST}", FormulaRule(formula=[f'AND($A2<>"",$P2="")'],
                               fill=PatternFill("solid", fgColor=AMBER), stopIfTrue=False))
ws_log.conditional_formatting.add(
    f"Q2:Q{LAST}", FormulaRule(formula=[f'AND($A2<>"",$P2<>"",$Q2="")'],
                               fill=PatternFill("solid", fgColor=AMBER), stopIfTrue=False))
ws_log.conditional_formatting.add(
    f"M2:M{LAST}", CellIsRule(operator="equal", formula=['"FAIL"'],
                              fill=PatternFill("solid", fgColor=RED),
                              font=Font(name=FONT, size=10, bold=True, color="912018")))
ws_log.conditional_formatting.add(
    f"AA2:AA{LAST}", CellIsRule(operator="equal", formula=['"YES"'],
                                fill=PatternFill("solid", fgColor=GREEN),
                                font=Font(name=FONT, size=10, bold=True, color="0B6B34")))
ws_log.conditional_formatting.add(
    f"AA2:AA{LAST}", CellIsRule(operator="equal", formula=['"NO"'],
                                fill=PatternFill("solid", fgColor=RED),
                                font=Font(name=FONT, size=10, bold=True, color="912018")))
ws_log.conditional_formatting.add(
    f"Y2:Y{LAST}", CellIsRule(operator="greaterThan", formula=["0"],
                              font=Font(name=FONT, size=10, bold=True, color="0B6B34")))
ws_log.conditional_formatting.add(
    f"Y2:Y{LAST}", CellIsRule(operator="lessThan", formula=["0"],
                              font=Font(name=FONT, size=10, bold=True, color="912018")))
# hide the running-bank / status clutter on rows with no bet in them
for col in ("AD", "AF", "AG"):
    ws_log.conditional_formatting.add(
        f"{col}2:{col}{LAST}",
        FormulaRule(formula=[f'$A2=""'], font=Font(name=FONT, size=10, color=GREY)))

ws_log.auto_filter.ref = f"A1:AE{LAST}"

# ================================================================ DASHBOARD
ws_dash.sheet_view.showGridLines = False
title_cell(ws_dash, "B2", "BETTING LOG  -  DASHBOARD", size=18)
ws_dash["B3"] = ('=IF(COUNT(Settings!$B$3:$B$7)<5,'
                 '"SETTINGS INCOMPLETE - open the Settings tab and fill every yellow cell. '
                 'Until you do, the money figures below are wrong.",'
                 '"Settings complete.")')
ws_dash["B3"].font = Font(name=FONT, size=10, bold=True, color="B54708")
ws_dash.merge_cells("B3:J3")

L, D = "'Bet Log'!", LAST
section(ws_dash, "B5", "MONEY")
ws_dash.merge_cells("B5:C5")
section(ws_dash, "E5", "CLV SCORECARD  -  the only scorecard")
ws_dash.merge_cells("E5:F5")
section(ws_dash, "H5", "DISCIPLINE & WORKFLOW")
ws_dash.merge_cells("H5:I5")

money_block = [
    ("Bets logged", f'=COUNT({L}$A$2:$A${D})', INT),
    ("Bets settled", f'=COUNTA({L}$Q$2:$Q${D})', INT),
    ("Turnover (money at risk)", f'=SUM({L}$U$2:$U${D})', MONEY0),
    ("Net profit / loss", f'=SUM({L}$AB$2:$AB${D})', MONEY),
    ("Return on turnover", f'=IFERROR($C$9/SUMIF({L}$Q$2:$Q${D},"<>",{L}$U$2:$U${D}),"")', PCT),
    ("Bank now", f'=Settings!$B$3+$C$9', MONEY),
    ("Biggest drawdown", f'=MAX({L}$AH$2:$AH${D})', MONEY0),
]
clv_block = [
    ("Bets with a closing price", f'=COUNT({L}$P$2:$P${D})', INT),
    ("Average CLV %", f'=IFERROR(SUM({L}$Z$2:$Z${D})/SUMIF({L}$P$2:$P${D},">0",{L}$U$2:$U${D}),"")', PCT),
    ("Beat the close %", f'=IFERROR(COUNTIF({L}$AA$2:$AA${D},"YES")/'
                         f'(COUNTIF({L}$AA$2:$AA${D},"YES")+COUNTIF({L}$AA$2:$AA${D},"NO")),"")', PCT),
    ("Profit you SHOULD have made", f'=SUMIFS({L}$Z$2:$Z${D},{L}$Q$2:$Q${D},"<>",{L}$P$2:$P${D},">0")', MONEY),
    ("Profit you ACTUALLY made", f'=SUMIFS({L}$AB$2:$AB${D},{L}$Q$2:$Q${D},"<>",{L}$P$2:$P${D},">0")', MONEY),
    ("Luck (actual minus should)", '=$F$10-$F$9', MONEY),
    ("Is the edge real yet?",
     f'=IF(Settings!$B$7="","Set the minimum bets figure on Settings",'
     f'IF($F$6<Settings!$B$7,"TOO FEW BETS - keep logging",'
     f'IFERROR(IF(AVERAGE({L}$Y$2:$Y${D})/(STDEV({L}$Y$2:$Y${D})/'
     f'SQRT(COUNT({L}$Y$2:$Y${D})))>2,"YES - the CLV edge looks real",'
     f'"NOT PROVEN YET - keep logging"),"")))', None),
]
disc_block = [
    ("Waiting on a closing price", '=$C$6-$F$6', INT),
    ("Waiting on a result", '=$C$6-$C$7', INT),
    ("Bets that FAILED the gate", f'=COUNTIF({L}$M$2:$M${D},"FAIL")', INT),
    ("Their profit / loss", f'=SUMIF({L}$M$2:$M${D},"FAIL",{L}$AB$2:$AB${D})', MONEY),
    ("Framework bets", f'=COUNTIF({L}$S$2:$S${D},"Framework")', INT),
    ("TAB instinct bets", f'=COUNTIF({L}$S$2:$S${D},"TAB")', INT),
]
for block, lcol, vcol in ((money_block, "B", "C"), (clv_block, "E", "F"), (disc_block, "H", "I")):
    for i, (lab, f, fmt) in enumerate(block):
        r = 6 + i
        label(ws_dash, f"{lcol}{r}", lab)
        value(ws_dash, f"{vcol}{r}", f, fmt)
        ws_dash[f"{vcol}{r}"].border = BOX
ws_dash["F12"].alignment = Alignment(horizontal="center")
ws_dash["F12"].font = Font(name=FONT, size=10, bold=True, color=NAVY)

label(ws_dash, "E13",
      "'Is the edge real yet' is a standard statistical check (t > 2, roughly 95% confidence). "
      "It is a guide, not proof.", italic=True, colour="667085")
ws_dash.merge_cells("E13:J13")
label(ws_dash, "B14",
      "CLV = Closing Line Value. It compares the price you took against the price "
      "the market settled on. Beating the close is the one thing that predicts long-run profit. "
      "A bet can lose and still be a good bet.", italic=True, colour="667085")
ws_dash.merge_cells("B14:J14")

for col, w in {"A": 3, "B": 27, "C": 15, "D": 3, "E": 27, "F": 31,
               "G": 3, "H": 24, "I": 14, "J": 3}.items():
    ws_dash.column_dimensions[col].width = w
ws_dash.conditional_formatting.add("C9", CellIsRule(operator="lessThan", formula=["0"],
                                                    font=Font(name=FONT, bold=True, color="912018")))

# ---- charts
ch1 = LineChart()
ch1.title = "Bank: what you actually made vs what CLV said you should"
ch1.style = 2
ch1.height, ch1.width = 9, 23
ch1.y_axis.title = "Bank ($)"
ch1.x_axis.title = "Bet number"
ch1.x_axis.delete = False
ch1.y_axis.delete = False
ch1.add_data(Reference(ws_log, min_col=30, min_row=1, max_row=LAST), titles_from_data=True)
ch1.add_data(Reference(ws_log, min_col=33, min_row=1, max_row=LAST), titles_from_data=True)
ch1.visible_cells_only = False
ch1.display_blanks = 'gap'
ws_dash.add_chart(ch1, "B16")

ch2 = LineChart()
ch2.title = "Rolling 20-bet average CLV % (above zero is the target)"
ch2.style = 2
ch2.height, ch2.width = 9, 23
ch2.y_axis.title = "CLV %"
ch2.x_axis.title = "Bet number"
ch2.x_axis.delete = False
ch2.y_axis.delete = False
ch2.add_data(Reference(ws_log, min_col=32, min_row=1, max_row=LAST), titles_from_data=True)
ch2.visible_cells_only = False
ch2.display_blanks = 'gap'
ws_dash.add_chart(ch2, "B36")

# ================================================================ WHATS WORKING
ws_work.sheet_view.showGridLines = False
title_cell(ws_work, "A1", "WHAT'S WORKING", size=18)
label(ws_work, "A2",
      "Every table is ranked by CLV, not by profit. Read the Verdict column. "
      "TOO FEW BETS means exactly that - do not act on it.", italic=True)

COLS = ["Segment", "Bets", "Turnover", "Avg CLV %", "Beat Close %",
        "Should have made", "Actually made", "Return", "Verdict"]
FMTS = [None, INT, MONEY0, PCT, PCT, MONEY, MONEY, PCT, None]

tables = [
    ("BY TRIGGER  -  which of your tests actually beat the close", "L", "L", 22),
    ("BY SPORT", "B", "D", 6),
    ("BY COMPETITION", "C", "E", 22),
    ("BY MARKET", "F", "F", 22),
    ("BY STREAM  -  Framework vs TAB instinct", "S", "N", 4),
    ("BY BACK / LAY", "H", "G", 4),
    ("BY ODDS BAND", "AI", "O", 8),
    ("BY PRE-BET GATE  -  what breaking your own rules costs", "M", "K", 4),
    ("BY MONTH", "AJ", "MONTH", 24),
]

row = 4
for title, cc, src, n in tables:
    section(ws_work, f"A{row}", title)
    ws_work.merge_cells(f"A{row}:I{row}")
    hr = row + 1
    for i, h in enumerate(COLS):
        c = ws_work.cell(row=hr, column=1 + i, value=h)
        c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="475467")
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        c.border = BOX
    for j in range(n):
        r = hr + 1 + j
        if src == "MONTH":
            if j == 0:
                ws_work[f"L{r}"] = (f'=IF(COUNT({L}$A$2:$A${D})=0,"",'
                                    f'DATE(YEAR(MIN({L}$A$2:$A${D})),'
                                    f'MONTH(MIN({L}$A$2:$A${D})),1))')
            else:
                ws_work[f"L{r}"] = f'=IF($L{r-1}="","",EDATE($L{r-1},1))'
            ws_work[f"A{r}"] = f'=IF($L{r}="","",TEXT($L{r},"YYYY-MM"))'
        else:
            ws_work[f"A{r}"] = f'=IF(Settings!${src}${13+j}="","",Settings!${src}${13+j})'
        g = f'IF($A{r}="",""'
        ws_work[f"B{r}"] = f'={g},COUNTIFS({L}${cc}$2:${cc}${D},$A{r}))'
        ws_work[f"C{r}"] = f'={g},SUMIFS({L}$U$2:$U${D},{L}${cc}$2:${cc}${D},$A{r}))'
        ws_work[f"D{r}"] = (f'={g},IFERROR(SUMIFS({L}$Z$2:$Z${D},{L}${cc}$2:${cc}${D},$A{r})/'
                            f'SUMIFS({L}$U$2:$U${D},{L}${cc}$2:${cc}${D},$A{r},'
                            f'{L}$P$2:$P${D},">0"),""))')
        ws_work[f"E{r}"] = (f'={g},IFERROR(COUNTIFS({L}${cc}$2:${cc}${D},$A{r},{L}$AA$2:$AA${D},"YES")/'
                            f'(COUNTIFS({L}${cc}$2:${cc}${D},$A{r},{L}$AA$2:$AA${D},"YES")+'
                            f'COUNTIFS({L}${cc}$2:${cc}${D},$A{r},{L}$AA$2:$AA${D},"NO")),""))')
        ws_work[f"F{r}"] = f'={g},SUMIFS({L}$Z$2:$Z${D},{L}${cc}$2:${cc}${D},$A{r}))'
        ws_work[f"G{r}"] = f'={g},SUMIFS({L}$AB$2:$AB${D},{L}${cc}$2:${cc}${D},$A{r}))'
        ws_work[f"H{r}"] = (f'={g},IFERROR($G{r}/SUMIFS({L}$U$2:$U${D},{L}${cc}$2:${cc}${D},$A{r},'
                            f'{L}$Q$2:$Q${D},"<>"),""))')
        ws_work[f"I{r}"] = (f'={g},IF(Settings!$B$7="","SET MINIMUM BETS",'
                            f'IF(COUNTIFS({L}${cc}$2:${cc}${D},$A{r},{L}$P$2:$P${D},">0")<Settings!$B$7,'
                            f'"TOO FEW BETS",IF(AND(ISNUMBER($D{r}),$D{r}>0),"POSITIVE CLV",'
                            f'"NEGATIVE CLV - REVIEW"))))')
        for i, fmt in enumerate(FMTS):
            c = ws_work.cell(row=r, column=1 + i)
            c.font = Font(name=FONT, size=10)
            c.border = BOX
            if fmt:
                c.number_format = fmt
        ws_work[f"I{r}"].alignment = Alignment(horizontal="center")
    rng = f"I{hr+1}:I{hr+n}"
    ws_work.conditional_formatting.add(rng, CellIsRule(
        operator="equal", formula=['"POSITIVE CLV"'],
        fill=PatternFill("solid", fgColor=GREEN), font=Font(name=FONT, size=10, bold=True, color="0B6B34")))
    ws_work.conditional_formatting.add(rng, CellIsRule(
        operator="equal", formula=['"NEGATIVE CLV - REVIEW"'],
        fill=PatternFill("solid", fgColor=RED), font=Font(name=FONT, size=10, bold=True, color="912018")))
    ws_work.conditional_formatting.add(rng, CellIsRule(
        operator="equal", formula=['"TOO FEW BETS"'],
        fill=PatternFill("solid", fgColor=GREY), font=Font(name=FONT, size=10, italic=True, color="667085")))
    ws_work.conditional_formatting.add(f"D{hr+1}:D{hr+n}", CellIsRule(
        operator="lessThan", formula=["0"], font=Font(name=FONT, size=10, color="912018")))
    row = hr + n + 2

for col, w in {"A": 34, "B": 8, "C": 13, "D": 11, "E": 13,
               "F": 17, "G": 15, "H": 10, "I": 23, "L": 12}.items():
    ws_work.column_dimensions[col].width = w
ws_work.column_dimensions["L"].hidden = True
ws_work.freeze_panes = "B1"

ch3 = BarChart()
ch3.type = "bar"
ch3.title = "Average CLV % by Trigger"
ch3.height, ch3.width = 11, 20
ch3.add_data(Reference(ws_work, min_col=4, min_row=5, max_row=27), titles_from_data=True)
ch3.set_categories(Reference(ws_work, min_col=1, min_row=6, max_row=27))
ch3.visible_cells_only = False
ch3.display_blanks = 'gap'
ws_work.add_chart(ch3, "K4")

# ================================================================ HOW TO USE
ws_help.sheet_view.showGridLines = False
title_cell(ws_help, "B2", "HOW TO USE THIS BETTING LOG", size=18)

steps = [
    ("SET IT UP  -  once, on the laptop", None),
    ("1.", "Save this file into OneDrive, not your Documents folder. "
           "Open File Explorer, click OneDrive in the left-hand list, and drop the file in there. "
           "That is what makes the phone and the laptop show the same file."),
    ("2.", "Open the Settings tab (along the bottom). Fill the five yellow cells from the Rulebook. "
           "Type 0 for bookmaker commission rather than leaving it empty."),
    ("3.", "Still on Settings, look at the lists in the coloured block. Add your own competitions "
           "and triggers on the blank rows underneath each list. The dropdowns update on their own."),
    ("4.", "On your phone, install Microsoft Excel from the app store, sign in with the same "
           "Microsoft account, and open the file from OneDrive. Do this once and it stays there."),
    ("", ""),
    ("LOG A BET  -  about 25 seconds", None),
    ("5.", "Open the Bet Log tab and go to the first empty row. "
           "Row 2 is an example - type your first real bet straight over the top of it."),
    ("6.", "Date: press Ctrl and the semicolon key together on the laptop. On the phone, type it."),
    ("7.", "Work left to right to the Note column. Any cell with a small arrow is a dropdown - "
           "on the laptop press Alt and the down arrow to open it, on the phone tap the arrow. "
           "Press Tab to move to the next cell."),
    ("8.", "Line / Total is only for Line, Match Total and Asian Handicap bets. "
           "Type the number you took, like -12.5 or 165.5. Leave it empty otherwise."),
    ("9.", "Stake means the amount you put up for a back bet, and the backer's stake for a lay - "
           "the same number Betfair asks you for. The sheet works out your liability itself."),
    ("10.", "Then stop. The three orange columns are for later."),
    ("", ""),
    ("FINISH THE BET OFF  -  do these in one batch", None),
    ("11.", "Closing Odds: the price the market settled at. Racing - use the Betfair SP. "
            "AFL and soccer - use the last price matched right on the jump or kick-off. "
            "Cells still needing one glow amber, so they are easy to find."),
    ("12.", "Result: this means DID YOUR BET WIN, not did the team win. "
            "A lay that comes off is a Win."),
    ("13.", "Manual P/L: only touch this if you cashed out or were partly matched. "
            "Type the real profit or loss and it overrides everything else."),
    ("", ""),
    ("READ IT", None),
    ("14.", "Dashboard tab: the top-left block is money, the middle block is the one that matters. "
            "'Profit you should have made' against 'Profit you actually made' is the gap that tells "
            "you whether a bad month was bad process or bad luck."),
    ("15.", "What's Working tab: nine tables, all ranked on CLV rather than profit. "
            "The Verdict column is the whole point. TOO FEW BETS means do not act on it yet - "
            "that warning is there to stop you killing a good angle after nine bets."),
    ("16.", "Grey columns on the Bet Log calculate themselves. Never type in them. "
            "If you do, that row's numbers go wrong and nothing will warn you."),
    ("", ""),
    ("IF YOU NEED MORE ROOM", None),
    ("17.", "The log holds 500 bets. To add more, click the row number of the last row, "
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
    ("At Risk", "What the bet can actually cost you. Your stake on a back, your liability on a lay."),
    ("CLV %", "Your edge against the closing price, per dollar at risk. Above zero is a good bet, "
              "whatever the result was."),
    ("CLV $", "The profit that edge is worth in dollars. Add the column up and it is what you "
              "should have made if the closing price is the true price."),
    ("Beat Close", "YES or NO. The percentage of YES answers is the single most honest number "
                   "in this workbook."),
    ("P/L", "Real profit or loss, with Betfair commission already taken off winnings. "
            "Commission is never taken off CLV - CLV measures the price, not the payout."),
    ("Edge %", "What YOUR model said the edge was, if you filled in Fair Odds. "
               "Compare it against CLV % - if your model claims an edge the market never agrees with, "
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
      "This workbook contains no figures of its own. Bank, unit size, commission and the "
      "minimum sample size all live on the Settings tab, because the Rulebook is the only "
      "place a parameter belongs.", italic=True, colour="667085")
ws_help.merge_cells(f"B{r}:F{r}")
ws_help.row_dimensions[r].height = 30

for col, w in {"A": 3, "B": 22, "C": 40, "D": 20, "E": 20, "F": 20}.items():
    ws_help.column_dimensions[col].width = w


# ================================================================ demo data
if "--demo" in sys.argv:
    import random
    random.seed(11)
    from datetime import date, timedelta
    ws_set["B3"], ws_set["B4"] = 2000, 25
    ws_set["B5"], ws_set["B6"], ws_set["B7"] = 0.05, 0, 30
    comps = {"AFL": ["AFL"], "Soccer": ["EPL", "Championship", "A-League Men", "Serie A"],
             "Horse Racing": ["Other"]}
    mkts = {"AFL": ["Match Odds", "Line", "Match Total"],
            "Soccer": ["Match Odds", "Over/Under 2.5 Goals", "Both Teams To Score",
                       "Double Chance", "Over/Under 1.5 Goals"],
            "Horse Racing": ["Win (Racing)", "Place (Racing)"]}
    # each trigger has a real underlying CLV edge; the log has to find them
    trig = {"One Kick Test": 0.030, "4-Game Win Ceiling": 0.045, "xG Regression": 0.055,
            "Promotion Year 1": 0.020, "Relegation Year 1": -0.025, "TAB Instinct": -0.040}
    d0 = date(2026, 5, 2)
    NDEMO = int(os.environ.get("DEMO_N", "45"))
    for i in range(NDEMO):
        r = 2 + i
        sp = random.choice(["AFL", "Soccer", "Soccer", "Horse Racing"])
        tg = random.choice(list(trig))
        side = "Lay" if random.random() < 0.22 else "Back"
        close = round(random.uniform(1.6, 6.5), 2)
        edge = trig[tg] + random.gauss(0, 0.045)
        taken = round(close * (1 + edge) if side == "Back" else close * (1 - edge), 2)
        taken = max(1.05, taken)
        p_true = 1 / close
        won = random.random() < p_true
        res = ("Win" if won else "Lose") if side == "Back" else ("Lose" if won else "Win")
        if random.random() < 0.05:
            res = "Void"
        vals = {
            "A": d0 + timedelta(days=i * 3 + random.randint(0, 2)),
            "B": sp, "C": random.choice(comps[sp]), "D": f"Fixture {i+1}",
            "E": f"Selection {i+1}", "F": random.choice(mkts[sp]), "H": side,
            "I": taken, "J": random.choice([25, 25, 50, 50, 75, 100]),
            "K": round(close * (1 + random.gauss(0, 0.03)), 2),
            "L": tg, "M": "FAIL" if random.random() < 0.07 else "PASS",
            "N": "Betfair Exchange" if random.random() < 0.85 else "Bookmaker",
            "O": "", "P": close, "Q": res,
        }
        if i >= NDEMO - 3:               # a few still open, to show the amber states
            vals["P"], vals["Q"] = "", ""
        elif i >= NDEMO - 5:
            vals["Q"] = ""
        for col, v in vals.items():
            c = ws_log[f"{col}{r}"]
            c.value = v if v != "" else None
            c.font = Font(name=FONT, size=10)
            c.fill = PatternFill("solid", fgColor="FFFFFF")
            if col == "A":
                c.number_format = DATEF
        ws_log[f"G{r}"].value = 2.5 if "Over/Under" in str(vals["F"]) else None

# ================================================================ page setup
for ws in (ws_log, ws_dash, ws_work, ws_set, ws_help):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
ws_log.print_title_rows = "1:1"

# ================================================================ save
wb.active = 0
for ws in (ws_log, ws_dash, ws_work, ws_set, ws_help):
    ws.sheet_view.zoomScale = 100
out = sys.argv[1] if len(sys.argv) > 1 else "Betting Log.xlsx"
wb.save(out)
print(f"written: {out}")
