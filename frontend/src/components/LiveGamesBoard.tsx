"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { LIVE_GAMES_SSE_URL, type Game } from "@/lib/api";

/* ── Helper: format American odds ────────────────────────────────────────── */

function fmtOdds(value: number | null | undefined): string {
  if (value == null) return "—";
  return value > 0 ? `+${value}` : `${value}`;
}

/* ── Helper: quarter label ───────────────────────────────────────────────── */

function quarterLabel(q: number | null): string {
  if (!q) return "";
  if (q <= 4) return `Q${q}`;
  return "OT";
}

/* ── Game Card Component ─────────────────────────────────────────────────── */

function GameCard({ game }: { game: Game }) {
  const isLive = game.status === "in_progress";
  const isPre = game.status === "pre";
  const startDate = game.start_time ? new Date(game.start_time) : null;

  return (
    <div
      className={`glass-card p-5 animate-fade-in relative overflow-hidden
        ${isLive ? "ring-1 ring-accent-blue/30" : ""}`}
    >
      {/* Live glow accent */}
      {isLive && (
        <div className="absolute top-0 left-0 right-0 h-[2px]
                        bg-gradient-to-r from-accent-blue via-accent-cyan to-accent-purple" />
      )}

      {/* ── Header: Status / Quarter / Clock ── */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          {isLive && <span className="live-dot" />}
          <span className={`text-xs font-semibold uppercase tracking-wider
            ${isLive ? "text-nfl-win" : isPre ? "text-nfl-pending" : "text-gray-500"}`}>
            {isLive
              ? `${quarterLabel(game.quarter)} ${game.clock || ""}`
              : isPre
                ? "Upcoming"
                : "Final"}
          </span>
        </div>
        {game.broadcast && (
          <span className="text-[10px] uppercase tracking-widest text-gray-500 font-medium">
            {game.broadcast}
          </span>
        )}
      </div>

      {/* ── Teams & Scores ── */}
      <div className="space-y-3">
        {/* Away team */}
        <TeamRow
          team={game.away_team}
          score={game.away_score}
          hasPossession={game.possession_team_id === game.away_team?.id}
          isLive={isLive}
          isWinning={game.away_score > game.home_score}
        />
        {/* Home team */}
        <TeamRow
          team={game.home_team}
          score={game.home_score}
          hasPossession={game.possession_team_id === game.home_team?.id}
          isLive={isLive}
          isWinning={game.home_score > game.away_score}
        />
      </div>

      {/* ── Down & Distance / Field Position ── */}
      {isLive && game.down && (
        <div className="mt-4 pt-3 border-t border-white/[0.06]">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1.5">
            <span className="font-medium">
              {game.down && game.distance
                ? `${game.down}${ordinal(game.down)} & ${game.distance}`
                : ""}
            </span>
            {game.yard_line != null && (
              <span>
                {game.yard_line_territory || ""} {game.yard_line}
              </span>
            )}
          </div>
          {game.yard_line != null && (
            <div className="field-bar">
              <div
                className="field-bar-fill"
                style={{ width: `${Math.min(game.yard_line, 100)}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* ── Pre-game: Start time ── */}
      {isPre && startDate && (
        <div className="mt-4 pt-3 border-t border-white/[0.06]">
          <p className="text-xs text-gray-500">
            {startDate.toLocaleDateString("en-US", {
              weekday: "short", month: "short", day: "numeric",
            })}{" "}
            ·{" "}
            {startDate.toLocaleTimeString("en-US", {
              hour: "numeric", minute: "2-digit",
            })}
          </p>
        </div>
      )}

      {/* ── Odds Row ── */}
      {game.latest_odds && (
        <div className="mt-3 pt-3 border-t border-white/[0.06]
                        grid grid-cols-3 gap-2 text-center">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Spread</p>
            <p className="text-xs font-semibold text-gray-300">
              {game.latest_odds.spread != null ? (game.latest_odds.spread > 0 ? `+${game.latest_odds.spread}` : game.latest_odds.spread) : "—"}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">O/U</p>
            <p className="text-xs font-semibold text-gray-300">
              {game.latest_odds.over_under ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">ML</p>
            <p className="text-xs font-semibold text-gray-300">
              {fmtOdds(game.latest_odds.home_moneyline)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Team Row ────────────────────────────────────────────────────────────── */

function TeamRow({
  team,
  score,
  hasPossession,
  isLive,
  isWinning,
}: {
  team: Game["home_team"];
  score: number;
  hasPossession: boolean;
  isLive: boolean;
  isWinning: boolean;
}) {
  const [prevScore, setPrevScore] = useState(score);
  const [pop, setPop] = useState(false);

  useEffect(() => {
    if (score !== prevScore) {
      setPop(true);
      setPrevScore(score);
      const t = setTimeout(() => setPop(false), 400);
      return () => clearTimeout(t);
    }
  }, [score, prevScore]);

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        {/* Possession indicator */}
        <div className={`w-1 h-8 rounded-full transition-colors duration-300
          ${hasPossession && isLive ? "bg-accent-blue" : "bg-transparent"}`}
        />
        {/* Team logo */}
        {team?.logo_url ? (
          <Image
            src={team.logo_url}
            alt={team.abbreviation}
            width={32}
            height={32}
            className="rounded"
            unoptimized
          />
        ) : (
          <div className="w-8 h-8 rounded bg-surface-600 flex items-center justify-center text-xs font-bold text-gray-400">
            {team?.abbreviation?.slice(0, 2) || "??"}
          </div>
        )}
        {/* Team name */}
        <div>
          <p className={`text-sm font-semibold
            ${isWinning ? "text-white" : "text-gray-400"}`}>
            {team?.abbreviation || "TBD"}
          </p>
          <p className="text-[11px] text-gray-500">{team?.name || ""}</p>
        </div>
      </div>
      {/* Score */}
      <span className={`text-2xl font-display font-bold tabular-nums
        ${isWinning ? "text-white" : "text-gray-500"}
        ${pop ? "score-change" : ""}`}>
        {score}
      </span>
    </div>
  );
}

/* ── Ordinal helper ──────────────────────────────────────────────────────── */

function ordinal(n: number): string {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return s[(v - 20) % 10] || s[v] || s[0];
}

/* ═══════════════════════════════════════════════════════════════════════════
   LiveGamesBoard — Main Export
   ═══════════════════════════════════════════════════════════════════════════ */

export default function LiveGamesBoard() {
  const [games, setGames] = useState<Game[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const retryCount = useRef(0);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    function connect() {
      const es = new EventSource(LIVE_GAMES_SSE_URL);
      eventSourceRef.current = es;

      es.onopen = () => {
        setConnected(true);
        setError(null);
        retryCount.current = 0;
      };

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (Array.isArray(data)) {
            setGames(data);
          }
        } catch {
          console.warn("Failed to parse SSE data:", event.data);
        }
      };

      es.onerror = () => {
        es.close();
        setConnected(false);
        retryCount.current += 1;
        const delay = Math.min(1000 * 2 ** retryCount.current, 30000);
        setError(`Reconnecting in ${Math.round(delay / 1000)}s...`);
        setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const liveGames = games.filter((g) => g.status === "in_progress");
  const upcomingGames = games.filter((g) => g.status === "pre");

  return (
    <div>
      {/* ── Connection Status ── */}
      <div className="flex items-center gap-2 mb-6">
        <div className={`w-2 h-2 rounded-full ${connected ? "bg-nfl-win" : "bg-nfl-loss animate-pulse"}`} />
        <span className="text-xs text-gray-500">
          {connected ? "Connected — Live updates active" : error || "Connecting..."}
        </span>
      </div>

      {/* ── Live Games ── */}
      {liveGames.length > 0 && (
        <section className="mb-10">
          <h2 className="text-sm font-semibold text-nfl-win uppercase tracking-wider mb-4 flex items-center gap-2">
            <span className="live-dot" />
            Live Now · {liveGames.length} Game{liveGames.length > 1 ? "s" : ""}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {liveGames.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
        </section>
      )}

      {/* ── Upcoming Games ── */}
      {upcomingGames.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-nfl-pending uppercase tracking-wider mb-4">
            Upcoming · {upcomingGames.length} Game{upcomingGames.length > 1 ? "s" : ""}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {upcomingGames.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
        </section>
      )}

      {/* ── Empty State ── */}
      {games.length === 0 && connected && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="w-16 h-16 rounded-full bg-surface-700/50 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M15 12H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h3 className="text-lg font-display font-semibold text-gray-400 mb-1">
            No Games Right Now
          </h3>
          <p className="text-sm text-gray-500 max-w-xs">
            The scoreboard will light up automatically when NFL games are scheduled or in progress.
          </p>
        </div>
      )}
    </div>
  );
}
