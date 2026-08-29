"""
NFL BetMaster v2.0 — FastAPI Application
==========================================
Main API server providing:
  • REST endpoints for games, teams, bets (CRUD), odds, stats
  • SSE streaming for live game updates
  • Monte Carlo simulation endpoint (CPU vectorized via Numba/NumPy)
  • NLP injury analysis endpoint (remote inference server)
  • Telegram +EV alert integration
  • Background ETL workers for ESPN + scheduled Odds data
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional

import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.database import init_pool, close_pool, fetch, fetchrow, fetchval, execute
from app.models import (
    BetCreate, BetOut, BetResult, BetSummary, BetUpdate,
    GameOut, OddsOut, TeamOut, TeamStats,
    SimulationRequest, SimulationResult,
    InjuryReport, InjuryAnalysisResult,
    PlayerOut, PositionGroup, TeamRoster,
    PoolPlayerCreate, PoolPlayerUpdate, PoolPlayerOut,
    PoolPickCreate, PoolPickBatchCreate, PoolPickOut,
    LeaderboardEntry,
)
from app.etl_live import etl_loop
from app.etl_odds import start_odds_scheduler, stop_odds_scheduler
from app.simulations import run_simulation, generate_synthetic_epa
from app.nlp_analysis import analyze_injuries
from app.alerts import check_and_alert_ev, format_injury_alert, send_telegram_message

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-18s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("nfl.api")

# ─── Background task references ─────────────────────────────────────────────

_etl_tasks: list[asyncio.Task] = []


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB pool + launch ETL workers + odds scheduler. Shutdown: cancel + close."""
    # Startup
    await init_pool()
    logger.info("Starting ETL background workers...")
    _etl_tasks.append(asyncio.create_task(etl_loop(), name="etl_live"))

    # v2.0: Use cron-based scheduler instead of polling loop
    logger.info("Starting Odds cron scheduler...")
    start_odds_scheduler()

    yield

    # Shutdown
    logger.info("Shutting down ETL workers...")
    for task in _etl_tasks:
        task.cancel()
    await asyncio.gather(*_etl_tasks, return_exceptions=True)

    # v2.0: Stop the odds scheduler
    stop_odds_scheduler()

    await close_pool()
    logger.info("Cleanup complete")


# ─── App Instance ────────────────────────────────────────────────────────────

