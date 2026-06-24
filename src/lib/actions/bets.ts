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

  const bet = await prisma.bet.create({
    data: {
      sportId: input.sportId,
      eventDate: new Date(input.eventDate),
      event: input.event,
      market: input.market,
      myProbability: input.myProbability,
      marginBuffer: input.marginBuffer,
      availablePrice: input.availablePrice,
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

export async function linkLessonToBet(betId: string, lessonId: string) {
  await prisma.bet.update({
    where: { id: betId },
    data: { lessonTags: { connect: { id: lessonId } } },
  });
  revalidatePath("/");
}
