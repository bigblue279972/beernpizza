import { getBetfairConnection, listSyncBets } from "@/lib/actions/betfair";
import { BetfairSyncClient } from "./BetfairSyncClient";

export default async function BetfairPage() {
  const [connection, bets] = await Promise.all([getBetfairConnection(), listSyncBets()]);

  return (
    <div className="px-6 py-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[var(--text)] mb-0.5">Betfair Sync</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Link your logged bets to your real Betfair bets, then pull the Betfair Starting Price as
          the closing line to calculate CLV.
        </p>
      </div>
      <BetfairSyncClient connection={connection} bets={bets} />
    </div>
  );
}
