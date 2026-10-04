// Heuristic session/tilt flags. These are deliberately simple and only ever
// warn — discipline tools that quietly block you breed workarounds, ones
// that show you the pattern in the moment tend to actually change behaviour.

export interface RecentBetForTilt {
  createdAt: Date;
  stake: number;
  result: "PENDING" | "WIN" | "LOSS" | "VOID";
  market: string;
}

export interface TiltFlags {
  rapidFire: boolean;
  stakeEscalationAfterLoss: boolean;
  offPatternMarket: boolean;
  messages: string[];
}

const RAPID_FIRE_WINDOW_MINUTES = 15;
const RAPID_FIRE_COUNT = 3;
const ESCALATION_MULTIPLE = 1.5;

export function detectTiltFlags(
  recentBetsNewestFirst: RecentBetForTilt[],
  candidateStake: number,
  candidateMarket: string,
): TiltFlags {
  const messages: string[] = [];

  const now = recentBetsNewestFirst[0]?.createdAt ?? new Date();
  const windowMs = RAPID_FIRE_WINDOW_MINUTES * 60 * 1000;
  const withinWindow = recentBetsNewestFirst.filter(
    (b) => now.getTime() - b.createdAt.getTime() <= windowMs,
  );
  const rapidFire = withinWindow.length >= RAPID_FIRE_COUNT;
  if (rapidFire) {
    messages.push(
      `${withinWindow.length} bets logged in the last ${RAPID_FIRE_WINDOW_MINUTES} minutes. Slow down — rapid-fire entry is a tilt signal, not a strategy.`,
    );
  }

  const lastResult = recentBetsNewestFirst[0];
  const priorStakes = recentBetsNewestFirst.slice(1, 6).map((b) => b.stake);
  const avgPriorStake =
    priorStakes.length > 0 ? priorStakes.reduce((a, b) => a + b, 0) / priorStakes.length : null;
  const stakeEscalationAfterLoss =
    lastResult?.result === "LOSS" &&
    avgPriorStake !== null &&
    candidateStake > avgPriorStake * ESCALATION_MULTIPLE;
  if (stakeEscalationAfterLoss) {
    messages.push(
      "This stake is well above your recent average and your last bet lost. That pattern looks like chasing, not edge.",
    );
  }

  const recentMarkets = new Set(recentBetsNewestFirst.slice(0, 20).map((b) => b.market.toLowerCase()));
  const offPatternMarket =
    recentBetsNewestFirst.length >= 5 && !recentMarkets.has(candidateMarket.toLowerCase());
  if (offPatternMarket) {
    messages.push(
      "You haven't logged this market recently in this sport. Confirm it's inside your defined edge, not a one-off curiosity bet.",
    );
  }

  return { rapidFire, stakeEscalationAfterLoss, offPatternMarket, messages };
}
