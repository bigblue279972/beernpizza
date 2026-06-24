import { getSports } from "@/lib/actions/sports";
import Link from "next/link";

export default async function SportsPage() {
  const sports = await getSports();

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text)] mb-1">Sport Modules</h1>
          <p className="text-sm text-[var(--text-muted)] max-w-xl">
            Each sport module tracks your edge discipline independently — bet entry with live
            Kelly sizing, a full CLV sheet, and lessons learned from every position.
          </p>
        </div>
        <Link
          href="/settings"
          className="shrink-0 text-sm text-[var(--blue)] hover:underline mt-0.5"
        >
          Manage sports
        </Link>
      </div>

      {sports.length === 0 ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-6 py-10 text-center">
          <p className="text-[var(--text-muted)] text-sm mb-2">No sport modules yet.</p>
          <p className="text-xs text-[var(--text-muted)]">
            Add a sport in{" "}
            <Link href="/settings" className="text-[var(--blue)] hover:underline">
              Settings
            </Link>{" "}
            to start tracking your CLV discipline.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sports.map((sport) => (
            <Link
              key={sport.id}
              href={`/sports/${sport.slug}`}
              className="group block rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-4 hover:border-[var(--blue)]/50 hover:bg-[var(--surface-2)] transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <span className="text-base font-semibold text-[var(--text)] group-hover:text-[var(--blue)] transition-colors">
                  {sport.name}
                </span>
                <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-[var(--green)]/10 text-[var(--green)] border border-[var(--green)]/20">
                  Active
                </span>
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-[var(--text-muted)]">Margin buffer</span>
                  <span className="text-[var(--text)] font-mono">
                    +{sport.defaultMarginBuffer.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-[var(--text-muted)]">Divergence threshold</span>
                  <span className="text-[var(--text)] font-mono">
                    {sport.divergenceThreshold.toFixed(1)} pts
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-[var(--text-muted)]">Per-bet cap</span>
                  <span className="text-[var(--text)] font-mono">
                    {sport.perBetCapPct.toFixed(1)}%
                  </span>
                </div>
              </div>
              <div className="mt-4 flex gap-2 text-[10px] font-medium text-[var(--text-muted)] uppercase tracking-wide">
                <span>Entry</span>
                <span>·</span>
                <span>Sheet</span>
                <span>·</span>
                <span>Lessons</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="mt-8 rounded-lg border border-[var(--border)]/60 bg-[var(--surface)] px-5 py-4">
        <p className="text-xs text-[var(--text-muted)] leading-relaxed">
          <span className="text-[var(--text)] font-medium">Entry</span> — enter bets with live
          Kelly sizing, tilt detection, and pre-bet checklists.{" "}
          <span className="text-[var(--text)] font-medium">Sheet</span> — review your full
          position history with CLV, P&amp;L, and settle open bets.{" "}
          <span className="text-[var(--text)] font-medium">Lessons</span> — record and search
          observations tied to individual bets and markets.
        </p>
      </div>
    </div>
  );
}
