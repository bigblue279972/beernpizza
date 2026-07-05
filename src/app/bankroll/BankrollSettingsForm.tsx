"use client";

import { useActionState } from "react";
import { useRouter } from "next/navigation";
import { updateBankrollSettings } from "@/lib/actions/bankroll";

interface Settings {
  id: string;
  startingBalance: number;
  currentBalance: number;
  hardStopLossPct: number;
  hardStopLossAmount: number | null;
  defaultKellyDivisor: number;
  globalPerBetCapPct: number;
}

interface FormState {
  error?: string;
  success?: boolean;
}

async function settingsAction(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  try {
    const hardStopLossPct = parseFloat(formData.get("hardStopLossPct") as string);
    const hardStopLossAmountRaw = (formData.get("hardStopLossAmount") as string).trim();
    const defaultKellyDivisor = parseFloat(formData.get("defaultKellyDivisor") as string);
    const globalPerBetCapPct = parseFloat(formData.get("globalPerBetCapPct") as string);

    if (isNaN(hardStopLossPct) || hardStopLossPct <= 0 || hardStopLossPct > 100) {
      return { error: "Hard stop loss % must be between 0 and 100." };
    }
    if (isNaN(defaultKellyDivisor) || defaultKellyDivisor <= 0) {
      return { error: "Kelly divisor must be a positive number." };
    }
    if (isNaN(globalPerBetCapPct) || globalPerBetCapPct <= 0 || globalPerBetCapPct > 100) {
      return { error: "Per-bet cap % must be between 0 and 100." };
    }

    const hardStopLossAmount =
      hardStopLossAmountRaw === "" ? null : parseFloat(hardStopLossAmountRaw);
    if (
      hardStopLossAmount !== null &&
      (isNaN(hardStopLossAmount) || hardStopLossAmount < 0)
    ) {
      return { error: "Hard stop loss floor must be a positive number or blank." };
    }

    await updateBankrollSettings({
      hardStopLossPct,
      hardStopLossAmount,
      defaultKellyDivisor,
      globalPerBetCapPct,
    });
    return { success: true };
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Failed to save settings." };
  }
}

export function BankrollSettingsForm({ settings }: { settings: Settings }) {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(settingsAction, {});

  // Refresh server component data on success
  if (state.success) {
    router.refresh();
  }

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label
          htmlFor="hardStopLossPct"
          className="block text-xs font-medium text-[var(--text)] mb-1"
        >
          Hard Stop Loss % (drawdown from peak)
        </label>
        <p className="text-xs text-[var(--text-muted)] mb-1.5">
          If your balance falls this far below the peak, betting is suspended. E.g. 20 means
          you stop at 20% below your all-time high.
        </p>
        <input
          id="hardStopLossPct"
          name="hardStopLossPct"
          type="number"
          step="0.1"
          min="0.1"
          max="100"
          defaultValue={settings.hardStopLossPct}
          required
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] transition-colors"
        />
      </div>

      <div>
        <label
          htmlFor="hardStopLossAmount"
          className="block text-xs font-medium text-[var(--text)] mb-1"
        >
          Hard Stop Loss Floor (£, optional)
        </label>
        <p className="text-xs text-[var(--text-muted)] mb-1.5">
          An absolute balance floor — if your bankroll drops below this amount, betting is
          also suspended regardless of drawdown %. Leave blank to disable.
        </p>
        <input
          id="hardStopLossAmount"
          name="hardStopLossAmount"
          type="number"
          step="0.01"
          min="0"
          defaultValue={settings.hardStopLossAmount ?? ""}
          placeholder="e.g. 500 (leave blank to disable)"
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] transition-colors"
        />
      </div>

      <div>
        <label
          htmlFor="defaultKellyDivisor"
          className="block text-xs font-medium text-[var(--text)] mb-1"
        >
          Default Kelly Divisor
        </label>
        <p className="text-xs text-[var(--text-muted)] mb-1.5">
          Divides the full Kelly stake to reduce variance. 2 = half-Kelly, 4 = quarter-Kelly.
          Higher values are more conservative.
        </p>
        <input
          id="defaultKellyDivisor"
          name="defaultKellyDivisor"
          type="number"
          step="0.5"
          min="1"
          defaultValue={settings.defaultKellyDivisor}
          required
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] transition-colors"
        />
      </div>

      <div>
        <label
          htmlFor="globalPerBetCapPct"
          className="block text-xs font-medium text-[var(--text)] mb-1"
        >
          Global Per-Bet Cap %
        </label>
        <p className="text-xs text-[var(--text-muted)] mb-1.5">
          Maximum stake as a percentage of current bankroll for any single bet, regardless of
          Kelly output. E.g. 5 means no single bet can exceed 5% of your balance.
        </p>
        <input
          id="globalPerBetCapPct"
          name="globalPerBetCapPct"
          type="number"
          step="0.5"
          min="0.1"
          max="100"
          defaultValue={settings.globalPerBetCapPct}
          required
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] transition-colors"
        />
      </div>

      {state.error && (
        <p className="text-sm text-[var(--red)] bg-[var(--red)]/10 border border-[var(--red)]/30 rounded-md px-3 py-2">
          {state.error}
        </p>
      )}
      {state.success && (
        <p className="text-sm text-[var(--green)] bg-[var(--green)]/10 border border-[var(--green)]/30 rounded-md px-3 py-2">
          Settings saved.
        </p>
      )}

      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-[var(--blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
      >
        {pending ? "Saving…" : "Save Settings"}
      </button>
    </form>
  );
}
