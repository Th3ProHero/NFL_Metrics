"use client";

import { useEffect, useState, useCallback } from "react";
import {
  fetchPoolPlayers,
  createPoolPlayer,
  updatePoolPlayer,
  deletePoolPlayer,
  fetchLeaderboard,
  fetchGames,
  fetchTeams,
  createPoolPicks,
  fetchPoolPicks,
  resolvePoolPicks,
  type PoolPlayer,
  type PoolPlayerCreate,
  type LeaderboardEntry,
  type Game,
  type Team,
  type PoolPick,
} from "@/lib/api";

/* ═══════════════════════════════════════════════════════════════════════════
   AVATAR GALLERY — default avatars for users without photos
   ═══════════════════════════════════════════════════════════════════════════ */

const DEFAULT_AVATARS = [
  "🏈", "🏆", "⚡", "🔥", "💎", "🎯", "🦅", "🐻", "🐬", "🐴",
  "🦁", "🐆", "🐏", "🦬", "⭐", "👑",
];

function AvatarDisplay({ player, size = "md" }: { player: PoolPlayer; size?: "sm" | "md" | "lg" }) {
  const sizeClasses = {
    sm: "w-8 h-8 text-sm",
    md: "w-12 h-12 text-xl",
    lg: "w-20 h-20 text-3xl",
  };

  if (player.avatar_url) {
    return (
      <img
        src={player.avatar_url}
        alt={player.name}
        className={`${sizeClasses[size]} rounded-full object-cover ring-2 ring-white/10`}
      />
    );
  }

  // Generate a consistent color from the player's name
  const hash = player.name.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  const hue = hash % 360;
  const emoji = DEFAULT_AVATARS[hash % DEFAULT_AVATARS.length];

  return (
    <div
      className={`${sizeClasses[size]} rounded-full flex items-center justify-center ring-2 ring-white/10`}
      style={{ background: `linear-gradient(135deg, hsl(${hue}, 70%, 35%), hsl(${(hue + 40) % 360}, 70%, 25%))` }}
    >
      {emoji}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   LEADERBOARD TAB
   ═══════════════════════════════════════════════════════════════════════════ */

function LeaderboardTab() {
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLeaderboard()
      .then(setLeaderboard)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner />;

  if (leaderboard.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <div className="text-5xl mb-4">🏆</div>
        <p className="text-lg font-medium mb-2">No hay jugadores aún</p>
        <p className="text-sm">Agrega amigos en la pestaña &ldquo;Jugadores&rdquo; para comenzar</p>
      </div>
    );
  }

  const medals = ["🥇", "🥈", "🥉"];

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Top 3 podium */}
      {leaderboard.length >= 2 && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          {leaderboard.slice(0, 3).map((entry, i) => (
            <div
              key={entry.player.id}
              className={`glass-card p-6 text-center relative overflow-hidden ${
                i === 0
                  ? "ring-2 ring-yellow-500/30 bg-gradient-to-b from-yellow-500/5 to-transparent order-2 -mt-4"
                  : i === 1
                  ? "order-1"
                  : "order-3"
              }`}
            >
              <div className="text-3xl mb-2">{medals[i] || `#${i + 1}`}</div>
              <AvatarDisplay player={entry.player} size={i === 0 ? "lg" : "md"} />
              <h3 className="text-white font-bold mt-3 text-lg">{entry.player.name}</h3>
              <div className="mt-3 space-y-1">
                <div className="text-2xl font-display font-bold text-accent-blue">
                  {entry.correct_picks}
                </div>
                <div className="text-xs text-gray-400 uppercase tracking-wide">Aciertos</div>
              </div>
              <div className="flex justify-center gap-4 mt-3 text-sm">
                <span className="text-gray-400">
                  {entry.accuracy}%
                </span>
                {entry.current_streak > 0 && (
                  <span className="text-nfl-win">
                    🔥 {entry.current_streak}
                  </span>
                )}
              </div>
              {/* Fav teams */}
              <div className="flex justify-center gap-1 mt-3">
                {[entry.player.fav_team_1, entry.player.fav_team_2, entry.player.fav_team_3]
                  .filter(Boolean)
                  .map((team) => (
                    <img
                      key={team!.id}
                      src={team!.logo_url || ""}
                      alt={team!.abbreviation}
                      className="w-5 h-5 object-contain"
                      title={team!.name}
                    />
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Full table */}
      <div className="glass-card overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/[0.06] text-xs uppercase tracking-wider text-gray-400">
              <th className="px-4 py-3 text-left">#</th>
              <th className="px-4 py-3 text-left">Jugador</th>
              <th className="px-4 py-3 text-center">Aciertos</th>
              <th className="px-4 py-3 text-center">Total</th>
              <th className="px-4 py-3 text-center">%</th>
              <th className="px-4 py-3 text-center">Racha</th>
              <th className="px-4 py-3 text-center">Mejor Racha</th>
              <th className="px-4 py-3 text-center">Favs</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {leaderboard.map((entry, i) => (
              <tr
                key={entry.player.id}
                className="hover:bg-white/[0.02] transition-colors"
              >
                <td className="px-4 py-3 text-gray-400 font-mono text-sm">
                  {i < 3 ? medals[i] : i + 1}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <AvatarDisplay player={entry.player} size="sm" />
                    <span className="font-medium text-white">{entry.player.name}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-center">
                  <span className="text-nfl-win font-bold">{entry.correct_picks}</span>
                </td>
                <td className="px-4 py-3 text-center text-gray-400">{entry.total_picks}</td>
                <td className="px-4 py-3 text-center">
                  <span className={`stat-badge ${
                    entry.accuracy >= 60 ? "stat-badge-win" : entry.accuracy >= 45 ? "stat-badge-pending" : "stat-badge-loss"
                  }`}>
                    {entry.accuracy}%
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  {entry.current_streak > 0 ? (
                    <span className="text-nfl-win font-medium">🔥 {entry.current_streak}</span>
                  ) : (
                    <span className="text-gray-500">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-center text-gray-400">
                  {entry.longest_streak > 0 ? entry.longest_streak : "—"}
                </td>
                <td className="px-4 py-3">
                  <div className="flex justify-center gap-1">
                    {[entry.player.fav_team_1, entry.player.fav_team_2, entry.player.fav_team_3]
                      .filter(Boolean)
                      .map((team) => (
                        <img
                          key={team!.id}
                          src={team!.logo_url || ""}
                          alt={team!.abbreviation}
                          className="w-5 h-5 object-contain"
                          title={team!.name}
                        />
                      ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   PICKS TAB
   ═══════════════════════════════════════════════════════════════════════════ */

function PicksTab() {
  const [players, setPlayers] = useState<PoolPlayer[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [existingPicks, setExistingPicks] = useState<PoolPick[]>([]);
  const [selectedWeek, setSelectedWeek] = useState(1);
  const [selectedSeason, setSelectedSeason] = useState(new Date().getFullYear());
  const [selectedPlayer, setSelectedPlayer] = useState<number | null>(null);
  // Map: `${gameId}` -> picked_team_id
  const [picks, setPicks] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [p, g] = await Promise.all([
        fetchPoolPlayers(),
        fetchGames({ season: String(selectedSeason), week: String(selectedWeek), limit: "50" }),
      ]);
      setPlayers(p);
      setGames(g);
      if (p.length > 0 && !selectedPlayer) {
        setSelectedPlayer(p[0].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [selectedSeason, selectedWeek, selectedPlayer]);

  // Load existing picks when player/week changes
  useEffect(() => {
    if (selectedPlayer) {
      fetchPoolPicks({
        player_id: String(selectedPlayer),
        season: String(selectedSeason),
        week: String(selectedWeek),
      })
        .then((pks) => {
          setExistingPicks(pks);
          const m: Record<string, number> = {};
          pks.forEach((pk) => {
            m[String(pk.game_id)] = pk.picked_team_id;
          });
          setPicks(m);
        })
        .catch(console.error);
    }
  }, [selectedPlayer, selectedSeason, selectedWeek]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handlePick = (gameId: number, teamId: number) => {
    const game = games.find((g) => g.id === gameId);
    const existingPk = existingPicks.find((p) => p.game_id === gameId);
    const isFinished = game?.status === "post";
    const isResolved = existingPk?.is_correct !== null && existingPk?.is_correct !== undefined;
    const isChanging = existingPk && existingPk.picked_team_id !== teamId;

    if (isFinished || isResolved) {
      const teamName = [game?.home_team, game?.away_team].find((t) => t?.id === teamId)?.name || "este equipo";
      const msg = isResolved
        ? `⚠️ Este partido ya terminó y el pick fue resuelto.\n\n¿Estás seguro de querer cambiar el pick a "${teamName}"?\n\nEsto reemplazará el resultado anterior.`
        : `⚠️ Este partido ya terminó.\n\n¿Estás seguro de querer elegir "${teamName}"?`;
      if (!confirm(msg)) return;
    } else if (isChanging) {
      const teamName = [game?.home_team, game?.away_team].find((t) => t?.id === teamId)?.name || "este equipo";
      if (!confirm(`¿Cambiar pick a "${teamName}"?`)) return;
    }

    setPicks((prev) => ({ ...prev, [String(gameId)]: teamId }));
  };

  const handleSave = async () => {
    if (!selectedPlayer) return;

    // Check if any picks are for finished games
    const finishedPicks = Object.keys(picks).filter((gameId) => {
      const game = games.find((g) => g.id === parseInt(gameId));
      return game?.status === "post";
    });

    if (finishedPicks.length > 0) {
      const msg = `⚠️ Estás guardando picks para ${finishedPicks.length} partido(s) ya terminado(s).\n\nLos picks resueltos se recalcularán.\n\n¿Deseas continuar?`;
      if (!confirm(msg)) return;
    }

    setSaving(true);
    try {
      const pickList = Object.entries(picks).map(([gameId, teamId]) => ({
        player_id: selectedPlayer,
        game_id: parseInt(gameId),
        picked_team_id: teamId,
      }));
      if (pickList.length > 0) {
        await createPoolPicks(pickList);
        // Re-resolve picks for finished games
        if (finishedPicks.length > 0) {
          await resolvePoolPicks();
        }
        // Refresh existing picks
        const pks = await fetchPoolPicks({
          player_id: String(selectedPlayer),
          season: String(selectedSeason),
          week: String(selectedWeek),
        });
        setExistingPicks(pks);
        const m: Record<string, number> = {};
        pks.forEach((pk) => { m[String(pk.game_id)] = pk.picked_team_id; });
        setPicks(m);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  if (players.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <div className="text-5xl mb-4">🎯</div>
        <p className="text-lg font-medium mb-2">No hay jugadores aún</p>
        <p className="text-sm">Agrega amigos primero en la pestaña &ldquo;Jugadores&rdquo;</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Controls */}
      <div className="flex flex-wrap gap-4 items-center">
        {/* Player selector */}
        <div className="flex-1 min-w-[200px]">
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">Jugador</label>
          <select
            className="input-field"
            value={selectedPlayer || ""}
            onChange={(e) => setSelectedPlayer(parseInt(e.target.value))}
          >
            {players.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        {/* Season */}
        <div className="w-32">
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">Temporada</label>
          <select
            className="input-field"
            value={selectedSeason}
            onChange={(e) => setSelectedSeason(parseInt(e.target.value))}
          >
            {[2026, 2025, 2024].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        {/* Week */}
        <div className="w-32">
          <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">Semana</label>
          <select
            className="input-field"
            value={selectedWeek}
            onChange={(e) => setSelectedWeek(parseInt(e.target.value))}
          >
            {Array.from({ length: 18 }, (_, i) => i + 1).map((w) => (
              <option key={w} value={w}>Week {w}</option>
            ))}
          </select>
        </div>

        <div className="flex items-end gap-2">
          <button onClick={handleSave} disabled={saving} className="btn-primary mt-5">
            {saving ? "Guardando..." : "💾 Guardar Picks"}
          </button>
        </div>
      </div>

      {/* Games grid */}
      {games.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg">No hay partidos para Week {selectedWeek}</p>
          <p className="text-sm mt-1">Intenta con otra semana</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {games.map((game) => {
            const currentPick = picks[String(game.id)];
            const existingPick = existingPicks.find((p) => p.game_id === game.id);
            const isResolved = existingPick?.is_correct !== null && existingPick?.is_correct !== undefined;
            const isFinished = game.status === "post";

            return (
              <div
                key={game.id}
                className={`glass-card p-4 transition-all duration-300 ${
                  isResolved
                    ? existingPick?.is_correct
                      ? "ring-1 ring-nfl-win/30"
                      : "ring-1 ring-nfl-loss/30"
                    : ""
                }`}
              >
                {/* Editable disclaimer for finished games */}
                {isFinished && (
                  <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-nfl-pending/5 border border-nfl-pending/20">
                    <span className="text-nfl-pending text-xs">⚠️</span>
                    <span className="text-[10px] text-nfl-pending/80">Partido terminado — picks editables con confirmación</span>
                  </div>
                )}

                {/* Game status badge */}
                <div className="flex justify-between items-center mb-3">
                  <span className="text-[10px] uppercase tracking-wider text-gray-500">
                    {game.venue || "TBD"}
                  </span>
                  {isFinished ? (
                    <span className="text-[10px] uppercase tracking-wider text-gray-500 bg-surface-700/50 px-2 py-0.5 rounded-full">
                      Final
                    </span>
                  ) : game.status === "in_progress" ? (
                    <span className="text-[10px] uppercase tracking-wider text-nfl-win flex items-center gap-1">
                      <span className="live-dot" style={{ width: 6, height: 6 }} /> En vivo
                    </span>
                  ) : (
                    <span className="text-[10px] text-gray-500">
                      {game.start_time ? new Date(game.start_time).toLocaleDateString("es-MX", { weekday: "short", hour: "2-digit", minute: "2-digit" }) : "TBD"}
                    </span>
                  )}
                </div>

                {/* Teams */}
                <div className="space-y-2">
                  {/* Away team */}
                  {game.away_team && (
                    <button
                      onClick={() => handlePick(game.id, game.away_team!.id)}
                      className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all duration-200 cursor-pointer ${
                        currentPick === game.away_team.id
                          ? isResolved
                            ? existingPick?.is_correct
                              ? "bg-nfl-win/15 ring-1 ring-nfl-win/30"
                              : "bg-nfl-loss/15 ring-1 ring-nfl-loss/30"
                            : "bg-accent-blue/15 ring-1 ring-accent-blue/40"
                          : "hover:bg-white/[0.04]"
                      }`}
                    >
                      <img
                        src={game.away_team.logo_url || ""}
                        alt={game.away_team.abbreviation}
                        className="w-8 h-8 object-contain"
                      />
                      <span className="flex-1 text-left font-medium text-white text-sm">
                        {game.away_team.name}
                      </span>
                      {isFinished && (
                        <span className="text-lg font-bold text-white">{game.away_score}</span>
                      )}
                      {currentPick === game.away_team.id && (
                        <span className={`text-sm ${
                          isResolved
                            ? existingPick?.is_correct ? "text-nfl-win" : "text-nfl-loss"
                            : "text-accent-blue"
                        }`}>
                          {isResolved ? (existingPick?.is_correct ? "✓" : "✗") : "◉"}
                        </span>
                      )}
                    </button>
                  )}

                  {/* Divider */}
                  <div className="flex items-center gap-2 px-3">
                    <div className="flex-1 h-px bg-white/[0.06]" />
                    <span className="text-[10px] text-gray-500 font-medium">VS</span>
                    <div className="flex-1 h-px bg-white/[0.06]" />
                  </div>

                  {/* Home team */}
                  {game.home_team && (
                    <button
                      onClick={() => handlePick(game.id, game.home_team!.id)}
                      className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all duration-200 cursor-pointer ${
                        currentPick === game.home_team.id
                          ? isResolved
                            ? existingPick?.is_correct
                              ? "bg-nfl-win/15 ring-1 ring-nfl-win/30"
                              : "bg-nfl-loss/15 ring-1 ring-nfl-loss/30"
                            : "bg-accent-blue/15 ring-1 ring-accent-blue/40"
                          : "hover:bg-white/[0.04]"
                      }`}
                    >
                      <img
                        src={game.home_team.logo_url || ""}
                        alt={game.home_team.abbreviation}
                        className="w-8 h-8 object-contain"
                      />
                      <span className="flex-1 text-left font-medium text-white text-sm">
                        {game.home_team.name}
                      </span>
                      {isFinished && (
                        <span className="text-lg font-bold text-white">{game.home_score}</span>
                      )}
                      {currentPick === game.home_team.id && (
                        <span className={`text-sm ${
                          isResolved
                            ? existingPick?.is_correct ? "text-nfl-win" : "text-nfl-loss"
                            : "text-accent-blue"
                        }`}>
                          {isResolved ? (existingPick?.is_correct ? "✓" : "✗") : "◉"}
                        </span>
                      )}
                    </button>
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

/* ═══════════════════════════════════════════════════════════════════════════
   PLAYERS TAB
   ═══════════════════════════════════════════════════════════════════════════ */

function PlayersTab() {
  const [players, setPlayers] = useState<PoolPlayer[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingPlayer, setEditingPlayer] = useState<PoolPlayer | null>(null);
  const [formData, setFormData] = useState<PoolPlayerCreate>({
    name: "",
    avatar_url: "",
    fav_team_1: null,
    fav_team_2: null,
    fav_team_3: null,
  });
  const [saving, setSaving] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [p, t] = await Promise.all([fetchPoolPlayers(), fetchTeams()]);
      setPlayers(p);
      setTeams(t);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmit = async () => {
    if (!formData.name.trim()) return;
    setSaving(true);
    try {
      const data = {
        ...formData,
        fav_team_1: formData.fav_team_1 || null,
        fav_team_2: formData.fav_team_2 || null,
        fav_team_3: formData.fav_team_3 || null,
        avatar_url: formData.avatar_url || null,
      };
      if (editingPlayer) {
        await updatePoolPlayer(editingPlayer.id, data);
      } else {
        await createPoolPlayer(data);
      }
      setShowForm(false);
      setEditingPlayer(null);
      setFormData({ name: "", avatar_url: "", fav_team_1: null, fav_team_2: null, fav_team_3: null });
      await loadData();
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (player: PoolPlayer) => {
    setEditingPlayer(player);
    setFormData({
      name: player.name,
      avatar_url: player.avatar_url || "",
      fav_team_1: player.fav_team_1?.id || null,
      fav_team_2: player.fav_team_2?.id || null,
      fav_team_3: player.fav_team_3?.id || null,
    });
    setShowForm(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm("¿Eliminar este jugador y todos sus picks?")) return;
    try {
      await deletePoolPlayer(id);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header + Add button */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-lg font-display font-bold text-white">
            {players.length} {players.length === 1 ? "Jugador" : "Jugadores"}
          </h3>
          <p className="text-sm text-gray-400">Gestiona los perfiles de tus amigos</p>
        </div>
        <button
          onClick={() => {
            setEditingPlayer(null);
            setFormData({ name: "", avatar_url: "", fav_team_1: null, fav_team_2: null, fav_team_3: null });
            setShowForm(true);
          }}
          className="btn-primary"
        >
          + Agregar Amigo
        </button>
      </div>

      {/* Form modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass-card w-full max-w-lg p-6 space-y-5 animate-slide-up">
            <h3 className="text-xl font-display font-bold text-white">
              {editingPlayer ? "Editar Jugador" : "Nuevo Jugador"}
            </h3>

            {/* Name */}
            <div>
              <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">Nombre</label>
              <input
                type="text"
                className="input-field"
                placeholder="Nombre del amigo"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                maxLength={60}
              />
            </div>

            {/* Avatar URL */}
            <div>
              <label className="block text-xs text-gray-400 mb-1 uppercase tracking-wider">
                Foto (URL) — opcional
              </label>
              <input
                type="url"
                className="input-field"
                placeholder="https://ejemplo.com/foto.jpg"
                value={formData.avatar_url || ""}
                onChange={(e) => setFormData({ ...formData, avatar_url: e.target.value })}
              />
              <p className="text-[11px] text-gray-500 mt-1">
                Deja vacío para usar un avatar generado automáticamente
              </p>
            </div>

            {/* Favorite teams */}
            <div>
              <label className="block text-xs text-gray-400 mb-2 uppercase tracking-wider">
                Top 3 Equipos Favoritos
              </label>
              <div className="grid grid-cols-3 gap-3">
                {[1, 2, 3].map((num) => {
                  const key = `fav_team_${num}` as keyof PoolPlayerCreate;
                  return (
                    <div key={num}>
                      <label className="block text-[10px] text-gray-500 mb-1">#{num}</label>
                      <select
                        className="input-field text-sm"
                        value={(formData[key] as number) || ""}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            [key]: e.target.value ? parseInt(e.target.value) : null,
                          })
                        }
                      >
                        <option value="">— Ninguno —</option>
                        {teams.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.abbreviation} — {t.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3 justify-end pt-2">
              <button
                onClick={() => {
                  setShowForm(false);
                  setEditingPlayer(null);
                }}
                className="btn-secondary"
              >
                Cancelar
              </button>
              <button onClick={handleSubmit} disabled={saving || !formData.name.trim()} className="btn-primary">
                {saving ? "Guardando..." : editingPlayer ? "Actualizar" : "Crear Jugador"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Player cards */}
      {players.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <div className="text-5xl mb-4">👥</div>
          <p className="text-lg font-medium mb-2">No hay jugadores aún</p>
          <p className="text-sm">Presiona &ldquo;Agregar Amigo&rdquo; para comenzar</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {players.map((player) => (
            <div key={player.id} className="glass-card p-5 group">
              <div className="flex items-start gap-4">
                <AvatarDisplay player={player} size="lg" />
                <div className="flex-1 min-w-0">
                  <h4 className="text-lg font-bold text-white truncate">{player.name}</h4>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Desde {player.created_at ? new Date(player.created_at).toLocaleDateString("es-MX") : "—"}
                  </p>

                  {/* Fav teams */}
                  <div className="flex gap-2 mt-3">
                    {[player.fav_team_1, player.fav_team_2, player.fav_team_3]
                      .filter(Boolean)
                      .map((team, i) => (
                        <div
                          key={team!.id}
                          className="flex items-center gap-1.5 bg-surface-700/50 rounded-lg px-2 py-1"
                          title={team!.name}
                        >
                          <img
                            src={team!.logo_url || ""}
                            alt={team!.abbreviation}
                            className="w-4 h-4 object-contain"
                          />
                          <span className="text-[11px] text-gray-300">{team!.abbreviation}</span>
                        </div>
                      ))}
                    {![player.fav_team_1, player.fav_team_2, player.fav_team_3].some(Boolean) && (
                      <span className="text-xs text-gray-500 italic">Sin equipos favoritos</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 mt-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => handleEdit(player)}
                  className="flex-1 btn-secondary text-xs py-2"
                >
                  ✏️ Editar
                </button>
                <button
                  onClick={() => handleDelete(player.id)}
                  className="btn-secondary text-xs py-2 text-nfl-loss hover:bg-nfl-loss/10 hover:border-nfl-loss/30"
                >
                  🗑️
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   LOADING SPINNER
   ═══════════════════════════════════════════════════════════════════════════ */

function LoadingSpinner() {
  return (
    <div className="flex justify-center items-center py-20">
      <div className="w-8 h-8 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin" />
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   MAIN PAGE
   ═══════════════════════════════════════════════════════════════════════════ */

type TabKey = "leaderboard" | "picks" | "players";

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: "leaderboard", label: "Leaderboard", icon: "🏆" },
  { key: "picks",       label: "Hacer Picks", icon: "🎯" },
  { key: "players",     label: "Jugadores",   icon: "👥" },
];

export default function FriendsPoolPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("leaderboard");

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex items-center justify-center w-14 h-14 rounded-2xl
                        bg-gradient-to-br from-accent-purple to-accent-blue
                        shadow-glow">
          <span className="text-2xl">🏈</span>
        </div>
        <div>
          <h1 className="text-3xl font-display font-bold text-white tracking-tight">
            Friends Pool
          </h1>
          <p className="text-sm text-gray-400 mt-0.5">
            Predicciones entre amigos · Temporada Regular NFL
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-surface-800/60 backdrop-blur-xl rounded-xl border border-white/[0.06]">
        {TABS.map(({ key, label, icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg
                        text-sm font-medium transition-all duration-200 ${
              activeTab === key
                ? "bg-gradient-to-r from-accent-blue/20 to-accent-purple/20 text-white border border-accent-blue/20 shadow-glow-sm"
                : "text-gray-400 hover:text-white hover:bg-white/[0.04]"
            }`}
          >
            <span>{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === "leaderboard" && <LeaderboardTab />}
        {activeTab === "picks" && <PicksTab />}
        {activeTab === "players" && <PlayersTab />}
      </div>
    </div>
  );
}
