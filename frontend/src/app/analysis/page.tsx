"use client";

import { useEffect, useState } from "react";
import {
  fetchTeams, fetchGames, fetchTeamStats,
  type Team, type Game, type TeamStats,
} from "@/lib/api";

/* ── Helper: implied probability from American odds ──────────────────────── */

function impliedProb(american: number | null): number | null {
  if (american == null) return null;
  if (american > 0) return 100 / (american + 100);
  return Math.abs(american) / (Math.abs(american) + 100);
}

function pctStr(val: number | null): string {
  if (val == null) return "—";
  return `${(val * 100).toFixed(1)}%`;
}

function fmtOdds(val: number | null): string {
  if (val == null) return "—";
  return val > 0 ? `+${val}` : `${val}`;
}

/* ═══════════════════════════════════════════════════════════════════════════
   Analysis Page
   ═══════════════════════════════════════════════════════════════════════════ */

export default function AnalysisPage() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<number | null>(null);
  const [teamStats, setTeamStats] = useState<TeamStats | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch initial data
  useEffect(() => {
    async function load() {
      try {
        const [t, g] = await Promise.all([
          fetchTeams(),
          fetchGames({ status: "pre", limit: "30" }),
        ]);
        setTeams(t);
        setGames(g);
      } catch (err) {
        console.error("Failed to load analysis data:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Fetch team stats when selected
  useEffect(() => {
    if (!selectedTeamId) {
      setTeamStats(null);
      return;
    }
    fetchTeamStats(selectedTeamId)
      .then(setTeamStats)
      .catch((err) => console.error("Failed to load team stats:", err));
  }, [selectedTeamId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      {/* ── Page Header ── */}
      <div className="mb-8">
        <h1 className="text-3xl font-display font-bold text-white tracking-tight">
          Analysis &amp; Edge Finder
        </h1>
        <p className="text-sm text-gray-400 mt-1">
          Compare odds vs. statistical models to identify +EV opportunities
        </p>
      </div>

      {/* ── Upcoming Games Odds Table ── */}
      <section className="mb-10">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Upcoming Games — Odds vs. Model
        </h2>

        <div className="glass-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06]">
                  <th className="text-left px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider">Matchup</th>
                  <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider">Spread</th>
                  <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider">O/U</th>
                  <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider">Home ML</th>
                  <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider">Away ML</th>
                  <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider">Implied Home%</th>
                  <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase tracking-wider">Signal</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {games.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-5 py-10 text-center text-gray-500">
                      No upcoming games with odds data available.
                    </td>
                  </tr>
                )}
                {games.map((game) => {
                  const odds = game.latest_odds;
                  const homeProb = impliedProb(odds?.home_moneyline ?? null);
                  const awayProb = impliedProb(odds?.away_moneyline ?? null);

                  // Simple +EV signal: if implied home probability < 45%, flag as potential away value
                  // and vice versa. This is a basic heuristic placeholder.
                  let signal = "—";
                  let signalColor = "text-gray-500";
                  if (homeProb != null && awayProb != null) {
                    const vig = homeProb + awayProb;
                    const trueHome = homeProb / vig;
                    const trueAway = awayProb / vig;

                    if (trueHome > 0.55) {
                      signal = "Home Favorite";
                      signalColor = "text-accent-blue";
                    } else if (trueAway > 0.55) {
                      signal = "Away Favorite";
                      signalColor = "text-accent-purple";
                    } else {
                      signal = "Toss-Up";
                      signalColor = "text-nfl-pending";
                    }
                  }

                  return (
                    <tr key={game.id} className="hover:bg-surface-700/30 transition-colors">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <span className="text-gray-300 font-medium">
                            {game.away_team?.abbreviation || "TBD"}
                          </span>
                          <span className="text-gray-600 text-xs">@</span>
                          <span className="text-white font-semibold">
                            {game.home_team?.abbreviation || "TBD"}
                          </span>
                        </div>
                        <p className="text-[11px] text-gray-500 mt-0.5">
                          {game.start_time
                            ? new Date(game.start_time).toLocaleDateString("en-US", {
                              weekday: "short", month: "short", day: "numeric",
                              hour: "numeric", minute: "2-digit",
                            })
                            : "TBD"}
                        </p>
                      </td>
                      <td className="px-5 py-3 text-center text-gray-300 font-mono text-xs">
                        {odds?.spread != null ? (odds.spread > 0 ? `+${odds.spread}` : odds.spread) : "—"}
                      </td>
                      <td className="px-5 py-3 text-center text-gray-300 font-mono text-xs">
                        {odds?.over_under ?? "—"}
                      </td>
                      <td className="px-5 py-3 text-center text-gray-300 font-mono text-xs">
                        {fmtOdds(odds?.home_moneyline ?? null)}
                      </td>
                      <td className="px-5 py-3 text-center text-gray-300 font-mono text-xs">
                        {fmtOdds(odds?.away_moneyline ?? null)}
                      </td>
                      <td className="px-5 py-3 text-center text-gray-300 font-mono text-xs">
                        {pctStr(homeProb)}
                      </td>
                      <td className={`px-5 py-3 text-center text-xs font-semibold ${signalColor}`}>
                        {signal}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── Team Deep Dive ── */}
      <section>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Team Deep Dive
        </h2>

        <div className="flex items-center gap-4 mb-6">
          <select
            value={selectedTeamId ?? ""}
            onChange={(e) => setSelectedTeamId(e.target.value ? parseInt(e.target.value) : null)}
            className="input-field max-w-xs"
          >
            <option value="">Select a team...</option>
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.abbreviation})
              </option>
            ))}
          </select>
        </div>

        {teamStats && (
          <div className="animate-fade-in">
            {/* Stats Overview */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="glass-card p-4 text-center">
                <p className="text-2xl font-display font-bold text-white">{teamStats.record || "0-0"}</p>
                <p className="text-[11px] text-gray-500 uppercase tracking-wider mt-1">Record</p>
              </div>
              <div className="glass-card p-4 text-center">
                <p className="text-2xl font-display font-bold text-accent-blue">
                  {teamStats.points_for.toFixed(0)}
                </p>
                <p className="text-[11px] text-gray-500 uppercase tracking-wider mt-1">Points For</p>
              </div>
              <div className="glass-card p-4 text-center">
                <p className="text-2xl font-display font-bold text-nfl-loss">
                  {teamStats.points_against.toFixed(0)}
                </p>
                <p className="text-[11px] text-gray-500 uppercase tracking-wider mt-1">Points Against</p>
              </div>
              <div className="glass-card p-4 text-center">
                <p className="text-2xl font-display font-bold text-nfl-win">
                  {teamStats.epa_per_play != null ? teamStats.epa_per_play.toFixed(3) : "N/A"}
                </p>
                <p className="text-[11px] text-gray-500 uppercase tracking-wider mt-1">EPA / Play</p>
              </div>
            </div>

            {/* Recent Games */}
            {teamStats.recent_games.length > 0 && (
              <>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                  Recent Results
                </h3>
                <div className="glass-card overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-white/[0.06]">
                          <th className="text-left px-5 py-3 text-[11px] text-gray-500 uppercase">Opponent</th>
                          <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase">Score</th>
                          <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase">Result</th>
                          <th className="text-center px-5 py-3 text-[11px] text-gray-500 uppercase">Week</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/[0.04]">
                        {teamStats.recent_games.map((g) => {
                          const isHome = g.home_team?.id === selectedTeamId;
                          const opponent = isHome ? g.away_team : g.home_team;
                          const teamScore = isHome ? g.home_score : g.away_score;
                          const oppScore = isHome ? g.away_score : g.home_score;
                          const won = teamScore > oppScore;
                          return (
                            <tr key={g.id} className="hover:bg-surface-700/30 transition-colors">
                              <td className="px-5 py-3 text-gray-300">
                                {isHome ? "vs" : "@"} {opponent?.abbreviation || "TBD"}
                              </td>
                              <td className="px-5 py-3 text-center font-mono text-gray-300">
                                {teamScore} - {oppScore}
                              </td>
                              <td className="px-5 py-3 text-center">
                                <span className={won ? "stat-badge-win" : "stat-badge-loss"}>
                                  {won ? "W" : "L"}
                                </span>
                              </td>
                              <td className="px-5 py-3 text-center text-gray-500">
                                Wk {g.week}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
