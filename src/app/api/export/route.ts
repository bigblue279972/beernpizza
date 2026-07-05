import { NextRequest, NextResponse } from "next/server";
import * as XLSX from "xlsx";
import { prisma } from "@/lib/db";
import { computeBetView } from "@/lib/betView";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const sportSlug = searchParams.get("sport");

  const sport = sportSlug ? await prisma.sport.findUnique({ where: { slug: sportSlug } }) : null;
  const bets = await prisma.bet.findMany({
    where: sport ? { sportId: sport.id } : {},
    include: { sport: true, lessonTags: true },
    orderBy: [{ sport: { order: "asc" } }, { eventDate: "asc" }],
  });

  const rows = bets.map((b) => {
    const view = computeBetView(b, b.sport);
    const lessonTagStr = b.lessonTags.map((l) => l.tags).join("; ");
    return {
      Date: b.eventDate.toISOString().split("T")[0],
      Sport: b.sport.name,
      Event: b.event,
      Market: b.market,
      "My Probability %": b.myProbability,
      "My Fair Price": +view.fairPrice.toFixed(4),
      "Required +EV Price": +view.requiredPrice.toFixed(4),
      "Betfair Price Available": b.availablePrice,
      "Bet Placed? (Y/N)": b.placed ? "Y" : "N",
      "Suggested Stake (units)": +b.suggestedStake.toFixed(2),
      "Stake (units)": +b.stake.toFixed(2),
      "Closing Price": b.closingPrice ?? "",
      "CLV %": view.clvPercent != null ? +view.clvPercent.toFixed(2) : "",
      Result: b.result,
      "P&L (units)": b.pnl != null ? +b.pnl.toFixed(2) : "",
      "Divergence Points": +view.divergencePoints.toFixed(1),
      "Divergence Flagged": view.divergenceFlagged ? "Y" : "N",
      "Divergence Justification": b.divergenceJustification ?? "",
      "Lesson Tags": lessonTagStr,
      Notes: b.notes ?? "",
    };
  });

  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, sport?.name ?? "All Bets");

  // Column widths
  const colWidths = [
    12, 14, 30, 20, 16, 16, 18, 20, 16, 20, 16, 14, 8, 10, 12, 18, 20, 30, 25, 30,
  ].map((w) => ({ wch: w }));
  ws["!cols"] = colWidths;

  const buffer = XLSX.write(wb, { type: "buffer", bookType: "xlsx" });
  const filename = sport ? `${sport.slug}-bets.xlsx` : "all-bets.xlsx";

  return new NextResponse(buffer, {
    headers: {
      "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
