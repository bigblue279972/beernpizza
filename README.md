# beernpizza

Tooling for the Unleashed Pro / Tipping Edge betting operation.

## Betting log

`tools/build_betting_log.py` generates a macro-free Excel workbook for logging bets
and scoring them on Closing Line Value.

```bash
pip install openpyxl
python tools/build_betting_log.py "Betting Log.xlsx"            # blank template
DEMO_N=45 python tools/build_betting_log.py "demo.xlsx" --demo   # filled sample
```

Five tabs: **Bet Log** (the only tab with typing in it), **Dashboard**,
**Whats Working**, **Settings**, **How To Use**.

### Design rules this file obeys

- **No operational parameter is hardcoded.** Bank, unit size, commission and the
  minimum sample size are blank input cells on the Settings tab, filled from the
  Rulebook. The Dashboard refuses to be trusted until they are set.
- **Result means "did YOUR BET win"**, not "did the selection win". A winning lay
  is `Win`. Back and lay P/L, liability and CLV are all handled separately.
- **CLV $** is the expected profit if the closing price is the true price.
  **CLV %** is CLV $ divided by money at risk, so backs and lays stay comparable.
- **CLV is measured gross of commission** (it is a price measure); **P/L is net**
  of it.
- Segment verdicts return `TOO FEW BETS` below the sample threshold rather than
  a reading of noise.

### Compatibility notes

- Dropdowns use plain ranges, not dynamic `OFFSET`/`COUNTA` named ranges, which
  are unreliable in Excel for Android/iOS. The workbook has to work on a phone.
- Charted helper columns are kept **visible**: Excel and LibreOffice drop hidden
  cells from charts by default, which silently empties a series.
- Chart series use fixed ranges. Sheet-scoped dynamic names were tested and do
  not render, so the equity curve spans all 500 rows and fills in as bets are logged.
- No macros, so the file opens without a security warning.

### Verification

Formulas are validated by recalculating a *copy* in LibreOffice (the shipped file
stays pristine openpyxl output), then cross-checking every computed bet against an
independent Python calculation, and confirming the breakdown tables recover a
known edge injected into 400 generated bets.
