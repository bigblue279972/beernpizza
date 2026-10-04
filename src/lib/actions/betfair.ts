"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";
import {
  BetfairError,
  listClearedOrders,
  listMarketBook,
  login,
  type BetfairEndpoint,
} from "@/lib/betfair";

// ---------- Settings / connection ----------

async function getSettingsRow() {
  const existing = await prisma.betfairSettings.findFirst();
  if (existing) return existing;
  return prisma.betfairSettings.create({ data: {} });
}

export interface BetfairConnectionView {
  endpoint: BetfairEndpoint;
  hasAppKey: boolean;
  appKeyHint: string | null; // last 4 chars only — the key itself never reaches the browser
  username: string | null;
  connected: boolean;
  connectedAt: Date | null;
}

export async function getBetfairConnection(): Promise<BetfairConnectionView> {
  const s = await getSettingsRow();
  return {
    endpoint: (s.endpoint as BetfairEndpoint) ?? "AU",
    hasAppKey: !!s.appKey,
    appKeyHint: s.appKey ? s.appKey.slice(-4) : null,
    username: s.username,
    connected: !!s.sessionToken,
    connectedAt: s.sessionTokenAt,
  };
}

export async function saveBetfairSettings(data: {
  endpoint: BetfairEndpoint;
  username: string;
  appKey?: string; // blank = keep the existing key
}) {
  const s = await getSettingsRow();
  const appKey = data.appKey?.trim();
  await prisma.betfairSettings.update({
    where: { id: s.id },
    data: {
      endpoint: data.endpoint,
      username: data.username.trim() || null,
      ...(appKey ? { appKey } : {}),
      // Changing account details invalidates any existing session.
      sessionToken: null,
      sessionTokenAt: null,
    },
  });
  revalidatePath("/betfair");
}

// The password is used for this one login call and then discarded.
export async function connectBetfair(password: string) {
  const s = await getSettingsRow();
  if (!s.appKey) throw new Error("Add your Betfair Application Key first.");
  if (!s.username) throw new Error("Add your Betfair username first.");
  if (!password) throw new Error("Enter your Betfair password.");

  const token = await login(s.endpoint as BetfairEndpoint, s.appKey, s.username, password);
  await prisma.betfairSettings.update({
    where: { id: s.id },
    data: { sessionToken: token, sessionTokenAt: new Date() },
  });
  revalidatePath("/betfair");
}

export async function disconnectBetfair() {
  const s = await getSettingsRow();
  await prisma.betfairSettings.update({
    where: { id: s.id },
    data: { sessionToken: null, sessionTokenAt: null },
  });
  revalidatePath("/betfair");
}

async function requireSession() {
  const s = await getSettingsRow();
  if (!s.appKey || !s.sessionToken) {
    throw new Error("Not connected to Betfair. Connect first.");
  }
  return { endpoint: s.endpoint as BetfairEndpoint, appKey: s.appKey, token: s.sessionToken, id: s.id };
}

// On an expired session, clear the stored token so the UI shows "disconnected".
async function handleBetfairError(err: unknown, settingsId: string): Promise<never> {
  if (err instanceof BetfairError && err.isSessionError) {
    await prisma.betfairSettings.update({
      where: { id: settingsId },
      data: { sessionToken: null, sessionTokenAt: null },
    });
    revalidatePath("/betfair");
  }
  throw err instanceof Error ? new Error(err.message) : new Error("Betfair request failed.");
}

// ---------- Bets to sync ----------

export interface SyncBet {
  id: string;
  sportName: string;
  sportSlug: string;
  eventDate: Date;
  event: string;
  market: string;
  availablePrice: number;
  closingPrice: number | null;
  clvPercent: number | null;
  result: string;
  betfairMarketId: string | null;
  betfairSelectionId: string | null;
}

