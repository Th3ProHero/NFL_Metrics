"""
NFL BetMaster v2.0 — Monte Carlo Simulator (CPU Vectorization)
================================================================
Uses NumPy for bulk random sampling and Numba @njit(parallel=True)
for JIT-compiled, multi-threaded simulation loops. NO GPU / CUDA
dependencies — runs on any machine with a modern x86-64 CPU.

## Performance Architecture (CPU-Only)
```
  ┌─────────────────────────────────────────────────────────────┐
  │                   CPU EXECUTION MODEL                       │
  ├─────────────────────────────────────────────────────────────┤
  │                                                             │
  │  TIER 1 — NumPy Vectorized (default, always available)      │
  │  ─────────────────────────────────────────────────────────   │
  │  • Pre-generates ALL random indices as 2D arrays            │
  │  • Uses advanced indexing to sample EPA in one shot          │
  │  • Sum reduction via np.sum(axis=1)                         │
  │  • Throughput: ~10K sims in 50-150ms (single-threaded BLAS) │
  │                                                             │
  │  TIER 2 — Numba @njit(parallel=True) (if numba installed)   │
  │  ─────────────────────────────────────────────────────────   │
  │  • JIT-compiles Python to native machine code via LLVM      │
  │  • prange() distributes simulation iterations across        │
  │    all available CPU cores (OpenMP-style threading)          │
  │  • First call incurs ~1-2s compilation; subsequent calls    │
  │    run at native speed from cached machine code              │
  │  • Throughput: ~10K sims in 10-40ms (multi-core)            │
  │                                                             │
  │  Tier selection is automatic: Numba if available, else NumPy │
  └─────────────────────────────────────────────────────────────┘
```

## Why @njit(parallel=True) and NOT @cuda.jit
- Zero hardware requirements: runs on any server, VM, or container
- No NVIDIA driver, CUDA toolkit, or GPU memory management needed
- Numba's prange parallelism scales across all CPU cores automatically
- For 10K simulations, CPU multi-threading is more than sufficient;
  GPU acceleration only pays off at >100K simulations with complex kernels
- Docker image stays slim: no nvidia-docker, no CUDA base image

## How Simulations Work

1. **Input**: Historical EPA distributions (numpy arrays) for both
   teams' offense and defense.

2. **Per simulation**: Each "game" runs PLAYS_PER_GAME plays.
   Per play, a random EPA sample is drawn from the offensive team's
   distribution and the defensive team's distribution, averaged:
       play_epa = (offense_epa_sample + defense_epa_sample) / 2
   Points accumulate per team across all plays.

3. **Output**: Win probability derived from the fraction of simulations
   won, plus projected points and mathematically fair moneyline odds.
"""

import logging
import time
from typing import Optional

import numpy as np

logger = logging.getLogger("nfl.simulations")

# ─── Configuration ──────────────────────────────────────────────────────────

N_SIMULATIONS = 10_000        # Number of game simulations to run
PLAYS_PER_GAME = 130          # Avg NFL plays per game (~65 per team)
EPA_TO_POINTS_SCALE = 0.35    # Empirical scale: cumulative EPA → points
BASE_POINTS = 20.0            # Baseline expected points per team

# ─── Try to import Numba for JIT acceleration ───────────────────────────────
# If numba is not installed, we fall back to pure NumPy vectorization
# which is still fast enough for 10K simulations.

_NUMBA_AVAILABLE = False

try:
    from numba import njit, prange, config as numba_config

    # Verify numba can actually compile (catches broken installs)
    @njit(cache=True)
    def _numba_test():
        return 1 + 1
    _numba_test()

    _NUMBA_AVAILABLE = True
    logger.info(
        "Numba JIT available (threads: %s, LLVM: parallel+fastmath)",
        numba_config.NUMBA_NUM_THREADS,
    )
except ImportError:
    logger.warning("numba not installed — using NumPy vectorized fallback (still fast)")
except Exception as exc:
    logger.warning("numba import failed (%s) — using NumPy fallback", exc)


# =============================================================================
#  TIER 2: NUMBA @njit(parallel=True) — Multi-Core JIT
# =============================================================================
# @njit compiles this function to native machine code via LLVM.
# parallel=True enables automatic parallelism: prange() distributes
# iterations of the outer loop across all available CPU cores.
# fastmath=True allows LLVM to use SIMD and reorder floating-point ops.
# cache=True persists compiled code to disk, so subsequent starts skip
# the ~1-2s compilation overhead.

