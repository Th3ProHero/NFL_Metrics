"""
NFL BetMaster — Live ETL Worker
=================================
Asynchronous worker that polls the ESPN Scoreboard API and upserts
game state into PostgreSQL.

Polling strategy:
  • If any game is in_progress → poll every 15 seconds
  • If all games are pre/post  → poll every 4 hours (14 400s)
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.database import get_pool

logger = logging.getLogger("nfl.etl_live")

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
)

# Retry / backoff
MAX_RETRIES = 5
BASE_BACKOFF_SECONDS = 2


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_status(status_type: dict) -> str:
    """Map ESPN status.type to our game_status enum."""
    state = status_type.get("state", "pre")
    if state == "in":
        return "in_progress"
    return state  # "pre" or "post"


def _safe_int(value, default=None):
    """Safely convert a value to int."""
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


# ─── Team Upsert ─────────────────────────────────────────────────────────────

async def _upsert_team(conn, team_data: dict) -> int | None:
    """Upsert a team from ESPN data and return our internal team id."""
    espn_id = str(team_data.get("id", ""))
    if not espn_id:
        return None

    abbreviation = team_data.get("abbreviation", "")
    name = team_data.get("displayName", team_data.get("shortDisplayName", ""))
    logo = team_data.get("logo", "")
    color = team_data.get("color", "")
    if color and not color.startswith("#"):
        color = f"#{color}"

    row = await conn.fetchrow(
        """
        INSERT INTO teams (espn_id, abbreviation, name, conference, division, logo_url, primary_color)
        VALUES ($1, $2, $3, '', '', $4, $5)
        ON CONFLICT (espn_id) DO UPDATE
            SET abbreviation = EXCLUDED.abbreviation,
                name         = EXCLUDED.name,
                logo_url     = EXCLUDED.logo_url,
                primary_color= EXCLUDED.primary_color
        RETURNING id
        """,
        espn_id, abbreviation, name, logo, color,
    )
    return row["id"] if row else None


# ─── Game Upsert ─────────────────────────────────────────────────────────────

async def _upsert_game(conn, event: dict) -> None:
    """Parse one ESPN event and upsert into the games table."""
    espn_event_id = str(event.get("id", ""))
    if not espn_event_id:
        return

    # --- Competition details (first competition) ---
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])

    home_data = away_data = None
    home_score = away_score = 0
    for comp in competitors:
        team_info = comp.get("team", {})
        score = _safe_int(comp.get("score"), 0)
        if comp.get("homeAway") == "home":
            home_data = team_info
            home_score = score
        else:
            away_data = team_info
            away_score = score

    home_team_id = await _upsert_team(conn, home_data) if home_data else None
    away_team_id = await _upsert_team(conn, away_data) if away_data else None

    # --- Status ---
    status_obj = event.get("status", {})
    status_type = status_obj.get("type", {})
    status = _parse_status(status_type)
    period = _safe_int(status_obj.get("period"))
    clock = status_obj.get("displayClock", "")

    # --- Situation (down, distance, possession) ---
    situation = competition.get("situation", {})
    possession_espn_id = None
    if "possession" in situation:
        possession_espn_id = str(situation["possession"])
    down = _safe_int(situation.get("down"))
    distance = _safe_int(situation.get("distance"))
    yard_line = _safe_int(situation.get("yardLine"))
    yard_line_territory = situation.get("possessionText", "")[:5] if situation.get("possessionText") else None

    # Resolve possession team_id
    possession_team_id = None
    if possession_espn_id:
        row = await conn.fetchrow("SELECT id FROM teams WHERE espn_id = $1", possession_espn_id)
        if row:
            possession_team_id = row["id"]

    # --- Season / week ---
    season_info = event.get("season", {})
    season = _safe_int(season_info.get("year"), datetime.now().year)
    week_info = event.get("week", {})
    week = _safe_int(week_info.get("number"), 0)

    # --- Metadata ---
    game_type = season_info.get("slug", "regular-season")
    start_time_str = event.get("date")
    start_time = None
    if start_time_str:
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    venue_data = competition.get("venue", {})
    venue = venue_data.get("fullName", "")

    broadcasts = competition.get("broadcasts", [])
    broadcast = ""
    if broadcasts:
        names = broadcasts[0].get("names", [])
        broadcast = ", ".join(names) if names else ""

    # --- Upsert ---
    await conn.execute(
        """
        INSERT INTO games (
            espn_event_id, season, week, game_type, status,
            home_team_id, away_team_id, home_score, away_score,
            quarter, clock, possession_team_id,
            down, distance, yard_line, yard_line_territory,
            start_time, venue, broadcast, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5::game_status,
            $6, $7, $8, $9,
            $10, $11, $12,
            $13, $14, $15, $16,
            $17, $18, $19, NOW()
        )
        ON CONFLICT (espn_event_id) DO UPDATE SET
            status              = EXCLUDED.status,
            home_score          = EXCLUDED.home_score,
            away_score          = EXCLUDED.away_score,
            quarter             = EXCLUDED.quarter,
            clock               = EXCLUDED.clock,
            possession_team_id  = EXCLUDED.possession_team_id,
            down                = EXCLUDED.down,
            distance            = EXCLUDED.distance,
            yard_line           = EXCLUDED.yard_line,
            yard_line_territory = EXCLUDED.yard_line_territory,
            venue               = EXCLUDED.venue,
            broadcast           = EXCLUDED.broadcast,
            updated_at          = NOW()
        """,
        espn_event_id, season, week, game_type, status,
        home_team_id, away_team_id, home_score, away_score,
        period, clock, possession_team_id,
        down, distance, yard_line, yard_line_territory,
        start_time, venue, broadcast,
    )
    logger.debug("Upserted game %s — %s vs %s (%s)", espn_event_id,
                 away_data.get("abbreviation", "?") if away_data else "?",
                 home_data.get("abbreviation", "?") if home_data else "?",
                 status)


# ─── Main Poll Function ─────────────────────────────────────────────────────

async def poll_espn_scoreboard() -> bool:
    """
    Fetch the ESPN scoreboard, upsert all events.
    Returns True if any game is currently in_progress.
    """
    pool = get_pool()
    has_live = False

    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.get(ESPN_SCOREBOARD_URL)
                resp.raise_for_status()
                data = resp.json()
                break
            except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as exc:
                wait = BASE_BACKOFF_SECONDS * (2 ** attempt)
                logger.warning(
                    "ESPN API attempt %d/%d failed (%s). Retrying in %ds...",
                    attempt + 1, MAX_RETRIES, exc, wait,
                )
                if attempt + 1 == MAX_RETRIES:
                    logger.error("ESPN API unreachable after %d retries. Skipping cycle.", MAX_RETRIES)
                    return False
                await asyncio.sleep(wait)

    events = data.get("events", [])
    logger.info("ESPN returned %d events", len(events))

    async with pool.acquire() as conn:
        for event in events:
            try:
                await _upsert_game(conn, event)
                status = _parse_status(event.get("status", {}).get("type", {}))
                if status == "in_progress":
                    has_live = True
            except Exception:
                logger.exception("Error upserting event %s", event.get("id", "?"))

    return has_live


# ─── Adaptive Loop ──────────────────────────────────────────────────────────

POLL_LIVE_INTERVAL = 15         # seconds when games are live
POLL_IDLE_INTERVAL = 4 * 3600   # 4 hours when no live games

async def _resolve_pool_picks() -> None:
    """Resolve any pending pool picks for games that have finished."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            # Find finished games with unresolved picks
            rows = await conn.fetch("""
                SELECT DISTINCT g.id, g.home_team_id, g.away_team_id,
                       g.home_score, g.away_score
                FROM games g
                INNER JOIN pool_picks pk ON pk.game_id = g.id
                WHERE g.status = 'post' AND pk.is_correct IS NULL
            """)
            if not rows:
                return

            total = 0
            for row in rows:
                if row["home_score"] > row["away_score"]:
                    winner_id = row["home_team_id"]
                elif row["away_score"] > row["home_score"]:
                    winner_id = row["away_team_id"]
                else:
                    winner_id = None  # tie

                if winner_id is not None:
                    result = await conn.execute(
                        """
                        UPDATE pool_picks
                        SET is_correct = (picked_team_id = $1), resolved_at = NOW()
                        WHERE game_id = $2 AND is_correct IS NULL
                        """,
                        winner_id, row["id"],
                    )
                else:
                    result = await conn.execute(
                        """
                        UPDATE pool_picks
                        SET is_correct = FALSE, resolved_at = NOW()
                        WHERE game_id = $1 AND is_correct IS NULL
                        """,
                        row["id"],
                    )
                try:
                    total += int(result.split()[-1])
                except (ValueError, IndexError):
                    pass

            if total > 0:
                logger.info("Auto-resolved %d pool picks across %d games", total, len(rows))
    except Exception:
        logger.exception("Error auto-resolving pool picks")


async def etl_loop() -> None:
    """Run the adaptive polling loop forever."""
    logger.info("ETL Live loop started")
    while True:
        try:
            has_live = await poll_espn_scoreboard()

            # Auto-resolve pool picks for finished games
            await _resolve_pool_picks()

            interval = POLL_LIVE_INTERVAL if has_live else POLL_IDLE_INTERVAL
            label = "15s (live)" if has_live else "4h (idle)"
            logger.info("Next poll in %s", label)
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("ETL Live loop cancelled")
            break
        except Exception:
            logger.exception("Unexpected error in ETL loop; retrying in 30s")
            await asyncio.sleep(30)

