"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";

export async function listResearchLinks(sportId?: string) {
  return prisma.researchLink.findMany({
    where: sportId ? { OR: [{ sportId }, { sportId: null }] } : { sportId: null },
    include: { sport: true },
    orderBy: [{ sportId: "asc" }, { category: "asc" }, { order: "asc" }],
  });
}

export async function createResearchLink(data: {
  sportId?: string;
  label: string;
  url: string;
  category: string;
}) {
  const count = await prisma.researchLink.count({ where: { sportId: data.sportId ?? null } });
  const link = await prisma.researchLink.create({
    data: {
      sportId: data.sportId ?? null,
      label: data.label.trim(),
      url: data.url.trim(),
      category: data.category,
      order: count,
    },
  });
  revalidatePath("/research");
  return link;
}

export async function deleteResearchLink(id: string) {
  await prisma.researchLink.delete({ where: { id } });
  revalidatePath("/research");
}

export async function updateResearchLink(
  id: string,
  data: { label?: string; url?: string; category?: string; sportId?: string | null },
) {
  const link = await prisma.researchLink.update({
    where: { id },
    data: {
      ...(data.label !== undefined ? { label: data.label.trim() } : {}),
      ...(data.url !== undefined ? { url: data.url.trim() } : {}),
      ...(data.category !== undefined ? { category: data.category } : {}),
      ...("sportId" in data ? { sportId: data.sportId ?? null } : {}),
    },
  });
  revalidatePath("/research");
  return link;
}

export async function updateResearchLinkOrder(ids: string[]) {
  await Promise.all(ids.map((id, i) => prisma.researchLink.update({ where: { id }, data: { order: i } })));
  revalidatePath("/research");
}