export async function listSyncBets(): Promise<SyncBet[]> {
  const bets = await prisma.bet.findMany({
    where: { placed: true },
    include: { sport: true },
    orderBy: { eventDate: "desc" },
  });
  return bets.map((b) => ({
    id: b.id,
    sportName: b.sport.name,
    sportSlug: b.sport.slug,
    eventDate: b.eventDate,
    event: b.event,
    market: b.market,
    availablePrice: b.availablePrice,
    closingPrice: b.closingPrice,
    clvPercent: b.closingPrice != null ? (b.availablePrice / b.closingPrice - 1) * 100 : null,
    result: b.result,
    betfairMarketId: b.betfairMarketId,
    betfairSelectionId: b.betfairSelectionId,
  }));
}

// ---------- Betfair bet history + matching ----------

export interface BetfairOrderView {
  key: string; // marketId:selectionId
  marketId: string;
  selectionId: string;
  eventDesc: string;
  marketDesc: string;
  runnerDesc: string;
  eventTypeDesc: string;
  marketStartTime: string | null;
  placedDate: string;
  priceMatched: number;
  sizeSettled: number;
  side: string;
}

export interface MatchSuggestion {
  betId: string;
  orderKey: string;
  confidence: "high" | "medium";
  reason: string;
}

const STOPWORDS = new Set(["the", "vs", "v", "and", "race", "r", "win", "match", "odds", "to", "of", "at"]);

function tokens(s: string): Set<string> {
  return new Set(
    s
      .toLowerCase()
      .replace(/[^a-z0-9 ]/g, " ")
      .split(/\s+/)
      .filter((t) => t.length > 1 && !STOPWORDS.has(t)),
  );
}

function overlap(a: Set<string>, b: Set<string>): number {
  let n = 0;
  for (const t of a) if (b.has(t)) n++;
  return n;
}

export async function loadBetfairHistory(days: number): Promise<{
  orders: BetfairOrderView[];
  suggestions: MatchSuggestion[];
}> {
  const session = await requireSession();
  const to = new Date();
  const from = new Date(to.getTime() - days * 24 * 60 * 60 * 1000);

  let raw;
  try {
    raw = await listClearedOrders(session.endpoint, session.appKey, session.token, from, to);
  } catch (err) {
    return handleBetfairError(err, session.id);
  }

  const orders: BetfairOrderView[] = raw.map((o) => ({
    key: `${o.marketId}:${o.selectionId}`,
    marketId: o.marketId,
    selectionId: String(o.selectionId),
    eventDesc: o.itemDescription?.eventDesc ?? "",
    marketDesc: o.itemDescription?.marketDesc ?? "",
    runnerDesc: o.itemDescription?.runnerDesc ?? "",
    eventTypeDesc: o.itemDescription?.eventTypeDesc ?? "",
    marketStartTime: o.itemDescription?.marketStartTime ?? null,
    placedDate: o.placedDate,
    priceMatched: o.priceMatched,
    sizeSettled: o.sizeSettled,
    side: o.side,
  }));

  // Suggest a Betfair bet for every placed app bet that isn't linked yet.
  const bets = await prisma.bet.findMany({ where: { placed: true } });
  const alreadyLinked = new Set(
    bets
      .filter((b) => b.betfairMarketId && b.betfairSelectionId)
      .map((b) => `${b.betfairMarketId}:${b.betfairSelectionId}`),
  );
  const claimed = new Set<string>();
  const suggestions: MatchSuggestion[] = [];

  for (const bet of bets) {
    if (bet.betfairMarketId && bet.betfairSelectionId) continue;
    const betTokens = tokens(`${bet.event} ${bet.market} ${bet.notes ?? ""}`);

    let best: { order: BetfairOrderView; score: number; reason: string; high: boolean } | null = null;
    for (const o of orders) {
      if (o.side !== "BACK" || alreadyLinked.has(o.key) || claimed.has(o.key)) continue;

      const when = new Date(o.marketStartTime ?? o.placedDate).getTime();
      const dayGap = Math.abs(when - bet.eventDate.getTime()) / 86_400_000;
      if (dayGap > 1.5) continue; // timezones can shift a race by a calendar day

      const priceGap = Math.abs(o.priceMatched - bet.availablePrice) / bet.availablePrice;
      const nameHits = overlap(betTokens, tokens(`${o.eventDesc} ${o.marketDesc} ${o.runnerDesc}`));
      if (priceGap > 0.1 && nameHits === 0) continue;

      const score = nameHits * 2 + (priceGap <= 0.02 ? 3 : priceGap <= 0.05 ? 1.5 : 0) + (dayGap <= 1 ? 1 : 0);
      const high = priceGap <= 0.02 && nameHits > 0;
      const reason = [
        `matched @ ${o.priceMatched} vs your ${bet.availablePrice}`,
        nameHits > 0 ? `${nameHits} name word${nameHits > 1 ? "s" : ""} in common` : "no name match",
      ].join(", ");

      if (!best || score > best.score) best = { order: o, score, reason, high };
    }

    if (best && best.score >= 2) {
      claimed.add(best.order.key);
      suggestions.push({
        betId: bet.id,
        orderKey: best.order.key,
        confidence: best.high ? "high" : "medium",
        reason: best.reason,
      });
    }
  }

  return { orders, suggestions };
}

