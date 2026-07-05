"use client";

import { useState } from "react";

interface StopLossBannerProps {
  triggered: boolean;
  drawdownPct: number;
  hardStopPct: number;
  balance: number;
}

export function StopLossBanner({ triggered, drawdownPct, hardStopPct, balance }: StopLossBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (!triggered || dismissed) return null;

  return (
    <div className="relative flex items-start gap-4 rounded-lg border border-[var(--red)] bg-[var(--red)]/10 px-5 py-4 mb-6">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-1">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-[var(--red)] shrink-0 animate-pulse" />
          <span className="text-[var(--red)] font-bold text-base tracking-wide uppercase">
            Hard Stop-Loss Triggered
          </span>
        </div>
        <p className="text-[var(--text)] text-sm mt-1">
          Your bankroll has drawn down{" "}
          <span className="font-semibold text-[var(--red)]">{drawdownPct.toFixed(1)}%</span>
          {" "}against your hard limit of{" "}
          <span className="font-semibold">{hardStopPct.toFixed(1)}%</span>.
          {" "}Current balance:{" "}
          <span className="font-semibold">£{balance.toFixed(2)}</span>.
        </p>
        <p className="text-[var(--red)] font-semibold text-sm mt-2">
          Do not place another bet today. Review your process.
        </p>
      </div>
      <button
        onClick={() => setDismissed(true)}
        aria-label="Dismiss stop-loss warning"
        className="shrink-0 text-[var(--text-muted)] hover:text-[var(--text)] transition-colors text-lg leading-none mt-0.5"
      >
        ✕
      </button>
    </div>
  );
}
