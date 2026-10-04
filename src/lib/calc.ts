// Core discipline math. Every number the app shows is derived from here so the
// rules (no bet without edge, no stake without a Kelly basis, no verdict
// without CLV) can't be quietly bypassed somewhere in the UI layer.

export function impliedProbabilityPct(decimalOdds: number): number {
  return 100 / decimalOdds;
}

export function fairPrice(myProbabilityPct: number): number {
  return 100 / myProbabilityPct;
}

// "Required +EV price" = fair price plus the margin you demand as a buffer
// against your own estimation error. Expressed in decimal-odds points so it
// reads the same way the exchange price ladder does.
export function requiredPrice(fair: number, marginBuffer: number): number {
  return fair + marginBuffer;
}

export function qualifies(availablePrice: number, required: number): boolean {
  return availablePrice >= required;
}

// Positive = you think the market is wrong in your favour. Large positive
// divergence on a liquid market is the single most common way bettors lose:
// it usually means the model is wrong, not the market.
export function divergencePoints(myProbabilityPct: number, availablePrice: number): number {
  return myProbabilityPct - impliedProbabilityPct(availablePrice);
}

// Kelly fraction for a bet at decimal odds `price` with true win probability `p`.
// f* = (b*p - q) / b, where b = price - 1, q = 1 - p. Clamped to zero: a
// negative Kelly fraction means the bet is -EV and there is no fraction worth
// taking.
export function kellyFraction(myProbabilityPct: number, price: number): number {
  const p = myProbabilityPct / 100;
  const b = price - 1;
  if (b <= 0) return 0;
  const q = 1 - p;
  const f = (b * p - q) / b;
  return Math.max(0, f);
}

export interface StakeResult {
  rawKellyFraction: number;
  fractionalKelly: number; // after dividing by the kelly divisor (e.g. /4)
  cappedFraction: number; // after applying the per-bet cap
  suggestedStake: number;
  capApplied: boolean;
}

export function quarterKellyStake(
  bankroll: number,
  myProbabilityPct: number,
  price: number,
  kellyDivisor: number,
  capPct: number,
): StakeResult {
  const rawKellyFraction = kellyFraction(myProbabilityPct, price);
  const fractionalKelly = rawKellyFraction / kellyDivisor;
  const cap = capPct / 100;
  const cappedFraction = Math.min(fractionalKelly, cap);
  return {
    rawKellyFraction,
    fractionalKelly,
    cappedFraction,
    suggestedStake: bankroll * cappedFraction,
    capApplied: fractionalKelly > cap,
  };
}

// The number that matters. CLV = the price you actually got vs. the price
// the market settled on at the close. Positive, sustained, over a large
// sample is the only honest evidence of edge.
export function clvPercent(priceTaken: number, closingPrice: number): number {
  return (priceTaken / closingPrice - 1) * 100;
}

export type BetResult = "PENDING" | "WIN" | "LOSS" | "VOID";

export function settlePnl(stake: number, priceTaken: number, result: BetResult): number | null {
  switch (result) {
    case "WIN":
      return stake * (priceTaken - 1);
    case "LOSS":
      return -stake;
    case "VOID":
      return 0;
    default:
      return null;
  }
}

export function mean(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

// Cumulative running average, used to draw the "does this converge to
// positive or negative" CLV chart. Index i = average of values[0..i].
export function cumulativeAverage(values: number[]): number[] {
  const out: number[] = [];
  let sum = 0;
  values.forEach((v, i) => {
    sum += v;
    out.push(sum / (i + 1));
  });
  return out;
}
