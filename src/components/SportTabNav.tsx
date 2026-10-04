"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

interface Tab {
  label: string;
  href: string;
}

export function SportTabNav({ tabs }: { tabs: Tab[] }) {
  const pathname = usePathname();

  return (
    <nav className="flex gap-0 -mb-px">
      {tabs.map((tab) => {
        const isActive = pathname === tab.href || pathname.startsWith(tab.href + "/");
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={clsx(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
              isActive
                ? "border-[var(--blue)] text-[var(--text)]"
                : "border-transparent text-[var(--text-muted)] hover:text-[var(--text)] hover:border-[var(--border)]",
            )}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
