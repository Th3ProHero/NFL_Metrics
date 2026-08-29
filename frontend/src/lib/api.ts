/**
 * NFL BetMaster — API Client
 * ===========================
 * Centralised HTTP helpers for the FastAPI backend.
 */

function getApiBase(): string {
  if (typeof window !== "undefined") {
    // When served over HTTPS (e.g. Cloudflare tunnel), avoid mixed-content blocking
    // by using relative URLs which Next.js rewrites to the backend internally.
    if (window.location.protocol === "https:" && process.env.NEXT_PUBLIC_API_URL?.startsWith("http:")) {
      return "";
    }
  }
  return process.env.NEXT_PUBLIC_API_URL || "";
}

const API_BASE = getApiBase();

/* ── Generic Fetch Wrapper ──────────────────────────────────────────────── */

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/* ── Types ──────────────────────────────────────────────────────────────── */

export interface Team {
  id: number;
  espn_id: string;
  abbreviation: string;
  name: string;
  conference: string;
  division: string;
  logo_url: string | null;
  primary_color: string | null;
}

export interface Game {
  id: number;
  espn_event_id: string;
  season: number;
  week: number;
  game_type: string;
  status: "pre" | "in_progress" | "post";
  home_team: Team | null;
  away_team: Team | null;
  home_score: number;
  away_score: number;
  quarter: number | null;
  clock: string | null;
  possession_team_id: number | null;
  down: number | null;
  distance: number | null;
  yard_line: number | null;
  yard_line_territory: string | null;
  start_time: string | null;
  venue: string | null;
  broadcast: string | null;
  updated_at: string | null;
  latest_odds?: Odds | null;
}

export interface Odds {
  id: number;
  game_id: number;
  sportsbook: string;
  home_moneyline: number | null;
  away_moneyline: number | null;
  spread: number | null;
  spread_odds_home: number | null;
  spread_odds_away: number | null;
  over_under: number | null;
  over_odds: number | null;
  under_odds: number | null;
  captured_at: string | null;
}

export interface Bet {
  id: number;
  game_id: number | null;
  bet_type: string;
  pick: string;
  odds_decimal: number;
  odds_american: number | null;
  stake: number;
  potential_payout: number | null;
  result: "pending" | "won" | "lost" | "push" | "void";
  profit: number;
  notes: string | null;
  created_at: string | null;
  resolved_at: string | null;
}

export interface BetSummary {
  total_bets: number;
  total_staked: number;
  total_profit: number;
  roi_percent: number;
  wins: number;
  losses: number;
  pushes: number;
  pending: number;
  win_rate: number;
}

export interface BetCreate {
  game_id?: number | null;
  bet_type: string;
  pick: string;
  odds_decimal: number;
  odds_american?: number | null;
  stake: number;
  notes?: string | null;
}

export interface TeamStats {
  team: Team;
  record: string | null;
  points_for: number;
  points_against: number;
  epa_per_play: number | null;
  pass_epa: number | null;
  rush_epa: number | null;
  defensive_epa: number | null;
  recent_games: Game[];
  upcoming_games: Game[];
}

/* ── API Functions ──────────────────────────────────────────────────────── */

// Teams
export const fetchTeams = () => apiFetch<Team[]>("/api/teams");

// Games
export const fetchGames = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<Game[]>(`/api/games${qs}`);
};

// Stats
export const fetchTeamStats = (teamId: number) =>
  apiFetch<TeamStats>(`/api/stats/${teamId}`);

// Odds
export const fetchOddsHistory = (gameId: number) =>
  apiFetch<Odds[]>(`/api/odds/${gameId}`);

// Bets
export const fetchBets = (result?: string) => {
  const qs = result ? `?result=${result}` : "";
  return apiFetch<Bet[]>(`/api/bets${qs}`);
};

export const fetchBetSummary = () =>
  apiFetch<BetSummary>("/api/bets/summary");

export const createBet = (bet: BetCreate) =>
  apiFetch<Bet>("/api/bets", {
    method: "POST",
    body: JSON.stringify(bet),
  });

