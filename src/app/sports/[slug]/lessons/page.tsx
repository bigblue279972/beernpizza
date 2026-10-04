import { getSportBySlug } from "@/lib/actions/sports";
import { listLessons, getAllTags } from "@/lib/actions/lessons";
import { notFound } from "next/navigation";
import { LessonsPanel } from "@/components/LessonsPanel";

export default async function LessonsPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const sport = await getSportBySlug(slug);
  if (!sport) notFound();

  const [lessons, allTags] = await Promise.all([
    listLessons({ sportId: sport.id }),
    getAllTags(),
  ]);

  return (
    <LessonsPanel
      sportId={sport.id}
      initialLessons={lessons}
      allTags={allTags}
    />
  );
}
