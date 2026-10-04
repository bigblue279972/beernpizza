import { getSportBySlug } from "@/lib/actions/sports";
import { getBankrollSettings } from "@/lib/actions/bankroll";
import { getRecentBetsForTilt } from "@/lib/actions/bets";
import { notFound } from "next/navigation";
import { BetEntryForm } from "@/components/BetEntryForm";

export default async function EntryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const [sport, bankroll] = await Promise.all([
    getSportBySlug(slug),
    getBankrollSettings(),
  ]);
  if (!sport) notFound();

  const recentBets = await getRecentBetsForTilt(sport.id);

  return (
    <BetEntryForm
      sportId={sport.id}
      sportSlug={sport.slug}
      defaultMarginBuffer={sport.defaultMarginBuffer}
      divergenceThreshold={sport.divergenceThreshold}
      capPct={sport.perBetCapPct}
      bankrollBalance={bankroll.currentBalance}
      kellyDivisor={bankroll.defaultKellyDivisor}
      recentBets={recentBets}
    />
  );
}
