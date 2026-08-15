"""
NFL BetMaster — Pydantic Models
================================
Request/response schemas for the REST API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────────────────

class GameStatus(str, Enum):
    PRE = "pre"
    IN_PROGRESS = "in_progress"
    POST = "post"


class BetType(str, Enum):
    MONEYLINE = "moneyline"
    SPREAD = "spread"
    OVER_UNDER = "over_under"
    PROP = "prop"
    PARLAY = "parlay"


class BetResult(str, Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    PUSH = "push"
    VOID = "void"


# ─── Team ────────────────────────────────────────────────────────────────────

class TeamOut(BaseModel):
    id: int
    espn_id: str
    abbreviation: str
    name: str
    conference: str
    division: str
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None


# ─── Game ────────────────────────────────────────────────────────────────────

class GameOut(BaseModel):
    id: int
    espn_event_id: str
    season: int
    week: int
    game_type: str
    status: GameStatus
    home_team: Optional[TeamOut] = None
    away_team: Optional[TeamOut] = None
    home_score: int = 0
    away_score: int = 0
    quarter: Optional[int] = None
    clock: Optional[str] = None
    possession_team_id: Optional[int] = None
    down: Optional[int] = None
    distance: Optional[int] = None
    yard_line: Optional[int] = None
    yard_line_territory: Optional[str] = None
    start_time: Optional[datetime] = None
    venue: Optional[str] = None
    broadcast: Optional[str] = None
    updated_at: Optional[datetime] = None


# ─── Odds ────────────────────────────────────────────────────────────────────

class OddsOut(BaseModel):
    id: int
    game_id: int
    sportsbook: str
    home_moneyline: Optional[int] = None
    away_moneyline: Optional[int] = None
    spread: Optional[float] = None
    spread_odds_home: Optional[int] = None
    spread_odds_away: Optional[int] = None
    over_under: Optional[float] = None
    over_odds: Optional[int] = None
    under_odds: Optional[int] = None
    captured_at: Optional[datetime] = None


# ─── User Bets ───────────────────────────────────────────────────────────────

class BetCreate(BaseModel):
    game_id: Optional[int] = None
    bet_type: BetType
    pick: str = Field(..., min_length=1, max_length=120)
    odds_decimal: float = Field(..., gt=1.0)
    odds_american: Optional[int] = None
    stake: float = Field(..., ge=0)
    notes: Optional[str] = None


class BetUpdate(BaseModel):
    bet_type: Optional[BetType] = None
    pick: Optional[str] = None
    odds_decimal: Optional[float] = None
    odds_american: Optional[int] = None
    stake: Optional[float] = None
    result: Optional[BetResult] = None
    profit: Optional[float] = None
    notes: Optional[str] = None


class BetOut(BaseModel):
    id: int
    game_id: Optional[int] = None
    bet_type: BetType
    pick: str
    odds_decimal: float
    odds_american: Optional[int] = None
    stake: float
    potential_payout: Optional[float] = None
    result: BetResult
    profit: float = 0
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class BetSummary(BaseModel):
    total_bets: int = 0
    total_staked: float = 0
    total_profit: float = 0
    roi_percent: float = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    pending: int = 0
    win_rate: float = 0


# ─── Stats ───────────────────────────────────────────────────────────────────

class TeamStats(BaseModel):
    team: TeamOut
    record: Optional[str] = None
    points_for: float = 0
    points_against: float = 0
    epa_per_play: Optional[float] = None
    pass_epa: Optional[float] = None
    rush_epa: Optional[float] = None
    defensive_epa: Optional[float] = None
    recent_games: list[GameOut] = []


# ─── v2.0: Simulation ───────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    n_simulations: Optional[int] = Field(10_000, ge=100, le=100_000)


class SimulationResult(BaseModel):
    game_id: int
    home_team: str
    away_team: str
    home_win_prob: float
    away_win_prob: float
    fair_home_ml: int
    fair_away_ml: int
    projected_home_pts: float
    projected_away_pts: float
    projected_total: float
    n_simulations: int
    engine: str  # "numba_cpu" or "numpy_cpu"
    ev_home: Optional[dict] = None
    ev_away: Optional[dict] = None


# ─── v2.0: Injury NLP Analysis ──────────────────────────────────────────────

class InjuryItem(BaseModel):
    player: str
    position: str
    injury: str = "Undisclosed"
    status: str = "Questionable"  # Out, Doubtful, Questionable, Probable


class InjuryReport(BaseModel):
    team_name: str
    opponent_name: str
    injuries: list[InjuryItem]
    model: Optional[str] = None  # Override Ollama model


class InjuryAnalysisResult(BaseModel):
    impact_summary: str
    spread_adjustment: float
    confidence: float
    key_absences: list[str] = []
    risk_factors: list[str] = []
    model_used: str
    raw_response: Optional[str] = None
