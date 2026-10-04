#!/usr/bin/env python3
"""Build the printable instruction sheet for tools/fixtures_import.py.

    pip install reportlab
    python tools/build_instruction_sheet.py "Fixtures Import - Instructions.pdf"

Kept as a builder rather than a hand-written PDF for the same reason the
workbooks are: when the tool changes, the sheet is regenerated instead of
drifting out of date.
"""

import sys
from datetime import date
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame,
                                KeepTogether, PageTemplate, Paragraph,
                                Preformatted, Spacer, Table, TableStyle)

NAVY = colors.HexColor("#1F3864")
RULE = colors.HexColor("#C9CFDD")
CODEBG = colors.HexColor("#F2F4F8")
WARNBG = colors.HexColor("#FFF4E5")
WARNED = colors.HexColor("#B36A00")
GREY = colors.HexColor("#5A6472")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm

ss = getSampleStyleSheet()


def st(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10, leading=14,
                textColor=colors.black, alignment=TA_LEFT)
    base.update(kw)
    return ParagraphStyle(name, parent=ss["Normal"], **base)


S = {
    "title": st("title", fontName="Helvetica-Bold", fontSize=21, leading=25,
                textColor=NAVY, spaceAfter=2),
    "sub": st("sub", fontSize=10.5, leading=14, textColor=GREY, spaceAfter=2),
    "h1": st("h1", fontName="Helvetica-Bold", fontSize=13.5, leading=17,
             textColor=colors.white, spaceBefore=0, spaceAfter=0,
             leftIndent=5, backColor=NAVY, borderPadding=(5, 5, 5, 5)),
    "h2": st("h2", fontName="Helvetica-Bold", fontSize=11, leading=14,
             textColor=NAVY, spaceBefore=9, spaceAfter=3),
    "body": st("body", spaceAfter=5),
    "step": st("step", leftIndent=16, firstLineIndent=-16, spaceAfter=5),
    "bullet": st("bullet", leftIndent=12, firstLineIndent=-9, spaceAfter=4),
    "note": st("note", fontSize=9.5, leading=13, textColor=GREY, spaceAfter=5),
    "cell": st("cell", fontSize=9, leading=12),
    "cellb": st("cellb", fontName="Helvetica-Bold", fontSize=9, leading=12),
    "code": ParagraphStyle("code", parent=ss["Code"], fontName="Courier-Bold",
                           fontSize=9.5, leading=12.5, leftIndent=0,
                           rightIndent=0, firstLineIndent=0,
                           textColor=colors.HexColor("#102A54")),
    "codecell": ParagraphStyle("codecell", parent=ss["Code"],
                               fontName="Courier-Bold", fontSize=8.3,
                               leading=11, leftIndent=0, rightIndent=0,
                               firstLineIndent=0,
                               textColor=colors.HexColor("#102A54")),
    "warn": st("warn", fontSize=10, leading=13.5),
    "warnh": st("warnh", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
                textColor=WARNED, spaceAfter=3),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def H1(text):
    """A section heading, guaranteed at least this much room beneath it."""
    return [CondPageBreak(60 * mm), Spacer(1, 11),
            Paragraph(escape(text), S["h1"]), Spacer(1, 7)]


def H2(text):
    return Paragraph(escape(text), S["h2"])


CODE_W = PAGE_W - 2 * MARGIN - 16          # panel width less its padding


def code(*lines):
    """A command block: monospace on a tinted panel, ready to be typed.

    Preformatted does not wrap, so a long command would be silently clipped
    at the right edge -- which on an instruction sheet means handing over a
    command that cannot work. The block is shrunk until the longest line
    fits instead.
    """
    size = S["code"].fontSize
    while size > 6.5 and max(stringWidth(ln, "Courier-Bold", size)
                             for ln in lines) > CODE_W:
        size -= 0.25
    sty = ParagraphStyle("code_fit", parent=S["code"], fontSize=size,
                         leading=size * 1.32)
    body = Preformatted("\n".join(lines), sty)
    t = Table([[body]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return KeepTogether([Spacer(1, 2), t, Spacer(1, 7)])


def warn(heading, *paras):
    inner = [Paragraph(escape(heading), S["warnh"])]
    for p in paras:
        inner.append(Paragraph(p, S["warn"]))
    t = Table([[inner]], colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARNBG),
        ("BOX", (0, 0), (-1, -1), 0.8, WARNED),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 8)])


