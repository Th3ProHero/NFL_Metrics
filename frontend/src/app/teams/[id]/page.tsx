"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { fetchTeamStats, fetchTeamRoster, type TeamStats, type TeamRoster, type Player, type PositionGroup } from "@/lib/api";
import { GameCard } from "@/components/LiveGamesBoard";

export default function TeamDeepDive({ params }: { params: { id: string } }) {
  const [stats, setStats] = useState<TeamStats | null>(null);
  const [roster, setRoster] = useState<TeamRoster | null>(null);
  const [loading, setLoading] = useState(true);
  const [rosterLoading, setRosterLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(0);

  useEffect(() => {
    const teamId = Number(params.id);
    fetchTeamStats(teamId)
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));

    fetchTeamRoster(teamId)
      .then(setRoster)
      .catch(console.error)
      .finally(() => setRosterLoading(false));
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

      {/* ─── Roster & Depth Chart ─────────────────────────────────────── */}
      <section>
        <h2 className="text-xl font-display font-bold text-white mb-4 uppercase tracking-wider flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-accent-blue" />
          Roster & Depth Chart
          {roster && (
            <span className="ml-auto text-xs text-gray-500 font-normal normal-case tracking-normal">
              {roster.total_players} players · {roster.season} Season
            </span>
          )}
        </h2>

        {rosterLoading ? (
          <div className="glass-card p-16 flex flex-col items-center justify-center">
            <div className="w-8 h-8 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin mb-3" />
            <p className="text-gray-500 text-sm">Loading roster from ESPN...</p>
          </div>
        ) : roster && roster.groups.length > 0 ? (
          <div>
            {/* Tabs */}
            <div className="flex gap-1 mb-6 bg-surface-900/50 p-1 rounded-xl border border-white/5 w-fit">
              {roster.groups.map((group, idx) => (
                <button
                  key={group.name}
                  onClick={() => setActiveTab(idx)}
                  className={`
                    px-5 py-2.5 rounded-lg text-sm font-semibold uppercase tracking-wider transition-all duration-300
                    ${activeTab === idx
                      ? "bg-accent-blue/20 text-accent-blue border border-accent-blue/30 shadow-lg shadow-accent-blue/10"
                      : "text-gray-500 hover:text-gray-300 hover:bg-white/5 border border-transparent"
                    }
                  `}
                >
                  {group.name}
                  <span className={`ml-2 text-xs tabular-nums ${activeTab === idx ? "text-accent-blue/70" : "text-gray-600"}`}>
                    {group.count}
                  </span>
                </button>
              ))}
            </div>

            {/* Player Cards Grid */}
            <RosterGrid group={roster.groups[activeTab]} teamColor={team.primary_color} />
          </div>
        ) : (
          <div className="glass-card p-10 flex flex-col items-center justify-center text-center">
            <span className="text-4xl mb-3">🏈</span>
            <p className="text-gray-400 font-medium">Roster data not available.</p>
          </div>
        )}
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

/* ─── Roster Grid Component ──────────────────────────────────────────────── */

function RosterGrid({ group, teamColor }: { group: PositionGroup; teamColor: string | null }) {
  const color = teamColor ? `#${teamColor.replace("#", "")}` : "#3b82f6";

  // Group players by position for sub-headers
  const positionMap = new Map<string, Player[]>();
  for (const p of group.players) {
    const key = p.position_name || p.position;
    if (!positionMap.has(key)) positionMap.set(key, []);
    positionMap.get(key)!.push(p);
  }

  return (
    <div className="space-y-8">
      {Array.from(positionMap.entries()).map(([posName, players]) => (
        <div key={posName}>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-1.5 h-6 rounded-full" style={{ backgroundColor: color }} />
            <h3 className="text-sm font-bold text-gray-300 uppercase tracking-widest">{posName}</h3>
            <div className="flex-1 h-px bg-white/5" />
            <span className="text-xs text-gray-600 tabular-nums">{players.length}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {players.map((player) => (
              <PlayerCard key={player.espn_id} player={player} teamColor={color} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─── Player Card Component ──────────────────────────────────────────────── */

function PlayerCard({ player, teamColor }: { player: Player; teamColor: string }) {
  const isInjured = player.injuries.length > 0 || player.status === "Injured Reserve";
  const isPracticeSquad = player.status === "Practice Squad";

  return (
    <div className="group glass-card p-0 overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-xl hover:shadow-black/20 border border-white/5 hover:border-white/10">
      <div className="flex items-stretch">
        {/* Jersey Number Strip */}
        <div
          className="w-16 shrink-0 flex flex-col items-center justify-center relative overflow-hidden"
          style={{ backgroundColor: `${teamColor}15` }}
        >
          <div className="absolute inset-0 opacity-10" style={{
            background: `linear-gradient(135deg, ${teamColor}40 0%, transparent 60%)`,
          }} />
          <span
            className="text-2xl font-black tabular-nums relative z-10"
            style={{ color: teamColor }}
          >
            {player.jersey || "—"}
          </span>
          <span className="text-[9px] font-bold text-gray-500 uppercase tracking-widest relative z-10 mt-0.5">
            {player.position}
          </span>
        </div>

        {/* Player Info */}
        <div className="flex-1 p-3 min-w-0">
          <div className="flex items-start gap-3">
            {/* Headshot */}
            {player.headshot_url ? (
              <div className="w-11 h-11 rounded-full overflow-hidden bg-surface-700 shrink-0 border border-white/10 group-hover:border-white/20 transition-colors">
                <Image
                  src={player.headshot_url}
                  alt={player.full_name}
                  width={44}
                  height={44}
                  className="object-cover w-full h-full"
                  unoptimized
                />
              </div>
            ) : (
              <div className="w-11 h-11 rounded-full bg-surface-700 shrink-0 flex items-center justify-center text-xs font-bold text-gray-600 border border-white/10">
                {player.full_name.split(" ").map(n => n[0]).join("").slice(0, 2)}
              </div>
            )}

            {/* Name & Details */}
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-white truncate leading-tight group-hover:text-gray-100">
                {player.full_name}
              </p>
              <p className="text-[10px] text-gray-500 mt-0.5 truncate">
                {player.position_name}
              </p>

              {/* Badges */}
              <div className="flex flex-wrap gap-1 mt-1.5">
                {isInjured && (
                  <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-red-500/15 text-red-400 border border-red-500/20">
                    🩹 {player.status === "Injured Reserve" ? "IR" : "INJ"}
                  </span>
                )}
                {isPracticeSquad && (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-yellow-500/15 text-yellow-500 border border-yellow-500/20">
                    PS
                  </span>
                )}
                {player.experience_years === 0 && (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                    R
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Physical Stats Row */}
          <div className="flex items-center gap-3 mt-2 pt-2 border-t border-white/5">
            {player.height && (
              <span className="text-[10px] text-gray-500 flex items-center gap-1">
                <svg className="w-2.5 h-2.5 text-gray-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2v20M8 6l4-4 4 4M8 18l4 4 4-4" />
                </svg>
                {player.height}
              </span>
            )}
            {player.weight && (
              <span className="text-[10px] text-gray-500">{player.weight}</span>
            )}
            {player.experience_years > 0 && (
              <span className="text-[10px] text-gray-500">
                {player.experience_years}yr{player.experience_years !== 1 ? "s" : ""}
              </span>
            )}
            {player.college && (
              <span className="text-[10px] text-gray-600 truncate ml-auto">
                {player.college}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Stat Card Component ────────────────────────────────────────────────── */

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