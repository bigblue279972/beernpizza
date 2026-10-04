"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";

export async function getBankrollSettings() {
  const existing = await prisma.bankrollSettings.findFirst();
  if (existing) return existing;
  return prisma.bankrollSettings.create({ data: {} });
}

export async function updateBankrollSettings(data: {
  startingBalance?: number;
  hardStopLossPct?: number;
  hardStopLossAmount?: number | null;
  defaultKellyDivisor?: number;
  globalPerBetCapPct?: number;
}) {
  const settings = await getBankrollSettings();
  const updated = await prisma.bankrollSettings.update({ where: { id: settings.id }, data });
  revalidatePath("/bankroll");
  return updated;
}

export async function addBankrollTransaction(
  type: "DEPOSIT" | "WITHDRAWAL" | "ADJUSTMENT",
  amount: number,
  note?: string,
) {
  const settings = await getBankrollSettings();
  const signedAmount = type === "WITHDRAWAL" ? -Math.abs(amount) : amount;

  const [txn] = await prisma.$transaction([
    prisma.bankrollTransaction.create({ data: { type, amount: signedAmount, note } }),
    prisma.bankrollSettings.update({
      where: { id: settings.id },
      data: { currentBalance: settings.currentBalance + signedAmount },
    }),
  ]);
  revalidatePath("/bankroll");
  return txn;
}

export interface BankrollPoint {
  date: Date;
  balance: number;
  label: string;
}

// Reconstructs the balance over time from the starting balance, every
// manual transaction, and every settled bet's P&L, in chronological order.
// This is what drives the drawdown chart and the hard-stop check — it must
// match prisma's currentBalance exactly or the stop-loss alert is lying.
export async function listBankrollTransactions() {
  return prisma.bankrollTransaction.findMany({ orderBy: { createdAt: "asc" } });
}

export async function deleteBankrollTransaction(id: string) {
  const settings = await getBankrollSettings();
  const txn = await prisma.bankrollTransaction.findUniqueOrThrow({ where: { id } });
  await prisma.$transaction([
    prisma.bankrollTransaction.delete({ where: { id } }),
    prisma.bankrollSettings.update({
      where: { id: settings.id },
      data: { currentBalance: settings.currentBalance - txn.amount },
    }),
  ]);
  revalidatePath("/bankroll");
}

export async function getBankrollSeries(): Promise<{
  settings: Awaited<ReturnType<typeof getBankrollSettings>>;
  series: BankrollPoint[];
  peak: number;
  currentDrawdownPct: number;
  stopLossTriggered: boolean;
}> {
  const settings = await getBankrollSettings();
  const [transactions, settledBets] = await Promise.all([
    prisma.bankrollTransaction.findMany({ orderBy: { createdAt: "asc" } }),
    prisma.bet.findMany({
      where: { placed: true, result: { not: "PENDING" } },
      orderBy: { eventDate: "asc" },
    }),
  ]);

  type Event = { date: Date; delta: number; label: string };
  const events: Event[] = [
    ...transactions.map((t) => ({ date: t.createdAt, delta: t.amount, label: t.type })),
    ...settledBets.map((b) => ({
      date: b.eventDate,
      delta: b.pnl ?? 0,
      label: `${b.event} (${b.result})`,
    })),
  ].sort((a, b) => a.date.getTime() - b.date.getTime());

  let balance = settings.startingBalance;
  let peak = balance;
  const series: BankrollPoint[] = [{ date: new Date(0), balance, label: "Starting balance" }];
  for (const ev of events) {
    balance += ev.delta;
    peak = Math.max(peak, balance);
    series.push({ date: ev.date, balance, label: ev.label });
  }

  const currentDrawdownPct = peak > 0 ? ((peak - balance) / peak) * 100 : 0;
  const floor = settings.hardStopLossAmount;
  const stopLossTriggered =
    currentDrawdownPct >= settings.hardStopLossPct || (floor != null && balance <= floor);

  return { settings, series, peak, currentDrawdownPct, stopLossTriggered };
}
