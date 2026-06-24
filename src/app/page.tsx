import { getClvDashboard } from "@/lib/actions/dashboard";
import { StopLossBanner } from "@/components/StopLossBanner";
import { VerdictBanner } from "@/components/VerdictBanner";
import { CLVChart } from "@/components/CLVChart";
import Link from "next/link";

function fmt(n: number | null, decimals = 2, prefix = ""): string {
  if (n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${prefix}${sign}${n.toFixed(decimals)}`;
}

function fmtPnl(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}£${Math.abs(n).toFixed(2)}`;
}

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
      <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-medium">{label}</span>
      <span className={`text-2xl font-bold tabular-nums ${valueClass ?? "text-[var(--text)]"}`}>{value}</span>
      {sub && <span className="text-xs text-[var(--text-muted)]">{sub}</span>}
    </div>
  );
}

export default async function HomePage() {
  const data = await getClvDashboard();
  const { verdict, chartData, sportSummaries, overall, bankroll } = data;

  const avgClvClass =
    overall.avgClvPct === null
      ? "text-[var(--text-muted)]"
      : overall.avgClvPct > 0
        ? "text-[var(--green)]"
        : overall.avgClvPct < -1
          ? "text-[var(--red)]"
          : "text-[var(--amber)]";

  const pnlClass = overall.totalPnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]";

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto">
      <StopLossBanner
        triggered={bankroll.stopLossTriggered}
        drawdownPct={bankroll.currentDrawdownPct}
        hardStopPct={bankroll.hardStopLossPct}
        balance={bankroll.currentBalance}
      />

      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[var(--text)] mb-0.5">CLV Dashboard</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Closing line value — the only honest measure of your edge.
        </p>
      </div>

      <div className="mb-6">
        <VerdictBanner verdict={verdict} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <StatCard
          label="Avg CLV %"
          value={overall.avgClvPct !== null ? `${fmt(overall.avgClvPct)}%` : "—"}
          valueClass={avgClvClass}
          sub={`${overall.settledCount} bets with closing prices`}
        />
        <StatCard
          label="Sample Size"
          value={String(verdict.sampleSize)}
          sub="settled bets w/ close"
        />
        <StatCard
          label="Win Rate"
          value={overall.winRate !== null ? `${overall.winRate.toFixed(1)}%` : "—"}
          sub={`${overall.settledCount} settled`}
        />
        <StatCard
          label="Total P&amp;L"
          value={fmtPnl(overall.totalPnl)}
          valueClass={pnlClass}
          sub={`${overall.totalBetsPlaced} bets placed`}
        />
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 pt-5 pb-4 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text)]">Cumulative Avg CLV %</h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Bold line = running average. Faint line = individual bets.
            </p>
          </div>
          <span className="text-xs text-[var(--text-muted)]">{chartData.length} data points</span>
        </div>
        <CLVChart data={chartData} />
      </div>

      <div className="rounded-lg border border-[var(--blue)]/30 bg-[var(--blue)]/5 px-5 py-4 mb-6 flex gap-3 items-start">
        <span className="text-[var(--blue)] text-base mt-0.5 shrink-0">◎</span>
        <div>
          <p className="text-sm font-semibold text-[var(--text)] mb-0.5">Results are noise. CLV is signal.</p>
          <p className="text-xs text-[var(--text-muted)] leading-relaxed">
            A positive win/loss record over 50 bets tells you almost nothing. A positive average CLV over 100 bets
            tells you everything. The market sets the closing line with sharp money — beating it consistently is the
            only replicable proof of edge.
          </p>
        </div>
      </div>

      {sportSummaries.length > 0 && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
          <div className="px-5 py-3 border-b border-[var(--border)]">
            <h2 className="text-sm font-semibold text-[var(--text)]">CLV by Sport</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border)]">
                <th className="text-left px-5 py-2.5 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                  Sport
                </th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                  Avg CLV %
                </th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                  Sample
                </th>
                <th className="text-right px-4 py-2.5 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                  Win Rate
                </th>
                <th className="text-right px-5 py-2.5 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
                  P&amp;L
                </th>
              </tr>
            </thead>
            <tbody>
              {sportSummaries.map((s) => {
                const clvColor =
                  s.avgClvPct === null
                    ? "text-[var(--text-muted)]"
                    : s.avgClvPct > 0
                      ? "text-[var(--green)]"
                      : s.avgClvPct < -1
                        ? "text-[var(--red)]"
                        : "text-[var(--amber)]";
                const pnlColor = s.totalPnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]";

                return (
                  <tr
                    key={s.sportId}
                    className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)] transition-colors"
                  >
                    <td className="px-5 py-3">
                      <Link
                        href={`/sports/${s.sportSlug}`}
                        className="text-[var(--text)] hover:text-[var(--blue)] transition-colors font-medium"
                      >
                        {s.sportName}
                      </Link>
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums font-semibold ${clvColor}`}>
                      {s.avgClvPct !== null ? `${fmt(s.avgClvPct)}%` : "—"}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[var(--text-muted)]">
                      {s.sampleSize}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[var(--text-muted)]">
                      {s.winRate !== null ? `${s.winRate.toFixed(1)}%` : "—"}
                    </td>
                    <td className={`px-5 py-3 text-right tabular-nums font-medium ${pnlColor}`}>
                      {fmtPnl(s.totalPnl)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {sportSummaries.length === 0 && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-8 text-center">
          <p className="text-[var(--text-muted)] text-sm">No sport data yet.</p>
          <p className="text-[var(--text-muted)] text-xs mt-1">
            Place and settle bets with closing prices to see per-sport CLV breakdowns.
          </p>
        </div>
      )}
    </div>
  );
}