if _NUMBA_AVAILABLE:
    @njit(parallel=True, fastmath=True, cache=True)
    def _simulate_numba(
        home_off_epa: np.ndarray,   # float64[N_SAMPLES] — home offensive EPA distribution
        home_def_epa: np.ndarray,   # float64[N_SAMPLES] — home defensive EPA distribution
        away_off_epa: np.ndarray,   # float64[N_SAMPLES] — away offensive EPA distribution
        away_def_epa: np.ndarray,   # float64[N_SAMPLES] — away defensive EPA distribution
        n_sims: int,                # number of simulations to run
        n_plays: int,               # plays per simulated game
    ) -> tuple:                     # returns (home_wins, total_home_pts, total_away_pts)
        """
        Numba JIT-compiled Monte Carlo game simulator.

        Memory model:
        - All input EPA arrays are read-only contiguous float64 in L1/L2 cache
        - Each prange iteration writes to its own scalar accumulators (no contention)
        - Output arrays are written once per simulation (no false sharing)
        - prange uses OpenMP-style static scheduling by default

        Threading model:
        - prange(n_sims) splits the 10K iterations across N CPU cores
        - Each core processes ~10K/N independent simulations
        - No synchronization needed between iterations (embarrassingly parallel)
        - GIL is released inside @njit — true multi-threading

        Performance notes:
        - First call compiles via LLVM (~1-2s). Subsequent calls run from cache.
        - fastmath=True enables SIMD vectorization of inner loop arithmetic
        - Typical throughput: 10K sims × 130 plays in 10-40ms on a 4-core CPU
        """
        n_samples = len(home_off_epa)

        # Output arrays — one element per simulation
        out_home_wins = np.zeros(n_sims, dtype=np.int32)
        out_home_pts = np.zeros(n_sims, dtype=np.float64)
        out_away_pts = np.zeros(n_sims, dtype=np.float64)

        # prange distributes these iterations across all CPU cores
        for sim in prange(n_sims):
            home_points = 0.0
            away_points = 0.0

            for play in range(n_plays):
                # ── Home team possession ──
                # np.random is thread-safe in numba; each thread gets
                # its own PRNG state automatically
                idx_ho = np.random.randint(0, n_samples)
                idx_ad = np.random.randint(0, n_samples)
                play_epa_home = (home_off_epa[idx_ho] + away_def_epa[idx_ad]) / 2.0
                home_points += play_epa_home

                # ── Away team possession ──
                idx_ao = np.random.randint(0, n_samples)
                idx_hd = np.random.randint(0, n_samples)
                play_epa_away = (away_off_epa[idx_ao] + home_def_epa[idx_hd]) / 2.0
                away_points += play_epa_away

            out_home_wins[sim] = 1 if home_points > away_points else 0
            out_home_pts[sim] = home_points
            out_away_pts[sim] = away_points

        total_home_wins = np.sum(out_home_wins)
        avg_home_pts = np.mean(out_home_pts)
        avg_away_pts = np.mean(out_away_pts)

        return total_home_wins, avg_home_pts, avg_away_pts


# =============================================================================
#  TIER 1: NUMPY VECTORIZED — Single-Threaded Fallback
# =============================================================================

def _simulate_numpy(
    home_off_epa: np.ndarray,
    home_def_epa: np.ndarray,
    away_off_epa: np.ndarray,
    away_def_epa: np.ndarray,
    n_sims: int = N_SIMULATIONS,
    n_plays: int = PLAYS_PER_GAME,
) -> dict:
    """
    Pure NumPy vectorized simulation — no dependencies beyond numpy.

    Strategy: pre-generate ALL random indices as 2D arrays, then use
    advanced indexing to compute all play EPAs in one vectorized pass.
    This avoids Python loops entirely.

    Memory layout:
    - Index arrays: 4 × (n_sims, n_plays) int64 ≈ 4 × 10K × 130 × 8B ≈ 40MB
    - EPA arrays: 4 × (n_sims, n_plays) float64 ≈ 40MB
    - Total peak: ~80MB for 10K sims (fits comfortably in RAM)

    Performance:
    - ~50-150ms for 10K simulations on modern CPU
    - Bottleneck is memory bandwidth (random access into EPA arrays)
    - Scales with CPU cache size and BLAS/LAPACK backend
    """
    rng = np.random.default_rng()
    n_samples = len(home_off_epa)

    # Pre-sample all random indices at once — fully vectorized, no Python loops
    # Shape: (n_sims, n_plays) — one index per play per simulation
    home_off_idx = rng.integers(0, n_samples, size=(n_sims, n_plays))
    away_def_idx = rng.integers(0, n_samples, size=(n_sims, n_plays))
    away_off_idx = rng.integers(0, n_samples, size=(n_sims, n_plays))
    home_def_idx = rng.integers(0, n_samples, size=(n_sims, n_plays))

    # Compute all play EPAs via advanced indexing — O(1) Python overhead
    home_play_epa = (home_off_epa[home_off_idx] + away_def_epa[away_def_idx]) / 2.0
    away_play_epa = (away_off_epa[away_off_idx] + home_def_epa[home_def_idx]) / 2.0

    # Sum across plays → total cumulative EPA per simulation
    home_total = home_play_epa.sum(axis=1)
    away_total = away_play_epa.sum(axis=1)

    home_wins = int((home_total > away_total).sum())

    return {
        "home_wins": home_wins,
        "away_wins": n_sims - home_wins,
        "avg_home_pts": float(home_total.mean()),
        "avg_away_pts": float(away_total.mean()),
    }