// ---------- Linking ----------

export async function linkBets(links: { betId: string; marketId: string; selectionId: string }[]) {
  await prisma.$transaction(
    links.map((l) =>
      prisma.bet.update({
        where: { id: l.betId },
        data: { betfairMarketId: l.marketId, betfairSelectionId: l.selectionId },
      }),
    ),
  );
  revalidatePath("/betfair");
}

export async function unlinkBet(betId: string) {
  await prisma.bet.update({
    where: { id: betId },
    data: { betfairMarketId: null, betfairSelectionId: null },
  });
  revalidatePath("/betfair");
}

// ---------- Closing prices ----------

export interface FetchOutcome {
  betId: string;
  event: string;
  status: "updated" | "skipped";
  closingPrice?: number;
  reason?: string;
}

// Pulls Betfair Starting Price for every linked bet and stores it as the
// closing price. Only touches closingPrice — P&L doesn't depend on it, so the
// bankroll is never affected.
export async function fetchClosingPrices(opts: { overwrite: boolean }): Promise<FetchOutcome[]> {
  const session = await requireSession();

  const bets = await prisma.bet.findMany({
    where: {
      placed: true,
      betfairMarketId: { not: null },
      betfairSelectionId: { not: null },
      ...(opts.overwrite ? {} : { closingPrice: null }),
    },
  });
  if (bets.length === 0) return [];

  const marketIds = [...new Set(bets.map((b) => b.betfairMarketId!))];
  let books;
  try {
    books = await listMarketBook(session.endpoint, session.appKey, session.token, marketIds);
  } catch (err) {
    return handleBetfairError(err, session.id);
  }
  const bookById = new Map(books.map((b) => [b.marketId, b]));

  const outcomes: FetchOutcome[] = [];
  const updates = [];

  for (const bet of bets) {
    const book = bookById.get(bet.betfairMarketId!);
    if (!book) {
      outcomes.push({
        betId: bet.id,
        event: bet.event,
        status: "skipped",
        reason: "Betfair no longer returns this market (too old).",
      });
      continue;
    }
    const runner = book.runners.find((r) => String(r.selectionId) === bet.betfairSelectionId);
    if (!runner) {
      outcomes.push({ betId: bet.id, event: bet.event, status: "skipped", reason: "Selection not found in market." });
      continue;
    }
    if (runner.status === "REMOVED") {
      outcomes.push({ betId: bet.id, event: bet.event, status: "skipped", reason: "Runner was scratched — no SP." });
      continue;
    }
    const sp = runner.sp?.actualSP;
    if (!sp || !Number.isFinite(sp) || sp <= 1) {
      outcomes.push({
        betId: bet.id,
        event: bet.event,
        status: "skipped",
        reason:
          book.status === "CLOSED"
            ? "Market has no Betfair Starting Price (BSP is mainly offered on racing)."
            : "SP not reconciled yet — the event hasn't started.",
      });
      continue;
    }

    const closingPrice = Math.round(sp * 100) / 100;
    updates.push(prisma.bet.update({ where: { id: bet.id }, data: { closingPrice } }));
    outcomes.push({ betId: bet.id, event: bet.event, status: "updated", closingPrice });
  }

  if (updates.length > 0) {
    await prisma.$transaction(updates);
    revalidatePath("/", "layout");
  }
  return outcomes;
}
