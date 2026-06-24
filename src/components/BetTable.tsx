"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { settleBet, deleteBet } from "@/lib/actions/bets";
import type { BetComputed } from "@/lib/betView";

interface Props {
  bets: BetComputed[];
  sportSlug: string;
}

function fmt(n: number | null, decimals = 2): string {
  if (n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(decimals)}`;
}

function fmtPnl(n: number | null): string {
  if (n === null) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}£${Math.abs(n).toFixed(2)}`;
}

function fmtDate(d: Date | string): string {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "2-digit" });
}

const RESULT_STYLES: Record<string, string> = {
  WIN: "text-[var(--green)]",
  LOSS: "text-[var(--red)]",
  VOID: "text-[var(--text-muted)]",
  PENDING: "text-[var(--amber)]",
};

function SettleForm({ betId, onDone }: { betId: string; onDone: () => void }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [closingPrice, setClosingPrice] = useState("");
  const [result, setResult] = useState<"WIN" | "LOSS" | "VOID">("WIN");
  const [error, setError] = useState<string | null>(null);

  async function handleSettle() {
    if (!closingPrice) {
      setError("Closing price is required.");
      return;
    }
    setError(null);
    startTransition(async () => {
      try {
        await settleBet(betId, { closingPrice: parseFloat(closingPrice), result });
        router.refresh();
        onDone();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to settle bet.");
      }
    });
  }

  return (
    <div className="flex items-start gap-2 flex-wrap">
      <input
        type="number"
        value={closingPrice}
        onChange={(e) => setClosingPrice(e.target.value)}
        placeholder="Closing price"
        step="0.01"
        min="1.01"
        className="w-28 rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs text-[var(--text)] font-mono focus:border-[var(--blue)] focus:outline-none"
      />
      <select
        value={result}
        onChange={(e) => setResult(e.target.value as "WIN" | "LOSS" | "VOID")}
        className="rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs text-[var(--text)] focus:border-[var(--blue)] focus:outline-none"
      >
        <option value="WIN">WIN</option>
        <option value="LOSS">LOSS</option>
        <option value="VOID">VOID</option>
      </select>
      <button
        onClick={handleSettle}
        disabled={isPending}
        className="px-3 py-1 rounded bg-[var(--green)] text-white text-xs font-semibold disabled:opacity-50 hover:bg-[var(--green)]/80 transition-colors"
      >
        {isPending ? "..." : "Confirm"}
      </button>
      <button
        onClick={onDone}
        className="px-2 py-1 rounded text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
      >
        Cancel
      </button>
      {error && <span className="text-xs text-[var(--red)] w-full">{error}</span>}
    </div>
  );
}

