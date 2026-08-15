"""
NFL BetMaster v2.0 — Odds ETL Worker (Optimized Schedule)
==========================================================
PROBLEM (v1): Polling every 30 minutes consumed ~1,440 requests/month,
far exceeding The Odds API free tier of 500 requests/month.

SOLUTION (v2): Switch from a fixed-interval loop to a cron-based schedule
that fires ONLY at strategically valuable moments during the NFL week:

  • Tuesday  10:00 AM CT — Lines open for the upcoming week
  • Thursday  5:00 PM CT — Pre Thursday Night Football (last-minute moves)
  • Sunday    8:00 AM CT — Early morning line adjustments
  • Sunday   11:30 AM CT — Final adjustments before 12:00 PM CT kickoffs

This yields ~4 requests/week × ~22 NFL weeks = ~88 requests/season,
well within the 500/month free-tier budget.

The scheduler uses APScheduler CronTrigger with US Central timezone
(America/Chicago) since NFL schedules are anchored to ET/CT.
"""

import asyncio
import logging
import os
from datetime import datetime

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import get_pool

logger = logging.getLogger("nfl.etl_odds")

ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"

# ─── Timezone for NFL schedule alignment ────────────────────────────────────
# NFL week rhythm is US-based; CT is a neutral midpoint between ET and PT.
NFL_TIMEZONE = "America/Chicago"


def _american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds."""
    if american > 0:
        return round(1 + american / 100, 3)
    return round(1 + 100 / abs(american), 3)


async def poll_odds() -> None:
    """
    Fetch current NFL odds from The Odds API and store snapshots.

    Each call consumes 1 request from the free-tier quota. The response
    includes an 'x-requests-remaining' header so we can monitor usage.
    """
    api_key = os.getenv("ODDS_API_KEY", "")
    if not api_key:
        logger.warning("ODDS_API_KEY not set — skipping odds poll")
        return

    pool = get_pool()

    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        try:
            resp = await client.get(ODDS_API_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()

            # Log remaining API quota from response headers
            remaining = resp.headers.get("x-requests-remaining", "?")
            used = resp.headers.get("x-requests-used", "?")
            logger.info(
                "Odds API returned %d events (used: %s, remaining: %s)",
                len(data), used, remaining,
            )

        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as exc:
            logger.error("Odds API request failed: %s", exc)
            return

    async with pool.acquire() as conn:
        for event in data:
            home_team = event.get("home_team", "")
            away_team = event.get("away_team", "")

            # Match The Odds API event to our game via team name fuzzy match
            game_row = await conn.fetchrow(
                """
                SELECT g.id FROM games g
                JOIN teams ht ON g.home_team_id = ht.id
                JOIN teams at2 ON g.away_team_id = at2.id
                WHERE (ht.name ILIKE $1 OR ht.name ILIKE $2)
                  AND (at2.name ILIKE $3 OR at2.name ILIKE $4)
                  AND g.status != 'post'
                ORDER BY g.start_time DESC
                LIMIT 1
                """,
                f"%{home_team}%", home_team, f"%{away_team}%", away_team,
            )

            if not game_row:
                logger.debug("No matching game for %s vs %s", away_team, home_team)
                continue

            game_id = game_row["id"]

            # Process each bookmaker's markets
            for bookmaker in event.get("bookmakers", []):
                sportsbook = bookmaker.get("title", "Unknown")
                home_ml = away_ml = None
                spread = spread_home = spread_away = None
                total = over = under = None

                for market in bookmaker.get("markets", []):
                    key = market.get("key")
                    outcomes = market.get("outcomes", [])

                    if key == "h2h":
                        for o in outcomes:
                            price = o.get("price", 0)
                            if o.get("name") == home_team:
                                home_ml = price
                            else:
                                away_ml = price

                    elif key == "spreads":
                        for o in outcomes:
                            if o.get("name") == home_team:
                                spread = o.get("point")
                                spread_home = o.get("price")
                            else:
                                spread_away = o.get("price")

                    elif key == "totals":
                        for o in outcomes:
                            if o.get("name") == "Over":
                                total = o.get("point")
                                over = o.get("price")
                            else:
                                under = o.get("price")

                try:
                    await conn.execute(
                        """
                        INSERT INTO odds (
                            game_id, sportsbook,
                            home_moneyline, away_moneyline,
                            spread, spread_odds_home, spread_odds_away,
                            over_under, over_odds, under_odds
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                        game_id, sportsbook,
                        home_ml, away_ml,
                        spread, spread_home, spread_away,
                        total, over, under,
                    )
                except Exception:
                    logger.exception("Error inserting odds for game %d / %s", game_id, sportsbook)

    logger.info("Odds snapshot stored successfully at %s", datetime.now().isoformat())


# ─── Scheduler Setup ────────────────────────────────────────────────────────
# We use APScheduler's AsyncIOScheduler with CronTrigger objects.
# Each trigger fires at a specific day+time during the NFL week.
#
# SCHEDULE RATIONALE:
#   Tuesday  10:00 — Sportsbooks open lines for the following week
#   Thursday 17:00 — Final adjustments before Thursday Night Football
#   Sunday   08:00 — Early movers (weather, late-week injury designations)
#   Sunday   11:30 — Last-minute steam moves ~30min before main slate kickoff
# ─────────────────────────────────────────────────────────────────────────────

_scheduler: AsyncIOScheduler | None = None


def _sync_poll_wrapper() -> None:
    """
    APScheduler calls sync functions from its executor.
    We bridge to async by scheduling the coroutine on the running loop.
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(poll_odds())
    else:
        loop.run_until_complete(poll_odds())


def start_odds_scheduler() -> AsyncIOScheduler:
    """
    Create and start the APScheduler with NFL-optimized cron triggers.
    Returns the scheduler instance so the lifespan can shut it down.
    """
    global _scheduler

    _scheduler = AsyncIOScheduler(timezone=NFL_TIMEZONE)

    # ── Tuesday 10:00 AM CT — Line opening ──
    _scheduler.add_job(
        poll_odds,
        CronTrigger(day_of_week="tue", hour=10, minute=0, timezone=NFL_TIMEZONE),
        id="odds_tuesday_open",
        name="Odds: Tuesday line open",
        replace_existing=True,
    )

    # ── Thursday 5:00 PM CT — Pre-TNF ──
    _scheduler.add_job(
        poll_odds,
        CronTrigger(day_of_week="thu", hour=17, minute=0, timezone=NFL_TIMEZONE),
        id="odds_thursday_tnf",
        name="Odds: Thursday pre-TNF",
        replace_existing=True,
    )

    # ── Sunday 8:00 AM CT — Early adjustments ──
    _scheduler.add_job(
        poll_odds,
        CronTrigger(day_of_week="sun", hour=8, minute=0, timezone=NFL_TIMEZONE),
        id="odds_sunday_early",
        name="Odds: Sunday early",
        replace_existing=True,
    )

    # ── Sunday 11:30 AM CT — Final pre-kickoff ──
    _scheduler.add_job(
        poll_odds,
        CronTrigger(day_of_week="sun", hour=11, minute=30, timezone=NFL_TIMEZONE),
        id="odds_sunday_final",
        name="Odds: Sunday final pre-kickoff",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Odds scheduler started with %d cron jobs (TZ: %s)",
        len(_scheduler.get_jobs()), NFL_TIMEZONE,
    )
    for job in _scheduler.get_jobs():
        logger.info("  → %s | next run: %s", job.name, job.next_run_time)

    return _scheduler


def stop_odds_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Odds scheduler shut down")
        _scheduler = None
