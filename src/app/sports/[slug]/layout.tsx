import { getSportBySlug } from "@/lib/actions/sports";
import { notFound } from "next/navigation";
import { SportTabNav } from "@/components/SportTabNav";

export default async function SportLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const sport = await getSportBySlug(slug);
  if (!sport) notFound();

  const tabs = [
    { label: "Entry", href: `/sports/${slug}/entry` },
    { label: "Sheet", href: `/sports/${slug}/sheet` },
    { label: "Lessons", href: `/sports/${slug}/lessons` },
  ];

  return (
    <div className="flex flex-col min-h-screen">
      <div className="px-6 pt-8 pb-0 border-b border-[var(--border)] bg-[var(--surface)]">
        <div className="max-w-6xl mx-auto">
          <div className="mb-4">
            <p className="text-xs text-[var(--text-muted)] uppercase tracking-widest font-medium mb-1">
              Sport Module
            </p>
            <h1 className="text-2xl font-bold text-[var(--text)]">{sport.name}</h1>
          </div>
          <SportTabNav tabs={tabs} />
        </div>
      </div>
      <div className="flex-1 max-w-6xl mx-auto w-full px-6 py-6">{children}</div>
    </div>
  );
}
