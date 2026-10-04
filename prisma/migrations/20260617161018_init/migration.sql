-- CreateTable
CREATE TABLE "Sport" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "order" INTEGER NOT NULL DEFAULT 0,
    "archived" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "defaultMarginBuffer" REAL NOT NULL DEFAULT 0.05,
    "divergenceThreshold" REAL NOT NULL DEFAULT 8,
    "perBetCapPct" REAL NOT NULL DEFAULT 2
);

-- CreateTable
CREATE TABLE "Bet" (
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
    "stakeOverride" REAL,
    "stakeCapPct" REAL NOT NULL,
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

-- CreateTable
CREATE TABLE "Lesson" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sportId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "text" TEXT NOT NULL,
    "tags" TEXT NOT NULL,
    CONSTRAINT "Lesson_sportId_fkey" FOREIGN KEY ("sportId") REFERENCES "Sport" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "BankrollSettings" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "startingBalance" REAL NOT NULL DEFAULT 1000,
    "currentBalance" REAL NOT NULL DEFAULT 1000,
    "hardStopLossPct" REAL NOT NULL DEFAULT 20,
    "hardStopLossAmount" REAL,
    "defaultKellyDivisor" REAL NOT NULL DEFAULT 4,
    "globalPerBetCapPct" REAL NOT NULL DEFAULT 2,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "BankrollTransaction" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "type" TEXT NOT NULL,
    "amount" REAL NOT NULL,
    "note" TEXT
);

-- CreateTable
CREATE TABLE "ResearchLink" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sportId" TEXT,
    "label" TEXT NOT NULL,
    "url" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "order" INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT "ResearchLink_sportId_fkey" FOREIGN KEY ("sportId") REFERENCES "Sport" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "_BetLessons" (
    "A" TEXT NOT NULL,
    "B" TEXT NOT NULL,
    CONSTRAINT "_BetLessons_A_fkey" FOREIGN KEY ("A") REFERENCES "Bet" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "_BetLessons_B_fkey" FOREIGN KEY ("B") REFERENCES "Lesson" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE UNIQUE INDEX "Sport_name_key" ON "Sport"("name");

-- CreateIndex
CREATE UNIQUE INDEX "Sport_slug_key" ON "Sport"("slug");

-- CreateIndex
CREATE UNIQUE INDEX "_BetLessons_AB_unique" ON "_BetLessons"("A", "B");

-- CreateIndex
CREATE INDEX "_BetLessons_B_index" ON "_BetLessons"("B");
