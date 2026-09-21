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

### Stake weighting

Staking is **tier-weighted, never edge-proportional**. Each bet carries a Stake
Tier; the multiplier beside that tier on the Settings tab turns the unit into a
Plan Stake, and the log records what was actually staked beside it. A unit can be
a fixed dollar amount or a share of the bank before the bet, selectable on Settings.

Kelly-as-staking-driver is a retired concept (SKILL.md house style; Rulebook
Section 12.2 scaling discipline), and sizing off a self-reported edge estimate
would amplify an optimistic model rather than test it. So the workbook does not
size bets — it *measures whether the tiers earn their keep*:

- **Stake-weighted CLV** counts every dollar risked; **flat-stake CLV** counts every
  bet equally. Weighted above flat means bigger bets are landing on better prices.
- **Off plan, by CLV** is the process read; **off plan, in money** is the outcome and
  carries luck, so the CLV line is the one to trust.
- The **By Stake Tier** breakdown shows CLV per tier, which is what proves or
  disproves the weighting.

Every row also carries **Bank Before** and **Bank After**, so each bet shows its own
opening and closing balance and the two chain together down the sheet.

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
- Columns are addressed through the `COL` map, never by hardcoded letters, so
  inserting a column cannot silently break a downstream formula.
- An unset tier multiplier prints `SET MULTIPLIER` rather than staking nothing —
  a blank cell indexes to 0, which would otherwise pass silently.

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
known edge injected into 400 generated bets. The staking layer is verified by
inverting the tiers on a 300-bet run and confirming the sizing metric flips
negative and the By Stake Tier table ranks the big tiers worst.
