"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createResearchLink, deleteResearchLink, updateResearchLink } from "@/lib/actions/research";

type ResearchLink = {
  id: string;
  sportId: string | null;
  sport?: { name: string; slug: string } | null;
  label: string;
  url: string;
  category: string;
  order: number;
};

type Sport = {
  id: string;
  name: string;
  slug: string;
};

const CATEGORIES = ["EXCHANGE", "STATS", "NEWS", "SPREADSHEET", "OTHER"] as const;
type Category = typeof CATEGORIES[number];

const CATEGORY_LABELS: Record<string, string> = {
  EXCHANGE: "Exchange",
  STATS: "Stats",
  NEWS: "News",
  SPREADSHEET: "Spreadsheet",
  OTHER: "Other",
};

const CATEGORY_COLORS: Record<string, string> = {
  EXCHANGE: "text-[var(--blue)] bg-[var(--blue)]/10 border-[var(--blue)]/20",
  STATS: "text-[var(--green)] bg-[var(--green)]/10 border-[var(--green)]/20",
  NEWS: "text-[var(--amber)] bg-[var(--amber)]/10 border-[var(--amber)]/20",
  SPREADSHEET: "text-[var(--text-muted)] bg-[var(--surface-2)] border-[var(--border)]",
  OTHER: "text-[var(--text-muted)] bg-[var(--surface-2)] border-[var(--border)]",
};

const inputClass =
  "w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--blue)] disabled:opacity-50";
const selectClass =
  "w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text)] focus:outline-none focus:border-[var(--blue)] disabled:opacity-50 appearance-none";

function AddLinkForm({ sports }: { sports: Sport[] }) {
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [category, setCategory] = useState<string>("EXCHANGE");
  const [sportId, setSportId] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess(false);
    if (!label.trim()) { setError("Label is required."); return; }
    if (!url.trim()) { setError("URL is required."); return; }

    startTransition(async () => {
      try {
        await createResearchLink({
          label: label.trim(),
          url: url.trim(),
          category,
          sportId: sportId || undefined,
        });
        setLabel("");
        setUrl("");
        setCategory("EXCHANGE");
        setSportId("");
        setSuccess(true);
        setTimeout(() => setSuccess(false), 3000);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to add link.");
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
      <h2 className="text-sm font-semibold text-[var(--text)] mb-4">Add Link</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-xs text-[var(--text-muted)] mb-1">Label</label>
          <input
            type="text"
            className={inputClass}
            placeholder="e.g. Betfair Exchange"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            disabled={isPending}
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--text-muted)] mb-1">URL</label>
          <input
            type="url"
            className={inputClass}
            placeholder="https://..."
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            disabled={isPending}
          />
        </div>
        <div>
          <label className="block text-xs text-[var(--text-muted)] mb-1">Category</label>
          <select
            className={selectClass}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            disabled={isPending}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-[var(--text-muted)] mb-1">Sport</label>
          <select
            className={selectClass}
            value={sportId}
            onChange={(e) => setSportId(e.target.value)}
            disabled={isPending}
          >
            <option value="">Global</option>
            {sports.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
      </div>
      {error && <p className="text-xs text-[var(--red)] mb-3">{error}</p>}
      {success && <p className="text-xs text-[var(--green)] mb-3">Link added successfully.</p>}
      <button
        type="submit"
        disabled={isPending}
        className="px-4 py-2 rounded-md bg-[var(--blue)] text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
      >
        {isPending ? "Adding…" : "Add Link"}
      </button>
    </form>
  );
}

function LinkCard({ link, sports }: { link: ResearchLink; sports: Sport[] }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(link.label);
  const [url, setUrl] = useState(link.url);
  const [category, setCategory] = useState(link.category);
  const [sportId, setSportId] = useState(link.sportId ?? "");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!label.trim()) { setError("Label is required."); return; }
    if (!url.trim()) { setError("URL is required."); return; }
    setError("");
    startTransition(async () => {
      try {
        await updateResearchLink(link.id, {
          label: label.trim(),
          url: url.trim(),
          category,
          sportId: sportId || null,
        });
        setEditing(false);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to save.");
      }
    });
  }

  function handleDelete() {
    if (!window.confirm("Delete this link?")) return;
    startTransition(async () => {
      try {
        await deleteResearchLink(link.id);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete.");
      }
    });
  }

  if (editing) {
    return (
      <div className="rounded-lg border border-[var(--blue)]/40 bg-[var(--surface)] p-4 flex flex-col gap-3">
        <form onSubmit={handleSave} className="flex flex-col gap-2">
          <div>
            <label className="block text-xs text-[var(--text-muted)] mb-1">Label</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className={inputClass}
              disabled={isPending}
            />
          </div>
          <div>
            <label className="block text-xs text-[var(--text-muted)] mb-1">URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className={inputClass}
              disabled={isPending}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-[var(--text-muted)] mb-1">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className={selectClass}
                disabled={isPending}
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--text-muted)] mb-1">Sport</label>
              <select
                value={sportId}
                onChange={(e) => setSportId(e.target.value)}
                className={selectClass}
                disabled={isPending}
              >
                <option value="">Global</option>
                {sports.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          </div>
          {error && <p className="text-xs text-[var(--red)]">{error}</p>}
          <div className="flex gap-2 mt-1">
            <button
              type="submit"
              disabled={isPending}
              className="px-3 py-1.5 rounded bg-[var(--blue)] text-white text-xs font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {isPending ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={() => { setEditing(false); setLabel(link.label); setUrl(link.url); setCategory(link.category); setSportId(link.sportId ?? ""); setError(""); }}
              className="px-3 py-1.5 rounded border border-[var(--border)] text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    );
  }

  const categoryColor = CATEGORY_COLORS[link.category] ?? CATEGORY_COLORS.OTHER;
  const sportLabel = link.sport ? link.sport.name : "Global";
  const isGlobal = !link.sportId;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4 flex flex-col gap-3 hover:border-[var(--blue)]/30 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[var(--text)] truncate">{link.label}</p>
          <p className="text-xs text-[var(--text-muted)] truncate mt-0.5">{link.url}</p>
        </div>
        <a
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 text-[var(--blue)] hover:opacity-80 transition-opacity text-base leading-none mt-0.5"
          title={`Open ${link.label}`}
          aria-label={`Open ${link.label} in new tab`}
        >
          ↗
        </a>
      </div>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${categoryColor}`}>
            {CATEGORY_LABELS[link.category] ?? link.category}
          </span>
          <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${
            isGlobal
              ? "border-[var(--border)] text-[var(--text-muted)] bg-[var(--surface-2)]"
              : "border-[var(--green)]/20 text-[var(--green)] bg-[var(--green)]/10"
          }`}>
            {sportLabel}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setEditing(true)}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--blue)] transition-colors"
          >
            Edit
          </button>
          <button
            onClick={handleDelete}
            disabled={isPending}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--red)] transition-colors disabled:opacity-50"
          >
            {isPending ? "…" : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
}

