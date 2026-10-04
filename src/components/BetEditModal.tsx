"use client";

import { useState, useMemo, useTransition, useEffect } from "react";
import { useRouter } from "next/navigation";
import { updateBet } from "@/lib/actions/bets";
import {
  fairPrice,
  requiredPrice,
  qualifies,
  quarterKellyStake,
  divergencePoints,
} from "@/lib/calc";
import type { BetComputed } from "@/lib/betView";

interface Props {
  bet: BetComputed;
  sportSlug: string;
  divergenceThreshold: number;
  bankrollBalance: number;
  onClose: () => void;
}

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals);
}

function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-[10px] text-[var(--text-muted)] mt-1">{hint}</p>}
    </div>
  );
}

const inputCls =
  "w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors";
const monoInputCls = inputCls + " font-mono";

function CheckCard({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label
      className={`flex items-center gap-3 rounded-md border px-3 py-2.5 cursor-pointer transition-colors ${
        checked ? "border-[var(--green)]/40 bg-[var(--green)]/5" : "border-[var(--border)] bg-[var(--bg)]"
      }`}
    >
      <div
        className={`h-4 w-4 shrink-0 rounded border-2 flex items-center justify-center transition-colors ${
          checked ? "border-[var(--green)] bg-[var(--green)]" : "border-[var(--border)]"
        }`}
      >
        {checked && (
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="sr-only" />
      <span className="text-sm text-[var(--text)]">{label}</span>
    </label>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <div className="px-5 py-2.5 border-b border-[var(--border)] bg-[var(--surface-2)]">
      <h3 className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-muted)]">
        {title}
      </h3>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
      <SectionHeader title={title} />
      <div className="px-5 py-4 space-y-4">{children}</div>
    </div>
  );
}