export const updateBet = (id: number, data: Partial<Bet>) =>
  apiFetch<Bet>(`/api/bets/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deleteBet = (id: number) =>
  apiFetch<{ detail: string }>(`/api/bets/${id}`, { method: "DELETE" });

// SSE URL (used by components directly)
export const LIVE_GAMES_SSE_URL = `${API_BASE}/api/live-games`;

// Manual data refresh
export const triggerRefresh = () =>
  apiFetch<{ status: string; has_live_games: boolean; timestamp: string }>("/api/refresh", { method: "POST" });

export interface SimulationResult {
  game_id: number;
  home_team: string;
  away_team: string;
  home_win_prob: number;
  away_win_prob: number;
  fair_home_ml: number;
  fair_away_ml: number;
  projected_home_pts: number;
  projected_away_pts: number;
  projected_total: number;
  n_simulations: number;
  engine: string;
  elapsed_ms: number;
  ev_home?: { is_positive_ev: boolean; ev_percent: number; edge_percent: number } | null;
  ev_away?: { is_positive_ev: boolean; ev_percent: number; edge_percent: number } | null;
}

export const simulateGame = (gameId: number) =>
  apiFetch<SimulationResult>(`/api/simulate/${gameId}`, { method: "POST" });

/* ── Roster Types ──────────────────────────────────────────────────────────── */

export interface Player {
  espn_id: string;
  full_name: string;
  jersey: string | null;
  position: string;
  position_name: string;
  headshot_url: string | null;
  height: string | null;
  weight: string | null;
  age: number | null;
  experience_years: number;
  college: string | null;
  status: string;
  injuries: string[];
}

export interface PositionGroup {
  name: string;
  players: Player[];
  count: number;
}

export interface TeamRoster {
  team_id: number;
  team_name: string;
  season: number | null;
  groups: PositionGroup[];
  total_players: number;
}

// Roster
export const fetchTeamRoster = (teamId: number) =>
  apiFetch<TeamRoster>(`/api/teams/${teamId}/roster`);


/* ── Friends Pool Types ────────────────────────────────────────────────────── */

export interface PoolPlayer {
  id: number;
  name: string;
  avatar_url: string | null;
  fav_team_1: Team | null;
  fav_team_2: Team | null;
  fav_team_3: Team | null;
  created_at: string | null;
}

export interface PoolPlayerCreate {
  name: string;
  avatar_url?: string | null;
  fav_team_1?: number | null;
  fav_team_2?: number | null;
  fav_team_3?: number | null;
}

export interface PoolPick {
  id: number;
  player_id: number;
  game_id: number;
  picked_team_id: number;
  picked_team: Team | null;
  is_correct: boolean | null;
  created_at: string | null;
  resolved_at: string | null;
}

export interface PoolPickCreate {
  player_id: number;
  game_id: number;
  picked_team_id: number;
}

export interface LeaderboardEntry {
  player: PoolPlayer;
  correct_picks: number;
  total_picks: number;
  accuracy: number;
  current_streak: number;
  longest_streak: number;
}

/* ── Friends Pool API Functions ────────────────────────────────────────────── */

// Pool Players
export const fetchPoolPlayers = () =>
  apiFetch<PoolPlayer[]>("/api/pool/players");

export const fetchPoolPlayer = (id: number) =>
  apiFetch<PoolPlayer>(`/api/pool/players/${id}`);

export const createPoolPlayer = (data: PoolPlayerCreate) =>
  apiFetch<PoolPlayer>("/api/pool/players", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const updatePoolPlayer = (id: number, data: Partial<PoolPlayerCreate>) =>
  apiFetch<PoolPlayer>(`/api/pool/players/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });

export const deletePoolPlayer = (id: number) =>
  apiFetch<{ detail: string }>(`/api/pool/players/${id}`, { method: "DELETE" });

// Pool Picks
export const createPoolPicks = (picks: PoolPickCreate[]) =>
  apiFetch<PoolPick[]>("/api/pool/picks", {
    method: "POST",
    body: JSON.stringify({ picks }),
  });

export const fetchPoolPicks = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<PoolPick[]>(`/api/pool/picks${qs}`);
};

export const deletePoolPick = (id: number) =>
  apiFetch<{ detail: string }>(`/api/pool/picks/${id}`, { method: "DELETE" });

// Leaderboard
export const fetchLeaderboard = (params?: Record<string, string>) => {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return apiFetch<LeaderboardEntry[]>(`/api/pool/leaderboard${qs}`);
};

// Resolve picks
export const resolvePoolPicks = () =>
  apiFetch<{ detail: string; resolved_count: number }>("/api/pool/resolve", {
    method: "POST",
  });

// Upload avatar file
export const uploadAvatar = async (file: File): Promise<{ url: string; filename: string }> => {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/api/pool/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Upload failed: ${err}`);
  }
  return res.json();
};

