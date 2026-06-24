"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

export interface NavSport {
  id: string;
  name: string;
  slug: string;
}

const TOP_LINKS = [
  { href: "/", label: "CLV Dashboard", icon: "◎" },
  { href: "/sports", label: "Sports", icon: "⚽" },
  { href: "/bankroll", label: "Bankroll", icon: "₿" },
  { href: "/research", label: "Research Links", icon: "🔗" },
  { href: "/settings", label: "Settings", icon: "⚙" },
];

function NavLink({
  href,
  label,
  icon,
  active,
}: {
  href: string;
  label: string;
  icon: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={clsx(
        "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
        active
          ? "bg-[var(--surface-2)] text-[var(--text)] font-medium"
          : "text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
      )}
    >
      <span className="text-base leading-none w-5 text-center select-none">{icon}</span>
      <span className="truncate">{label}</span>
    </Link>
  );
}

export function Nav({ sports }: { sports: NavSport[] }) {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 flex flex-col border-r border-[var(--border)] bg-[var(--surface)] h-screen sticky top-0 overflow-y-auto">
      <div className="px-4 py-4 border-b border-[var(--border)]">
        <span className="text-xs font-bold tracking-widest text-[var(--text-muted)] uppercase">
          BeerNPizza CLV
        </span>
      </div>

      <nav className="flex flex-col gap-0.5 px-2 py-3">
        {TOP_LINKS.map((l) => (
          <NavLink
            key={l.href}
            href={l.href}
            label={l.label}
            icon={l.icon}
            active={l.href === "/" ? pathname === "/" : pathname.startsWith(l.href)}
          />
        ))}
      </nav>

      {sports.length > 0 && (
        <div className="px-2 pb-4 mt-1 border-t border-[var(--border)] pt-3">
          <p className="px-3 mb-1.5 text-[10px] uppercase tracking-widest text-[var(--text-muted)] font-semibold">
            Sport Modules
          </p>
          <div className="flex flex-col gap-0.5">
            {sports.map((s) => (
              <NavLink
                key={s.id}
                href={`/sports/${s.slug}`}
                label={s.name}
                icon="·"
                active={pathname.startsWith(`/sports/${s.slug}`)}
              />
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
