"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { deleteBankrollTransaction } from "@/lib/actions/bankroll";

type Transaction = {
  id: string;
  type: string;
  amount: number;
  note: string | null;
  createdAt: Date;
};

function formatDate(d: Date | string): string {
  const date = new Date(d);
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function DeleteTxnButton({ id }: { id: string }) {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleDelete() {
    if (!confirm("Delete this transaction? This will reverse its effect on your balance.")) return;
    startTransition(async () => {
      await deleteBankrollTransaction(id);
      router.refresh();
    });
  }

  return (
    <button
      onClick={handleDelete}
      disabled={isPending}
      className="text-xs text-[var(--text-muted)] hover:text-[var(--red)] transition-colors disabled:opacity-50 px-2 py-0.5 rounded border border-transparent hover:border-[var(--red)]/30"
    >
      {isPending ? "…" : "Delete"}
    </button>
  );
}

export function BankrollTransactionList({ transactions }: { transactions: Transaction[] }) {
  if (transactions.length === 0) {
    return (
      <div className="px-5 py-8 text-center">
        <p className="text-[var(--text-muted)] text-sm">No manual transactions yet.</p>
        <p className="text-[var(--text-muted)] text-xs mt-1">
          Add a deposit, withdrawal, or adjustment using the form above.
        </p>
      </div>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-[var(--border)]">
          <th className="text-left px-5 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
            Date
          </th>
          <th className="text-left px-4 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
            Type
          </th>
          <th className="text-left px-4 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
            Note
          </th>
          <th className="text-right px-4 py-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
            Amount
          </th>
          <th className="px-4 py-2" />
        </tr>
      </thead>
      <tbody>
        {transactions.map((txn) => {
          const amountClass =
            txn.amount > 0
              ? "text-[var(--green)]"
              : txn.amount < 0
                ? "text-[var(--red)]"
                : "text-[var(--text-muted)]";
          return (
            <tr
              key={txn.id}
              className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--surface-2)] transition-colors"
            >
              <td className="px-5 py-2.5 text-xs text-[var(--text-muted)] whitespace-nowrap">
                {formatDate(txn.createdAt)}
              </td>
              <td className="px-4 py-2.5 text-xs text-[var(--text)]">{txn.type}</td>
              <td className="px-4 py-2.5 text-xs text-[var(--text-muted)] max-w-[180px] truncate">
                {txn.note ?? "—"}
              </td>
              <td className={`px-4 py-2.5 text-xs text-right tabular-nums font-medium font-mono ${amountClass}`}>
                {txn.amount > 0 ? "+" : ""}£{Math.abs(txn.amount).toFixed(2)}
              </td>
              <td className="px-4 py-2.5 text-right">
                <DeleteTxnButton id={txn.id} />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
