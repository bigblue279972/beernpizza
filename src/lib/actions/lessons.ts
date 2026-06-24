"use server";

import { revalidatePath } from "next/cache";
import { prisma } from "@/lib/db";

export async function listLessons(filters?: { sportId?: string; query?: string; tag?: string }) {
  return prisma.lesson.findMany({
    where: {
      ...(filters?.sportId ? { sportId: filters.sportId } : {}),
      ...(filters?.query
        ? { OR: [{ text: { contains: filters.query } }, { tags: { contains: filters.query } }] }
        : {}),
      ...(filters?.tag ? { tags: { contains: filters.tag } } : {}),
    },
    include: { sport: true, bets: { select: { id: true, event: true, market: true } } },
    orderBy: { createdAt: "desc" },
  });
}

export async function createLesson(data: {
  sportId?: string;
  text: string;
  tags: string;
  betId?: string;
}) {
  const lesson = await prisma.lesson.create({
    data: {
      sportId: data.sportId ?? null,
      text: data.text.trim(),
      tags: data.tags.trim(),
      ...(data.betId ? { bets: { connect: { id: data.betId } } } : {}),
    },
  });
  revalidatePath("/");
  if (data.sportId) {
    const sport = await prisma.sport.findUnique({ where: { id: data.sportId } });
    if (sport) revalidatePath(`/sports/${sport.slug}/lessons`);
  }
  return lesson;
}

export async function deleteLesson(id: string) {
  await prisma.lesson.delete({ where: { id } });
  revalidatePath("/");
}

export async function getAllTags(): Promise<string[]> {
  const lessons = await prisma.lesson.findMany({ select: { tags: true } });
  const tags = new Set<string>();
  for (const l of lessons) {
    l.tags.split(",").map((t) => t.trim()).filter(Boolean).forEach((t) => tags.add(t));
  }
  return Array.from(tags).sort();
}
