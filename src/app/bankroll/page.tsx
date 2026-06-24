import { getBankrollSeries } from "@/lib/actions/bankroll";
import { BankrollChart } from "@/components/BankrollChart";
import { BankrollSettingsForm } from "./BankrollSettingsForm";
import { BankrollTransactionForm } from "./BankrollTransactionForm";

function StatCard({
  label,
  value,
  valueClass,
  sub,
}: {
  label: string;
  value: string;
  valueClass?: string;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-4 flex flex-col gap-1">
      <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-medium">
        {label}
      </span>
      <span className={`text-2xl font-bold tabular-nums ${valueClass ?? "text-[var(--text)]"}`}>
        {value}
      </span>
      {sub && <span className="text-xs text-[var(--text-muted)]">{sub}</span>}
    </div>
  );
}

export default async function BankrollPage() {
  const { settings, series, peak, currentDrawdownPct, stopLossTriggered } =
    await getBankrollSeries();

  const currentBalance = settings.currentBalance;
  const startingBalance = settings.startingBalance;
  const totalPnl = currentBalance - startingBalance;

  const balanceClass =
    currentBalance > startingBalance
      ? "text-[var(--green)]"
      : currentBalance < startingBalance
        ? "text-[var(--red)]"
        : "text-[var(--text)]";

  const drawdownClass = currentDrawdownPct > 10 ? "text-[var(--red)]" : "text-[var(--text)]";
  const pnlClass = totalPnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]";

  // Last 20 series entries for the timeline log, with deltas
  const recentEntries = series.slice(-20).map((pt, i, arr) => {
    const prev = i > 0 ? arr[i - 1].balance : pt.balance;
    return {
      ...pt,
      delta: pt.balance - prev,
    };
  });

  // Separate manual transactions from bet settlements
  const manualLabels = new Set(["DEPOSIT", "WITHDRAWAL", "ADJUSTMENT", "Starting balance"]);
  const manualEntries = recentEntries.filter((e) => manualLabels.has(e.label));
  const betEntries = recentEntries.filter((e) => !manualLabels.has(e.label));

  function formatDate(d: Date | string): string {
    const date = new Date(d);
    const isEpoch =
      date.getFullYear() === 1970 && date.getMonth() === 0 && date.getDate() === 1;
    if (isEpoch) return "Start";
    return date.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto">
      {/* Stop-loss alert */}
      {stopLossTriggered && (
        <div className="rounded-lg border border-[var(--red)] bg-[var(--red)]/10 px-5 py-4 mb-6 flex items-start gap-4">
          <span className="inline-block w-3 h-3 rounded-full bg-[var(--red)] shrink-0 mt-0.5 animate-pulse" />
          <div>
            <p className="text-[var(--red)] font-bold text-base uppercase tracking-wide mb-1">
              HARD STOP TRIGGERED — Do not bet.
            </p>
            <p className="text-[var(--text)] text-sm">
              Your drawdown of{" "}
              <span className="font-semibold text-[var(--red)]">
                {currentDrawdownPct.toFixed(1)}%
              </span>{" "}
              has reached your limit of{" "}
              <span className="font-semibold">{settings.hardStopLossPct.toFixed(1)}%</span>.
              Current balance:{" "}
              <span className="font-semibold">£{currentBalance.toFixed(2)}</span>.
            </p>
          </div>
        </div>
      )}

      {/* Page heading */}
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[var(--text)] mb-0.5">Bankroll Tracker</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Balance history, discipline settings, and transaction management.
        </p>
      </div>

      {/* Summary stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="Current Balance"
          value={`£${currentBalance.toFixed(2)}`}
          valueClass={balanceClass}
          sub={`Started at £${startingBalance.toFixed(2)}`}
        />
        <StatCard
          label="Peak Balance"
          value={`£${peak.toFixed(2)}`}
          sub="All-time high"
        />
        <StatCard
          label="Drawdown from Peak"
          value={`${currentDrawdownPct.toFixed(1)}%`}
          valueClass={drawdownClass}
          sub={`Limit: ${settings.hardStopLossPct.toFixed(1)}%`}
        />
        <StatCard
          label="Total P&L"
          value={`${totalPnl >= 0 ? "+" : ""}£${Math.abs(totalPnl).toFixed(2)}`}
          valueClass={pnlClass}
          sub="vs starting balance"
        />
      </div>

      {/* Balance over time chart */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 pt-5 pb-4 mb-6">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-[var(--text)]">Balance Over Time</h2>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Dashed lines show your starting balance and hard stop-loss floor.
          </p>
        </div>
        <BankrollChart
          series={series}
          peak={peak}
          hardStopLossPct={settings.hardStopLossPct}
          startingBalance={startingBalance}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Discipline settings */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-5">
          <h2 className="text-sm font-semibold text-[var(--text)] mb-1">Discipline Settings</h2>
          <p className="text-xs text-[var(--text-muted)] mb-4">
            These rules govern your staking and risk limits.
          </p>
          <BankrollSettingsForm settings={settings} />
        </div>

        {/* Deposit / Withdrawal / Adjustment */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-5">
          <h2 className="text-sm font-semibold text-[var(--text)] mb-1">
            Add Transaction
          </h2>
          <p className="text-xs text-[var(--text-muted)] mb-4">
            Record deposits, withdrawals, or balance adjustments.
          </p>
          <BankrollTransactionForm />
        </div>
      </div>

      {/* Transaction history / series log */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-6">
        <div className="px-5 py-3 border-b border-[var(--border)]">
          <h2 className="text-sm font-semibold text-[var(--text)]">Recent Activity</h2>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">Last 20 events in chronological order.</p>
        </div>

        {recentEntries.length <= 1 ? (
          <div className="px-5 py-8 text-center">
            <p className="text-[var(--text-muted)] text-sm">No activity yet.</p>
            <p className="text-[var(--text-muted)] text-xs mt-1">
              Add a deposit or settle a bet to see history here.
            </p>
          </div>
        ) : (
          <div>
            {/* Manual transactions section */}
            {manualEntries.length > 0 && (
              <div>
                <div className="px-5 py-2 bg-[var(--surface-2)] border-b border-[var(--border)]">
                  <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                    Manual Transactions
                  </span>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)]">
                      <th className="text-left px-5 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                        Date
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                        Type
                      </th>
                      <th className="text-right px-4 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                        Change
                      </th>
                      <th className="text-right px-5 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                        Balance
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {manualEntries.map((entry, i) => {
                      const deltaClass =
                        entry.delta > 0
                          ? "text-[var(--green)]"
                          : entry.delta < 0
                            ? "text-[var(--red)]"
                            : "text-[var(--text-muted)]";
                      return (
                        <tr
                          key={i}
                          className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)] transition-colors"
                        >
                          <td className="px-5 py-2.5 text-[var(--text-muted)] whitespace-nowrap">
                            {formatDate(entry.date)}
                          </td>
                          <td className="px-4 py-2.5 text-[var(--text)]">{entry.label}</td>
                          <td className={`px-4 py-2.5 text-right tabular-nums font-medium ${deltaClass}`}>
                            {entry.delta === 0
                              ? "—"
                              : `${entry.delta > 0 ? "+" : ""}£${Math.abs(entry.delta).toFixed(2)}`}
                          </td>
                          <td className="px-5 py-2.5 text-right tabular-nums text-[var(--text)]">
                            £{entry.balance.toFixed(2)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Bet settlements section */}
            {betEntries.length > 0 && (
              <div>
                <div className="px-5 py-2 bg-[var(--surface-2)] border-b border-[var(--border)]">
                  <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                    Bet Settlements
                  </span>
                </div>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[var(--border)]">
                      <th className="text-left px-5 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                        Date
                      </th>
                      <th className="text-left px-4 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                        Event
                      </th>
                      <th className="text-right px-4 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                        P&amp;L
                      </th>
                      <th className="text-right px-5 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                        Balance
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {betEntries.map((entry, i) => {
                      const deltaClass =
                        entry.delta > 0
                          ? "text-[var(--green)]"
                          : entry.delta < 0
                            ? "text-[var(--red)]"
                            : "text-[var(--text-muted)]";
                      return (
                        <tr
                          key={i}
                          className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)] transition-colors"
                        >
                          <td className="px-5 py-2.5 text-[var(--text-muted)] whitespace-nowrap">
                            {formatDate(entry.date)}
                          </td>
                          <td className="px-4 py-2.5 text-[var(--text)] max-w-[220px] truncate">
                            {entry.label}
                          </td>
                          <td className={`px-4 py-2.5 text-right tabular-nums font-medium ${deltaClass}`}>
                            {entry.delta === 0
                              ? "—"
                              : `${entry.delta > 0 ? "+" : ""}£${Math.abs(entry.delta).toFixed(2)}`}
                          </td>
                          <td className="px-5 py-2.5 text-right tabular-nums text-[var(--text)]">
                            £{entry.balance.toFixed(2)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
