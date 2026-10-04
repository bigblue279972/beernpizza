"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";
import { computeBetView } from "@/lib/betView";
import {
  divergencePoints,
  fairPrice,
  qualifies,
  quarterKellyStake,
  requiredPrice,
  settlePnl,
  type BetResult,
} from "@/lib/calc";
import { getBankrollSettings } from "@/lib/actions/bankroll";
import type { RecentBetForTilt } from "@/lib/tilt";

export interface CreateBetInput {
  sportId: string;
  eventDate: string;
  event: string;
  market: string;
  myProbability: number;
  marginBuffer: number;
  availablePrice: number;
  noVigProb?: number;
  kellyDivisor: number;
  capPct: number;
  checklistPriceMet: boolean;
  checklistLiquidMarket: boolean;
  checklistNotChasing: boolean;
  divergenceJustification?: string;
  placedIntent: boolean;
  stakeOverride?: number;
  notes?: string;
}

export interface UpdateBetInput {
  eventDate?: string;
  event?: string;
  market?: string;
  myProbability?: number;
  marginBuffer?: number;
  availablePrice?: number;
  noVigProb?: number | null;
  kellyDivisor?: number;
  capPct?: number;
  stakeOverride?: number;
  checklistPriceMet?: boolean;
  checklistLiquidMarket?: boolean;
  checklistNotChasing?: boolean;
  divergenceJustification?: string | null;
  placed?: boolean;
  closingPrice?: number | null;
  result?: BetResult;
  notes?: string | null;
}

export async function listBetsForSport(sportId: string) {
  const sport = await prisma.sport.findUniqueOrThrow({ where: { id: sportId } });
  const bets = await prisma.bet.findMany({
    where: { sportId },
    orderBy: { eventDate: "desc" },
    include: { lessonTags: true },
  });
  return bets.map((b) => computeBetView(b, sport));
}

export async function listAllPlacedSettledBets() {
  const bets = await prisma.bet.findMany({
    where: { placed: true, closingPrice: { not: null } },
    include: { sport: true },
    orderBy: { eventDate: "asc" },
  });
  return bets.map((b) => ({ ...computeBetView(b, b.sport), sport: b.sport }));
}

export async function getRecentBetsForTilt(sportId: string, limit = 20): Promise<RecentBetForTilt[]> {
  const bets = await prisma.bet.findMany({
    where: { sportId },
    orderBy: { createdAt: "desc" },
    take: limit,
    select: { createdAt: true, stake: true, result: true, market: true },
  });
  return bets;
}

export async function createBet(input: CreateBetInput) {
  const sport = await prisma.sport.findUniqueOrThrow({ where: { id: input.sportId } });
  const bankroll = await getBankrollSettings();

  const fair = fairPrice(input.myProbability);
  const required = requiredPrice(fair, input.marginBuffer);
  const priceQualifies = qualifies(input.availablePrice, required);

  const divergence = divergencePoints(input.myProbability, input.availablePrice);
  const flagged = Math.abs(divergence) > sport.divergenceThreshold;
  if (flagged && !input.divergenceJustification?.trim()) {
    throw new Error(
      "You are far from a liquid market. Add a divergence justification before saving this bet.",
    );
  }

  if (input.placedIntent) {
    if (!priceQualifies) {
      throw new Error(
        "Cannot mark this bet as placed: the available price does not meet your required +EV price.",
      );
    }
    if (!input.checklistPriceMet || !input.checklistLiquidMarket || !input.checklistNotChasing) {
      throw new Error("Cannot mark this bet as placed until the pre-bet checklist is complete.");
    }
  }

  const placed = input.placedIntent;
  const stakeResult = quarterKellyStake(
    bankroll.currentBalance,
    input.myProbability,
    input.availablePrice,
    input.kellyDivisor,
    input.capPct,
  );

  const stake = placed ? input.stakeOverride ?? stakeResult.suggestedStake : 0;

  const impliedProbTaken = 100 / input.availablePrice;
  const edgePercent =
    input.noVigProb !== undefined ? input.noVigProb - impliedProbTaken : null;

  const bet = await prisma.bet.create({
    data: {
      sportId: input.sportId,
      eventDate: new Date(input.eventDate),
      event: input.event,
      market: input.market,
      myProbability: input.myProbability,
      marginBuffer: input.marginBuffer,
      availablePrice: input.availablePrice,
      noVigProb: input.noVigProb ?? null,
      impliedProbTaken,
      edgePercent,
      bankrollAtEntry: bankroll.currentBalance,
      kellyDivisor: input.kellyDivisor,
      capPct: input.capPct,
      suggestedStake: stakeResult.suggestedStake,
      stake,
      checklistPriceMet: input.checklistPriceMet,
      checklistLiquidMarket: input.checklistLiquidMarket,
      checklistNotChasing: input.checklistNotChasing,
      divergenceJustification: flagged ? input.divergenceJustification : null,
      placed,
      notes: input.notes,
      ...(flagged && input.divergenceJustification
        ? {
            lessonTags: {
              create: {
                sportId: input.sportId,
                text: input.divergenceJustification,
                tags: "model-vs-market-divergence",
              },
            },
          }
        : {}),
    },
  });

  revalidatePath(`/sports/${sport.slug}`);
  revalidatePath("/");
  return bet;
}

