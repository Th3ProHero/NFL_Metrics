"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { fetchTeamStats, type TeamStats } from "@/lib/api";
import { GameCard } from "@/components/LiveGamesBoard";

export default function TeamDeepDive({ params }: { params: { id: string } }) {
  const [stats, setStats] = useState<TeamStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTeamStats(Number(params.id))
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) return (
    <div className="flex justify-center py-20">
      <div className="w-8 h-8 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin" />
    </div>
  );

  if (!stats) return <div className="text-white text-center py-20">Team not found</div>;

  const { team, record, points_for, points_against, epa_per_play, pass_epa, rush_epa, defensive_epa, recent_games, upcoming_games } = stats;

  return (
    <div className="max-w-6xl mx-auto space-y-10 pb-20">
      {/* Header */}
      <div className="glass-card p-8 flex flex-col md:flex-row items-center gap-8 relative overflow-hidden">
        {team.primary_color && (
          <div className="absolute top-0 left-0 w-2 h-full" style={{ backgroundColor: `#${team.primary_color.replace('#', '')}` }} />
        )}
        {team.logo_url ? (
          <div className="w-32 h-32 relative shrink-0">
            <Image src={team.logo_url} alt={team.name} fill className="object-contain" unoptimized />
          </div>
        ) : (
          <div className="w-32 h-32 rounded-full bg-surface-700 flex items-center justify-center text-3xl font-bold text-gray-500 shrink-0">
            {team.abbreviation}
          </div>
        )}
        <div className="text-center md:text-left">
          <h1 className="text-4xl font-display font-bold text-white tracking-tight">{team.name}</h1>
          <p className="text-gray-400 mt-2 uppercase tracking-widest text-sm font-semibold">
            {team.conference} {team.division}
          </p>
          <div className="mt-4 inline-flex bg-surface-800 px-5 py-3 rounded-xl border border-white/10 items-center">
            <span className="text-gray-500 uppercase text-xs tracking-widest mr-4">Season Record</span>
            <span className="text-2xl font-bold text-white tabular-nums tracking-wider">{record || "0-0"}</span>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <section>
        <h2 className="text-xl font-display font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-accent-purple" />
          Performance Metrics
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <StatCard title="Points For" value={points_for} suffix="pts" />
          <StatCard title="Points Against" value={points_against} suffix="pts" />
          <StatCard title="Offensive EPA/Play" value={epa_per_play} highlight={true} />
          <StatCard title="Defensive EPA/Play" value={defensive_epa} highlight={true} inverted={true} />
          <StatCard title="Pass EPA/Play" value={pass_epa} />
          <StatCard title="Rush EPA/Play" value={rush_epa} />
        </div>
      </section>

      {/* Upcoming Games */}
      <section>
        <h2 className="text-xl font-display font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-nfl-pending" />
          Next & Live Games
        </h2>
        {upcoming_games && upcoming_games.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {upcoming_games.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
        ) : (
          <div className="glass-card p-10 flex flex-col items-center justify-center text-center">
            <span className="text-4xl mb-3">📅</span>
            <p className="text-gray-400 font-medium">No upcoming or live games scheduled.</p>
          </div>
        )}
      </section>

      {/* Recent Games */}
      <section>
        <h2 className="text-xl font-display font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-gray-500" />
          Recent Games
        </h2>
        {recent_games && recent_games.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recent_games.map((game) => (
              <GameCard key={game.id} game={game} />
            ))}
          </div>
        ) : (
          <div className="glass-card p-10 flex flex-col items-center justify-center text-center">
            <span className="text-4xl mb-3">🏈</span>
            <p className="text-gray-400 font-medium">No recent games found.</p>
          </div>
        )}
      </section>

    </div>
  );
}

function StatCard({ title, value, suffix = "", highlight = false, inverted = false }: { title: string, value: number | null, suffix?: string, highlight?: boolean, inverted?: boolean }) {
  if (value === null) value = 0;
  
  let isPositive = value > 0;
  if (inverted) isPositive = !isPositive; // For defense, negative EPA is good

  return (
    <div className={`glass-card p-5 border-l-4 ${highlight ? (isPositive ? 'border-nfl-win' : 'border-nfl-loss') : 'border-transparent'}`}>
      <h3 className="text-[10px] text-gray-500 uppercase tracking-widest mb-2 leading-tight h-8">{title}</h3>
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-bold tabular-nums ${highlight ? (isPositive ? 'text-nfl-win' : 'text-nfl-loss') : 'text-white'}`}>
          {value > 0 ? "+" : ""}{value.toFixed(2)}
        </span>
        {suffix && <span className="text-xs text-gray-500">{suffix}</span>}
      </div>
    </div>
  );
}