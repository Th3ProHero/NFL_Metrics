"""
NFL BetMaster v2.0 — Telegram Alert System
============================================
Sends notifications to a Telegram chat when high-value (+EV) betting
opportunities are detected.

## Configuration (Environment Variables)
  TELEGRAM_BOT_TOKEN  — Token from @BotFather (e.g., "123456:ABC-DEF...")
  TELEGRAM_CHAT_ID    — Chat/channel ID to send alerts to

## How to Set Up
1. Message @BotFather on Telegram → /newbot → get your token
2. Add the bot to a group/channel or start a DM with it
3. Get your chat_id from https://api.telegram.org/bot{TOKEN}/getUpdates
4. Set both env vars in your .env file

## Alert Triggers
This module is called by the odds ETL and simulation endpoints.
When the calculated Expected Value (EV) exceeds a threshold (default 5%),
an alert is fired immediately.

## EV Calculation
  EV = (win_probability × potential_profit) - (loss_probability × stake)
  EV% = EV / stake × 100

  Example: Team at +150 (implied 40%), model says 50% real probability
    EV = (0.50 × $150) - (0.50 × $100) = $75 - $50 = $25
    EV% = 25% → ALERT!
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger("nfl.alerts")

# ─── Configuration ──────────────────────────────────────────────────────────

TELEGRAM_API_BASE = "https://api.telegram.org"
EV_THRESHOLD_PERCENT = 5.0  # Minimum +EV% to trigger an alert


def _get_credentials() -> tuple[str, str] | None:
    """Load Telegram credentials from env vars."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return None
    return token, chat_id


# ─── Core Send Function ─────────────────────────────────────────────────────

