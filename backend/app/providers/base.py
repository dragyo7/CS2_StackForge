from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

STANDARD_PROVIDER_STATUSES = frozenset(
    {
        "SUCCESS",
        "PARTIAL",
        "PRIVATE",
        "NOT_LINKED",
        "NOT_CONFIGURED",
        "RATE_LIMITED",
        "NOT_FOUND",
        "UNAVAILABLE",
        "FAILED",
    }
)


@dataclass
class ProviderResult:
    provider: str
    status: str  # OK | FLAGGED | SUCCESS | PARTIAL | PRIVATE | NOT_LINKED | NOT_CONFIGURED | RATE_LIMITED | NOT_FOUND | UNAVAILABLE | FAILED
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    endpoint_category: str = "profile"
    player_identity: str | None = None
    failure_reason: str | None = None
    retry_eligible: bool = False
    freshness: str = "FRESH"
    last_successful_at: datetime | None = None