function LinksGrid({ links, sports }: { links: ResearchLink[]; sports: Sport[] }) {
  if (links.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-8 text-center">
        <p className="text-sm text-[var(--text-muted)]">No links yet.</p>
        <p className="text-xs text-[var(--text-muted)] mt-1">Add your first link using the form above.</p>
      </div>
    );
  }

  // Group by category
  const grouped: Record<string, { global: ResearchLink[]; sport: ResearchLink[] }> = {};
  for (const link of links) {
    if (!grouped[link.category]) {
      grouped[link.category] = { global: [], sport: [] };
    }
    if (link.sportId) {
      grouped[link.category].sport.push(link);
    } else {
      grouped[link.category].global.push(link);
    }
  }

  const orderedCats = [
    ...CATEGORIES.filter((c) => grouped[c]),
    ...Object.keys(grouped).filter((c) => !(CATEGORIES as readonly string[]).includes(c)),
  ];

  return (
    <div className="space-y-6">
      {orderedCats.map((cat) => {
        const { global: globalLinks, sport: sportLinks } = grouped[cat];
        const allLinks = [...globalLinks, ...sportLinks];
        if (allLinks.length === 0) return null;
        return (
          <div key={cat}>
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-3">
              {CATEGORY_LABELS[cat] ?? cat}
              <span className="ml-2 font-normal normal-case">({allLinks.length})</span>
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {globalLinks.map((link) => <LinkCard key={link.id} link={link} sports={sports} />)}
              {sportLinks.map((link) => <LinkCard key={link.id} link={link} sports={sports} />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ResearchPageClient({
  links,
  sports,
}: {
  links: ResearchLink[];
  sports: Sport[];
}) {
  return (
    <div className="px-6 py-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-[var(--text)] mb-0.5">Research Links</h1>
        <p className="text-sm text-[var(--text-muted)]">
          Bookmarked links to your data sources, exchange, spreadsheets, and news feeds.
          Opening links here launches them directly — no data is shared with external services.
        </p>
      </div>

      <div className="mb-6">
        <AddLinkForm sports={sports} />
      </div>

      <div className="rounded-lg border border-[var(--blue)]/20 bg-[var(--blue)]/5 px-4 py-3 mb-6 flex gap-3 items-start">
        <span className="text-[var(--blue)] text-base mt-0.5 shrink-0">◎</span>
        <p className="text-xs text-[var(--text-muted)] leading-relaxed">
          This panel contains direct links to your tools and information sources. It is the only integration
          with external services in this app — you open the links manually, deliberately.
        </p>
      </div>

      <LinksGrid links={links} sports={sports} />
    </div>
  );
}
