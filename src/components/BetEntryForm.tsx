"use client";

import { useState, useMemo, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createBet } from "@/lib/actions/bets";
import {
  fairPrice,
  requiredPrice,
  qualifies,
  quarterKellyStake,
  divergencePoints,
} from "@/lib/calc";
import { detectTiltFlags } from "@/lib/tilt";
import type { RecentBetForTilt } from "@/lib/tilt";

interface Props {
  sportId: string;
  sportSlug: string;
  defaultMarginBuffer: number;
  divergenceThreshold: number;
  capPct: number;
  bankrollBalance: number;
  kellyDivisor: number;
  recentBets: RecentBetForTilt[];
}

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals);
}

export function BetEntryForm({
  sportId,
  sportSlug,
  defaultMarginBuffer,
  divergenceThreshold,
  capPct,
  bankrollBalance,
  kellyDivisor,
  recentBets,
}: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Bet identification
  const [event, setEvent] = useState("");
  const [market, setMarket] = useState("");
  const [eventDate, setEventDate] = useState("");

  // Probability & pricing
  const [myProbability, setMyProbability] = useState("");
  const [marginBuffer, setMarginBuffer] = useState(String(defaultMarginBuffer));
  const [availablePrice, setAvailablePrice] = useState("");

  // Staking
  const [kellyDiv, setKellyDiv] = useState(String(kellyDivisor));
  const [capPctVal, setCapPctVal] = useState(String(capPct));
  const [stakeOverride, setStakeOverride] = useState("");

  // Divergence
  const [divJustification, setDivJustification] = useState("");

  // Checklist
  const [checklistPrice, setChecklistPrice] = useState(false);
  const [checklistLiquid, setChecklistLiquid] = useState(false);
  const [checklistNotChasing, setChecklistNotChasing] = useState(false);

  // Placed
  const [placed, setPlaced] = useState(false);

  // Notes
  const [notes, setNotes] = useState("");

  // Error
  const [error, setError] = useState<string | null>(null);

  // Live calculations
  const probNum = parseFloat(myProbability) || 0;
  const bufferNum = parseFloat(marginBuffer) || 0;
  const priceNum = parseFloat(availablePrice) || 0;
  const kellyDivNum = parseFloat(kellyDiv) || 4;
  const capNum = parseFloat(capPctVal) || 2;

  const fair = useMemo(() => (probNum > 0 ? fairPrice(probNum) : null), [probNum]);
  const required = useMemo(
    () => (fair !== null ? requiredPrice(fair, bufferNum) : null),
    [fair, bufferNum],
  );
  const priceQualifies = useMemo(
    () => (required !== null && priceNum > 0 ? qualifies(priceNum, required) : null),
    [priceNum, required],
  );
  const divPoints = useMemo(
    () => (probNum > 0 && priceNum > 0 ? divergencePoints(probNum, priceNum) : null),
    [probNum, priceNum],
  );
  const divFlagged = useMemo(
    () => divPoints !== null && Math.abs(divPoints) > divergenceThreshold,
    [divPoints, divergenceThreshold],
  );

  const stakeCalc = useMemo(() => {
    if (probNum > 0 && priceNum > 0 && bankrollBalance > 0) {
      return quarterKellyStake(bankrollBalance, probNum, priceNum, kellyDivNum, capNum);
    }
    return null;
  }, [probNum, priceNum, bankrollBalance, kellyDivNum, capNum]);

  const candidateStake = stakeOverride
    ? parseFloat(stakeOverride) || 0
    : stakeCalc?.suggestedStake ?? 0;

  const tiltFlags = useMemo(
    () => detectTiltFlags(recentBets, candidateStake, market),
    [recentBets, candidateStake, market],
  );

  const checklistComplete = checklistPrice && checklistLiquid && checklistNotChasing;
  const canPlace = checklistComplete && priceQualifies === true;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    startTransition(async () => {
      try {
        await createBet({
          sportId,
          eventDate: eventDate ? new Date(eventDate).toISOString() : new Date().toISOString(),
          event,
          market,
          myProbability: probNum,
          marginBuffer: bufferNum,
          availablePrice: priceNum,
          kellyDivisor: kellyDivNum,
          capPct: capNum,
          checklistPriceMet: checklistPrice,
          checklistLiquidMarket: checklistLiquid,
          checklistNotChasing: checklistNotChasing,
          divergenceJustification: divJustification || undefined,
          placedIntent: placed,
          stakeOverride: stakeOverride ? parseFloat(stakeOverride) : undefined,
          notes: notes || undefined,
        });

        // Reset form
        setEvent("");
        setMarket("");
        setEventDate("");
        setMyProbability("");
        setMarginBuffer(String(defaultMarginBuffer));
        setAvailablePrice("");
        setKellyDiv(String(kellyDivisor));
        setCapPctVal(String(capPct));
        setStakeOverride("");
        setDivJustification("");
        setChecklistPrice(false);
        setChecklistLiquid(false);
        setChecklistNotChasing(false);
        setPlaced(false);
        setNotes("");

        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "An unexpected error occurred.");
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-0">
      {/* Tilt Warning Banners */}
      {tiltFlags.messages.length > 0 && (
        <div className="mb-6 space-y-2">
          {tiltFlags.messages.map((msg, i) => (
            <div
              key={i}
              className="flex gap-3 items-start rounded-lg border border-[var(--red)]/40 bg-[var(--red)]/8 px-4 py-3"
            >
              <span className="text-[var(--red)] text-lg leading-none shrink-0">⚠</span>
              <p className="text-sm text-[var(--text)] leading-snug">{msg}</p>
            </div>
          ))}
        </div>
      )}

      {/* Section: Bet Identification */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-4">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">
            Bet Identification
          </h2>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Event
            </label>
            <input
              type="text"
              value={event}
              onChange={(e) => setEvent(e.target.value)}
              placeholder="e.g. Arsenal vs Chelsea"
              required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Market
              </label>
              <input
                type="text"
                value={market}
                onChange={(e) => setMarket(e.target.value)}
                placeholder="e.g. Match Odds"
                required
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Event Date
              </label>
              <input
                type="date"
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
                required
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--blue)] focus:outline-none transition-colors"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Section: Probability & Pricing */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-4">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">
            Probability &amp; Pricing
          </h2>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                My Probability (%)
              </label>
              <input
                type="number"
                value={myProbability}
                onChange={(e) => setMyProbability(e.target.value)}
                placeholder="e.g. 55"
                min="0.01"
                max="99.99"
                step="0.01"
                required
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Margin Buffer (decimal odds)
              </label>
              <input
                type="number"
                value={marginBuffer}
                onChange={(e) => setMarginBuffer(e.target.value)}
                placeholder="e.g. 0.05"
                step="0.01"
                min="0"
                required
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors font-mono"
              />
            </div>
          </div>

          {/* Computed: Fair Price + Required Price */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5">
              <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium mb-0.5">
                Fair Price
              </p>
              <p className="text-base font-mono font-semibold text-[var(--text)]">
                {fair !== null ? fmt(fair, 3) : "—"}
              </p>
            </div>
            <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5">
              <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium mb-0.5">
                Required +EV Price
              </p>
              <p className="text-base font-mono font-semibold text-[var(--text)]">
                {required !== null ? fmt(required, 3) : "—"}
              </p>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Betfair Price Available
            </label>
            <input
              type="number"
              value={availablePrice}
              onChange={(e) => setAvailablePrice(e.target.value)}
              placeholder="e.g. 1.95"
              step="0.01"
              min="1.01"
              required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors font-mono"
            />
          </div>

          {/* Qualifies indicator */}
          {priceQualifies !== null && (
            <div
              className={`flex items-center gap-3 rounded-md px-4 py-3 border ${
                priceQualifies
                  ? "border-[var(--green)]/40 bg-[var(--green)]/8"
                  : "border-[var(--red)]/40 bg-[var(--red)]/8"
              }`}
            >
              <span
                className={`text-2xl leading-none ${priceQualifies ? "text-[var(--green)]" : "text-[var(--red)]"}`}
              >
                {priceQualifies ? "✓" : "✗"}
              </span>
              <div>
                <p
                  className={`text-sm font-semibold ${priceQualifies ? "text-[var(--green)]" : "text-[var(--red)]"}`}
                >
                  {priceQualifies ? "Price qualifies" : "Price does not qualify"}
                </p>
                <p className="text-xs text-[var(--text-muted)] font-mono">
                  Available {fmt(priceNum, 3)} vs required {required !== null ? fmt(required, 3) : "—"}
                </p>
              </div>
            </div>
          )}

          {/* Divergence meter */}
          {divPoints !== null && (
            <div
              className={`rounded-md border px-4 py-3 ${
                divFlagged
                  ? "border-[var(--amber)]/60 bg-[var(--amber)]/8"
                  : "border-[var(--border)] bg-[var(--bg)]"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium">
                  Divergence from market
                </p>
                <span
                  className={`text-sm font-mono font-bold ${
                    divFlagged
                      ? "text-[var(--amber)]"
                      : Math.abs(divPoints) > 0
                        ? "text-[var(--text)]"
                        : "text-[var(--text-muted)]"
                  }`}
                >
                  {divPoints > 0 ? "+" : ""}{fmt(divPoints, 1)} pts
                </span>
              </div>
              {divFlagged && (
                <p className="text-xs text-[var(--amber)]">
                  Divergence exceeds your {divergenceThreshold}-point threshold. Justification
                  required below.
                </p>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Section: Divergence Justification (only when flagged) */}
      {divFlagged && (
        <section className="rounded-lg border-2 border-[var(--amber)]/60 bg-[var(--amber)]/5 overflow-hidden mb-4">
          <div className="px-5 py-3 border-b border-[var(--amber)]/30">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--amber)]">
              ⚠ Divergence Justification Required
            </h2>
          </div>
          <div className="px-5 py-4">
            <p className="text-xs text-[var(--text-muted)] mb-3 leading-relaxed">
              Your probability is significantly different from the market implied probability.
              On a liquid market, this most often means your model is wrong. Explain why you
              believe you have an edge here despite the divergence.
            </p>
            <textarea
              value={divJustification}
              onChange={(e) => setDivJustification(e.target.value)}
              placeholder="Explain the divergence — e.g. injury news not priced in, model accounts for pace data the market hasn't reacted to, line movement in your favour..."
              rows={3}
              required={divFlagged}
              className="w-full rounded-md border border-[var(--amber)]/40 bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--amber)] focus:outline-none transition-colors resize-none"
            />
          </div>
        </section>
      )}

      {/* Section: Staking */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-4">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">
            Staking
          </h2>
        </div>
        <div className="px-5 py-4 space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Kelly Divisor
              </label>
              <input
                type="number"
                value={kellyDiv}
                onChange={(e) => setKellyDiv(e.target.value)}
                min="1"
                step="0.5"
                required
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--blue)] focus:outline-none transition-colors font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Per-bet Cap (%)
              </label>
              <input
                type="number"
                value={capPctVal}
                onChange={(e) => setCapPctVal(e.target.value)}
                min="0.1"
                step="0.1"
                required
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--blue)] focus:outline-none transition-colors font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Bankroll
              </label>
              <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] font-mono">
                £{bankrollBalance.toFixed(2)}
              </div>
            </div>
          </div>

          {/* Suggested stake display */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5">
              <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium mb-0.5">
                Suggested Stake
              </p>
              <p className="text-base font-mono font-bold text-[var(--text)]">
                {stakeCalc !== null ? `£${fmt(stakeCalc.suggestedStake)}` : "—"}
              </p>
              {stakeCalc?.capApplied && (
                <p className="text-[10px] text-[var(--amber)] mt-0.5">Cap applied</p>
              )}
            </div>
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Stake Override (optional)
              </label>
              <input
                type="number"
                value={stakeOverride}
                onChange={(e) => setStakeOverride(e.target.value)}
                placeholder={stakeCalc ? fmt(stakeCalc.suggestedStake) : "0.00"}
                min="0"
                step="0.01"
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors font-mono"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Section: Pre-bet Checklist */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-4">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">
            Pre-bet Checklist
          </h2>
        </div>
        <div className="px-5 py-4 space-y-3">
          <ChecklistItem
            checked={checklistPrice}
            onChange={setChecklistPrice}
            label="The available price meets my required price"
            description="Confirm you are only placing this bet because the price qualifies, not because you want to bet."
          />
          <ChecklistItem
            checked={checklistLiquid}
            onChange={setChecklistLiquid}
            label="This is a liquid market where I am unlikely to have a structural edge"
            description="Liquid markets efficiently incorporate information. Your edge must come from your probability model being better calibrated, not from information asymmetry."
          />
          <ChecklistItem
            checked={checklistNotChasing}
            onChange={setChecklistNotChasing}
            label="I am not chasing a previous loss"
            description="This bet is motivated by edge, not by wanting to recover losses from a prior position."
          />
        </div>
      </section>

      {/* Section: Placed toggle */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-4">
        <div className="px-5 py-4">
          <div className="flex items-start gap-4">
            <button
              type="button"
              onClick={() => {
                if (!canPlace && !placed) return;
                setPlaced(!placed);
              }}
              disabled={!canPlace && !placed}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 transition-colors ${
                placed
                  ? "border-[var(--green)] bg-[var(--green)]"
                  : canPlace
                    ? "border-[var(--border)] bg-[var(--surface-2)]"
                    : "border-[var(--border)] bg-[var(--surface-2)] opacity-40 cursor-not-allowed"
              }`}
              aria-label="Mark as placed"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                  placed ? "translate-x-5" : "translate-x-0.5"
                }`}
              />
            </button>
            <div>
              <p className="text-sm font-medium text-[var(--text)]">Mark as Placed</p>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                {canPlace
                  ? "All checklist items confirmed and price qualifies. Toggle to mark this bet as placed."
                  : "Complete the checklist and ensure price qualifies to enable."}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section: Notes */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-4">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">
            Notes (optional)
          </h2>
        </div>
        <div className="px-5 py-4">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Any additional context, model reasoning, or observations..."
            rows={3}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors resize-none"
          />
        </div>
      </section>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-[var(--red)]/40 bg-[var(--red)]/8 px-4 py-3 mb-4">
          <p className="text-sm text-[var(--red)]">{error}</p>
        </div>
      )}

      {/* Submit */}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={isPending}
          className="px-6 py-2.5 rounded-md bg-[var(--blue)] text-white text-sm font-semibold hover:bg-[var(--blue)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isPending ? "Saving…" : placed ? "Save Bet (Placed)" : "Save Bet (Not Placed)"}
        </button>
      </div>
    </form>
  );
}

function ChecklistItem({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (val: boolean) => void;
  label: string;
  description: string;
}) {
  return (
    <label
      className={`flex items-start gap-3 rounded-md border px-4 py-3 cursor-pointer transition-colors ${
        checked
          ? "border-[var(--green)]/40 bg-[var(--green)]/5"
          : "border-[var(--border)] bg-[var(--bg)] hover:border-[var(--border)]"
      }`}
    >
      <div
        className={`mt-0.5 h-4 w-4 shrink-0 rounded border-2 flex items-center justify-center transition-colors ${
          checked ? "border-[var(--green)] bg-[var(--green)]" : "border-[var(--border)]"
        }`}
      >
        {checked && (
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path
              d="M1 4L3.5 6.5L9 1"
              stroke="white"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="sr-only"
      />
      <div>
        <p className="text-sm font-medium text-[var(--text)]">{label}</p>
        <p className="text-xs text-[var(--text-muted)] mt-0.5 leading-relaxed">{description}</p>
      </div>
    </label>
  );
}
