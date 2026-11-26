from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

# Provider-specific freshness TTLs (seconds) for manual non-forced refreshes
PROVIDER_TTLS: dict[str, int] = {
    "steam": 900,      # 15 minutes
    "leetify": 1800,   # 30 minutes
    "faceit": 1800,    # 30 minutes
    "cswatch": 3600,   # 60 minutes
}

AUTO_STALE_SECONDS = 24 * 3600  # 24 hours for startup / 24h cycle / login refresh

# Minimum spacing between uncached upstream HTTP calls per provider
PROVIDER_MIN_INTERVAL: dict[str, float] = {
    "steam": 0.35,
    "leetify": 0.70,
    "faceit": 0.40,
    "cswatch": 2.40,  # <= 25 req/min cap
}

_rate_locks: dict[str, asyncio.Lock] = {}
_last_call_at: dict[str, float] = {}
_in_flight: dict[tuple[str, str], asyncio.Future] = {}


def normalize_v2_status(raw: str | None) -> str:
    if not raw:
        return "UNAVAILABLE"
    up = raw.upper()
    if up == "OK":
        return "SUCCESS"
    if up in ("SUCCESS", "PARTIAL", "PRIVATE", "NOT_LINKED", "NOT_CONFIGURED", "RATE_LIMITED", "UNAVAILABLE", "FAILED"):
        return up
    if up == "FLAGGED":
        return "SUCCESS"
    return "UNAVAILABLE"


def is_provider_fresh(fetched_at: datetime | None, provider_key: str, max_age_seconds: int | None = None) -> bool:
    if fetched_at is None:
        return False
    dt = fetched_at if fetched_at.tzinfo is not None else fetched_at.replace(tzinfo=timezone.utc)
    ttl = max_age_seconds if max_age_seconds is not None else PROVIDER_TTLS.get(provider_key, 900)
    return (datetime.now(timezone.utc) - dt).total_seconds() < ttl


async def throttle_provider(provider_key: str, jitter: bool = True) -> None:
    """Per-provider async spacing limiter with optional small randomized jitter."""
    lock = _rate_locks.setdefault(provider_key, asyncio.Lock())
    min_gap = PROVIDER_MIN_INTERVAL.get(provider_key, 0.3)
    async with lock:
        now = time.monotonic()
        prev = _last_call_at.get(provider_key, 0.0)
        wait_for = (prev + min_gap) - now
        if wait_for > 0:
            if jitter:
                wait_for += random.uniform(0.05, 0.25)
            await asyncio.sleep(wait_for)
        _last_call_at[provider_key] = time.monotonic()


async def run_single_flight(
    key: tuple[str, str],
    coro_factory: Callable[[], Awaitable[Any]],
) -> tuple[Any, bool]:
    """
    Single-flight request deduplication.
    Returns (result, deduplicated_hit).
    """
    existing = _in_flight.get(key)
    if existing is not None and not existing.done():
        res = await existing
        return res, True

    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _in_flight[key] = fut
    try:
        res = await coro_factory()
        if not fut.done():
            fut.set_result(res)
        return res, False
    except Exception as exc:
        if not fut.done():
            fut.set_exception(exc)
        raise
    finally:
        if _in_flight.get(key) is fut:
            _in_flight.pop(key, None)
