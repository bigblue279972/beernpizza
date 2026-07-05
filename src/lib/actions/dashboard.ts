"use server";

import { prisma } from "@/lib/db";
import { clvPercent, cumulativeAverage, mean } from "@/lib/calc";
import { getBankrollSeries } from "@/lib/actions/bankroll";

export interface ClvVerdict {
  label: "INSUFFICIENT_DATA" | "EDGE_DETECTED" | "BREAK_EVEN" | "NO_EDGE";
  message: string;
  avgClvPct: number | null;
  sampleSize: number;
}

export interface SportClvSummary {
  sportId: string;
  sportName: string;
  sportSlug: string;
  avgClvPct: number | null;
  sampleSize: number;
  winRate: number | null;
  totalPnl: number;
}

export interface ClvChartPoint {
  betIndex: number;
  date: string;
  event: string;
  clvPct: number;
  cumulativeAvgClvPct: number;
}

export async function getClvDashboard() {
  const bets = await prisma.bet.findMany({
    where: { placed: true, closingPrice: { not: null }, result: { not: "PENDING" } },
    include: { sport: true },
    orderBy: { eventDate: "asc" },
  });

  const withClv = bets.map((b) => ({
    ...b,
    clvPct: clvPercent(b.availablePrice, b.closingPrice!),
  }));

  const clvValues = withClv.map((b) => b.clvPct);
  const cumAvgs = cumulativeAverage(clvValues);

  const chartData: ClvChartPoint[] = withClv.map((b, i) => ({
    betIndex: i + 1,
    date: b.eventDate.toISOString().split("T")[0],
    event: b.event,
    clvPct: b.clvPct,
    cumulativeAvgClvPct: cumAvgs[i],
  }));

  const avgClv = mean(clvValues);
  const n = clvValues.length;

  const verdict: ClvVerdict = buildVerdict(avgClv, n);

  // Per-sport breakdown
  const sportMap = new Map<
    string,
    { name: string; slug: string; clvs: number[]; pnls: number[]; wins: number; settled: number }
  >();
  for (const b of withClv) {
    if (!sportMap.has(b.sportId)) {
      sportMap.set(b.sportId, {
        name: b.sport.name,
        slug: b.sport.slug,
        clvs: [],
        pnls: [],
        wins: 0,
        settled: 0,
      });
    }
    const entry = sportMap.get(b.sportId)!;
    entry.clvs.push(b.clvPct);
    if (b.pnl != null) entry.pnls.push(b.pnl);
    if (b.result === "WIN") entry.wins++;
    if (b.result !== "PENDING") entry.settled++;
  }

  const sportSummaries: SportClvSummary[] = Array.from(sportMap.entries()).map(([id, s]) => ({
    sportId: id,
    sportName: s.name,
    sportSlug: s.slug,
    avgClvPct: mean(s.clvs),
    sampleSize: s.clvs.length,
    winRate: s.settled > 0 ? (s.wins / s.settled) * 100 : null,
    totalPnl: s.pnls.reduce((a, b) => a + b, 0),
  }));

  // Overall stats
  const settledBets = bets.filter((b) => b.result !== "PENDING");
  const wins = settledBets.filter((b) => b.result === "WIN").length;
  const totalPnl = settledBets.reduce((a, b) => a + (b.pnl ?? 0), 0);

  // Edge estimate: avg edgePercent across placed bets that had noVigProb set
  const allPlacedBets = await prisma.bet.findMany({
    where: { placed: true, edgePercent: { not: null } },
    select: { edgePercent: true },
  });
  const edgeValues = allPlacedBets.map((b) => b.edgePercent!);
  const avgEdgePct = mean(edgeValues);

  const { settings, currentDrawdownPct, stopLossTriggered } = await getBankrollSeries();

  return {
    verdict,
    chartData,
    sportSummaries,
    overall: {
      totalBetsPlaced: bets.length,
      settledCount: settledBets.length,
      winRate: settledBets.length > 0 ? (wins / settledBets.length) * 100 : null,
      totalPnl,
      avgClvPct: avgClv,
      avgEdgePct,
    },
    bankroll: {
      currentBalance: settings.currentBalance,
      startingBalance: settings.startingBalance,
      currentDrawdownPct,
      stopLossTriggered,
      hardStopLossPct: settings.hardStopLossPct,
    },
  };
}

function buildVerdict(avgClv: number | null, n: number): ClvVerdict {
  if (n < 30) {
    return {
      label: "INSUFFICIENT_DATA",
      message: `Only ${n} settled bet${n === 1 ? "" : "s"} with closing prices. You need at least 30 before drawing conclusions — and really 100+ for statistical confidence. Keep logging.`,
      avgClvPct: avgClv,
      sampleSize: n,
    };
  }
  if (avgClv === null) {
    return { label: "INSUFFICIENT_DATA", message: "No CLV data yet.", avgClvPct: null, sampleSize: n };
  }
  const confidence = n >= 100 ? "high" : "low";
  if (avgClv > 0) {
    return {
      label: "EDGE_DETECTED",
      message: `Positive average CLV of +${avgClv.toFixed(2)}% across ${n} bets (${confidence} confidence). You are consistently beating the closing line. This is the honest signal of edge — not your win/loss record.`,
      avgClvPct: avgClv,
      sampleSize: n,
    };
  }
  if (avgClv >= -1) {
    return {
      label: "BREAK_EVEN",
      message: `Average CLV of ${avgClv.toFixed(2)}% across ${n} bets — effectively break-even at the close. Keep logging. This can resolve either way with more sample.`,
      avgClvPct: avgClv,
      sampleSize: n,
    };
  }
  return {
    label: "NO_EDGE",
    message: `Average CLV of ${avgClv.toFixed(2)}% across ${n} bets. You are not beating the closing line. Profitable runs with this profile are luck, not skill, and will regress. Review your model assumptions.`,
    avgClvPct: avgClv,
    sampleSize: n,
  };
}
