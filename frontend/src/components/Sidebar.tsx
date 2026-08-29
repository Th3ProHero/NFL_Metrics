"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/* ── Icon SVGs (inline to avoid extra deps) ──────────────────────────────── */

const IconLive = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M5.636 18.364a9 9 0 1112.728 0M9.172 14.828a5 5 0 017.656 0" />
    <circle cx="12" cy="18" r="1" fill="currentColor" />
  </svg>
);

const IconAnalysis = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M3 13h2l3-8 4 16 3-8h2M21 13h-2" />
  </svg>
);

const IconTracker = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M9 7h6m-6 4h6m-6 4h4M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z" />
  </svg>
);

const IconBook = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
  </svg>
);

const IconTrophy = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M8 21h8m-4-4v4m-4.5-8.5c-2.5 0-4.5-1-4.5-4V5h4m9 3.5c2.5 0 4.5-1 4.5-4V5h-4M7 5h10a1 1 0 011 1v3c0 3.5-2.5 6-5 6h-2c-2.5 0-5-2.5-5-6V6a1 1 0 011-1z" />
  </svg>
);

const IconTeam = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round"
      d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
  </svg>
);

const IconFootball = () => (
  <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
    <ellipse cx="12" cy="12" rx="9" ry="6" transform="rotate(-45 12 12)"
      className="text-accent-blue" fill="currentColor" fillOpacity={0.15} />
    <path d="M15.5 8.5l-7 7M10 8l-2 2M16 14l-2 2" strokeLinecap="round" />
  </svg>
);

/* ── Navigation Items ────────────────────────────────────────────────────── */

const navItems = [
  { href: "/live",     label: "Live Games",    icon: IconLive },
  { href: "/analysis", label: "Analysis",      icon: IconAnalysis },
  { href: "/teams",    label: "Teams",         icon: IconTeam },
  { href: "/tracker",  label: "Bet Tracker",   icon: IconTracker },
  { href: "/pool",     label: "Friends Pool",  icon: IconTrophy },
  { href: "/guide",    label: "Betting Guide",  icon: IconBook },
];

/* ── Sidebar Component ───────────────────────────────────────────────────── */

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-40 w-64 flex flex-col
                      bg-surface-800/40 backdrop-blur-2xl border-r border-white/[0.06]">
      {/* ── Brand ── */}
      <Link href="/" className="flex items-center gap-3 px-6 py-6 group">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl
                        bg-gradient-to-br from-accent-blue to-accent-purple
                        shadow-glow group-hover:shadow-glow transition-shadow duration-300">
          <IconFootball />
        </div>
        <div>
          <h1 className="text-lg font-display font-bold tracking-tight text-white">
            NFL BetMaster
          </h1>
          <p className="text-[10px] uppercase tracking-widest text-accent-blue/70 font-semibold">
            Analytics Hub
          </p>
        </div>
      </Link>

      {/* ── Separator ── */}
      <div className="mx-4 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

      {/* ── Navigation ── */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || pathname?.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={`nav-link ${isActive ? "nav-link-active" : ""}`}
            >
              <Icon />
              <span className="text-sm font-medium">{label}</span>
              {href === "/live" && (
                <span className="ml-auto">
                  <span className="live-dot" />
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* ── Footer ── */}
      <div className="px-5 py-4 border-t border-white/[0.06]">
        <p className="text-[11px] text-gray-500 leading-relaxed">
          Self-hosted · 100% Free
          <br />
          Data via ESPN &amp; The Odds API
        </p>
      </div>
    </aside>
  );
}
