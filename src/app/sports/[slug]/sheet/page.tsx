import { getSportBySlug } from "@/lib/actions/sports";
import { listBetsForSport } from "@/lib/actions/bets";
import { notFound } from "next/navigation";
import { BetTable } from "@/components/BetTable";

function fmt(n: number | null, decimals = 2): string {
  if (n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(decimals)}`;
}

function fmtPnl(n: number): string {
  const sign = n >= 0 ? "+" : "";
  return `${sign}£${Math.abs(n).toFixed(2)}`;
}

export default async function SheetPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const sport = await getSportBySlug(slug);
  if (!sport) notFound();

  const bets = await listBetsForSport(sport.id);

  const settledBets = bets.filter((b) => b.placed && b.closingPrice !== null && b.clvPercent !== null);
  const avgClv =
    settledBets.length > 0
      ? settledBets.reduce((sum, b) => sum + (b.clvPercent ?? 0), 0) / settledBets.length
      : null;
  const totalPnl = bets
    .filter((b) => b.placed && b.result !== "PENDING")
    .reduce((sum, b) => sum + (b.pnl ?? 0), 0);

  const avgClvClass =
    avgClv === null
      ? "text-[var(--text-muted)]"
      : avgClv > 0
        ? "text-[var(--green)]"
        : avgClv < -1
          ? "text-[var(--red)]"
          : "text-[var(--amber)]";

  const pnlClass = totalPnl >= 0 ? "text-[var(--green)]" : "text-[var(--red)]";

  return (
    <div>
      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide font-medium text-[var(--text-muted)]">
            Avg CLV %
          </span>
          <span className={`text-xl font-bold tabular-nums font-mono ${avgClvClass}`}>
            {avgClv !== null ? `${fmt(avgClv)}%` : "—"}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {settledBets.length} settled bets w/ close
          </span>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide font-medium text-[var(--text-muted)]">
            Total P&amp;L
          </span>
          <span className={`text-xl font-bold tabular-nums font-mono ${pnlClass}`}>
            {fmtPnl(totalPnl)}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {bets.filter((b) => b.placed && b.result !== "PENDING").length} settled placed bets
          </span>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide font-medium text-[var(--text-muted)]">
            Total Bets
          </span>
          <span className="text-xl font-bold tabular-nums font-mono text-[var(--text)]">
            {bets.length}
          </span>
          <span className="text-[10px] text-[var(--text-muted)]">
            {bets.filter((b) => b.placed).length} placed,{" "}
            {bets.filter((b) => b.result === "PENDING").length} pending
          </span>
        </div>
      </div>

      {/* Export button + table */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-[var(--text)]">Bet History</h2>
        <a
          href={`/api/export?sport=${slug}`}
          download
          className="text-xs text-[var(--blue)] border border-[var(--blue)]/30 rounded px-3 py-1.5 hover:bg-[var(--blue)]/10 transition-colors"
        >
          Export to Excel
        </a>
      </div>

      <BetTable bets={bets} sportSlug={slug} />
    </div>
  );
}