export async function settleBet(
  id: string,
  data: { closingPrice: number; result: BetResult },
) {
  const bet = await prisma.bet.findUniqueOrThrow({ where: { id }, include: { sport: true } });

  const newPnl = settlePnl(bet.stake, bet.availablePrice, data.result);
  const oldPnl = bet.result !== "PENDING" ? bet.pnl ?? 0 : 0;
  const delta = (newPnl ?? 0) - oldPnl;

  const bankroll = await getBankrollSettings();

  await prisma.$transaction([
    prisma.bet.update({
      where: { id },
      data: { closingPrice: data.closingPrice, result: data.result, pnl: newPnl },
    }),
    prisma.bankrollSettings.update({
      where: { id: bankroll.id },
      data: { currentBalance: bankroll.currentBalance + delta },
    }),
  ]);

  revalidatePath(`/sports/${bet.sport.slug}`);
  revalidatePath("/bankroll");
  revalidatePath("/");
}

export async function deleteBet(id: string) {
  const bet = await prisma.bet.findUniqueOrThrow({ where: { id }, include: { sport: true } });

  const operations = [];
  if (bet.result !== "PENDING" && bet.pnl != null) {
    const bankroll = await getBankrollSettings();
    operations.push(
      prisma.bankrollSettings.update({
        where: { id: bankroll.id },
        data: { currentBalance: bankroll.currentBalance - bet.pnl },
      }),
    );
  }
  operations.push(prisma.bet.delete({ where: { id } }));
  await prisma.$transaction(operations);

  revalidatePath(`/sports/${bet.sport.slug}`);
  revalidatePath("/bankroll");
  revalidatePath("/");
}

export async function updateBet(id: string, input: UpdateBetInput) {
  const existing = await prisma.bet.findUniqueOrThrow({ where: { id }, include: { sport: true } });
  const sport = existing.sport;

  const myProbability = input.myProbability ?? existing.myProbability;
  const marginBuffer = input.marginBuffer ?? existing.marginBuffer;
  const availablePrice = input.availablePrice ?? existing.availablePrice;
  const kellyDivisor = input.kellyDivisor ?? existing.kellyDivisor;
  const capPct = input.capPct ?? existing.capPct;
  const placed = input.placed !== undefined ? input.placed : existing.placed;
  const checklistPriceMet =
    input.checklistPriceMet !== undefined ? input.checklistPriceMet : existing.checklistPriceMet;
  const checklistLiquidMarket =
    input.checklistLiquidMarket !== undefined
      ? input.checklistLiquidMarket
      : existing.checklistLiquidMarket;
  const checklistNotChasing =
    input.checklistNotChasing !== undefined
      ? input.checklistNotChasing
      : existing.checklistNotChasing;

  const fair = fairPrice(myProbability);
  const required = requiredPrice(fair, marginBuffer);
  const priceQualifies = qualifies(availablePrice, required);
  const divergence = divergencePoints(myProbability, availablePrice);
  const flagged = Math.abs(divergence) > sport.divergenceThreshold;

  if (placed) {
    if (!priceQualifies) {
      throw new Error("Cannot mark as placed: available price does not meet required +EV price.");
    }
    if (!checklistPriceMet || !checklistLiquidMarket || !checklistNotChasing) {
      throw new Error("Cannot mark as placed until the pre-bet checklist is complete.");
    }
  }

  const bankroll = await getBankrollSettings();
  const stakeResult = quarterKellyStake(
    bankroll.currentBalance,
    myProbability,
    availablePrice,
    kellyDivisor,
    capPct,
  );

  const stake = placed
    ? input.stakeOverride !== undefined
      ? input.stakeOverride
      : existing.stake
    : 0;

  const noVigProb = "noVigProb" in input ? input.noVigProb : (existing.noVigProb ?? null);
  const impliedProbTaken = 100 / availablePrice;
  const edgePercent = noVigProb !== null && noVigProb !== undefined
    ? noVigProb - impliedProbTaken
    : null;

  const result = (input.result ?? existing.result) as BetResult;
  const closingPrice =
    "closingPrice" in input ? input.closingPrice ?? null : existing.closingPrice;

  const newPnl =
    result !== "PENDING" && closingPrice !== null && placed
      ? settlePnl(stake, availablePrice, result)
      : null;

  const oldPnl = existing.result !== "PENDING" && existing.pnl != null ? existing.pnl : 0;
  const delta = (newPnl ?? 0) - oldPnl;

  const betUpdate = prisma.bet.update({
    where: { id },
    data: {
      eventDate: input.eventDate ? new Date(input.eventDate) : existing.eventDate,
      event: input.event ?? existing.event,
      market: input.market ?? existing.market,
      myProbability,
      marginBuffer,
      availablePrice,
      noVigProb: noVigProb ?? null,
      impliedProbTaken,
      edgePercent,
      kellyDivisor,
      capPct,
      suggestedStake: stakeResult.suggestedStake,
      stake,
      checklistPriceMet,
      checklistLiquidMarket,
      checklistNotChasing,
      divergenceJustification:
        flagged
          ? (input.divergenceJustification !== undefined
              ? input.divergenceJustification
              : existing.divergenceJustification)
          : null,
      placed,
      closingPrice,
      result,
      pnl: newPnl,
      notes: "notes" in input ? input.notes ?? null : existing.notes,
    },
  });

  if (delta !== 0) {
    await prisma.$transaction([
      betUpdate,
      prisma.bankrollSettings.update({
        where: { id: bankroll.id },
        data: { currentBalance: bankroll.currentBalance + delta },
      }),
    ]);
  } else {
    await betUpdate;
  }

  revalidatePath(`/sports/${sport.slug}`);
  revalidatePath("/bankroll");
  revalidatePath("/");
}

export async function linkLessonToBet(betId: string, lessonId: string) {
  await prisma.bet.update({
    where: { id: betId },
    data: { lessonTags: { connect: { id: lessonId } } },
  });
  revalidatePath("/");
}