async def send_telegram_message(
    text: str,
    parse_mode: str = "HTML",
    token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """
    Send a message via the Telegram Bot API.

    Parameters
    ----------
    text       : str  — Message content (supports HTML formatting)
    parse_mode : str  — "HTML" or "MarkdownV2"
    token      : str  — Override bot token (default: from env)
    chat_id    : str  — Override chat ID (default: from env)

    Returns
    -------
    bool — True if message was sent successfully
    """
    creds = _get_credentials()
    if not token:
        if creds is None:
            logger.warning("Telegram credentials not configured — skipping alert")
            return False
        token, chat_id_env = creds
        chat_id = chat_id or chat_id_env

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            result = resp.json()

            if result.get("ok"):
                logger.info("Telegram alert sent successfully (chat_id=%s)", chat_id)
                return True
            else:
                logger.error("Telegram API error: %s", result.get("description", "Unknown"))
                return False

    except httpx.ConnectError:
        logger.error("Cannot connect to Telegram API")
        return False
    except httpx.TimeoutException:
        logger.error("Telegram API request timed out")
        return False
    except httpx.HTTPStatusError as exc:
        logger.error("Telegram HTTP %d: %s", exc.response.status_code, exc.response.text)
        return False


# ─── EV Calculation ─────────────────────────────────────────────────────────

def calculate_ev(
    win_probability: float,
    american_odds: int,
) -> dict:
    """
    Calculate Expected Value for a bet.

    Parameters
    ----------
    win_probability : float — True win probability (0–1), e.g. from simulation
    american_odds   : int   — Current market odds in American format

    Returns
    -------
    dict with: ev_dollars (per $100), ev_percent, implied_prob, edge,
               decimal_odds, is_positive_ev
    """
    # Convert American to decimal
    if american_odds > 0:
        decimal_odds = 1 + american_odds / 100
    else:
        decimal_odds = 1 + 100 / abs(american_odds)

    # Implied probability from the market odds
    if american_odds > 0:
        implied_prob = 100 / (american_odds + 100)
    else:
        implied_prob = abs(american_odds) / (abs(american_odds) + 100)

    # EV per $100 stake
    stake = 100.0
    potential_profit = stake * (decimal_odds - 1)
    ev_dollars = (win_probability * potential_profit) - ((1 - win_probability) * stake)
    ev_percent = (ev_dollars / stake) * 100

    # Edge = our probability minus market implied probability
    edge = win_probability - implied_prob

    return {
        "ev_dollars": round(ev_dollars, 2),
        "ev_percent": round(ev_percent, 2),
        "implied_prob": round(implied_prob, 4),
        "model_prob": round(win_probability, 4),
        "edge": round(edge, 4),
        "decimal_odds": round(decimal_odds, 3),
        "is_positive_ev": ev_percent > 0,
    }


# ─── Alert Formatters ───────────────────────────────────────────────────────

def format_ev_alert(
    team_name: str,
    bet_type: str,
    american_odds: int,
    ev_data: dict,
    game_info: str = "",
) -> str:
    """
    Format a +EV alert message for Telegram using HTML.

    Example output:
    🚨 +EV Detectado: KC Chiefs ML a cuota -150. EV: +8.3%
    """
    ev_pct = ev_data["ev_percent"]
    edge = ev_data["edge"] * 100

    odds_str = f"+{american_odds}" if american_odds > 0 else str(american_odds)

    # Emoji based on EV magnitude
    if ev_pct >= 15:
        emoji = "🔥🔥🔥"
    elif ev_pct >= 10:
        emoji = "🔥🔥"
    elif ev_pct >= 5:
        emoji = "🚨"
    else:
        emoji = "📊"

    msg = (
        f"{emoji} <b>+EV Detectado</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏈 <b>{team_name}</b> — {bet_type}\n"
    )

    if game_info:
        msg += f"📅 {game_info}\n"

    msg += (
        f"\n"
        f"💰 Cuota: <b>{odds_str}</b> (decimal: {ev_data['decimal_odds']})\n"
        f"📈 EV: <b>+{ev_pct:.1f}%</b> (${ev_data['ev_dollars']:.2f}/unit)\n"
        f"🎯 Prob. Modelo: {ev_data['model_prob']*100:.1f}%\n"
        f"📉 Prob. Implícita: {ev_data['implied_prob']*100:.1f}%\n"
        f"⚡ Edge: +{edge:.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>NFL BetMaster v2.0 · Simulación Monte Carlo</i>"
    )

    return msg


def format_injury_alert(
    team_name: str,
    game_info: str,
    nlp_result: dict,
) -> str:
    """Format an injury impact alert for Telegram."""
    adj = nlp_result.get("spread_adjustment", 0)
    confidence = nlp_result.get("confidence", 0)
    summary = nlp_result.get("impact_summary", "No analysis available.")
    key_abs = nlp_result.get("key_absences", [])

    msg = (
        f"🏥 <b>Injury Impact Alert</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏈 <b>{team_name}</b>\n"
        f"📅 {game_info}\n"
        f"\n"
        f"📊 Spread Adjustment: <b>{adj:+.1f} pts</b>\n"
        f"🎯 Confidence: {confidence*100:.0f}%\n"
    )

    if key_abs:
        msg += f"🚫 Key absences: {', '.join(key_abs)}\n"

    msg += (
        f"\n"
        f"<i>{summary}</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>NFL BetMaster v2.0 · NLP Analysis</i>"
    )

    return msg


# ─── High-Level Trigger Function ────────────────────────────────────────────

async def check_and_alert_ev(
    team_name: str,
    bet_type: str,
    win_probability: float,
    american_odds: int,
    game_info: str = "",
    threshold: float = EV_THRESHOLD_PERCENT,
) -> dict:
    """
    Calculate EV and send a Telegram alert if it exceeds the threshold.

    This is the main entry point called by the simulation and odds
    update pipelines.

    Returns the EV data dict with an additional 'alert_sent' key.
    """
    ev_data = calculate_ev(win_probability, american_odds)

    ev_data["alert_sent"] = False

    if ev_data["ev_percent"] >= threshold:
        logger.info(
            "+EV detected: %s %s at %d → EV: %.1f%%",
            team_name, bet_type, american_odds, ev_data["ev_percent"],
        )
        message = format_ev_alert(team_name, bet_type, american_odds, ev_data, game_info)
        sent = await send_telegram_message(message)
        ev_data["alert_sent"] = sent

    return ev_data
