-- AlterTable
ALTER TABLE "Bet" ADD COLUMN "betfairMarketId" TEXT;
ALTER TABLE "Bet" ADD COLUMN "betfairSelectionId" TEXT;

-- CreateTable
CREATE TABLE "BetfairSettings" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "endpoint" TEXT NOT NULL DEFAULT 'AU',
    "appKey" TEXT,
    "username" TEXT,
    "sessionToken" TEXT,
    "sessionTokenAt" DATETIME,
    "updatedAt" DATETIME NOT NULL
);
