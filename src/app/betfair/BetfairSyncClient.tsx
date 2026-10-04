"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  connectBetfair,
  disconnectBetfair,
  fetchClosingPrices,
  linkBets,
  loadBetfairHistory,
  saveBetfairSettings,
  unlinkBet,
  type BetfairConnectionView,
  type BetfairOrderView,
  type FetchOutcome,
  type MatchSuggestion,
  type SyncBet,
} from "@/lib/actions/betfair";

const inputClass =
  "w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none disabled:opacity-50";
const btnPrimary =
  "px-4 py-2 rounded-md bg-[var(--blue)] text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity";
const btnSecondary =
  "px-3 py-1.5 rounded-md border border-[var(--border)] text-xs text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--surface-2)] disabled:opacity-50 transition-colors";

function fmtDate(d: Date | string): string {
  return new Date(d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "2-digit" });
}

function errMsg(err: unknown, fallback: string) {
  return err instanceof Error ? err.message : fallback;
}

function Card({ title, step, children }: { title: string; step?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden mb-5">
      <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--surface-2)] flex items-center gap-2">
        {step && (
          <span className="text-[10px] font-bold rounded-full bg-[var(--blue)]/15 text-[var(--blue)] px-2 py-0.5">
            {step}
          </span>
        )}
        <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">{title}</h2>
      </div>
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

// ---------- Connection ----------

function ConnectionCard({ connection }: { connection: BetfairConnectionView }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [endpoint, setEndpoint] = useState(connection.endpoint);
  const [username, setUsername] = useState(connection.username ?? "");
  const [appKey, setAppKey] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  function run(fn: () => Promise<void>, okText: string) {
    setMessage(null);
    startTransition(async () => {
      try {
        await fn();
        setMessage({ ok: true, text: okText });
        router.refresh();
      } catch (err) {
        setMessage({ ok: false, text: errMsg(err, "Something went wrong.") });
      }
    });
  }

  return (
    <Card title="Betfair Connection" step="SETUP">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-[var(--text-muted)] mb-1">Exchange</label>
              <select
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value as "AU" | "UK")}
                className={inputClass}
                disabled={isPending}
              >
                <option value="AU">Betfair Australia (.com.au)</option>
                <option value="UK">Betfair UK/Global (.com)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--text-muted)] mb-1">Username</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={inputClass}
                disabled={isPending}
                autoComplete="username"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-[var(--text-muted)] mb-1">Application Key</label>
            <input
              value={appKey}
              onChange={(e) => setAppKey(e.target.value)}
              placeholder={
                connection.hasAppKey ? `Saved (ends …${connection.appKeyHint}) — leave blank to keep` : "Paste your app key"
              }
              className={`${inputClass} font-mono`}
              disabled={isPending}
            />
            <p className="text-[11px] text-[var(--text-muted)] mt-1 leading-relaxed">
              Get one free from Betfair&apos;s developer program (developer.betfair.com). The Delayed key is
              enough — Starting Prices for finished races aren&apos;t time-sensitive.
            </p>
          </div>
          <button
            onClick={() =>
              run(async () => {
                await saveBetfairSettings({ endpoint, username, appKey });
                setAppKey("");
              }, "Settings saved. Now connect with your password.")
            }
            disabled={isPending}
            className={btnSecondary}
          >
            Save settings
          </button>
        </div>

        <div className="space-y-3">
          <div
            className={`rounded-md border px-4 py-3 ${
              connection.connected
                ? "border-[var(--green)]/40 bg-[var(--green)]/8"
                : "border-[var(--border)] bg-[var(--bg)]"
            }`}
          >
            <p
              className={`text-sm font-semibold ${
                connection.connected ? "text-[var(--green)]" : "text-[var(--text-muted)]"
              }`}
            >
              {connection.connected ? "● Connected" : "○ Not connected"}
            </p>
            {connection.connected && connection.connectedAt && (
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Since {new Date(connection.connectedAt).toLocaleString("en-GB")}. Sessions expire after a
                few hours of inactivity — just reconnect if asked.
              </p>
            )}
          </div>

          {connection.connected ? (
            <button onClick={() => run(disconnectBetfair, "Disconnected.")} disabled={isPending} className={btnSecondary}>
              Disconnect
            </button>
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                run(async () => {
                  await connectBetfair(password);
                  setPassword("");
                }, "Connected to Betfair.");
              }}
              className="space-y-2"
            >
              <label className="block text-xs text-[var(--text-muted)]">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
                disabled={isPending}
                autoComplete="current-password"
              />
              <p className="text-[11px] text-[var(--text-muted)]">
                Used once to log in, never saved. If you use 2-step verification, add the code to the end of
                your password.
              </p>
              <button type="submit" disabled={isPending || !password} className={btnPrimary}>
                {isPending ? "Connecting…" : "Connect"}
              </button>
            </form>
          )}
        </div>
      </div>
      {message && (
        <p className={`text-xs mt-3 ${message.ok ? "text-[var(--green)]" : "text-[var(--red)]"}`}>{message.text}</p>
      )}
    </Card>
  );
}