function BetRow({ bet, sportSlug }: { bet: BetComputed; sportSlug: string }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [showSettle, setShowSettle] = useState(false);
  const [showHover, setShowHover] = useState(false);

  const lessonTags =
    "lessonTags" in bet && Array.isArray((bet as BetComputed & { lessonTags: Array<{ tags: string }> }).lessonTags)
      ? (bet as BetComputed & { lessonTags: Array<{ tags: string }> }).lessonTags
          .flatMap((lt) => lt.tags.split(",").map((t) => t.trim()).filter(Boolean))
      : [];

  async function handleDelete() {
    if (!confirm("Delete this bet? This cannot be undone.")) return;
    startTransition(async () => {
      await deleteBet(bet.id);
      router.refresh();
    });
  }

  const clvClass =
    bet.clvPercent === null
      ? "text-[var(--text-muted)]"
      : bet.clvPercent > 0
        ? "text-[var(--green)]"
        : "text-[var(--red)]";

  const resultClass = RESULT_STYLES[bet.result ?? "PENDING"] ?? "text-[var(--text-muted)]";
  const pnlClass =
    bet.pnl === null || bet.pnl === undefined
      ? "text-[var(--text-muted)]"
      : bet.pnl >= 0
        ? "text-[var(--green)]"
        : "text-[var(--red)]";

  return (
    <>
      <tr
        className="border-b border-[var(--border)] hover:bg-[var(--surface-2)] transition-colors group"
        onMouseEnter={() => setShowHover(true)}
        onMouseLeave={() => setShowHover(false)}
      >
        <td className="px-3 py-2.5 text-xs text-[var(--text-muted)] whitespace-nowrap tabular-nums">
          {fmtDate(bet.eventDate)}
        </td>
        <td className="px-3 py-2.5 text-xs text-[var(--text)] max-w-[140px] truncate">
          {bet.event}
        </td>
        <td className="px-3 py-2.5 text-xs text-[var(--text-muted)]">{bet.market}</td>
        <td className="px-3 py-2.5 text-xs tabular-nums font-mono text-right">
          {bet.myProbability.toFixed(1)}%
        </td>
        <td className="px-3 py-2.5 text-xs tabular-nums font-mono text-right">
          {bet.fairPrice.toFixed(3)}
        </td>
        <td className="px-3 py-2.5 text-xs tabular-nums font-mono text-right">
          {bet.requiredPrice.toFixed(3)}
        </td>
        <td className="px-3 py-2.5 text-xs tabular-nums font-mono text-right">
          {bet.availablePrice.toFixed(3)}
        </td>
        <td className="px-3 py-2.5 text-center">
          {bet.priceQualifies ? (
            <span className="text-[var(--green)] font-bold">✓</span>
          ) : (
            <span className="text-[var(--red)] font-bold">✗</span>
          )}
        </td>
        <td className="px-3 py-2.5 text-xs tabular-nums font-mono text-right text-[var(--text-muted)]">
          {bet.suggestedStake !== null ? `£${bet.suggestedStake.toFixed(2)}` : "—"}
        </td>
        <td className="px-3 py-2.5 text-xs tabular-nums font-mono text-right">
          {bet.placed ? `£${bet.stake.toFixed(2)}` : <span className="text-[var(--text-muted)]">—</span>}
        </td>
        <td className="px-3 py-2.5 text-xs tabular-nums font-mono text-right text-[var(--text-muted)]">
          {bet.closingPrice !== null ? bet.closingPrice.toFixed(3) : "—"}
        </td>
        <td className={`px-3 py-2.5 text-xs tabular-nums font-mono text-right font-semibold ${clvClass}`}>
          {bet.clvPercent !== null ? `${fmt(bet.clvPercent)}%` : "—"}
        </td>
        <td className={`px-3 py-2.5 text-xs font-semibold ${resultClass}`}>
          {bet.result ?? "PENDING"}
        </td>
        <td className={`px-3 py-2.5 text-xs tabular-nums font-mono text-right font-semibold ${pnlClass}`}>
          {fmtPnl(bet.pnl ?? null)}
        </td>
        <td className="px-3 py-2.5 text-xs">
          <div className="flex flex-wrap gap-1">
            {lessonTags.slice(0, 2).map((tag) => (
              <span
                key={tag}
                className="inline-block rounded px-1.5 py-0.5 text-[10px] bg-[var(--surface-2)] text-[var(--text-muted)] border border-[var(--border)]"
              >
                {tag}
              </span>
            ))}
            {lessonTags.length > 2 && (
              <span className="text-[10px] text-[var(--text-muted)]">+{lessonTags.length - 2}</span>
            )}
          </div>
        </td>
        <td className="px-3 py-2.5">
          {bet.divergenceFlagged && (
            <span
              title={`Divergence: ${bet.divergencePoints.toFixed(1)} pts`}
              className="text-[var(--amber)] cursor-help"
            >
              ⚠
            </span>
          )}
        </td>
        <td className="px-3 py-2.5">
          <div className={`flex gap-1 transition-opacity ${showHover || showSettle ? "opacity-100" : "opacity-0"}`}>
            {bet.result === "PENDING" && bet.placed && (
              <button
                onClick={() => setShowSettle(true)}
                className="text-[10px] px-2 py-0.5 rounded border border-[var(--blue)]/40 text-[var(--blue)] hover:bg-[var(--blue)]/10 transition-colors"
              >
                Settle
              </button>
            )}
            <button
              onClick={handleDelete}
              disabled={isPending}
              className="text-[10px] px-2 py-0.5 rounded border border-[var(--red)]/30 text-[var(--red)] hover:bg-[var(--red)]/10 transition-colors disabled:opacity-50"
            >
              {isPending ? "…" : "Delete"}
            </button>
          </div>
        </td>
      </tr>
      {showSettle && (
        <tr className="border-b border-[var(--border)] bg-[var(--surface-2)]">
          <td colSpan={17} className="px-4 py-3">
            <SettleForm betId={bet.id} onDone={() => setShowSettle(false)} />
          </td>
        </tr>
      )}
    </>
  );
}

export function BetTable({ bets, sportSlug }: Props) {
  if (bets.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-6 py-10 text-center">
        <p className="text-[var(--text-muted)] text-sm">No bets yet for this sport.</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">
          Use the Entry tab to log your first bet.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm whitespace-nowrap">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--surface-2)]">
              <Th>Date</Th>
              <Th>Event</Th>
              <Th>Market</Th>
              <Th right>My Prob%</Th>
              <Th right>Fair</Th>
              <Th right>Required</Th>
              <Th right>Available</Th>
              <Th center>Qual.</Th>
              <Th right>Sug. Stake</Th>
              <Th right>Stake</Th>
              <Th right>Close</Th>
              <Th right>CLV%</Th>
              <Th>Result</Th>
              <Th right>P&amp;L</Th>
              <Th>Tags</Th>
              <Th center>Div.</Th>
              <Th>Actions</Th>
            </tr>
          </thead>
          <tbody>
            {bets.map((bet) => (
              <BetRow key={bet.id} bet={bet} sportSlug={sportSlug} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({
  children,
  right,
  center,
}: {
  children: React.ReactNode;
  right?: boolean;
  center?: boolean;
}) {
  return (
    <th
      className={`px-3 py-2.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-muted)] ${
        right ? "text-right" : center ? "text-center" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}
