"""
NFL BetMaster v2.0 — NLP Injury Analysis via Remote Inference Server
=====================================================================
Connects to a remote LLM inference server (e.g. Ollama running on a
Jetson device on the local network) to analyze NFL injury reports
using a large language model (e.g., Llama 3, Mistral).

## Architecture
```
  FastAPI Backend → httpx (async) → Remote Inference Server (OLLAMA_BASE_URL)
                                      ↓
                                   Llama 3 / Mistral (on Jetson or other device)
                                      ↓
                                 Structured JSON response
```

The OLLAMA_BASE_URL environment variable points to the inference server's
IP on the network (e.g. http://192.168.1.50:11434). This decouples the
compute-heavy NLP work from the backend container, allowing it to run on
dedicated hardware like an NVIDIA Jetson with local GPU acceleration.

## How the Prompt is Structured

The prompt uses a multi-shot "system → user" pattern:

1. **System Prompt**: Sets the LLM's persona as an NFL analytics expert
   and defines the exact JSON output schema it must follow.

2. **User Prompt**: Provides the structured injury report data (team,
   player, position, injury type, game status) and asks for:
   - A human-readable impact summary (2-3 sentences)
   - A numeric spread_adjustment (float, in points)
   - A confidence level (0.0 – 1.0)

The response is parsed as JSON. If the LLM returns malformed JSON,
we attempt to extract it via regex fallback.

## Spread Adjustment Logic

The adjustment represents how many points the spread should shift
due to injuries. Examples:
  - Starting QB out:        -2.5 to -4.0 points
  - #1 WR out:              -1.0 to -2.0 points
  - Starting RB out:        -0.5 to -1.5 points
  - Key defensive player:   -0.5 to -1.5 points
  - Backup players out:     -0.0 to -0.5 points
"""

import json
import logging
import os
import re
from typing import Optional

import httpx

logger = logging.getLogger("nfl.nlp_analysis")

# ─── Ollama Configuration ───────────────────────────────────────────────────
# Default URL uses Docker's special DNS for reaching the host machine
# from within a container. Override via OLLAMA_BASE_URL env var.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_TIMEOUT = 120  # LLMs can be slow on first load; generous timeout


# ─── System Prompt ──────────────────────────────────────────────────────────
# This prompt defines the LLM's role and the exact JSON schema it must output.
# We use explicit instructions to enforce structured output because local LLMs
# don't support tool/function calling as reliably as cloud APIs.

SYSTEM_PROMPT = """You are an expert NFL sports analytics consultant specializing in injury impact analysis. Your job is to evaluate how player injuries affect a team's competitive performance, specifically the point spread in betting markets.

You will receive an injury report for an upcoming NFL game. Analyze it and respond with ONLY a valid JSON object (no markdown, no code fences, no explanation outside the JSON) using this exact schema:

{
  "impact_summary": "A 2-3 sentence analysis explaining how the listed injuries affect the team's performance.",
  "spread_adjustment": -1.5,
  "confidence": 0.75,
  "key_absences": ["Player Name (Position)"],
  "risk_factors": ["Brief risk factor descriptions"]
}

Rules for spread_adjustment:
- NEGATIVE values mean the injured team gets WEAKER (e.g., -3.0 if the starting QB is out)
- Starting QB out = typically -2.5 to -4.0 points
- #1 WR or elite pass rusher out = typically -1.0 to -2.0 points  
- Starting RB out = typically -0.5 to -1.5 points
- Multiple starters out = cumulative but with diminishing returns (cap at -6.0)
- All players healthy or only backups out = 0.0 to -0.5
- NEVER return a positive adjustment (injuries never help)

confidence:
- 0.0 to 1.0 — how confident you are in the adjustment
- Higher if the report is detailed and key positions are affected
- Lower if injuries are minor or the report is vague"""


def _build_user_prompt(
    team_name: str,
    opponent_name: str,
    injuries: list[dict],
) -> str:
    """
    Build the user-facing prompt with the injury report data.

    Each injury dict should have:
        {
            "player": "Patrick Mahomes",
            "position": "QB",
            "injury": "Ankle",
            "status": "Out"  // Out, Doubtful, Questionable, Probable
        }
    """
    # Format injuries into a readable list
    injury_lines = []
    for inj in injuries:
        status = inj.get("status", "Unknown")
        player = inj.get("player", "Unknown")
        position = inj.get("position", "?")
        injury_type = inj.get("injury", "Undisclosed")
        injury_lines.append(f"  - {player} ({position}) — {injury_type} — Status: {status}")

    injury_text = "\n".join(injury_lines) if injury_lines else "  - No injuries reported"

    return f"""Analyze the following injury report for an upcoming NFL game:

GAME: {team_name} vs {opponent_name}
TEAM BEING ANALYZED: {team_name}

INJURY REPORT:
{injury_text}

Based on these injuries, provide your analysis as a JSON object following the schema from your instructions."""


# ─── Main Analysis Function ─────────────────────────────────────────────────

