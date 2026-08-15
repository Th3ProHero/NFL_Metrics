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

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.database import init_pool, close_pool, fetch, fetchrow, fetchval, execute
from app.models import (
    BetCreate, BetOut, BetResult, BetSummary, BetUpdate,
    GameOut, OddsOut, TeamOut, TeamStats,
    SimulationRequest, SimulationResult,
    InjuryReport, InjuryAnalysisResult,
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
    }


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
