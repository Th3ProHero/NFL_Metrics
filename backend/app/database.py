"""
NFL BetMaster — Async Database Layer (asyncpg)
===============================================
Manages a connection pool to PostgreSQL and provides helper functions
for executing queries.
"""

import os
import logging
from typing import Any

import asyncpg

logger = logging.getLogger("nfl.database")

# ─── Global pool reference ──────────────────────────────────────────────────

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Create the asyncpg connection pool from DATABASE_URL."""
    global _pool
    dsn = os.getenv("DATABASE_URL", "postgresql://nfluser:nflpass@localhost:5440/nflbetmaster")
    logger.info("Connecting to PostgreSQL at %s", dsn.split("@")[-1])
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    logger.info("Database pool created (min=2, max=10)")
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> asyncpg.Pool:
    """Return the active pool; raise if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


# ─── Query Helpers ───────────────────────────────────────────────────────────

async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    """Execute a SELECT and return all rows."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> asyncpg.Record | None:
    """Execute a SELECT and return the first row."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    """Execute a SELECT and return a single value."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args: Any) -> str:
    """Execute a DML statement and return the status string."""
    pool = get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