// ---------- Main ----------

export function BetfairSyncClient({
  connection,
  bets,
}: {
  connection: BetfairConnectionView;
  bets: SyncBet[];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [days, setDays] = useState(90);
  const [orders, setOrders] = useState<BetfairOrderView[] | null>(null);
  const [suggestions, setSuggestions] = useState<MatchSuggestion[]>([]);
  const [choices, setChoices] = useState<Record<string, string>>({}); // betId -> orderKey
  const [overwrite, setOverwrite] = useState(false);
  const [outcomes, setOutcomes] = useState<FetchOutcome[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const orderByKey = useMemo(() => new Map((orders ?? []).map((o) => [o.key, o])), [orders]);
  const suggestionByBet = useMemo(() => new Map(suggestions.map((s) => [s.betId, s])), [suggestions]);

  const withClv = bets.filter((b) => b.clvPercent !== null).length;
  const linked = bets.filter((b) => b.betfairMarketId && b.betfairSelectionId);
  const linkedNoClose = linked.filter((b) => b.closingPrice === null).length;
  const unlinked = bets.filter((b) => !b.betfairMarketId || !b.betfairSelectionId);

  function act(fn: () => Promise<void>) {
    setError(null);
    setNotice(null);
    startTransition(async () => {
      try {
        await fn();
      } catch (err) {
        setError(errMsg(err, "Something went wrong."));
        router.refresh();
      }
    });
  }

  function loadHistory() {
    act(async () => {
      const res = await loadBetfairHistory(days);
      setOrders(res.orders);
      setSuggestions(res.suggestions);
      setChoices(Object.fromEntries(res.suggestions.map((s) => [s.betId, s.orderKey])));
      setNotice(
        `Loaded ${res.orders.length} settled Betfair bets. Suggested matches for ${res.suggestions.length} of ${unlinked.length} unlinked bets.`,
      );
    });
  }

  function linkChosen(betIds: string[]) {
    const links = betIds
      .map((betId) => {
        const o = orderByKey.get(choices[betId]);
        return o ? { betId, marketId: o.marketId, selectionId: o.selectionId } : null;
      })
      .filter((l): l is { betId: string; marketId: string; selectionId: string } => l !== null);
    if (links.length === 0) return;
    act(async () => {
      await linkBets(links);
      setNotice(`Linked ${links.length} bet${links.length > 1 ? "s" : ""}. Now fetch closing prices.`);
      router.refresh();
    });
  }

  function fetchPrices() {
    act(async () => {
      const res = await fetchClosingPrices({ overwrite });
      setOutcomes(res);
      router.refresh();
    });
  }

  const highConfidence = unlinked.filter((b) => suggestionByBet.get(b.id)?.confidence === "high");
  const chosenUnlinked = unlinked.filter((b) => choices[b.id]);

  // Candidate orders for a bet's dropdown: closest dates first.
  function candidatesFor(bet: SyncBet): BetfairOrderView[] {
    if (!orders) return [];
    const t = new Date(bet.eventDate).getTime();
    return [...orders]
      .filter((o) => o.side === "BACK")
      .sort(
        (a, b) =>
          Math.abs(new Date(a.marketStartTime ?? a.placedDate).getTime() - t) -
          Math.abs(new Date(b.marketStartTime ?? b.placedDate).getTime() - t),
      )
      .slice(0, 40);
  }

  return (
    <div>
      <ConnectionCard connection={connection} />

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
        <Stat label="Placed bets" value={bets.length} />
        <Stat label="With CLV" value={withClv} tone="green" />
        <Stat label="Linked, no close yet" value={linkedNoClose} tone="amber" />
        <Stat label="Not linked" value={unlinked.length} />
      </div>

      {error && (
        <div className="rounded-md border border-[var(--red)]/40 bg-[var(--red)]/8 px-4 py-3 mb-5 text-sm text-[var(--red)]">
          {error}
        </div>
      )}
      {notice && (
        <div className="rounded-md border border-[var(--blue)]/30 bg-[var(--blue)]/5 px-4 py-3 mb-5 text-sm text-[var(--text)]">
          {notice}
        </div>
      )}

      {/* Step 1: link */}
      <Card title="Link your bets to Betfair" step="STEP 1">
        <p className="text-xs text-[var(--text-muted)] mb-3 leading-relaxed">
          Loads your settled bets from your Betfair account and suggests which one matches each bet logged
          here (same day, similar price, matching names). Betfair only keeps a limited window of history, so
          link recent bets soon after they settle.
        </p>
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)]"
            disabled={isPending}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={loadHistory} disabled={isPending || !connection.connected} className={btnPrimary}>
            {isPending && !orders ? "Loading…" : "Load my Betfair bets"}
          </button>
          {orders && highConfidence.length > 0 && (
            <button
              onClick={() => linkChosen(highConfidence.map((b) => b.id))}
              disabled={isPending}
              className="px-4 py-2 rounded-md bg-[var(--green)] text-white text-sm font-semibold hover:opacity-90 disabled:opacity-50"
            >
              Link {highConfidence.length} high-confidence match{highConfidence.length > 1 ? "es" : ""}
            </button>
          )}
          {orders && chosenUnlinked.length > 0 && (
            <button onClick={() => linkChosen(chosenUnlinked.map((b) => b.id))} disabled={isPending} className={btnSecondary}>
              Link all {chosenUnlinked.length} selected
            </button>
          )}
        </div>
        {!connection.connected && (
          <p className="text-xs text-[var(--amber)]">Connect to Betfair above first.</p>
        )}

        {orders && unlinked.length > 0 && (
          <div className="overflow-x-auto rounded-md border border-[var(--border)]">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-[var(--surface-2)] border-b border-[var(--border)] text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                  <th className="text-left px-3 py-2">Your bet</th>
                  <th className="text-right px-3 py-2">Taken</th>
                  <th className="text-left px-3 py-2">Matching Betfair bet</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {unlinked.map((bet) => {
                  const s = suggestionByBet.get(bet.id);
                  return (
                    <tr key={bet.id} className="border-b border-[var(--border)] last:border-0 align-top">
                      <td className="px-3 py-2.5">
                        <p className="text-[var(--text)]">{bet.event}</p>
                        <p className="text-[var(--text-muted)]">
                          {bet.market} · {fmtDate(bet.eventDate)} · {bet.sportName}
                        </p>
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono">{bet.availablePrice.toFixed(2)}</td>
                      <td className="px-3 py-2.5 min-w-[320px]">
                        <select
                          value={choices[bet.id] ?? ""}
                          onChange={(e) => setChoices((c) => ({ ...c, [bet.id]: e.target.value }))}
                          className="w-full rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-xs text-[var(--text)]"
                          disabled={isPending}
                        >
                          <option value="">— choose —</option>
                          {candidatesFor(bet).map((o) => (
                            <option key={o.key} value={o.key}>
                              {fmtDate(o.marketStartTime ?? o.placedDate)} · {o.eventDesc} · {o.marketDesc} ·{" "}
                              {o.runnerDesc} @ {o.priceMatched}
                            </option>
                          ))}
                        </select>
                        {s && (
                          <p
                            className={`mt-1 text-[11px] ${
                              s.confidence === "high" ? "text-[var(--green)]" : "text-[var(--amber)]"
                            }`}
                          >
                            Suggested ({s.confidence}): {s.reason}
                          </p>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button
                          onClick={() => linkChosen([bet.id])}
                          disabled={isPending || !choices[bet.id]}
                          className={btnSecondary}
                        >
                          Link
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {orders && unlinked.length === 0 && (
          <p className="text-xs text-[var(--green)]">Every placed bet is linked.</p>
        )}
      </Card>

      {/* Step 2: fetch */}
      <Card title="Fetch closing prices" step="STEP 2">
        <p className="text-xs text-[var(--text-muted)] mb-3 leading-relaxed">
          Pulls the Betfair Starting Price (BSP) for every linked bet and saves it as the closing price, which
          calculates CLV. This only changes the closing price — results, P&amp;L and bankroll are untouched.
        </p>
        <div className="flex flex-wrap items-center gap-4 mb-3">
          <button
            onClick={fetchPrices}
            disabled={isPending || !connection.connected || linked.length === 0}
            className={btnPrimary}
          >
            {isPending ? "Working…" : `Fetch closing prices (${overwrite ? linked.length : linkedNoClose} bets)`}
          </button>
          <label className="flex items-center gap-2 text-xs text-[var(--text-muted)] cursor-pointer">
            <input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
            Also replace closing prices I entered by hand
          </label>
        </div>

        {outcomes && (
          <div className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-4 py-3">
            <p className="text-sm text-[var(--text)] mb-2">
              <span className="text-[var(--green)] font-semibold">
                {outcomes.filter((o) => o.status === "updated").length} updated
              </span>
              {" · "}
              <span className="text-[var(--text-muted)]">
                {outcomes.filter((o) => o.status === "skipped").length} skipped
              </span>
            </p>
            {outcomes.length === 0 && (
              <p className="text-xs text-[var(--text-muted)]">No linked bets are waiting for a closing price.</p>
            )}
            <ul className="space-y-1">
              {outcomes.map((o) => (
                <li key={o.betId} className="text-xs flex gap-2">
                  <span className={o.status === "updated" ? "text-[var(--green)]" : "text-[var(--amber)]"}>
                    {o.status === "updated" ? "✓" : "–"}
                  </span>
                  <span className="text-[var(--text)]">{o.event}</span>
                  <span className="text-[var(--text-muted)]">
                    {o.status === "updated" ? `BSP ${o.closingPrice}` : o.reason}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>

      {/* All placed bets */}
      <Card title="Placed bets">
        {bets.length === 0 ? (
          <p className="text-sm text-[var(--text-muted)]">No placed bets yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs whitespace-nowrap">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                  <th className="text-left px-3 py-2">Date</th>
                  <th className="text-left px-3 py-2">Sport</th>
                  <th className="text-left px-3 py-2">Event</th>
                  <th className="text-left px-3 py-2">Market</th>
                  <th className="text-right px-3 py-2">Taken</th>
                  <th className="text-right px-3 py-2">Close</th>
                  <th className="text-right px-3 py-2">CLV%</th>
                  <th className="text-left px-3 py-2">Betfair link</th>
                </tr>
              </thead>
              <tbody>
                {bets.map((b) => {
                  const isLinked = b.betfairMarketId && b.betfairSelectionId;
                  const o = isLinked ? orderByKey.get(`${b.betfairMarketId}:${b.betfairSelectionId}`) : undefined;
                  return (
                    <tr key={b.id} className="border-b border-[var(--border)] last:border-0">
                      <td className="px-3 py-2 text-[var(--text-muted)]">{fmtDate(b.eventDate)}</td>
                      <td className="px-3 py-2 text-[var(--text-muted)]">{b.sportName}</td>
                      <td className="px-3 py-2 text-[var(--text)] max-w-[200px] truncate">{b.event}</td>
                      <td className="px-3 py-2 text-[var(--text-muted)]">{b.market}</td>
                      <td className="px-3 py-2 text-right font-mono">{b.availablePrice.toFixed(2)}</td>
                      <td className="px-3 py-2 text-right font-mono text-[var(--text-muted)]">
                        {b.closingPrice !== null ? b.closingPrice.toFixed(2) : "—"}
                      </td>
                      <td
                        className={`px-3 py-2 text-right font-mono font-semibold ${
                          b.clvPercent === null
                            ? "text-[var(--text-muted)]"
                            : b.clvPercent > 0
                              ? "text-[var(--green)]"
                              : "text-[var(--red)]"
                        }`}
                      >
                        {b.clvPercent !== null ? `${b.clvPercent > 0 ? "+" : ""}${b.clvPercent.toFixed(2)}%` : "—"}
                      </td>
                      <td className="px-3 py-2">
                        {isLinked ? (
                          <span className="inline-flex items-center gap-2">
                            <span className="text-[var(--green)]">
                              ✓ {o ? o.runnerDesc : `Market ${b.betfairMarketId}`}
                            </span>
                            <button
                              onClick={() =>
                                act(async () => {
                                  await unlinkBet(b.id);
                                  router.refresh();
                                })
                              }
                              disabled={isPending}
                              className="text-[10px] px-2 py-0.5 rounded border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--red)]"
                            >
                              Unlink
                            </button>
                          </span>
                        ) : (
                          <span className="text-[var(--text-muted)]">Not linked</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "green" | "amber" }) {
  const color =
    tone === "green" ? "text-[var(--green)]" : tone === "amber" ? "text-[var(--amber)]" : "text-[var(--text)]";
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
      <p className="text-[10px] uppercase tracking-wide font-medium text-[var(--text-muted)]">{label}</p>
      <p className={`text-xl font-bold font-mono tabular-nums ${color}`}>{value}</p>
    </div>
  );
}
