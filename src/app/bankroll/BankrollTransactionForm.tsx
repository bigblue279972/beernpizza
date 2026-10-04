"use client";

import { useActionState } from "react";
import { useRouter } from "next/navigation";
import { addBankrollTransaction } from "@/lib/actions/bankroll";

interface FormState {
  error?: string;
  success?: boolean;
  successMessage?: string;
}

async function transactionAction(
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  try {
    const type = formData.get("type") as "DEPOSIT" | "WITHDRAWAL" | "ADJUSTMENT";
    const amountRaw = parseFloat(formData.get("amount") as string);
    const note = (formData.get("note") as string).trim() || undefined;

    if (!["DEPOSIT", "WITHDRAWAL", "ADJUSTMENT"].includes(type)) {
      return { error: "Invalid transaction type." };
    }
    if (isNaN(amountRaw) || amountRaw <= 0) {
      return { error: "Amount must be a positive number." };
    }

    await addBankrollTransaction(type, amountRaw, note);
    const typeLabel =
      type === "DEPOSIT" ? "Deposit" : type === "WITHDRAWAL" ? "Withdrawal" : "Adjustment";
    return {
      success: true,
      successMessage: `${typeLabel} of £${amountRaw.toFixed(2)} recorded.`,
    };
  } catch (e) {
    return { error: e instanceof Error ? e.message : "Failed to record transaction." };
  }
}

export function BankrollTransactionForm() {
  const router = useRouter();
  const [state, formAction, pending] = useActionState(transactionAction, {});

  if (state.success) {
    router.refresh();
  }

  return (
    <form action={formAction} className="space-y-4">
      <div>
        <label
          htmlFor="type"
          className="block text-xs font-medium text-[var(--text)] mb-1"
        >
          Transaction Type
        </label>
        <select
          id="type"
          name="type"
          required
          defaultValue="DEPOSIT"
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] focus:outline-none focus:border-[var(--blue)] transition-colors"
        >
          <option value="DEPOSIT">Deposit — add funds to bankroll</option>
          <option value="WITHDRAWAL">Withdrawal — take funds out</option>
          <option value="ADJUSTMENT">Adjustment — manual correction</option>
        </select>
      </div>

      <div>
        <label
          htmlFor="amount"
          className="block text-xs font-medium text-[var(--text)] mb-1"
        >
          Amount (£)
        </label>
        <input
          id="amount"
          name="amount"
          type="number"
          step="0.01"
          min="0.01"
          placeholder="e.g. 100.00"
          required
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] transition-colors"
        />
        <p className="text-xs text-[var(--text-muted)] mt-1">
          Always enter a positive value. Withdrawals will be recorded as negative automatically.
        </p>
      </div>

      <div>
        <label
          htmlFor="note"
          className="block text-xs font-medium text-[var(--text)] mb-1"
        >
          Note (optional)
        </label>
        <input
          id="note"
          name="note"
          type="text"
          maxLength={200}
          placeholder="e.g. Monthly profit withdrawal"
          className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] transition-colors"
        />
      </div>

      {state.error && (
        <p className="text-sm text-[var(--red)] bg-[var(--red)]/10 border border-[var(--red)]/30 rounded-md px-3 py-2">
          {state.error}
        </p>
      )}
      {state.success && state.successMessage && (
        <p className="text-sm text-[var(--green)] bg-[var(--green)]/10 border border-[var(--green)]/30 rounded-md px-3 py-2">
          {state.successMessage}
        </p>
      )}

      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-[var(--blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
      >
        {pending ? "Recording…" : "Record Transaction"}
      </button>
    </form>
  );
}
