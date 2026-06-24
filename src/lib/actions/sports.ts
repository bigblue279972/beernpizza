"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

export async function getSports(includeArchived = false) {
  return prisma.sport.findMany({
    where: includeArchived ? {} : { archived: false },
    orderBy: { order: "asc" },
  });
}

export async function getSportBySlug(slug: string) {
  return prisma.sport.findUnique({ where: { slug } });
}

export async function createSport(name: string) {
  const trimmed = name.trim();
  if (!trimmed) throw new Error("Sport name is required.");
  const count = await prisma.sport.count();
  const sport = await prisma.sport.create({
    data: { name: trimmed, slug: slugify(trimmed), order: count },
  });
  revalidatePath("/sports");
  revalidatePath("/settings");
  return sport;
}

export async function renameSport(id: string, name: string) {
  const trimmed = name.trim();
  if (!trimmed) throw new Error("Sport name is required.");
  const sport = await prisma.sport.update({
    where: { id },
    data: { name: trimmed, slug: slugify(trimmed) },
  });
  revalidatePath("/sports");
  revalidatePath("/settings");
  return sport;
}

export async function setSportArchived(id: string, archived: boolean) {
  const sport = await prisma.sport.update({ where: { id }, data: { archived } });
  revalidatePath("/sports");
  revalidatePath("/settings");
  return sport;
}

export async function updateSportSettings(
  id: string,
  data: { defaultMarginBuffer?: number; divergenceThreshold?: number; perBetCapPct?: number },
) {
  const sport = await prisma.sport.update({ where: { id }, data });
  revalidatePath("/sports");
  return sport;
}
