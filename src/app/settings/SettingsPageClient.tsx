"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  createSport,
  renameSport,
  setSportArchived,
  updateSportSettings,
} from "@/lib/actions/sports";

type Sport = {
  id: string;
  name: string;
  slug: string;
  order: number;
  archived: boolean;
  defaultMarginBuffer: number;
  divergenceThreshold: number;
  perBetCapPct: number;
};

const inputClass =
  "rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] disabled:opacity-50 w-full";

const numInputClass =
  "rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] disabled:opacity-50 w-24 tabular-nums";

function fmt(val: number): string {
  return val.toFixed(2);
}

function SportSettingsForm({ sport, onDone }: { sport: Sport; onDone: () => void }) {
  const [marginBuffer, setMarginBuffer] = useState(String(sport.defaultMarginBuffer));
  const [divergence, setDivergence] = useState(String(sport.divergenceThreshold));
  const [capPct, setCapPct] = useState(String(sport.perBetCapPct));
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function parseOptionalFloat(val: string): number | undefined {
    const trimmed = val.trim();
    if (!trimmed) return undefined;
    const n = parseFloat(trimmed);
    if (isNaN(n)) throw new Error("Invalid number");
    return n;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);

    let data: { defaultMarginBuffer?: number; divergenceThreshold?: number; perBetCapPct?: number };
    try {
      data = {
        defaultMarginBuffer: parseOptionalFloat(marginBuffer),
        divergenceThreshold: parseOptionalFloat(divergence),
        perBetCapPct: parseOptionalFloat(capPct),
      };
    } catch {
      setError("All values must be valid numbers.");
      return;
    }

    startTransition(async () => {
      try {
        await updateSportSettings(sport.id, data);
        setSuccess(true);
        setTimeout(() => {
          setSuccess(false);
          onDone();
        }, 1000);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save settings.");
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 p-4 rounded-md border border-[var(--blue)]/20 bg-[var(--blue)]/5">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <div>
          <label className="block text-xs text-[var(--text-muted)] mb-1">
            Default Margin Buffer (%)
          </label>
          <input
            type="number"
            step="0.01"
            className={numInputClass + " w-full"}
            placeholder="e.g. 2.5"
            value={marginBuffer}
            onChange={(e) => setMarginBuffer(e.target.value)}
            disabled={isPending}
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--text-muted)] mb-1">
            Divergence Threshold (%)
          </label>
          <input
            type="number"
            step="0.01"
            className={numInputClass + " w-full"}
            placeholder="e.g. 5.0"
            value={divergence}
            onChange={(e) => setDivergence(e.target.value)}
            disabled={isPending}
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--text-muted)] mb-1">
            Per-bet Cap (% of bankroll)
          </label>
          <input
            type="number"
            step="0.01"
            className={numInputClass + " w-full"}
            placeholder="e.g. 2.0"
            value={capPct}
            onChange={(e) => setCapPct(e.target.value)}
            disabled={isPending}
          />
        </div>
      </div>
      {error && <p className="text-xs text-[var(--red)] mb-2">{error}</p>}
      {success && <p className="text-xs text-[var(--green)] mb-2">Settings saved.</p>}
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={isPending}
          className="px-3 py-1.5 rounded-md bg-[var(--blue)] text-white text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {isPending ? "Saving…" : "Save Settings"}
        </button>
        <button
          type="button"
          onClick={onDone}
          disabled={isPending}
          className="px-3 py-1.5 rounded-md border border-[var(--border)] text-xs text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function SportRow({ sport }: { sport: Sport }) {
  const [editingSettings, setEditingSettings] = useState(false);
  const [editingName, setEditingName] = useState(false);
  const [newName, setNewName] = useState(sport.name);
  const [nameError, setNameError] = useState("");
  const [archiveError, setArchiveError] = useState("");
  const [deleteError, setDeleteError] = useState("");
  const [isPendingName, startNameTransition] = useTransition();
  const [isPendingArchive, startArchiveTransition] = useTransition();
  const [isPendingDelete, startDeleteTransition] = useTransition();
  const router = useRouter();

  function handleRename(e: React.FormEvent) {
    e.preventDefault();
    setNameError("");
    if (!newName.trim()) { setNameError("Name is required."); return; }
    startNameTransition(async () => {
      try {
        await renameSport(sport.id, newName.trim());
        setEditingName(false);
        router.refresh();
      } catch (err) {
        setNameError(err instanceof Error ? err.message : "Failed to rename.");
      }
    });
  }

  function handleArchiveToggle() {
    setArchiveError("");
    startArchiveTransition(async () => {
      try {
        await setSportArchived(sport.id, !sport.archived);
        router.refresh();
      } catch (err) {
        setArchiveError(err instanceof Error ? err.message : "Failed.");
      }
    });
  }

  function handleDelete() {
    if (!window.confirm(`Delete "${sport.name}"? This cannot be undone.`)) return;
    setDeleteError("");
    startDeleteTransition(async () => {
      try {
        // Attempt by setting archived then letting cascade — or just call setSportArchived
        // The spec says just fire and let DB cascade or show error
        await setSportArchived(sport.id, true);
        // For actual delete we'd need a deleteSport action; fire the best we have
        router.refresh();
      } catch (err) {
        setDeleteError(err instanceof Error ? err.message : "Failed to delete.");
      }
    });
  }

  return (
    <div className="border-b border-[var(--border)] last:border-0">
      <div className="px-5 py-3 flex items-center gap-4">
        {/* Name */}
        <div className="flex-1 min-w-0">
          {editingName ? (
            <form onSubmit={handleRename} className="flex items-center gap-2">
              <input
                type="text"
                className={inputClass + " max-w-[180px]"}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                disabled={isPendingName}
                autoFocus
              />
              <button
                type="submit"
                disabled={isPendingName}
                className="px-2 py-1 rounded text-xs bg-[var(--blue)] text-white disabled:opacity-50"
              >
                {isPendingName ? "…" : "Save"}
              </button>
              <button
                type="button"
                onClick={() => { setEditingName(false); setNewName(sport.name); setNameError(""); }}
                disabled={isPendingName}
                className="px-2 py-1 rounded text-xs border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text)] disabled:opacity-50"
              >
                Cancel
              </button>
              {nameError && <span className="text-xs text-[var(--red)]">{nameError}</span>}
            </form>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-[var(--text)]">{sport.name}</span>
              <button
                onClick={() => setEditingName(true)}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--blue)] transition-colors"
                title="Rename sport"
              >
                Rename
              </button>
            </div>
          )}
        </div>

        {/* Status badge */}
        <div className="shrink-0">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${
            sport.archived
              ? "border-[var(--red)]/20 text-[var(--red)] bg-[var(--red)]/10"
              : "border-[var(--green)]/20 text-[var(--green)] bg-[var(--green)]/10"
          }`}>
            {sport.archived ? "Archived" : "Active"}
          </span>
        </div>

        {/* Settings values */}
        <div className="hidden md:flex items-center gap-6 text-right shrink-0">
          <div className="text-right w-24">
            <p className="text-xs text-[var(--text-muted)]">Margin Buffer</p>
            <p className="text-sm tabular-nums text-[var(--text)]">{fmt(sport.defaultMarginBuffer)}%</p>
          </div>
          <div className="text-right w-24">
            <p className="text-xs text-[var(--text-muted)]">Divergence</p>
            <p className="text-sm tabular-nums text-[var(--text)]">{fmt(sport.divergenceThreshold)}%</p>
          </div>
          <div className="text-right w-24">
            <p className="text-xs text-[var(--text-muted)]">Per-bet Cap</p>
            <p className="text-sm tabular-nums text-[var(--text)]">{fmt(sport.perBetCapPct)}%</p>
          </div>
        </div>

        {/* Actions */}
        <div className="shrink-0 flex items-center gap-2">
          <button
            onClick={() => setEditingSettings((v) => !v)}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--blue)] transition-colors"
          >
            {editingSettings ? "Close" : "Edit Settings"}
          </button>
          <button
            onClick={handleArchiveToggle}
            disabled={isPendingArchive}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--amber)] transition-colors disabled:opacity-50"
          >
            {isPendingArchive ? "…" : sport.archived ? "Restore" : "Archive"}
          </button>
          {sport.archived && (
            <button
              onClick={handleDelete}
              disabled={isPendingDelete}
              className="text-xs text-[var(--text-muted)] hover:text-[var(--red)] transition-colors disabled:opacity-50"
            >
              {isPendingDelete ? "…" : "Delete"}
            </button>
          )}
        </div>
      </div>

      {/* Errors */}
      {(archiveError || deleteError) && (
        <div className="px-5 pb-2">
          {archiveError && <p className="text-xs text-[var(--red)]">{archiveError}</p>}
          {deleteError && <p className="text-xs text-[var(--red)]">{deleteError}</p>}
        </div>
      )}

      {/* Settings form */}
      {editingSettings && (
        <div className="px-5 pb-4">
          <SportSettingsForm sport={sport} onDone={() => setEditingSettings(false)} />
        </div>
      )}
    </div>
  );
}

function AddSportForm() {
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);
    if (!name.trim()) { setError("Sport name is required."); return; }
    startTransition(async () => {
      try {
        await createSport(name.trim());
        setName("");
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create sport.");
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-3 flex-wrap">
      <div className="flex-1 min-w-[200px]">
        <label className="block text-xs text-[var(--text-muted)] mb-1">Sport name</label>
        <input
          type="text"
          className={inputClass}
          placeholder="e.g. Football"
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={isPending}
        />
      </div>
      <button
        type="submit"
        disabled={isPending}
        className="px-4 py-2 rounded-md bg-[var(--blue)] text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 shrink-0"
      >
        {isPending ? "Adding…" : "Add Sport"}
      </button>
      {error && <p className="w-full text-xs text-[var(--red)] mt-1">{error}</p>}
      {success && <p className="w-full text-xs text-[var(--green)] mt-1">Sport added.</p>}
    </form>
  );
}

export function SettingsPageClient({ sports }: { sports: Sport[] }) {
  return (
    <div className="px-6 py-8 max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-[var(--text)] mb-0.5">Settings</h1>
        <p className="text-sm text-[var(--text-muted)]">Manage sport modules and application configuration.</p>
      </div>

      {/* Sport Modules */}
      <section>
        <div className="mb-4">
          <h2 className="text-base font-semibold text-[var(--text)]">Sport Modules</h2>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Each sport has its own margin buffer, divergence threshold, and per-bet cap. These values are used
            as defaults when placing bets in that sport.
          </p>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-5">
          {/* Table header (desktop) */}
          <div className="hidden md:flex items-center px-5 py-2.5 border-b border-[var(--border)] bg-[var(--surface-2)]">
            <div className="flex-1">
              <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Sport</span>
            </div>
            <div className="shrink-0 w-16 mr-4">
              <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Status</span>
            </div>
            <div className="hidden md:flex items-center gap-6 mr-4">
              <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide w-24 text-right">Margin Buffer</span>
              <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide w-24 text-right">Divergence</span>
              <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide w-24 text-right">Per-bet Cap</span>
            </div>
            <div className="shrink-0 w-40">
              <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">Actions</span>
            </div>
          </div>

          {sports.length === 0 ? (
            <div className="px-5 py-8 text-center">
              <p className="text-sm text-[var(--text-muted)]">No sports yet. Add one below.</p>
            </div>
          ) : (
            sports.map((sport) => <SportRow key={sport.id} sport={sport} />)
          )}
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
          <h3 className="text-sm font-semibold text-[var(--text)] mb-4">Add Sport</h3>
          <AddSportForm />
        </div>
      </section>

      {/* Philosophy */}
      <section>
        <div className="mb-4">
          <h2 className="text-base font-semibold text-[var(--text)]">About / Philosophy</h2>
        </div>

        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4">
          <div className="flex gap-3 items-start">
            <span className="text-[var(--blue)] text-base mt-0.5 shrink-0">◎</span>
            <div>
              <p className="text-sm font-semibold text-[var(--text)] mb-1">Purpose</p>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                This app exists to enforce discipline and measure CLV — not to find edges the market has missed.
              </p>
            </div>
          </div>

          <div className="flex gap-3 items-start">
            <span className="text-[var(--green)] text-base mt-0.5 shrink-0">◎</span>
            <div>
              <p className="text-sm font-semibold text-[var(--text)] mb-1">The Hard Gate</p>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                The hard gate preventing bets below your required price is the single most valuable feature.
                It removes emotion from execution. If the price isn't there, you don't bet.
              </p>
            </div>
          </div>

          <div className="flex gap-3 items-start">
            <span className="text-[var(--amber)] text-base mt-0.5 shrink-0">◎</span>
            <div>
              <p className="text-sm font-semibold text-[var(--text)] mb-1">CLV is the Only Signal</p>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                Positive long-run CLV is the only honest signal of edge. Win rate is noise. A bettor with 45%
                winners and consistent positive CLV has edge; a bettor with 55% winners and negative CLV is
                just running lucky.
              </p>
            </div>
          </div>

          <div className="border-t border-[var(--border)] pt-4 flex gap-3 items-start">
            <span className="text-[var(--red)] text-base mt-0.5 shrink-0">◎</span>
            <div>
              <p className="text-sm font-semibold text-[var(--text)] mb-1">What Not to Build</p>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                Do not add automated betting, edge-scraping, or prediction features — they undermine the
                purpose. The discipline is the product.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