def grid(rows, widths, mono_col=None):
    data = [[Paragraph(c, S["cellb"]) for c in rows[0]]]
    for r in rows[1:]:
        line = []
        for j, c in enumerate(r):
            sty = (S["codecell"] if mono_col is not None and j == mono_col
                   else S["cell"])
            line.append(Paragraph(c, sty))
        data.append(line)
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F7F8FB")]),
    ]))
    return [Spacer(1, 2), t, Spacer(1, 8)]


def furniture(canv, doc):
    canv.saveState()
    canv.setStrokeColor(RULE)
    canv.setLineWidth(0.6)
    canv.line(MARGIN, PAGE_H - MARGIN + 6 * mm,
              PAGE_W - MARGIN, PAGE_H - MARGIN + 6 * mm)
    canv.setFont("Helvetica", 7.8)
    canv.setFillColor(GREY)
    canv.drawString(MARGIN, PAGE_H - MARGIN + 8 * mm,
                    "FIXTURES INTO EXCEL  -  fixtures_import.py")
    canv.line(MARGIN, MARGIN - 4 * mm, PAGE_W - MARGIN, MARGIN - 4 * mm)
    canv.drawString(MARGIN, MARGIN - 8.5 * mm,
                    f"Unleashed Pro / Tipping Edge  -  {date.today():%d %B %Y}")
    canv.drawRightString(PAGE_W - MARGIN, MARGIN - 8.5 * mm,
                         f"Page {doc.page}")
    canv.restoreState()


