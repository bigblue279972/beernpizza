import { PrismaClient } from "../src/generated/prisma";

const prisma = new PrismaClient();

const DEFAULT_SPORTS = [
  "AFL",
  "Horse Racing",
  "EPL/Football",
  "NFL",
  "NBA",
  "MLB",
  "Tennis",
  "Cricket",
  "Golf",
  "NHL",
];

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

async function main() {
  for (let i = 0; i < DEFAULT_SPORTS.length; i++) {
    const name = DEFAULT_SPORTS[i];
    await prisma.sport.upsert({
      where: { name },
      update: {},
      create: { name, slug: slugify(name), order: i },
    });
  }

  const settingsCount = await prisma.bankrollSettings.count();
  if (settingsCount === 0) {
    await prisma.bankrollSettings.create({ data: {} });
  }

  console.log("Seed complete.");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
