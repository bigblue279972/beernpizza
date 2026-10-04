/*
  Warnings:

  - You are about to drop the column `stakeCapPct` on the `Bet` table. All the data in the column will be lost.
  - You are about to drop the column `stakeOverride` on the `Bet` table. All the data in the column will be lost.
  - Added the required column `capPct` to the `Bet` table without a default value. This is not possible if the table is not empty.
  - Added the required column `suggestedStake` to the `Bet` table without a default value. This is not possible if the table is not empty.

*/
-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Bet" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sportId" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "eventDate" DATETIME NOT NULL,
    "event" TEXT NOT NULL,
    "market" TEXT NOT NULL,
    "myProbability" REAL NOT NULL,
    "marginBuffer" REAL NOT NULL,
    "availablePrice" REAL NOT NULL,
    "bankrollAtEntry" REAL NOT NULL,
    "kellyDivisor" REAL NOT NULL DEFAULT 4,
    "capPct" REAL NOT NULL,
    "suggestedStake" REAL NOT NULL,
    "stake" REAL NOT NULL DEFAULT 0,
    "checklistPriceMet" BOOLEAN NOT NULL DEFAULT false,
    "checklistLiquidMarket" BOOLEAN NOT NULL DEFAULT false,
    "checklistNotChasing" BOOLEAN NOT NULL DEFAULT false,
    "divergenceJustification" TEXT,
    "placed" BOOLEAN NOT NULL DEFAULT false,
    "closingPrice" REAL,
    "result" TEXT NOT NULL DEFAULT 'PENDING',
    "pnl" REAL,
    "notes" TEXT,
    CONSTRAINT "Bet_sportId_fkey" FOREIGN KEY ("sportId") REFERENCES "Sport" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_Bet" ("availablePrice", "bankrollAtEntry", "checklistLiquidMarket", "checklistNotChasing", "checklistPriceMet", "closingPrice", "createdAt", "divergenceJustification", "event", "eventDate", "id", "kellyDivisor", "marginBuffer", "market", "myProbability", "notes", "placed", "pnl", "result", "sportId") SELECT "availablePrice", "bankrollAtEntry", "checklistLiquidMarket", "checklistNotChasing", "checklistPriceMet", "closingPrice", "createdAt", "divergenceJustification", "event", "eventDate", "id", "kellyDivisor", "marginBuffer", "market", "myProbability", "notes", "placed", "pnl", "result", "sportId" FROM "Bet";
DROP TABLE "Bet";
ALTER TABLE "new_Bet" RENAME TO "Bet";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