export function BetEditModal({ bet, sportSlug, divergenceThreshold, bankrollBalance, onClose }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  // Bet identification
  const [event, setEvent] = useState(bet.event);
  const [market, setMarket] = useState(bet.market);
  const [eventDate, setEventDate] = useState(
    new Date(bet.eventDate).toISOString().split("T")[0],
  );

  // Probability & pricing
  const [myProbability, setMyProbability] = useState(String(bet.myProbability));
  const [noVigProb, setNoVigProb] = useState(
    bet.noVigProb != null ? String(bet.noVigProb) : "",
  );
  const [marginBuffer, setMarginBuffer] = useState(String(bet.marginBuffer));
  const [availablePrice, setAvailablePrice] = useState(String(bet.availablePrice));

  // Staking
  const [kellyDiv, setKellyDiv] = useState(String(bet.kellyDivisor));
  const [capPct, setCapPct] = useState(String(bet.capPct));
  const [stakeOverride, setStakeOverride] = useState(
    bet.placed && bet.stake > 0 ? String(bet.stake) : "",
  );

  // Checklist
  const [checklistPrice, setChecklistPrice] = useState(bet.checklistPriceMet);
  const [checklistLiquid, setChecklistLiquid] = useState(bet.checklistLiquidMarket);
  const [checklistNotChasing, setChecklistNotChasing] = useState(bet.checklistNotChasing);

  // Divergence
  const [divJustification, setDivJustification] = useState(bet.divergenceJustification ?? "");

  // Placed
  const [placed, setPlaced] = useState(bet.placed);

  // Settlement
  const [closingPrice, setClosingPrice] = useState(
    bet.closingPrice != null ? String(bet.closingPrice) : "",
  );
  const [result, setResult] = useState<"PENDING" | "WIN" | "LOSS" | "VOID">(
    (bet.result ?? "PENDING") as "PENDING" | "WIN" | "LOSS" | "VOID",
  );

  // Notes
  const [notes, setNotes] = useState(bet.notes ?? "");

  // Close on Escape
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Live calcs
  const probNum = parseFloat(myProbability) || 0;
  const bufferNum = parseFloat(marginBuffer) || 0;
  const priceNum = parseFloat(availablePrice) || 0;
  const kellyDivNum = parseFloat(kellyDiv) || 4;
  const capNum = parseFloat(capPct) || 2;

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

  const noVigNum = parseFloat(noVigProb) || null;
  const edgeEstimate = noVigNum !== null && priceNum > 0 ? noVigNum - 100 / priceNum : null;

  const checklistComplete = checklistPrice && checklistLiquid && checklistNotChasing;
  const canPlace = checklistComplete && priceQualifies === true;

  async function handleSave() {
    setError(null);
    startTransition(async () => {
      try {
        await updateBet(bet.id, {
          eventDate: eventDate ? new Date(eventDate).toISOString() : undefined,
          event,
          market,
          myProbability: probNum || undefined,
          noVigProb: noVigProb ? parseFloat(noVigProb) : null,
          marginBuffer: bufferNum,
          availablePrice: priceNum || undefined,
          kellyDivisor: kellyDivNum,
          capPct: capNum,
          stakeOverride: stakeOverride ? parseFloat(stakeOverride) : undefined,
          checklistPriceMet: checklistPrice,
          checklistLiquidMarket: checklistLiquid,
          checklistNotChasing,
          divergenceJustification: divFlagged ? divJustification || null : null,
          placed,
          closingPrice: closingPrice ? parseFloat(closingPrice) : null,
          result,
          notes: notes || null,
        });
        router.refresh();
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save changes.");
      }
    });
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-end"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Panel */}
      <div className="relative z-10 h-full w-full max-w-xl bg-[var(--bg)] border-l border-[var(--border)] overflow-y-auto flex flex-col">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between px-5 py-4 border-b border-[var(--border)] bg-[var(--bg)]">
          <div>
            <h2 className="text-sm font-semibold text-[var(--text)]">Edit Bet</h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5 truncate max-w-[280px]">{bet.event}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M2 2L14 14M14 2L2 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <div className="flex-1 px-5 py-5 space-y-4">
          {/* Bet Identification */}
          <Section title="Bet Identification">
            <Field label="Event">
              <input type="text" value={event} onChange={(e) => setEvent(e.target.value)} className={inputCls} />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Market">
                <input type="text" value={market} onChange={(e) => setMarket(e.target.value)} className={inputCls} />
              </Field>
              <Field label="Event Date">
                <input type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} className={inputCls} />
              </Field>
            </div>
          </Section>

          {/* Probability & Pricing */}
          <Section title="Probability & Pricing">
            <div className="grid grid-cols-2 gap-4">
              <Field label="My Probability (%)">
                <input
                  type="number"
                  value={myProbability}
                  onChange={(e) => setMyProbability(e.target.value)}
                  min="0.01"
                  max="99.99"
                  step="0.01"
                  className={monoInputCls}
                />
              </Field>
              <Field label="No-Vig Probability (%) — optional">
                <input
                  type="number"
                  value={noVigProb}
                  onChange={(e) => setNoVigProb(e.target.value)}
                  placeholder="de-vigged true prob"
                  min="0.01"
                  max="99.99"
                  step="0.01"
                  className={monoInputCls}
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Margin Buffer (decimal odds)">
                <input
                  type="number"
                  value={marginBuffer}
                  onChange={(e) => setMarginBuffer(e.target.value)}
                  step="0.01"
                  min="0"
                  className={monoInputCls}
                />
              </Field>
              <Field label="Betfair Price Available">
                <input
                  type="number"
                  value={availablePrice}
                  onChange={(e) => setAvailablePrice(e.target.value)}
                  step="0.01"
                  min="1.01"
                  className={monoInputCls}
                />
              </Field>
            </div>

            {/* Computed display */}
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium mb-0.5">Fair</p>
                <p className="text-sm font-mono font-semibold text-[var(--text)]">
                  {fair !== null ? fmt(fair, 3) : "—"}
                </p>
              </div>
              <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
                <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium mb-0.5">Required</p>
                <p className="text-sm font-mono font-semibold text-[var(--text)]">
                  {required !== null ? fmt(required, 3) : "—"}
                </p>
              </div>
              {edgeEstimate !== null ? (
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium mb-0.5">Edge Est.</p>
                  <p className={`text-sm font-mono font-bold ${edgeEstimate > 0 ? "text-[var(--green)]" : "text-[var(--red)]"}`}>
                    {edgeEstimate > 0 ? "+" : ""}{fmt(edgeEstimate, 2)}%
                  </p>
                </div>
              ) : (
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium mb-0.5">Qualifies</p>
                  <p className={`text-sm font-bold ${priceQualifies === true ? "text-[var(--green)]" : priceQualifies === false ? "text-[var(--red)]" : "text-[var(--text-muted)]"}`}>
                    {priceQualifies === true ? "✓ Yes" : priceQualifies === false ? "✗ No" : "—"}
                  </p>
                </div>
              )}
            </div>

            {/* Divergence */}
            {divPoints !== null && (
              <div className={`rounded-md border px-3 py-2.5 ${divFlagged ? "border-[var(--amber)]/60 bg-[var(--amber)]/8" : "border-[var(--border)] bg-[var(--bg)]"}`}>
                <div className="flex items-center justify-between">
                  <p className="text-[10px] uppercase tracking-wide text-[var(--text-muted)] font-medium">Divergence</p>
                  <span className={`text-sm font-mono font-bold ${divFlagged ? "text-[var(--amber)]" : "text-[var(--text)]"}`}>
                    {divPoints > 0 ? "+" : ""}{fmt(divPoints, 1)} pts
                  </span>
                </div>
                {divFlagged && (
                  <p className="text-xs text-[var(--amber)] mt-1">Exceeds {divergenceThreshold}-pt threshold — justification required.</p>
                )}
              </div>
            )}
          </Section>

          {/* Divergence Justification */}
          {divFlagged && (
            <div className="rounded-lg border-2 border-[var(--amber)]/60 bg-[var(--amber)]/5 overflow-hidden">
              <div className="px-5 py-2.5 border-b border-[var(--amber)]/30">
                <h3 className="text-[10px] font-semibold uppercase tracking-widest text-[var(--amber)]">
                  ⚠ Divergence Justification
                </h3>
              </div>
              <div className="px-5 py-4">
                <textarea
                  value={divJustification}
                  onChange={(e) => setDivJustification(e.target.value)}
                  placeholder="Explain the divergence..."
                  rows={3}
                  className="w-full rounded-md border border-[var(--amber)]/40 bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--amber)] focus:outline-none resize-none"
                />
              </div>
            </div>
          )}

          {/* Staking */}
          <Section title="Staking">
            <div className="grid grid-cols-3 gap-3">
              <Field label="Kelly Divisor">
                <input type="number" value={kellyDiv} onChange={(e) => setKellyDiv(e.target.value)} min="1" step="0.5" className={monoInputCls} />
              </Field>
              <Field label="Per-bet Cap (%)">
                <input type="number" value={capPct} onChange={(e) => setCapPct(e.target.value)} min="0.1" step="0.1" className={monoInputCls} />
              </Field>
              <div>
                <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">Suggested</label>
                <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm font-mono text-[var(--text)]">
                  {stakeCalc ? `£${fmt(stakeCalc.suggestedStake)}` : "—"}
                  {stakeCalc?.capApplied && <span className="text-[10px] text-[var(--amber)] block">Cap applied</span>}
                </div>
              </div>
            </div>
            <Field label="Actual Stake (£)" hint="Enter the stake actually placed">
              <input
                type="number"
                value={stakeOverride}
                onChange={(e) => setStakeOverride(e.target.value)}
                placeholder={stakeCalc ? fmt(stakeCalc.suggestedStake) : "0.00"}
                min="0"
                step="0.01"
                className={monoInputCls}
              />
            </Field>
          </Section>

          {/* Checklist */}
          <Section title="Pre-bet Checklist">
            <CheckCard checked={checklistPrice} onChange={setChecklistPrice} label="Price meets required +EV price" />
            <CheckCard checked={checklistLiquid} onChange={setChecklistLiquid} label="Liquid market — edge is from model, not info asymmetry" />
            <CheckCard checked={checklistNotChasing} onChange={setChecklistNotChasing} label="Not chasing a loss" />
          </Section>

          {/* Placed toggle */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-4">
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => { if (canPlace || placed) setPlaced(!placed); }}
                disabled={!canPlace && !placed}
                className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 transition-colors ${
                  placed
                    ? "border-[var(--green)] bg-[var(--green)]"
                    : canPlace
                      ? "border-[var(--border)] bg-[var(--surface-2)]"
                      : "border-[var(--border)] bg-[var(--surface-2)] opacity-40 cursor-not-allowed"
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${placed ? "translate-x-5" : "translate-x-0.5"}`} />
              </button>
              <div>
                <p className="text-sm font-medium text-[var(--text)]">Marked as Placed</p>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  {canPlace ? "Checklist complete and price qualifies." : "Complete checklist and ensure price qualifies."}
                </p>
              </div>
            </div>
          </div>

          {/* Settlement */}
          <Section title="Settlement">
            <div className="grid grid-cols-2 gap-4">
              <Field label="Closing Price">
                <input
                  type="number"
                  value={closingPrice}
                  onChange={(e) => setClosingPrice(e.target.value)}
                  placeholder="e.g. 1.85"
                  step="0.001"
                  min="1.01"
                  className={monoInputCls}
                />
              </Field>
              <Field label="Result">
                <select
                  value={result}
                  onChange={(e) => setResult(e.target.value as typeof result)}
                  className={inputCls}
                >
                  <option value="PENDING">PENDING</option>
                  <option value="WIN">WIN</option>
                  <option value="LOSS">LOSS</option>
                  <option value="VOID">VOID</option>
                </select>
              </Field>
            </div>
          </Section>

          {/* Notes */}
          <Section title="Notes">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any additional context, reasoning, or observations..."
              rows={3}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none resize-none"
            />
          </Section>

          {/* Error */}
          {error && (
            <div className="rounded-md border border-[var(--red)]/40 bg-[var(--red)]/8 px-4 py-3">
              <p className="text-sm text-[var(--red)]">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 border-t border-[var(--border)] bg-[var(--bg)] px-5 py-4 flex gap-3">
          <button
            onClick={handleSave}
            disabled={isPending}
            className="flex-1 py-2.5 rounded-md bg-[var(--blue)] text-white text-sm font-semibold hover:bg-[var(--blue)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isPending ? "Saving…" : "Save Changes"}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2.5 rounded-md border border-[var(--border)] text-sm text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
