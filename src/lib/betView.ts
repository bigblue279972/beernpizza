import type { Bet, Sport } from "@/generated/prisma";
import { clvPercent, divergencePoints, fairPrice, qualifies, requiredPrice } from "@/lib/calc";

export interface BetComputed extends Bet {
  fairPrice: number;
  requiredPrice: number;
  priceQualifies: boolean;
  divergencePoints: number;
  divergenceFlagged: boolean;
  clvPercent: number | null;
}

export function computeBetView(bet: Bet, sport: Pick<Sport, "divergenceThreshold">): BetComputed {
  const fair = fairPrice(bet.myProbability);
  const required = requiredPrice(fair, bet.marginBuffer);
  const divergence = divergencePoints(bet.myProbability, bet.availablePrice);
  return {
    ...bet,
    fairPrice: fair,
    requiredPrice: required,
    priceQualifies: qualifies(bet.availablePrice, required),
    divergencePoints: divergence,
    divergenceFlagged: Math.abs(divergence) > sport.divergenceThreshold,
    clvPercent:
      bet.placed && bet.closingPrice != null ? clvPercent(bet.availablePrice, bet.closingPrice) : null,
  };
}