def build(path):
    doc = BaseDocTemplate(path, pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=MARGIN,
                          title="Getting Downloaded Fixtures Into Excel",
                          author="Unleashed Pro / Tipping Edge")
    frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN,
                  id="main", leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame],
                                       onPage=furniture)])

    f = []
    f.append(P("Getting Downloaded Fixtures Into Excel", "title"))
    f.append(P("Turns a downloaded fixtures file into clean spreadsheet "
               "rows. Set it up once, then it is look, then write - two "
               "commands, every time.", "sub"))
    f.append(Spacer(1, 4))

    # ------------------------------------------------------------ setup ----
    f.extend(H1("PART 1  -  Set this up once (about 3 minutes)"))
    f.append(P("<b>1.</b>&nbsp;&nbsp;Press the <b>Windows key</b> on your "
               "keyboard, type <b>cmd</b>, then press <b>Enter</b>. A black "
               "window opens. That window is Command Prompt. Everything in "
               "this sheet gets typed into it.", "step"))
    f.append(P("<b>2.</b>&nbsp;&nbsp;Type this line, then press <b>Enter</b>. "
               "It installs the one add-on Python needs to write Excel files.",
               "step"))
    f.append(code("pip install openpyxl"))
    f.append(P("If it answers <i>Requirement already satisfied</i>, you "
               "already had it. That is fine - carry on.", "note"))
    f.append(P("<b>3.</b>&nbsp;&nbsp;Make the folders. Open <b>File "
               "Explorer</b> (the yellow folder on your taskbar), click in "
               "the address bar at the top, type <b>C:\\Users\\Cliff</b> and "
               "press <b>Enter</b>. Right-click any empty white space, choose "
               "<b>New</b> then <b>Folder</b>, and name it <b>betting</b>. "
               "Double-click into it and make one more folder inside called "
               "<b>tools</b>.", "step"))
    f.append(P("<b>4.</b>&nbsp;&nbsp;Save the file <b>fixtures_import.py</b> "
               "(the one attached in our chat) into the <b>tools</b> folder. "
               "When you are done it should sit at exactly this path:", "step"))
    f.append(code(r"C:\Users\Cliff\betting\tools\fixtures_import.py"))

    f.append(H2("Where things go from now on"))
    f.extend(grid([
        ["Put this here", "What goes in it"],
        [r"C:\Users\Cliff\betting",
         "Your <b>downloaded fixtures files</b>, and the spreadsheets you "
         "want to write into."],
        [r"C:\Users\Cliff\betting\tools",
         "The script. You never open or edit this - you only run it."],
    ], [62 * mm, PAGE_W - 2 * MARGIN - 62 * mm]))
    f.append(P("Keeping the downloads and the spreadsheet in the same folder "
               "is what lets you type short file names instead of long "
               "paths.", "note"))

    # ------------------------------------------------------------ daily ----
    f.extend(H1("PART 2  -  Every time you have a download"))
    f.append(P("Download your fixtures file and save it into "
               "<b>C:\\Users\\Cliff\\betting</b>. Note its exact name, "
               "including the bit after the dot. Then:"))

    f.append(H2("Step 1 of 3  -  Get into the right folder"))
    f.append(P("Open Command Prompt (Windows key, type <b>cmd</b>, Enter) and "
               "type this once per session:"))
    f.append(code(r"cd C:\Users\Cliff\betting"))
    f.append(P("The text at the left of the window changes to show that "
               "folder. That is how you know it worked.", "note"))

    f.append(H2("Step 2 of 3  -  Look before you write"))
    f.append(P("Swap <b>downloaded.csv</b> for your real file name:"))
    f.append(code(r"python tools\fixtures_import.py --inspect downloaded.csv"))
    f.append(P("<b>This writes nothing at all.</b> It only tells you what it "
               "found, so you can check it before anything is saved. Part 3 "
               "explains how to read what comes back."))

    f.append(H2("Step 3 of 3  -  Write it"))
    f.append(P("Once the inspect output looks right, pick <b>one</b> of these "
               "two:"))
    f.append(P("<b>A.</b>&nbsp;&nbsp;Into a brand-new clean spreadsheet:",
               "step"))
    f.append(code(r'python tools\fixtures_import.py downloaded.csv '
                  r'--out "Fixtures.xlsx"'))
    f.append(P("<b>B.</b>&nbsp;&nbsp;Added onto the end of your existing "
               "fixtures database:", "step"))
    f.append(code(r'python tools\fixtures_import.py downloaded.csv '
                  r'--into "Fixture Dbase v7.xlsx"'))
    f.append(P("Option B writes a <b>new file</b> called <b>Fixture Dbase v7 "
               "updated.xlsx</b> and leaves your original completely "
               "untouched. Open the new one, check it, and only then rename "
               "it over the top of the old one.", "note"))

    f.append(H2("Several downloads at once"))
    f.append(P("Just list them, separated by spaces. Anything appearing in "
               "two files is only written once:"))
    f.append(code(r'python tools\fixtures_import.py epl.csv china.csv '
                  r'aleague.xlsx --into "Fixture Dbase v7.xlsx"'))

    f.append(P("<b>Tip:</b> you do not have to type a file name. Drag the "
               "file from File Explorer and drop it onto the Command Prompt "
               "window - it pastes the full name for you.", "note"))

    # ----------------------------------------------------------- output ----
    f.extend(H1("PART 3  -  Reading what comes back"))
    f.append(P("A normal run looks like this. The lines in the middle are the "
               "ones to read:"))
    f.append(code(
        "=== downloaded.csv ===",
        "  read as tab-separated text; 4 non-empty rows; columns from header row 1",
        "  date   -> 'Date'  (column 2)",
        "  time   -> 'Time'  (column 3)",
        "  comp   -> 'Div'  (column 1)",
        "  home   -> 'HomeTeam'  (column 4)",
        "  away   -> 'AwayTeam'  (column 5)",
        "  date order: DMY  (proven by 2 rows with a day above 12)",
        "  usable fixtures: 3; unusable rows: 0",
        "  date range: 2026-10-04 to 2026-11-22",
        "    2026-10-04  19:30  E0  Arsenal v Chelsea",
    ))
    f.extend(grid([
        ["Line", "What to check"],
        ["<b>read as ...</b>",
         "How the file was actually split up. You do not need to do anything "
         "with this - it is there so you know it found real columns and not "
         "one long line."],
        ["<b>date / time / comp / home / away</b>",
         "The important block. Each one names the column it is going to use. "
         "If <b>home</b> and <b>away</b> have grabbed the wrong columns, stop "
         "and tell me - do not run Step 3."],
        ["<b>date order</b>",
         "Whether the file is day-first or month-first. See the warning "
         "below."],
        ["<b>usable fixtures</b>",
         "How many rows it can use. If this is much lower than the number of "
         "games you expected, the next few lines say why each row was "
         "skipped."],
        ["<b>the sample rows</b>",
         "The last few lines show real fixtures. Read one and sanity-check it "
         "against the website you downloaded from. This is your best check."],
    ], [44 * mm, PAGE_W - 2 * MARGIN - 44 * mm]))

    f.append(warn(
        "The date warning - this is the one that matters",
        "A date written <b>04/05/2026</b> is either 4 May or 5 April, and "
        "nothing in the row tells you which. Get it wrong and every fixture "
        "lands in the wrong month.",
        "The script checks the whole column for a day above 12. One row "
        "reading <b>25/10/2026</b> proves the file is day-first, and it says "
        "so: <b>proven by 2 rows with a day above 12</b>. That line means you "
        "are safe.",
        "But if nothing in the file proves it, you get this instead:",
    ))
    f.append(code(
        "  date order: DMY  (ASSUMED, nothing in the file proves it)",
        "  !! check one date against the source website before you trust these.",
    ))
    f.append(P("When you see <b>ASSUMED</b>, open the website you downloaded "
               "from and check one single fixture date. If the script has it "
               "right, carry on. If it is a month out, add "
               "<b>--date-order mdy</b> to the end of your command and run it "
               "again:"))
    f.append(code(r'python tools\fixtures_import.py downloaded.csv '
                  r'--out "Fixtures.xlsx" --date-order mdy'))
    f.append(P("If the file contradicts <i>itself</i>, the script refuses to "
               "import at all rather than getting half the rows wrong. That "
               "is deliberate.", "note"))

    # ---------------------------------------------------------- commands ----
    f.extend(H1("PART 4  -  Command reference"))
    f.append(P("Everything below is typed after "
               "<b>python tools\\fixtures_import.py</b>."))
    f.extend(grid([
        ["Add this", "What it does"],
        ["--inspect",
         "Shows what it found and <b>writes nothing</b>. Always run this "
         "first."],
        ['--out "Name.xlsx"',
         "Writes a brand-new spreadsheet with that name."],
        ['--into "Name.xlsx"',
         "Adds onto an existing spreadsheet. Copies it first, so your "
         "original is never changed."],
        ['--sheet "Fixture List"',
         "Only needed if the workbook has several sheets and it picked the "
         "wrong one."],
        ["--date-order dmy",
         "Force day-first. Use when the run says ASSUMED and you have checked "
         "it is day-first."],
        ["--date-order mdy",
         "Force month-first. Same, for an American source."],
        ["--in-place",
         "Write straight over the existing file instead of making a copy. "
         "<b>Avoid this</b> unless you have a backup."],
    ], [50 * mm, PAGE_W - 2 * MARGIN - 50 * mm], mono_col=0))

    # ----------------------------------------------------------- trouble ----
    f.extend(H1("PART 5  -  If something goes wrong"))
    f.extend(grid([
        ["What you see", "What it means and what to do"],
        ["<b>'python' is not recognized</b>",
         "Python is not installed, or not on your path. Install it from "
         "<b>python.org/downloads</b> and tick <b>Add python.exe to PATH</b> "
         "on the very first screen of the installer. That tickbox is easy to "
         "miss and is the usual cause."],
        ["<b>can't open file ... tools\\fixtures_import.py</b>",
         "You are not in the right folder, or the script is not where you "
         "think. Re-run the <b>cd C:\\Users\\Cliff\\betting</b> line, then "
         "type <b>dir tools</b> and press Enter - you should see "
         "<b>fixtures_import.py</b> listed."],
        ["<b>STOPPED: cannot find ...</b>",
         "The file name is not exactly right. Type <b>dir</b> and press Enter "
         "to list the folder, and copy the name from there. Names with spaces "
         "need double quotes around them."],
        ["<b>STOPPED: ... needs openpyxl</b>",
         "Run <b>pip install openpyxl</b> and try again."],
        ["<b>no date column</b>",
         "It could not find dates in that file. Send me the <b>--inspect</b> "
         "output and I will fix the detection."],
        ["<b>the dates disagree with each other</b>",
         "Some rows are day-first and some month-first in the one file. "
         "Nothing is imported. Send it to me."],
        ["<b>unusable rows</b> is high",
         "The lines underneath say why each row was skipped. Usually a header "
         "or a blank line in the middle of the file, which is harmless."],
        ["<b>It ran, but columns are blank</b>",
         "Normal. It lists the columns it could not fill and leaves them "
         "empty on purpose - your own notes and ratings are never "
         "overwritten."],
    ], [48 * mm, PAGE_W - 2 * MARGIN - 48 * mm]))

    # ------------------------------------------------------------ limits ----
    f.extend(H1("PART 6  -  What this does and does not do"))
    f.append(H2("What it handles for you"))
    for b in [
        "A file that is really <b>tab-separated but named .csv</b> - the one "
        "that drops the whole row into column A in Excel. It works out the "
        "real separator itself.",
        "Commas, semicolons, tabs, or a genuine <b>.xlsx</b> file.",
        "Both teams crammed into one column, like <b>Arsenal v Chelsea</b> or "
        "<b>Shanghai Port vs Beijing Guoan</b>.",
        "A file with <b>no heading row at all</b> - it reads the columns from "
        "the data itself.",
        "Dates written as <b>real Excel dates</b>, so Excel can never re-read "
        "them its own way later.",
        "Running the same download twice - it adds <b>nothing</b> the second "
        "time, so you cannot double up by accident.",
        "Your existing spreadsheet's own layout, wherever the headings sit, "
        "even with a title line above them.",
    ]:
        f.append(P("&bull;&nbsp;&nbsp;" + b, "bullet"))

    f.append(H2("What it does not do"))
    for b in [
        "<b>It does not download anything.</b> You still get the file "
        "yourself. The automatic worldwide feed is the part that needs the "
        "Betfair App Key.",
        "<b>Competition names come through as the source writes them</b> - "
        "<b>E0</b>, <b>SP1</b> - not Premier League. Say the word and I will "
        "add a lookup for readable names.",
        "<b>It does not bring odds across</b>, only the fixture itself.",
    ]:
        f.append(P("&bull;&nbsp;&nbsp;" + b, "bullet"))

    f.append(Spacer(1, 6))
    f.append(warn(
        "The one habit worth keeping",
        "Always run <b>--inspect</b> first and read the sample fixtures it "
        "prints. It takes five seconds and it is the only step that catches a "
        "wrong column or a wrong month <i>before</i> it is in your database.",
    ))

    doc.build(f)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "Fixtures Import - Instructions.pdf"
    build(out)
    print(f"Wrote {out}")
