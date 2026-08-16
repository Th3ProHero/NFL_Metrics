"use client";

import { useEffect, useState } from "react";
import LiveGamesBoard from "@/components/LiveGamesBoard";
import { GameCard } from "@/components/LiveGamesBoard";
import { fetchGames, type Game } from "@/lib/api";

export default function LivePage() {
  const [upcomingGames, setUpcomingGames] = useState<Game[]>([]);
  const [completedGames, setCompletedGames] = useState<Game[]>([]);
  const [loadingUpcoming, setLoadingUpcoming] = useState(true);
  const [loadingCompleted, setLoadingCompleted] = useState(true);

  useEffect(() => {
    fetchGames({ status: "pre", limit: "30" })
      .then((games) => {
        // Sort by start_time ascending (soonest first)
        games.sort((a, b) => {
          const ta = a.start_time ? new Date(a.start_time).getTime() : Infinity;
          const tb = b.start_time ? new Date(b.start_time).getTime() : Infinity;
          return ta - tb;
        });
        setUpcomingGames(games);
      })
      .catch(console.error)
      .finally(() => setLoadingUpcoming(false));

    fetchGames({ status: "post", limit: "30" })
      .then(setCompletedGames)
      .catch(console.error)
      .finally(() => setLoadingCompleted(false));
  }, []);

  return (
    <div>
      {/* ── Page Header ── */}
      <div className="mb-8">
        <h1 className="text-3xl font-display font-bold text-white tracking-tight">
          Live Scoreboard
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Real-time scores, odds, and field position updates via SSE
        </p>
      </div>

      {/* ── Live Board ── */}
      <LiveGamesBoard />

      {/* ── Upcoming / Scheduled Games ── */}
      <section className="mt-12">
        <h2 className="text-xl font-display font-bold text-white mb-2 uppercase tracking-wider flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-nfl-pending" />
          Upcoming Games
        </h2>
        <p className="text-xs text-gray-500 mb-5">
          Scheduled games — click any card to run a Monte Carlo simulation and find +EV bets.
        </p>

        {loadingUpcoming ? (
          <div className="flex justify-center py-12">
            <div className="w-7 h-7 border-2 border-nfl-pending/30 border-t-nfl-pending rounded-full animate-spin" />
          </div>
        ) : upcomingGames.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {upcomingGames.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
        ) : (
          <EmptyState emoji="📅" message="No upcoming games scheduled at this time." />
        )}
      </section>

      {/* ── Completed / Recent Games ── */}
      <section className="mt-12 pb-16">
        <h2 className="text-xl font-display font-bold text-white mb-2 uppercase tracking-wider flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-gray-500" />
          Recent Results
        </h2>
        <p className="text-xs text-gray-500 mb-5">
          Completed games with final scores. Click to review simulation accuracy.
        </p>

        {loadingCompleted ? (
          <div className="flex justify-center py-12">
            <div className="w-7 h-7 border-2 border-gray-600/30 border-t-gray-500 rounded-full animate-spin" />
          </div>
        ) : completedGames.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {completedGames.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
        ) : (
          <EmptyState emoji="🏈" message="No completed games found." />
        )}
      </section>
    </div>
  );
}

function EmptyState({ emoji, message }: { emoji: string; message: string }) {
  return (
    <div className="glass-card p-10 flex flex-col items-center justify-center text-center">
      <span className="text-4xl mb-3">{emoji}</span>
      <p className="text-gray-400 font-medium">{message}</p>
    </div>
  );
}
