// Thin client for the Betfair Exchange API (API-NG, REST flavour).
// Server-only: called from server actions, never from the browser, so the
// app key and session token never leave the machine running the app.

export type BetfairEndpoint = "AU" | "UK";

const LOGIN_HOSTS: Record<BetfairEndpoint, string> = {
  AU: "https://identitysso.betfair.com.au",
  UK: "https://identitysso.betfair.com",
};

// AU accounts are tried against the .com.au betting host first, then the
// global host — both have been used for Australian accounts over the years.
const BETTING_HOSTS: Record<BetfairEndpoint, string[]> = {
  AU: ["https://api.betfair.com.au", "https://api.betfair.com"],
  UK: ["https://api.betfair.com"],
};

const BETTING_PATH = "/exchange/betting/rest/v1.0";

export class BetfairError extends Error {
  constructor(
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = "BetfairError";
  }

  get isSessionError() {
    return this.code === "INVALID_SESSION_INFORMATION" || this.code === "NO_SESSION";
  }
}

// ---------- Auth ----------

export async function login(
  endpoint: BetfairEndpoint,
  appKey: string,
  username: string,
  password: string,
): Promise<string> {
  const res = await fetch(`${LOGIN_HOSTS[endpoint]}/api/login`, {
    method: "POST",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "X-Application": appKey,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: new URLSearchParams({ username, password }).toString(),
  });

  const text = await res.text();
  let data: { token?: string; status?: string; error?: string };
  try {
    data = JSON.parse(text);
  } catch {
    throw new BetfairError(`Betfair login returned an unexpected response (HTTP ${res.status}).`);
  }

  if (data.status !== "SUCCESS" || !data.token) {
    throw new BetfairError(loginErrorMessage(data.error), data.error);
  }
  return data.token;
}

function loginErrorMessage(code?: string): string {
  switch (code) {
    case "INVALID_USERNAME_OR_PASSWORD":
      return "Betfair rejected the username or password.";
    case "ACCOUNT_NOW_LOCKED":
    case "ACCOUNT_ALREADY_LOCKED":
      return "Your Betfair account is locked. Unlock it on the Betfair website first.";
    case "INVALID_APP_KEY":
    case "APP_KEY_CREATION_FAILED":
      return "Betfair rejected the Application Key.";
    case "SECURITY_QUESTION_WRONG_3X":
    case "PENDING_AUTH":
    case "STRONG_AUTH_CODE_REQUIRED":
      return "Betfair needs two-step verification for this login. Append your 2FA code directly to the end of your password and try again.";
    case "TELBET_TERMS_CONDITIONS_NA":
    case "CERT_AUTH_REQUIRED":
      return "Betfair requires certificate login for this account, which this app doesn't support.";
    default:
      return `Betfair login failed${code ? ` (${code})` : ""}.`;
  }
}

// ---------- Betting API ----------

async function bettingCall<T>(
  endpoint: BetfairEndpoint,
  appKey: string,
  token: string,
  operation: string,
  params: unknown,
): Promise<T> {
  let lastError: unknown;

  for (const host of BETTING_HOSTS[endpoint]) {
    let res: Response;
    try {
      res = await fetch(`${host}${BETTING_PATH}/${operation}/`, {
        method: "POST",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-Application": appKey,
          "X-Authentication": token,
        },
        body: JSON.stringify(params),
      });
    } catch (err) {
      // Network/DNS failure — try the next host.
      lastError = err;
      continue;
    }

    if (res.status === 404) {
      lastError = new BetfairError(`${operation} not found on ${host}.`);
      continue;
    }

    const text = await res.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      throw new BetfairError(`Betfair ${operation} returned an unexpected response (HTTP ${res.status}).`);
    }

    if (!res.ok) {
      const code = extractErrorCode(data);
      throw new BetfairError(
        code === "INVALID_SESSION_INFORMATION" || code === "NO_SESSION"
          ? "Your Betfair session has expired. Reconnect to continue."
          : `Betfair ${operation} failed${code ? ` (${code})` : ` (HTTP ${res.status})`}.`,
        code,
      );
    }
    return data as T;
  }

  throw lastError instanceof BetfairError
    ? lastError
    : new BetfairError(`Couldn't reach the Betfair API for ${operation}. Check your internet connection.`);
}

function extractErrorCode(data: unknown): string | undefined {
  const d = data as {
    detail?: { APINGException?: { errorCode?: string } };
    faultstring?: string;
  };
  return d?.detail?.APINGException?.errorCode ?? d?.faultstring;
}

export interface ClearedOrder {
  betId: string;
  eventTypeId: string;
  marketId: string;
  selectionId: number;
  placedDate: string;
  settledDate: string;
  side: "BACK" | "LAY";
  priceMatched: number;
  sizeSettled: number;
  profit: number;
  betOutcome: string;
  itemDescription?: {
    eventTypeDesc?: string;
    eventDesc?: string;
    marketDesc?: string;
    marketStartTime?: string;
    runnerDesc?: string;
  };
}

// The account's settled bets. Betfair only keeps a limited history here, so
// older bets fall out of this list.
export async function listClearedOrders(
  endpoint: BetfairEndpoint,
  appKey: string,
  token: string,
  from: Date,
  to: Date,
): Promise<ClearedOrder[]> {
  const all: ClearedOrder[] = [];
  let fromRecord = 0;
  // Page through results; Betfair caps each page at 1000 records.
  for (let page = 0; page < 10; page++) {
    const res = await bettingCall<{ clearedOrders: ClearedOrder[]; moreAvailable: boolean }>(
      endpoint,
      appKey,
      token,
      "listClearedOrders",
      {
        betStatus: "SETTLED",
        settledDateRange: { from: from.toISOString(), to: to.toISOString() },
        includeItemDescription: true,
        fromRecord,
        recordCount: 1000,
      },
    );
    all.push(...(res.clearedOrders ?? []));
    if (!res.moreAvailable) break;
    fromRecord += res.clearedOrders?.length ?? 0;
  }
  return all;
}

export interface MarketBookRunner {
  selectionId: number;
  status: string; // ACTIVE | WINNER | LOSER | REMOVED | PLACED
  sp?: { nearPrice?: number; farPrice?: number; actualSP?: number };
}

export interface MarketBook {
  marketId: string;
  status: string; // OPEN | SUSPENDED | CLOSED
  runners: MarketBookRunner[];
}

// Market books including Betfair Starting Price data. `actualSP` is set once
// the market has reconciled its SP (i.e. after the off).
export async function listMarketBook(
  endpoint: BetfairEndpoint,
  appKey: string,
  token: string,
  marketIds: string[],
): Promise<MarketBook[]> {
  const books: MarketBook[] = [];
  // Small batches keep each request well inside Betfair's data-weight limit.
  for (let i = 0; i < marketIds.length; i += 10) {
    const batch = marketIds.slice(i, i + 10);
    const res = await bettingCall<MarketBook[]>(endpoint, appKey, token, "listMarketBook", {
      marketIds: batch,
      priceProjection: { priceData: ["SP_AVAILABLE", "SP_TRADED"] },
    });
    books.push(...res);
  }
  return books;
}
