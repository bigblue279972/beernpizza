import type { ClvVerdict } from "@/lib/actions/dashboard";

interface VerdictBannerProps {
  verdict: ClvVerdict;
}

const labelConfig = {
  EDGE_DETECTED: {
    badge: "Edge Detected",
    borderClass: "border-l-4 border-l-[var(--green)]",
    bgClass: "bg-[var(--green)]/5",
    badgeBg: "bg-[var(--green)]/15 text-[var(--green)]",
    textClass: "text-[var(--green)]",
  },
  NO_EDGE: {
    badge: "No Edge",
    borderClass: "border-l-4 border-l-[var(--red)]",
    bgClass: "bg-[var(--red)]/5",
    badgeBg: "bg-[var(--red)]/15 text-[var(--red)]",
    textClass: "text-[var(--red)]",
  },
  BREAK_EVEN: {
    badge: "Break Even",
    borderClass: "border-l-4 border-l-[var(--amber)]",
    bgClass: "bg-[var(--amber)]/5",
    badgeBg: "bg-[var(--amber)]/15 text-[var(--amber)]",
    textClass: "text-[var(--amber)]",
  },
  INSUFFICIENT_DATA: {
    badge: "Insufficient Data",
    borderClass: "border-l-4 border-l-[var(--amber)]",
    bgClass: "bg-[var(--amber)]/5",
    badgeBg: "bg-[var(--amber)]/15 text-[var(--amber)]",
    textClass: "text-[var(--amber)]",
  },
} as const;

export function VerdictBanner({ verdict }: VerdictBannerProps) {
  const cfg = labelConfig[verdict.label];

  return (
    <div
      className={`rounded-lg border border-[var(--border)] ${cfg.borderClass} ${cfg.bgClass} px-6 py-5`}
    >
      <div className="flex items-center gap-3 mb-3">
        <span
          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wide ${cfg.badgeBg}`}
        >
          {cfg.badge}
        </span>
        {verdict.avgClvPct !== null && (
          <span className={`text-2xl font-bold tabular-nums ${cfg.textClass}`}>
            {verdict.avgClvPct > 0 ? "+" : ""}
            {verdict.avgClvPct.toFixed(2)}%
          </span>
        )}
        <span className="text-xs text-[var(--text-muted)] ml-auto">
          n = {verdict.sampleSize}
        </span>
      </div>

      <p className="text-[var(--text)] text-sm leading-relaxed">{verdict.message}</p>

      <p className="mt-3 text-[var(--text-muted)] text-xs italic">
        After 100+ bets your cumulative CLV chart will tell you the truth that individual results never can.
      </p>
    </div>
  );
}