# =============================================================================
#  PUBLIC API
# =============================================================================

def run_simulation(
    home_off_epa: np.ndarray,
    home_def_epa: np.ndarray,
    away_off_epa: np.ndarray,
    away_def_epa: np.ndarray,
    n_sims: int = N_SIMULATIONS,
) -> dict:
    """
    Run a Monte Carlo game simulation and return win probabilities + fair odds.

    Automatically selects the fastest available engine:
      1. Numba @njit(parallel=True) — multi-core JIT compiled
      2. NumPy vectorized — single-threaded BLAS fallback

    Parameters
    ----------
    home_off_epa : np.ndarray — Historical EPA values for home team offense
    home_def_epa : np.ndarray — Historical EPA values for home team defense
    away_off_epa : np.ndarray — Historical EPA values for away team offense
    away_def_epa : np.ndarray — Historical EPA values for away team defense
    n_sims       : int        — Number of simulations (default 10,000)

    Returns
    -------
    dict with keys:
        home_win_prob, away_win_prob, fair_home_ml, fair_away_ml,
        projected_home_pts, projected_away_pts, projected_total,
        n_simulations, engine, elapsed_ms
    """
    # Validate inputs — need enough samples for meaningful random draws
    for name, arr in [
        ("home_off_epa", home_off_epa),
        ("home_def_epa", home_def_epa),
        ("away_off_epa", away_off_epa),
        ("away_def_epa", away_def_epa),
    ]:
        if len(arr) < 10:
            raise ValueError(f"{name} must have at least 10 samples, got {len(arr)}")

    t_start = time.perf_counter()

    # ── Select execution engine ──
    if _NUMBA_AVAILABLE:
        # Numba path: returns a tuple (home_wins, avg_home_pts, avg_away_pts)
        hw, ahp, aap = _simulate_numba(
            home_off_epa.astype(np.float64),
            home_def_epa.astype(np.float64),
            away_off_epa.astype(np.float64),
            away_def_epa.astype(np.float64),
            n_sims, PLAYS_PER_GAME,
        )
        raw = {
            "home_wins": int(hw),
            "away_wins": n_sims - int(hw),
            "avg_home_pts": float(ahp),
            "avg_away_pts": float(aap),
        }
        engine = "numba_cpu"
    else:
        raw = _simulate_numpy(home_off_epa, home_def_epa, away_off_epa, away_def_epa, n_sims)
        engine = "numpy_cpu"

    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)

    # ── Derive probabilities and fair odds ──
    home_win_prob = raw["home_wins"] / n_sims
    away_win_prob = raw["away_wins"] / n_sims

    fair_home_ml = _prob_to_american(home_win_prob)
    fair_away_ml = _prob_to_american(away_win_prob)

    # Projected points: scale raw EPA totals to realistic NFL score range
    proj_home = BASE_POINTS + raw["avg_home_pts"] * EPA_TO_POINTS_SCALE
    proj_away = BASE_POINTS + raw["avg_away_pts"] * EPA_TO_POINTS_SCALE

    logger.info(
        "Simulation complete: %d sims in %.1fms (%s) — home %.1f%%, away %.1f%%",
        n_sims, elapsed_ms, engine, home_win_prob * 100, away_win_prob * 100,
    )

    return {
        "home_win_prob": round(home_win_prob, 4),
        "away_win_prob": round(away_win_prob, 4),
        "fair_home_ml": fair_home_ml,
        "fair_away_ml": fair_away_ml,
        "projected_home_pts": round(proj_home, 1),
        "projected_away_pts": round(proj_away, 1),
        "projected_total": round(proj_home + proj_away, 1),
        "n_simulations": n_sims,
        "engine": engine,
        "elapsed_ms": elapsed_ms,
    }


def _prob_to_american(prob: float) -> int:
    """
    Convert a win probability (0–1) to American moneyline odds.

    Examples:
        0.60 → -150   (favorite)
        0.40 → +150   (underdog)
    """
    if prob <= 0.0:
        return 10000  # Extreme underdog
    if prob >= 1.0:
        return -10000  # Lock
    if prob >= 0.5:
        return int(round(-100 * prob / (1 - prob)))
    else:
        return int(round(100 * (1 - prob) / prob))


def generate_synthetic_epa(mean: float = 0.0, std: float = 0.45, n: int = 500) -> np.ndarray:
    """
    Generate synthetic EPA data for testing when historical data is unavailable.

    Real NFL EPA distributions are roughly normal with:
      - Offense: mean ≈ 0.0, std ≈ 0.45
      - Defense: mean ≈ 0.0, std ≈ 0.40 (inverted: negative = good defense)
    """
    return np.random.default_rng().normal(loc=mean, scale=std, size=n).astype(np.float64)
