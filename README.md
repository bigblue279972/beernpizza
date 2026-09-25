# beernpizza

Tooling for the Unleashed Pro / Tipping Edge betting operation.

## Betting log

`tools/build_betting_log.py` generates a macro-free Excel workbook for logging bets
and scoring them on Closing Line Value.

```bash
pip install openpyxl
python tools/build_betting_log.py "Betting Log.xlsx"            # blank template
DEMO_N=45 python tools/build_betting_log.py "demo.xlsx" --demo   # filled sample
LOG_ROWS=3001 python tools/build_betting_log.py "big.xlsx"      # more capacity
```

The log holds 1500 bets by default (`LOG_ROWS`). Every running column -- bank
before/after, expected bank, peak and drawdown -- is **incremental**, each row
reading the row above it rather than re-summing the column from the top. The
obvious `SUM($X$2:$Xr)` form is O(n^2) for the sheet as a whole and makes a
few thousand rows sluggish on a laptop.

## Getting Closing Line Value

CLV needs one number per bet: the last traded price on that selection at the
off. Getting there is three steps.

**Step 1 - `tools/betfair_pull_bets.py`.** The website CSV export has no
`marketId` or `selectionId`, only free text, so it cannot be joined to price
data reliably. `listClearedOrders` returns both, plus `marketStartTime`. This is
time-critical: **Betfair caps that history at 90 days** and it cannot be
re-opened.

```bash
python tools/betfair_pull_bets.py          # writes betfair_bets_with_ids.csv
```

Standard library only. Credentials live in `betfair_config.txt` (gitignored) and
the password is prompted per run, never written to disk. A free *Delayed* App Key
is expected to be sufficient here, since cleared orders are account data rather
than live market prices.

**Step 2 - `tools/clv_backfill.py`.** Backfills CLV from football-data.co.uk,
which publishes free per-league season CSVs carrying **closing** odds (their
convention is an extra `C`: `B365CH` is Bet365's closing home price, `PSCH/PSCD/
PSCA` are Pinnacle's closing 1X2). Pinnacle's close is the sharpest public
benchmark in soccer, so it is preferred, falling back to the market average.
No App Key, no 90-day limit.

```bash
python tools/clv_backfill.py ExchangeBets_Settled.csv
```

Four things it is careful about:

- **Opening odds are never silently substituted.** Only closing columns are
  eligible; a file without them is reported, not quietly mis-benchmarked.
- **The bookmaker margin is stripped** before comparing. A book price carries
  overround and a Betfair price does not, so a raw comparison would show
  phantom CLV on every bet.
- **Team matching refuses a shared non-distinctive word.** A plain string ratio
  scores `Man City` against `Man Utd` at 0.81 — high enough to price a bet off
  the wrong fixture. Tokens are paired individually and the worst pairing gets
  half the weight, which drops that to 0.55 while keeping `Nott'm Forest` ↔
  `Nottingham Forest` at 0.93.
- **Ambiguous matches are refused**, not guessed: the best fixture must also
  beat the runner-up by a margin.

**Scope.** Club football in covered leagues only. It cannot reach international
fixtures or AFL, which between them are about a third of the sample bet history.
Those need Betfair Historical Data BASIC (free, last-traded-price per minute
back to April 2015, no 90-day limit) or an AFL-specific odds source.

**Step 3** - capture the price at the off for new bets, so the log fills its own
Closing Odds column.

## Analysing a Betfair export

`tools/betfair_analyse.py` reads a Betfair *ExchangeBets Settled* CSV and reports
turnover, commission-adjusted ROI, a significance test on the per-bet return,
profit concentration, and breakdowns by market, odds band and month.

```bash
python tools/betfair_analyse.py ExchangeBets_Settled.csv
```

Two parsing traps it handles: the month is written `Sept`, not `Sep`, so
`%b` will not parse it; and the description is `Event Selection-Market | Betfair
Bet ID`, where the market is after the **last** hyphen -- splitting on the first
one mangles every hyphenated club name (Zulte-Waregem, Red Bull Bragantino).

Note that the exported `Profit/Loss` column is **gross**: Betfair charges
commission separately on net market winnings, so it is not in that figure.

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
