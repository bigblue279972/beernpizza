import { redirect } from "next/navigation";

export default async function SportIndexPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  redirect(`/sports/${slug}/entry`);
}
