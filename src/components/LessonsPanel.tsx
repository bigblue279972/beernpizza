"use client";

import { useState, useTransition, useMemo } from "react";
import { useRouter } from "next/navigation";
import { createLesson, deleteLesson, updateLesson } from "@/lib/actions/lessons";
import type { Lesson } from "@/generated/prisma";

interface LessonWithRelations extends Lesson {
  sport?: { id: string; name: string; slug: string } | null;
  bets: { id: string; event: string; market: string }[];
}

interface Props {
  sportId: string;
  initialLessons: LessonWithRelations[];
  allTags: string[];
}

const SUGGESTED_TAGS = [
  "overrated-favourite",
  "narrative-bias",
  "model-too-high-underdog",
  "chasing",
  "line-movement-missed",
  "model-vs-market-divergence",
  "liquidity-concern",
  "price-discipline-failure",
];

function fmtDate(d: Date | string): string {
  const date = typeof d === "string" ? new Date(d) : d;
  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function TagPill({ tag, onClick }: { tag: string; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-block rounded-full px-2.5 py-0.5 text-[10px] font-medium border border-[var(--border)] bg-[var(--surface-2)] text-[var(--text-muted)] hover:border-[var(--blue)]/40 hover:text-[var(--blue)] transition-colors cursor-pointer"
    >
      {tag}
    </button>
  );
}

export function LessonsPanel({ sportId, initialLessons, allTags }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  // Filter state
  const [query, setQuery] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);

  // Form state
  const [formText, setFormText] = useState("");
  const [formTags, setFormTags] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState("");
  const [editTags, setEditTags] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  const filtered = useMemo(() => {
    return initialLessons.filter((lesson) => {
      const matchesQuery =
        !query ||
        lesson.text.toLowerCase().includes(query.toLowerCase()) ||
        lesson.tags.toLowerCase().includes(query.toLowerCase());
      const matchesTag =
        !activeTag ||
        lesson.tags
          .split(",")
          .map((t) => t.trim())
          .includes(activeTag);
      return matchesQuery && matchesTag;
    });
  }, [initialLessons, query, activeTag]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!formText.trim()) {
      setFormError("Lesson text is required.");
      return;
    }
    setFormError(null);
    startTransition(async () => {
      try {
        await createLesson({ sportId, text: formText, tags: formTags });
        setFormText("");
        setFormTags("");
        router.refresh();
      } catch (err) {
        setFormError(err instanceof Error ? err.message : "Failed to save lesson.");
      }
    });
  }

  async function handleDelete(id: string) {
    if (!confirm("Delete this lesson? This cannot be undone.")) return;
    startTransition(async () => {
      await deleteLesson(id);
      router.refresh();
    });
  }

  function startEdit(lesson: LessonWithRelations) {
    setEditingId(lesson.id);
    setEditText(lesson.text);
    setEditTags(lesson.tags);
    setEditError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditText("");
    setEditTags("");
    setEditError(null);
  }

  async function handleSaveEdit(id: string) {
    if (!editText.trim()) { setEditError("Lesson text is required."); return; }
    setEditError(null);
    startTransition(async () => {
      try {
        await updateLesson(id, { text: editText, tags: editTags });
        cancelEdit();
        router.refresh();
      } catch (err) {
        setEditError(err instanceof Error ? err.message : "Failed to save.");
      }
    });
  }

  function appendTag(tag: string) {
    const current = formTags
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    if (!current.includes(tag)) {
      setFormTags(current.length > 0 ? `${formTags}, ${tag}` : tag);
    }
  }

  return (
    <div className="space-y-6">
      {/* Add lesson form */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border)] bg-[var(--surface-2)]">
          <h2 className="text-xs font-semibold uppercase tracking-widest text-[var(--text-muted)]">
            Record a Lesson
          </h2>
        </div>
        <form onSubmit={handleCreate} className="px-5 py-4 space-y-3">
          <div>
            <textarea
              value={formText}
              onChange={(e) => setFormText(e.target.value)}
              placeholder="What did you learn? Be specific — describe the bet, the mistake or insight, and what you'd do differently..."
              rows={3}
              required
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors resize-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Tags (comma-separated)
            </label>
            <input
              type="text"
              value={formTags}
              onChange={(e) => setFormTags(e.target.value)}
              placeholder="e.g. narrative-bias, chasing"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors"
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {SUGGESTED_TAGS.map((tag) => (
                <TagPill key={tag} tag={tag} onClick={() => appendTag(tag)} />
              ))}
            </div>
          </div>

          {formError && (
            <p className="text-xs text-[var(--red)]">{formError}</p>
          )}

          <button
            type="submit"
            disabled={isPending}
            className="px-5 py-2 rounded-md bg-[var(--blue)] text-white text-sm font-semibold hover:bg-[var(--blue)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isPending ? "Saving…" : "Save Lesson"}
          </button>
        </form>
      </section>

      {/* Search + filter */}
      <div className="flex gap-3 items-start">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search lessons..."
          className="flex-1 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none transition-colors"
        />
        <select
          value={activeTag ?? ""}
          onChange={(e) => setActiveTag(e.target.value || null)}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--blue)] focus:outline-none transition-colors"
        >
          <option value="">All tags</option>
          {allTags.map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
        </select>
      </div>

      {/* Tag cloud */}
      {allTags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setActiveTag(null)}
            className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-medium border transition-colors ${
              activeTag === null
                ? "border-[var(--blue)] text-[var(--blue)] bg-[var(--blue)]/10"
                : "border-[var(--border)] text-[var(--text-muted)] bg-[var(--surface-2)] hover:border-[var(--blue)]/40"
            }`}
          >
            All
          </button>
          {allTags.map((tag) => (
            <button
              key={tag}
              type="button"
              onClick={() => setActiveTag(activeTag === tag ? null : tag)}
              className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-medium border transition-colors ${
                activeTag === tag
                  ? "border-[var(--blue)] text-[var(--blue)] bg-[var(--blue)]/10"
                  : "border-[var(--border)] text-[var(--text-muted)] bg-[var(--surface-2)] hover:border-[var(--blue)]/40 hover:text-[var(--blue)]"
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      )}

      {/* Lessons list */}
      {filtered.length === 0 ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-6 py-8 text-center">
          <p className="text-[var(--text-muted)] text-sm">
            {initialLessons.length === 0
              ? "No lessons recorded yet. Add your first lesson above."
              : "No lessons match the current filter."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((lesson) => {
            const tags = lesson.tags
              .split(",")
              .map((t) => t.trim())
              .filter(Boolean);

            if (editingId === lesson.id) {
              return (
                <div key={lesson.id} className="rounded-lg border border-[var(--blue)]/40 bg-[var(--surface)] px-5 py-4">
                  <div className="space-y-2">
                    <textarea
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      rows={3}
                      className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--text-muted)] focus:border-[var(--blue)] focus:outline-none resize-none"
                    />
                    <div>
                      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1">Tags (comma-separated)</label>
                      <input
                        type="text"
                        value={editTags}
                        onChange={(e) => setEditTags(e.target.value)}
                        className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)] focus:border-[var(--blue)] focus:outline-none"
                      />
                    </div>
                    {editError && <p className="text-xs text-[var(--red)]">{editError}</p>}
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSaveEdit(lesson.id)}
                        disabled={isPending}
                        className="px-3 py-1.5 rounded bg-[var(--blue)] text-white text-xs font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
                      >
                        {isPending ? "Saving…" : "Save"}
                      </button>
                      <button
                        onClick={cancelEdit}
                        className="px-3 py-1.5 rounded border border-[var(--border)] text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              );
            }

            return (
              <div
                key={lesson.id}
                className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-5 py-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-[var(--text)] leading-relaxed flex-1">{lesson.text}</p>
                  <div className="flex items-center gap-2 shrink-0 mt-0.5">
                    <button
                      onClick={() => startEdit(lesson)}
                      className="text-[10px] text-[var(--text-muted)] hover:text-[var(--blue)] transition-colors"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(lesson.id)}
                      disabled={isPending}
                      className="text-[10px] text-[var(--text-muted)] hover:text-[var(--red)] transition-colors disabled:opacity-50"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {tags.length > 0 && (
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {tags.map((tag) => (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => setActiveTag(activeTag === tag ? null : tag)}
                        className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium border transition-colors ${
                          activeTag === tag
                            ? "border-[var(--blue)]/60 text-[var(--blue)] bg-[var(--blue)]/10"
                            : "border-[var(--border)] text-[var(--text-muted)] bg-[var(--surface-2)] hover:border-[var(--blue)]/40"
                        }`}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                )}

                <div className="mt-3 flex items-center justify-between">
                  <span className="text-[10px] text-[var(--text-muted)]">
                    {fmtDate(lesson.createdAt)}
                  </span>
                  {lesson.bets.length > 0 && (
                    <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                      <span>Linked bets:</span>
                      {lesson.bets.map((b) => (
                        <span
                          key={b.id}
                          className="rounded px-1.5 py-0.5 bg-[var(--surface-2)] border border-[var(--border)]"
                          title={b.market}
                        >
                          {b.event}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