app = FastAPI(
    title="NFL BetMaster API",
    version="2.0.0",
    description="NFL analytics, live scores, CPU-vectorized Monte Carlo simulations, NLP injury analysis, odds tracking, and bet management",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:4000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Uploads directory & static files ────────────────────────────────────────

UPLOAD_DIR = Path("/app/uploads") if os.path.exists("/app") else Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")



# ─── Health Check ────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    try:
        count = await fetchval("SELECT COUNT(*) FROM teams")

        # v2.0: Report simulation engine availability
        sim_engine = "numpy_cpu"
        try:
            from app.simulations import _NUMBA_AVAILABLE
            sim_engine = "numba_cpu" if _NUMBA_AVAILABLE else "numpy_cpu"
        except Exception:
            pass

        return {
            "status": "healthy",
            "version": "2.0.0",
            "teams_loaded": count,
            "simulation_engine": sim_engine,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        return {"status": "unhealthy", "error": str(exc)}


# ─── Manual Refresh ──────────────────────────────────────────────────────────

@app.post("/api/refresh", tags=["System"])
async def manual_refresh():
    """
    Manually trigger an ESPN scoreboard sync.

    Forces the ETL to re-fetch all game data from ESPN immediately,
    without waiting for the next scheduled poll cycle.
    """
    from app.etl_live import poll_espn_scoreboard
    try:
        has_live = await poll_espn_scoreboard()
        return {
            "status": "ok",
            "has_live_games": has_live,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.exception("Manual refresh failed")
        raise HTTPException(status_code=500, detail=f"Refresh failed: {exc}")


# =============================================================================
#  TEAMS
# =============================================================================

@app.get("/api/teams", response_model=list[TeamOut], tags=["Teams"])
async def list_teams(conference: str | None = None, division: str | None = None):
    """List all NFL teams with optional filtering."""
    query = "SELECT * FROM teams WHERE 1=1"
    params = []
    idx = 1
    if conference:
        query += f" AND conference = ${idx}"
        params.append(conference)
        idx += 1
    if division:
        query += f" AND division = ${idx}"
        params.append(division)
        idx += 1
    query += " ORDER BY conference, division, name"
    rows = await fetch(query, *params)
    return [dict(r) for r in rows]


# =============================================================================
#  GAMES
# =============================================================================

def _build_game_dict(row) -> dict:
    """Convert a joined game row to a GameOut-compatible dict."""
    d = dict(row)
    # Nest team objects
    if d.get("home_team_name"):
        d["home_team"] = {
            "id": d.pop("home_team_db_id", d.get("home_team_id")),
            "espn_id": d.pop("home_espn_id", ""),
            "abbreviation": d.pop("home_abbreviation", ""),
            "name": d.pop("home_team_name", ""),
            "conference": d.pop("home_conference", ""),
            "division": d.pop("home_division", ""),
            "logo_url": d.pop("home_logo", None),
            "primary_color": d.pop("home_color", None),
        }
    if d.get("away_team_name"):
        d["away_team"] = {
            "id": d.pop("away_team_db_id", d.get("away_team_id")),
            "espn_id": d.pop("away_espn_id", ""),
            "abbreviation": d.pop("away_abbreviation", ""),
            "name": d.pop("away_team_name", ""),
            "conference": d.pop("away_conference", ""),
            "division": d.pop("away_division", ""),
            "logo_url": d.pop("away_logo", None),
            "primary_color": d.pop("away_color", None),
        }
    return d

GAMES_JOIN_SQL = """
    SELECT
        g.*,
        ht.id AS home_team_db_id, ht.espn_id AS home_espn_id,
        ht.abbreviation AS home_abbreviation, ht.name AS home_team_name,
        ht.conference AS home_conference, ht.division AS home_division,
        ht.logo_url AS home_logo, ht.primary_color AS home_color,
        at2.id AS away_team_db_id, at2.espn_id AS away_espn_id,
        at2.abbreviation AS away_abbreviation, at2.name AS away_team_name,
        at2.conference AS away_conference, at2.division AS away_division,
        at2.logo_url AS away_logo, at2.primary_color AS away_color
    FROM games g
    LEFT JOIN teams ht  ON g.home_team_id = ht.id
    LEFT JOIN teams at2 ON g.away_team_id = at2.id
"""


@app.get("/api/games", response_model=list[GameOut], tags=["Games"])
async def list_games(
    season: int | None = None,
    week: int | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List games with optional season/week/status filters."""
    query = GAMES_JOIN_SQL + " WHERE 1=1"
    params = []
    idx = 1
    if season:
        query += f" AND g.season = ${idx}"
        params.append(season)
        idx += 1
    if week:
        query += f" AND g.week = ${idx}"
        params.append(week)
        idx += 1
    if status:
        query += f" AND g.status = ${idx}::game_status"
        params.append(status)
        idx += 1
    query += f" ORDER BY g.start_time DESC LIMIT ${idx}"
    params.append(limit)
    rows = await fetch(query, *params)
    return [_build_game_dict(r) for r in rows]


@app.get("/api/games/{game_id}", response_model=GameOut, tags=["Games"])
async def get_game(game_id: int):
    """Get a single game by ID."""
    row = await fetchrow(GAMES_JOIN_SQL + " WHERE g.id = $1", game_id)
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")
    return _build_game_dict(row)


# =============================================================================
#  LIVE GAMES — SSE Streaming
# =============================================================================

async def _live_games_generator() -> AsyncGenerator[str, None]:
    """Yield JSON of in-progress (and recent pre) games every 5 seconds."""
    while True:
        try:
            rows = await fetch(
                GAMES_JOIN_SQL + " WHERE g.status IN ('in_progress', 'pre') ORDER BY g.start_time ASC",
            )
            games = [_build_game_dict(r) for r in rows]

            # Fetch latest odds for each game
            for game in games:
                odds_row = await fetchrow(
                    "SELECT * FROM odds WHERE game_id = $1 ORDER BY captured_at DESC LIMIT 1",
                    game["id"],
                )
                if odds_row:
                    game["latest_odds"] = dict(odds_row)

            # Serialize datetimes
            payload = json.dumps(games, default=str)
            yield payload
        except Exception as exc:
            logger.error("SSE generator error: %s", exc)
            yield json.dumps({"error": str(exc)})

        await asyncio.sleep(5)


@app.get("/api/live-games", tags=["Live"])
async def live_games_sse():
    """Server-Sent Events endpoint streaming live game data."""
    return EventSourceResponse(
        _live_games_generator(),
        media_type="text/event-stream",
    )


# =============================================================================
#  ODDS
# =============================================================================

@app.get("/api/odds/{game_id}", response_model=list[OddsOut], tags=["Odds"])
async def get_odds_history(game_id: int, limit: int = Query(50, ge=1, le=500)):
    """Get historical odds snapshots for a specific game."""
    rows = await fetch(
        "SELECT * FROM odds WHERE game_id = $1 ORDER BY captured_at DESC LIMIT $2",
        game_id, limit,
    )
    return [dict(r) for r in rows]


# =============================================================================
#  STATS
# =============================================================================

@app.get("/api/stats/{team_id}", response_model=TeamStats, tags=["Stats"])
async def get_team_stats(team_id: int):
    """Get historical statistics for a team."""
    team_row = await fetchrow("SELECT * FROM teams WHERE id = $1", team_id)
    if not team_row:
        raise HTTPException(status_code=404, detail="Team not found")

    # Aggregate points from completed games
    stats_row = await fetchrow(
        """
        SELECT
            COUNT(*) AS total_games,
            COALESCE(SUM(CASE
                WHEN home_team_id = $1 THEN home_score
                WHEN away_team_id = $1 THEN away_score
                ELSE 0 END), 0) AS points_for,
            COALESCE(SUM(CASE
                WHEN home_team_id = $1 THEN away_score
                WHEN away_team_id = $1 THEN home_score
                ELSE 0 END), 0) AS points_against,
            COALESCE(SUM(CASE
                WHEN (home_team_id = $1 AND home_score > away_score)
                  OR (away_team_id = $1 AND away_score > home_score)
                THEN 1 ELSE 0 END), 0) AS wins,
            COALESCE(SUM(CASE
                WHEN (home_team_id = $1 AND home_score < away_score)
                  OR (away_team_id = $1 AND away_score < home_score)
                THEN 1 ELSE 0 END), 0) AS losses
        FROM games
        WHERE (home_team_id = $1 OR away_team_id = $1) AND status = 'post'
        """,
        team_id,
    )

    wins = stats_row["wins"] if stats_row else 0
    losses = stats_row["losses"] if stats_row else 0
    total = stats_row["total_games"] if stats_row else 0
    ties = total - wins - losses
    record = f"{wins}-{losses}" + (f"-{ties}" if ties > 0 else "")

    pf = float(stats_row["points_for"]) if stats_row else 0
    pa = float(stats_row["points_against"]) if stats_row else 0

    # Recent games
    recent_rows = await fetch(
        GAMES_JOIN_SQL + """
        WHERE (g.home_team_id = $1 OR g.away_team_id = $1) AND g.status = 'post'
        ORDER BY g.start_time DESC LIMIT 10
        """,
        team_id,
    )
    recent_games = [_build_game_dict(r) for r in recent_rows]

    # Upcoming games
    upcoming_rows = await fetch(
        GAMES_JOIN_SQL + """
        WHERE (g.home_team_id = $1 OR g.away_team_id = $1) AND g.status IN ('pre', 'in_progress')
        ORDER BY g.start_time ASC
        """,
        team_id,
    )
    upcoming_games = [_build_game_dict(r) for r in upcoming_rows]
    
    # Check for latest odds for upcoming games
    for game in upcoming_games:
        odds_row = await fetchrow(
            "SELECT * FROM odds WHERE game_id = $1 ORDER BY captured_at DESC LIMIT 1",
            game["id"],
        )
        if odds_row:
            game["latest_odds"] = dict(odds_row)

    return {
        "team": dict(team_row),
        "record": record,
        "points_for": pf,
        "points_against": pa,
        "epa_per_play": None,      # Populated by nfl_data_py integration
        "pass_epa": None,
        "rush_epa": None,
        "defensive_epa": None,
        "recent_games": recent_games,
        "upcoming_games": upcoming_games,
    }


# =============================================================================
#  ROSTER (ESPN live-fetch with in-memory cache)
# =============================================================================

import time as _time
import httpx as _httpx

# Simple in-memory cache: { espn_id: (timestamp, data) }
_roster_cache: dict[str, tuple[float, dict]] = {}
_ROSTER_CACHE_TTL = 3600  # 1 hour

# Position sort priority — key positions first
_POS_PRIORITY = {
    "QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4,
    "OT": 5, "OG": 5, "G": 5, "OL": 5, "C": 6, "T": 5,
    "DE": 10, "DT": 11, "NT": 12, "DL": 12,
    "OLB": 13, "ILB": 14, "MLB": 14, "LB": 13,
    "CB": 15, "S": 16, "FS": 16, "SS": 16, "DB": 17,
    "K": 20, "P": 21, "LS": 22,
}


def _parse_espn_roster(data: dict, team_id: int, team_name: str) -> dict:
    """Parse ESPN roster JSON into our TeamRoster structure."""
    groups = []
    total = 0
    season_year = data.get("season", {}).get("year")

    for group in data.get("athletes", []):
        group_name = group.get("position", "Unknown").title()
        # ESPN uses lowercase: "offense", "defense", "specialTeams"
        if group_name == "Specialteams":
            group_name = "Special Teams"

        players = []
        for athlete in group.get("items", []):
            pos_data = athlete.get("position", {})
            headshot = athlete.get("headshot", {})
            college_data = athlete.get("college", {})
            experience = athlete.get("experience", {})
            status_data = athlete.get("status", {})

            # Parse injuries
            injury_list = []
            for inj in athlete.get("injuries", []):
                desc = inj.get("type", {}).get("description", "")
                detail = inj.get("details", {}).get("detail", "")
                injury_str = f"{desc}: {detail}" if detail else desc
                if injury_str:
                    injury_list.append(injury_str)

            player = {
                "espn_id": str(athlete.get("id", "")),
                "full_name": athlete.get("fullName", athlete.get("displayName", "")),
                "jersey": athlete.get("jersey"),
                "position": pos_data.get("abbreviation", ""),
                "position_name": pos_data.get("displayName", pos_data.get("name", "")),
                "headshot_url": headshot.get("href") if headshot else None,
                "height": athlete.get("displayHeight"),
                "weight": athlete.get("displayWeight"),
                "age": athlete.get("age"),
                "experience_years": experience.get("years", 0),
                "college": college_data.get("shortName", college_data.get("name")) if college_data else None,
                "status": status_data.get("name", "Active"),
                "injuries": injury_list,
            }
            players.append(player)

        # Sort players: by position priority, then by jersey number
        players.sort(key=lambda p: (
            _POS_PRIORITY.get(p["position"], 50),
            int(p["jersey"]) if p.get("jersey") and p["jersey"].isdigit() else 999,
        ))

        total += len(players)
        groups.append({
            "name": group_name,
            "players": players,
            "count": len(players),
        })

    return {
        "team_id": team_id,
        "team_name": team_name,
        "season": season_year,
        "groups": groups,
        "total_players": total,
    }


@app.get("/api/teams/{team_id}/roster", response_model=TeamRoster, tags=["Teams"])
async def get_team_roster(team_id: int):
    """
    Get the current roster for a team, fetched live from ESPN.

    Results are cached in memory for 1 hour to avoid excessive API calls.
    Players are grouped by position category (Offense, Defense, Special Teams)
    and sorted by position priority within each group.
    """
    # Look up the team's ESPN ID
    team_row = await fetchrow("SELECT * FROM teams WHERE id = $1", team_id)
    if not team_row:
        raise HTTPException(status_code=404, detail="Team not found")

    espn_id = team_row["espn_id"]
    team_name = team_row["name"]

    # Check cache
    now = _time.time()
    if espn_id in _roster_cache:
        cached_at, cached_data = _roster_cache[espn_id]
        if now - cached_at < _ROSTER_CACHE_TTL:
            logger.debug("Roster cache hit for %s (team %d)", espn_id, team_id)
            return cached_data

    # Fetch from ESPN
    espn_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{espn_id}/roster"
    try:
        async with _httpx.AsyncClient(timeout=_httpx.Timeout(15.0)) as client:
            resp = await client.get(espn_url)
            resp.raise_for_status()
            raw = resp.json()
    except Exception as exc:
        logger.error("Failed to fetch roster for team %d (ESPN %s): %s", team_id, espn_id, exc)
        # Return cached data if available (even if stale)
        if espn_id in _roster_cache:
            logger.warning("Returning stale cache for team %d", team_id)
            return _roster_cache[espn_id][1]
        raise HTTPException(status_code=502, detail=f"ESPN API error: {exc}")

    # Parse and cache
    roster_data = _parse_espn_roster(raw, team_id, team_name)
    _roster_cache[espn_id] = (now, roster_data)
    logger.info("Fetched roster for %s: %d players", team_name, roster_data["total_players"])

    return roster_data


# =============================================================================
#  v2.0: MONTE CARLO SIMULATION
# =============================================================================

@app.post("/api/simulate/{game_id}", response_model=SimulationResult, tags=["Simulation"])
async def simulate_game(game_id: int, req: Optional[SimulationRequest] = None):
    """
    Run a Monte Carlo simulation for a given game.

    Uses Numba @njit(parallel=True) for multi-core JIT-compiled simulation
    on CPU. Falls back to vectorized NumPy if Numba is unavailable.
    The simulation uses EPA (Expected Points Added) distributions to
    model play-by-play outcomes.

    If no historical EPA data exists, synthetic distributions are used
    based on league averages.

    After simulation, if odds are available, the endpoint also calculates
    Expected Value (EV) and fires a Telegram alert if +EV > 5%.
    """
    # Fetch game and team data
    game_row = await fetchrow(GAMES_JOIN_SQL + " WHERE g.id = $1", game_id)
    if not game_row:
        raise HTTPException(status_code=404, detail="Game not found")

    game = _build_game_dict(game_row)
    home_team = game.get("home_team", {})
    away_team = game.get("away_team", {})
    n_sims = req.n_simulations if req and req.n_simulations else 10_000

    # In a production environment, you'd pull real EPA data from nfl_data_py.
    # For now, we generate synthetic distributions with slight team-specific biases.
    # A positive offensive EPA mean = above-average offense.
    # A negative defensive EPA mean = above-average defense (holding opponents below avg).
    home_off_epa = generate_synthetic_epa(mean=0.05, std=0.45, n=500)
    home_def_epa = generate_synthetic_epa(mean=-0.02, std=0.40, n=500)
    away_off_epa = generate_synthetic_epa(mean=0.00, std=0.45, n=500)
    away_def_epa = generate_synthetic_epa(mean=0.00, std=0.40, n=500)

    # Run simulation
    try:
        result = run_simulation(home_off_epa, home_def_epa, away_off_epa, away_def_epa, n_sims)
    except Exception as exc:
        logger.exception("Simulation failed for game %d", game_id)
        raise HTTPException(status_code=500, detail=f"Simulation error: {exc}")

    # Enrich with team names
    result["game_id"] = game_id
    result["home_team"] = home_team.get("name", "Home")
    result["away_team"] = away_team.get("name", "Away")

    # ── Check for +EV and alert via Telegram ──
    odds_row = await fetchrow(
        "SELECT * FROM odds WHERE game_id = $1 ORDER BY captured_at DESC LIMIT 1",
        game_id,
    )
    if odds_row and odds_row.get("home_moneyline"):
        # Check home team ML
        ev_home = await check_and_alert_ev(
            team_name=home_team.get("name", "Home"),
            bet_type="Moneyline",
            win_probability=result["home_win_prob"],
            american_odds=odds_row["home_moneyline"],
            game_info=f"vs {away_team.get('abbreviation', '?')} (Week {game.get('week', '?')})",
        )
        result["ev_home"] = ev_home

    if odds_row and odds_row.get("away_moneyline"):
        # Check away team ML
        ev_away = await check_and_alert_ev(
            team_name=away_team.get("name", "Away"),
            bet_type="Moneyline",
            win_probability=result["away_win_prob"],
            american_odds=odds_row["away_moneyline"],
            game_info=f"@ {home_team.get('abbreviation', '?')} (Week {game.get('week', '?')})",
        )
        result["ev_away"] = ev_away

    return result


# =============================================================================
#  v2.0: NLP INJURY ANALYSIS
# =============================================================================

@app.post("/api/injuries/analyze", response_model=InjuryAnalysisResult, tags=["NLP Analysis"])
async def analyze_injury_report(report: InjuryReport):
    """
    Analyze an injury report using a remote LLM inference server.

    Sends the injury data to the server at OLLAMA_BASE_URL (e.g. a Jetson
    device on the local network), which runs a model like Llama 3 to
    evaluate the impact on the point spread.

    If the inference server is unavailable, falls back to a rule-based
    heuristic that estimates impact based on position weights.
    """
    result = await analyze_injuries(
        team_name=report.team_name,
        opponent_name=report.opponent_name,
        injuries=[inj.model_dump() for inj in report.injuries],
        model=report.model,
    )

    # Optionally send a Telegram alert for significant injury impacts
    if abs(result.get("spread_adjustment", 0)) >= 2.0:
        alert_msg = format_injury_alert(
            team_name=report.team_name,
            game_info=f"vs {report.opponent_name}",
            nlp_result=result,
        )
        await send_telegram_message(alert_msg)

    return result


# =============================================================================
#  BETS — CRUD
# =============================================================================

@app.get("/api/bets", response_model=list[BetOut], tags=["Bets"])
async def list_bets(
    result: str | None = None,
    limit: int = Query(50, ge=1, le=500),
):
    """List all user bets with optional result filter."""
    query = "SELECT * FROM user_bets WHERE 1=1"
    params = []
    idx = 1
    if result:
        query += f" AND result = ${idx}::bet_result"
        params.append(result)
        idx += 1
    query += f" ORDER BY created_at DESC LIMIT ${idx}"
    params.append(limit)
    rows = await fetch(query, *params)
    return [dict(r) for r in rows]


@app.post("/api/bets", response_model=BetOut, status_code=201, tags=["Bets"])
async def create_bet(bet: BetCreate):
    """Create a new bet entry."""
    row = await fetchrow(
        """
        INSERT INTO user_bets (game_id, bet_type, pick, odds_decimal, odds_american, stake, notes)
        VALUES ($1, $2::bet_type, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        bet.game_id, bet.bet_type.value, bet.pick,
        bet.odds_decimal, bet.odds_american, bet.stake, bet.notes,
    )
    return dict(row)


@app.put("/api/bets/{bet_id}", response_model=BetOut, tags=["Bets"])
async def update_bet(bet_id: int, bet: BetUpdate):
    """Update an existing bet (e.g., to resolve it)."""
    existing = await fetchrow("SELECT * FROM user_bets WHERE id = $1", bet_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bet not found")

    updates = {}
    if bet.bet_type is not None:
        updates["bet_type"] = bet.bet_type.value
    if bet.pick is not None:
        updates["pick"] = bet.pick
    if bet.odds_decimal is not None:
        updates["odds_decimal"] = bet.odds_decimal
    if bet.odds_american is not None:
        updates["odds_american"] = bet.odds_american
    if bet.stake is not None:
        updates["stake"] = bet.stake
    if bet.result is not None:
        updates["result"] = bet.result.value
    if bet.profit is not None:
        updates["profit"] = bet.profit
    if bet.notes is not None:
        updates["notes"] = bet.notes

    # Automatically set resolved_at when result changes from pending
    if bet.result and bet.result != BetResult.PENDING:
        updates["resolved_at"] = datetime.utcnow()

    # Auto-calculate profit if result is set and profit is not
    if bet.result and bet.profit is None:
        stake = bet.stake if bet.stake is not None else float(existing["stake"])
        odds = bet.odds_decimal if bet.odds_decimal is not None else float(existing["odds_decimal"])
        if bet.result == BetResult.WON:
            updates["profit"] = round(stake * odds - stake, 2)
        elif bet.result == BetResult.LOST:
            updates["profit"] = -stake
        elif bet.result in (BetResult.PUSH, BetResult.VOID):
            updates["profit"] = 0

    if not updates:
        return dict(existing)

    set_clauses = []
    params = []
    for i, (col, val) in enumerate(updates.items(), start=1):
        if col in ("bet_type", "result"):
            set_clauses.append(f"{col} = ${i}::{col}")
        else:
            set_clauses.append(f"{col} = ${i}")
        params.append(val)

    params.append(bet_id)
    query = f"UPDATE user_bets SET {', '.join(set_clauses)} WHERE id = ${len(params)} RETURNING *"
    row = await fetchrow(query, *params)
    return dict(row)


@app.delete("/api/bets/{bet_id}", tags=["Bets"])
async def delete_bet(bet_id: int):
    """Delete a bet entry."""
    result = await execute("DELETE FROM user_bets WHERE id = $1", bet_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Bet not found")
    return {"detail": "Bet deleted", "id": bet_id}


@app.get("/api/bets/summary", response_model=BetSummary, tags=["Bets"])
async def get_bet_summary():
    """Get aggregated summary of all bets — ROI, win rate, etc."""
    row = await fetchrow(
        """
        SELECT
            COUNT(*)                                               AS total_bets,
            COALESCE(SUM(stake), 0)                                AS total_staked,
            COALESCE(SUM(profit), 0)                               AS total_profit,
            COUNT(*) FILTER (WHERE result = 'won')                 AS wins,
            COUNT(*) FILTER (WHERE result = 'lost')                AS losses,
            COUNT(*) FILTER (WHERE result = 'push')                AS pushes,
            COUNT(*) FILTER (WHERE result = 'pending')             AS pending
        FROM user_bets
        """
    )

    total_staked = float(row["total_staked"])
    total_profit = float(row["total_profit"])
    wins = row["wins"]
    losses = row["losses"]
    decided = wins + losses

    return {
        "total_bets": row["total_bets"],
        "total_staked": total_staked,
        "total_profit": total_profit,
        "roi_percent": round((total_profit / total_staked * 100), 2) if total_staked > 0 else 0,
        "wins": wins,
        "losses": losses,
        "pushes": row["pushes"],
        "pending": row["pending"],
        "win_rate": round((wins / decided * 100), 2) if decided > 0 else 0,
    }


# =============================================================================
#  FRIENDS POOL — Players, Picks & Leaderboard
# =============================================================================

# ─── Helper: build a PoolPlayerOut dict with nested team objects ─────────────

POOL_PLAYER_JOIN_SQL = """
    SELECT
        pp.*,
        t1.id AS t1_id, t1.espn_id AS t1_espn, t1.abbreviation AS t1_abbr,
        t1.name AS t1_name, t1.conference AS t1_conf, t1.division AS t1_div,
        t1.logo_url AS t1_logo, t1.primary_color AS t1_color,
        t2.id AS t2_id, t2.espn_id AS t2_espn, t2.abbreviation AS t2_abbr,
        t2.name AS t2_name, t2.conference AS t2_conf, t2.division AS t2_div,
        t2.logo_url AS t2_logo, t2.primary_color AS t2_color,
        t3.id AS t3_id, t3.espn_id AS t3_espn, t3.abbreviation AS t3_abbr,
        t3.name AS t3_name, t3.conference AS t3_conf, t3.division AS t3_div,
        t3.logo_url AS t3_logo, t3.primary_color AS t3_color
    FROM pool_players pp
    LEFT JOIN teams t1 ON pp.fav_team_1 = t1.id
    LEFT JOIN teams t2 ON pp.fav_team_2 = t2.id
    LEFT JOIN teams t3 ON pp.fav_team_3 = t3.id
"""


def _build_pool_player(row) -> dict:
    """Convert a joined pool_players row into a PoolPlayerOut-compatible dict."""
    d = dict(row)
    result = {
        "id": d["id"],
        "name": d["name"],
        "avatar_url": d.get("avatar_url"),
        "created_at": d.get("created_at"),
    }
    # Nest fav team 1
    if d.get("t1_id"):
        result["fav_team_1"] = {
            "id": d["t1_id"], "espn_id": d["t1_espn"],
            "abbreviation": d["t1_abbr"], "name": d["t1_name"],
            "conference": d["t1_conf"], "division": d["t1_div"],
            "logo_url": d["t1_logo"], "primary_color": d["t1_color"],
        }
    if d.get("t2_id"):
        result["fav_team_2"] = {
            "id": d["t2_id"], "espn_id": d["t2_espn"],
            "abbreviation": d["t2_abbr"], "name": d["t2_name"],
            "conference": d["t2_conf"], "division": d["t2_div"],
            "logo_url": d["t2_logo"], "primary_color": d["t2_color"],
        }
    if d.get("t3_id"):
        result["fav_team_3"] = {
            "id": d["t3_id"], "espn_id": d["t3_espn"],
            "abbreviation": d["t3_abbr"], "name": d["t3_name"],
            "conference": d["t3_conf"], "division": d["t3_div"],
            "logo_url": d["t3_logo"], "primary_color": d["t3_color"],
        }
    return result


# ─── Pool Players CRUD ──────────────────────────────────────────────────────

ALLOWED_AVATAR_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_AVATAR_SIZE = 10 * 1024 * 1024  # 10 MB


@app.post("/api/pool/upload", tags=["Friends Pool"])
async def upload_pool_avatar(file: UploadFile = File(...)):
    """Upload an avatar image from user's gallery or files."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AVATAR_EXTS:
        if file.content_type == "image/jpeg":
            ext = ".jpg"
        elif file.content_type == "image/png":
            ext = ".png"
        elif file.content_type == "image/webp":
            ext = ".webp"
        elif file.content_type == "image/gif":
            ext = ".gif"
        else:
            raise HTTPException(
                status_code=400,
                detail="Formato no soportado. Usa JPG, PNG, WEBP o GIF.",
            )

    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=400,
            detail="La imagen supera el límite de 10 MB.",
        )

    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = UPLOAD_DIR / filename
    with open(dest_path, "wb") as f:
        f.write(content)

    return {"url": f"/api/uploads/{filename}", "filename": filename}


@app.get("/api/pool/players", response_model=list[PoolPlayerOut], tags=["Friends Pool"])
async def list_pool_players():
    """List all friends in the prediction pool."""
    rows = await fetch(POOL_PLAYER_JOIN_SQL + " ORDER BY pp.name")
    return [_build_pool_player(r) for r in rows]


@app.get("/api/pool/players/{player_id}", response_model=PoolPlayerOut, tags=["Friends Pool"])
async def get_pool_player(player_id: int):
    """Get a single pool player by ID."""
    row = await fetchrow(POOL_PLAYER_JOIN_SQL + " WHERE pp.id = $1", player_id)
    if not row:
        raise HTTPException(status_code=404, detail="Player not found")
    return _build_pool_player(row)


@app.post("/api/pool/players", response_model=PoolPlayerOut, status_code=201, tags=["Friends Pool"])
async def create_pool_player(player: PoolPlayerCreate):
    """Create a new friend profile in the pool."""
    row = await fetchrow(
        """
        INSERT INTO pool_players (name, avatar_url, fav_team_1, fav_team_2, fav_team_3)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        player.name, player.avatar_url,
        player.fav_team_1, player.fav_team_2, player.fav_team_3,
    )
    return await get_pool_player(row["id"])


@app.put("/api/pool/players/{player_id}", response_model=PoolPlayerOut, tags=["Friends Pool"])
async def update_pool_player(player_id: int, player: PoolPlayerUpdate):
    """Update a friend's profile."""
    existing = await fetchrow("SELECT * FROM pool_players WHERE id = $1", player_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Player not found")

    updates = {}
    if player.name is not None:
        updates["name"] = player.name
    if player.avatar_url is not None:
        updates["avatar_url"] = player.avatar_url
    if player.fav_team_1 is not None:
        updates["fav_team_1"] = player.fav_team_1
    if player.fav_team_2 is not None:
        updates["fav_team_2"] = player.fav_team_2
    if player.fav_team_3 is not None:
        updates["fav_team_3"] = player.fav_team_3

    if not updates:
        return await get_pool_player(player_id)

    set_clauses = []
    params = []
    for i, (col, val) in enumerate(updates.items(), start=1):
        set_clauses.append(f"{col} = ${i}")
        params.append(val)
    params.append(player_id)
    query = f"UPDATE pool_players SET {', '.join(set_clauses)} WHERE id = ${len(params)}"
    await execute(query, *params)
    return await get_pool_player(player_id)


@app.delete("/api/pool/players/{player_id}", tags=["Friends Pool"])
async def delete_pool_player(player_id: int):
    """Delete a friend from the pool (cascades to their picks)."""
    result = await execute("DELETE FROM pool_players WHERE id = $1", player_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Player not found")
    return {"detail": "Player deleted", "id": player_id}


# ─── Pool Picks ─────────────────────────────────────────────────────────────

@app.post("/api/pool/picks", response_model=list[PoolPickOut], status_code=201, tags=["Friends Pool"])
async def create_pool_picks(batch: PoolPickBatchCreate):
    """Register one or more game predictions. Uses upsert to allow changing picks."""
    created = []
    for pick in batch.picks:
        row = await fetchrow(
            """
            INSERT INTO pool_picks (player_id, game_id, picked_team_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (player_id, game_id)
            DO UPDATE SET picked_team_id = EXCLUDED.picked_team_id,
                          is_correct = NULL,
                          resolved_at = NULL
            RETURNING *
            """,
            pick.player_id, pick.game_id, pick.picked_team_id,
        )
        # Attach picked team info
        team_row = await fetchrow("SELECT * FROM teams WHERE id = $1", pick.picked_team_id)
        d = dict(row)
        if team_row:
            d["picked_team"] = dict(team_row)
        created.append(d)
    return created


@app.get("/api/pool/picks", response_model=list[PoolPickOut], tags=["Friends Pool"])
async def list_pool_picks(
    player_id: int | None = None,
    game_id: int | None = None,
    season: int | None = None,
    week: int | None = None,
):
    """List picks with optional filters."""
    query = """
        SELECT pk.*, t.id AS t_id, t.espn_id AS t_espn, t.abbreviation AS t_abbr,
               t.name AS t_name, t.conference AS t_conf, t.division AS t_div,
               t.logo_url AS t_logo, t.primary_color AS t_color
        FROM pool_picks pk
        LEFT JOIN teams t ON pk.picked_team_id = t.id
        LEFT JOIN games g ON pk.game_id = g.id
        WHERE 1=1
    """
    params = []
    idx = 1
    if player_id is not None:
        query += f" AND pk.player_id = ${idx}"
        params.append(player_id)
        idx += 1
    if game_id is not None:
        query += f" AND pk.game_id = ${idx}"
        params.append(game_id)
        idx += 1
    if season is not None:
        query += f" AND g.season = ${idx}"
        params.append(season)
        idx += 1
    if week is not None:
        query += f" AND g.week = ${idx}"
        params.append(week)
        idx += 1
    query += " ORDER BY pk.created_at DESC"
    rows = await fetch(query, *params)

    results = []
    for r in rows:
        d = dict(r)
        if d.get("t_id"):
            d["picked_team"] = {
                "id": d.pop("t_id"), "espn_id": d.pop("t_espn"),
                "abbreviation": d.pop("t_abbr"), "name": d.pop("t_name"),
                "conference": d.pop("t_conf"), "division": d.pop("t_div"),
                "logo_url": d.pop("t_logo"), "primary_color": d.pop("t_color"),
            }
        results.append(d)
    return results


@app.delete("/api/pool/picks/{pick_id}", tags=["Friends Pool"])
async def delete_pool_pick(pick_id: int):
    """Delete a prediction."""
    result = await execute("DELETE FROM pool_picks WHERE id = $1", pick_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Pick not found")
    return {"detail": "Pick deleted", "id": pick_id}


# ─── Resolve Picks ──────────────────────────────────────────────────────────

async def resolve_picks_for_game(game_id: int) -> int:
    """
    Resolve all pending picks for a finished game.
    Returns the number of picks resolved.
    """
    game = await fetchrow("SELECT * FROM games WHERE id = $1 AND status = 'post'", game_id)
    if not game:
        return 0

    # Determine winner
    if game["home_score"] > game["away_score"]:
        winner_id = game["home_team_id"]
    elif game["away_score"] > game["home_score"]:
        winner_id = game["away_team_id"]
    else:
        # Tie — mark all as incorrect (NFL regular season can tie)
        winner_id = None

    if winner_id is not None:
        result = await execute(
            """
            UPDATE pool_picks
            SET is_correct = (picked_team_id = $1),
                resolved_at = NOW()
            WHERE game_id = $2 AND is_correct IS NULL
            """,
            winner_id, game_id,
        )
    else:
        # Tie — no one wins
        result = await execute(
            """
            UPDATE pool_picks
            SET is_correct = FALSE,
                resolved_at = NOW()
            WHERE game_id = $1 AND is_correct IS NULL
            """,
            game_id,
        )
    # Extract count from "UPDATE N"
    try:
        return int(result.split()[-1])
    except (ValueError, IndexError):
        return 0


@app.post("/api/pool/resolve", tags=["Friends Pool"])
async def manual_resolve_picks():
    """
    Manually resolve all pending picks for finished games.
    This is also called automatically by the ETL worker.
    """
    finished_games = await fetch(
        """
        SELECT DISTINCT g.id
        FROM games g
        INNER JOIN pool_picks pk ON pk.game_id = g.id
        WHERE g.status = 'post' AND pk.is_correct IS NULL
        """
    )
    total_resolved = 0
    for row in finished_games:
        total_resolved += await resolve_picks_for_game(row["id"])

    return {
        "detail": f"Resolved {total_resolved} picks across {len(finished_games)} games",
        "resolved_count": total_resolved,
        "games_processed": len(finished_games),
    }


# ─── Leaderboard ────────────────────────────────────────────────────────────

@app.get("/api/pool/leaderboard", response_model=list[LeaderboardEntry], tags=["Friends Pool"])
async def get_leaderboard(
    season: int | None = None,
    week: int | None = None,
):
    """
    Get the prediction leaderboard, ranked by correct picks.
    Optionally filter by season and/or week.
    """
    # Get all players
    player_rows = await fetch(POOL_PLAYER_JOIN_SQL + " ORDER BY pp.name")
    players = [_build_pool_player(r) for r in player_rows]

    leaderboard = []
    for player in players:
        # Build pick stats query with optional filters
        stats_query = """
            SELECT
                COUNT(*) AS total_picks,
                COUNT(*) FILTER (WHERE pk.is_correct = TRUE) AS correct_picks
            FROM pool_picks pk
            LEFT JOIN games g ON pk.game_id = g.id
            WHERE pk.player_id = $1
        """
        params = [player["id"]]
        idx = 2
        if season is not None:
            stats_query += f" AND g.season = ${idx}"
            params.append(season)
            idx += 1
        if week is not None:
            stats_query += f" AND g.week = ${idx}"
            params.append(week)
            idx += 1

        stats = await fetchrow(stats_query, *params)
        total = stats["total_picks"] if stats else 0
        correct = stats["correct_picks"] if stats else 0

        # Calculate current streak (consecutive correct picks)
        streak_query = """
            SELECT pk.is_correct
            FROM pool_picks pk
            LEFT JOIN games g ON pk.game_id = g.id
            WHERE pk.player_id = $1 AND pk.is_correct IS NOT NULL
            ORDER BY g.start_time DESC
        """
        streak_rows = await fetch(streak_query, player["id"])
        current_streak = 0
        longest_streak = 0
        running = 0
        for sr in streak_rows:
            if sr["is_correct"]:
                if running >= 0:
                    running += 1
                else:
                    running = 1
            else:
                if running > 0:
                    running = -1
                else:
                    running -= 1
            if running > 0 and running > longest_streak:
                longest_streak = running
        # Current streak = how many recent correct in a row
        for sr in streak_rows:
            if sr["is_correct"]:
                current_streak += 1
            else:
                break

        leaderboard.append({
            "player": player,
            "correct_picks": correct,
            "total_picks": total,
            "accuracy": round((correct / total * 100), 1) if total > 0 else 0.0,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
        })

    # Sort by correct picks desc, then accuracy desc
    leaderboard.sort(key=lambda x: (x["correct_picks"], x["accuracy"]), reverse=True)
    return leaderboard