async def analyze_injuries(
    team_name: str,
    opponent_name: str,
    injuries: list[dict],
    model: Optional[str] = None,
) -> dict:
    """
    Send the injury report to the local Ollama LLM and parse the response.

    Parameters
    ----------
    team_name     : str  — Name of the team with injuries
    opponent_name : str  — Name of the opposing team
    injuries      : list — List of injury dicts (player, position, injury, status)
    model         : str  — Override the default Ollama model

    Returns
    -------
    dict with keys: impact_summary, spread_adjustment, confidence,
                    key_absences, risk_factors, model_used, raw_response
    """
    model_name = model or OLLAMA_MODEL
    user_prompt = _build_user_prompt(team_name, opponent_name, injuries)

    logger.info(
        "Sending injury analysis to Ollama (%s) for %s (%d injuries)",
        model_name, team_name, len(injuries),
    )

    # ── Call Ollama's /api/generate endpoint ──
    # We use the raw generate endpoint (not /api/chat) for maximum
    # compatibility across Ollama versions and models.
    payload = {
        "model": model_name,
        "prompt": user_prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,  # Wait for complete response
        "options": {
            "temperature": 0.3,      # Low temperature for consistent analysis
            "top_p": 0.9,
            "num_predict": 1024,      # Max tokens to generate
        },
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(OLLAMA_TIMEOUT)) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()

    except httpx.ConnectError:
        logger.error(
            "Cannot connect to Ollama at %s — is it running?", OLLAMA_BASE_URL
        )
        return _fallback_response(team_name, injuries, error="Ollama not reachable")

    except httpx.TimeoutException:
        logger.error("Ollama request timed out after %ds", OLLAMA_TIMEOUT)
        return _fallback_response(team_name, injuries, error="Ollama timeout")

    except httpx.HTTPStatusError as exc:
        logger.error("Ollama returned HTTP %d: %s", exc.response.status_code, exc.response.text)
        return _fallback_response(team_name, injuries, error=f"HTTP {exc.response.status_code}")

    # ── Parse LLM response ──
    raw_text = result.get("response", "")
    logger.debug("Ollama raw response: %s", raw_text[:500])

    parsed = _parse_llm_json(raw_text)

    if parsed is None:
        logger.warning("Failed to parse LLM JSON; using rule-based fallback")
        return _fallback_response(team_name, injuries, error="JSON parse failed")

    # Validate and clamp the spread adjustment
    spread_adj = parsed.get("spread_adjustment", 0.0)
    if isinstance(spread_adj, (int, float)):
        spread_adj = max(min(float(spread_adj), 0.0), -6.0)  # Clamp: [-6.0, 0.0]
    else:
        spread_adj = 0.0

    confidence = parsed.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))

    return {
        "impact_summary": parsed.get("impact_summary", "Analysis unavailable."),
        "spread_adjustment": round(spread_adj, 1),
        "confidence": round(confidence, 2),
        "key_absences": parsed.get("key_absences", []),
        "risk_factors": parsed.get("risk_factors", []),
        "model_used": model_name,
        "raw_response": raw_text[:2000],  # Truncate for storage
    }


# ─── JSON Parsing with Fallback ─────────────────────────────────────────────

def _parse_llm_json(text: str) -> Optional[dict]:
    """
    Attempt to parse JSON from LLM output.

    LLMs sometimes wrap JSON in markdown code fences or add preamble text.
    We try multiple strategies:
    1. Direct JSON parse
    2. Extract from ```json ... ``` code fence
    3. Find first { ... } block via regex
    """
    # Strategy 1: Direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from code fence
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Strategy 3: Find first JSON object
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ─── Rule-Based Fallback ────────────────────────────────────────────────────

def _fallback_response(
    team_name: str,
    injuries: list[dict],
    error: str = "",
) -> dict:
    """
    Generate a simple rule-based injury impact when the LLM is unavailable.

    This ensures the system always returns a usable response, even if
    Ollama is down. The rules are conservative approximations.
    """
    position_weights = {
        "QB": -3.0,
        "WR": -1.5,
        "RB": -1.0,
        "TE": -0.8,
        "OL": -0.7, "LT": -0.8, "RT": -0.7, "LG": -0.5, "RG": -0.5, "C": -0.6,
        "DE": -1.0, "DT": -0.7, "LB": -0.8, "OLB": -0.8, "ILB": -0.8, "MLB": -0.9,
        "CB": -1.0, "S": -0.8, "FS": -0.8, "SS": -0.7,
        "K": -0.5, "P": -0.3,
    }
    status_multiplier = {
        "Out": 1.0,
        "Doubtful": 0.8,
        "Questionable": 0.3,
        "Probable": 0.05,
    }

    total_adj = 0.0
    key_absences = []

    for inj in injuries:
        pos = inj.get("position", "").upper()
        status = inj.get("status", "Questionable")
        weight = position_weights.get(pos, -0.3)
        multiplier = status_multiplier.get(status, 0.3)
        adj = weight * multiplier
        total_adj += adj

        if multiplier >= 0.8:
            key_absences.append(f"{inj.get('player', '?')} ({pos})")

    # Diminishing returns cap
    total_adj = max(total_adj, -6.0)

    return {
        "impact_summary": (
            f"Rule-based analysis for {team_name}: "
            f"{len(injuries)} player(s) on the injury report. "
            f"{'LLM unavailable (' + error + '). ' if error else ''}"
            f"Estimated spread adjustment: {total_adj:.1f} points."
        ),
        "spread_adjustment": round(total_adj, 1),
        "confidence": 0.4,  # Lower confidence for rule-based
        "key_absences": key_absences,
        "risk_factors": [error] if error else [],
        "model_used": "rule_based_fallback",
        "raw_response": "",
    }
