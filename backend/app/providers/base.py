from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ProviderResult:
    provider: str
    status: str  # OK | FLAGGED | UNKNOWN | STALE | UNAVAILABLE | NOT_LINKED | NOT_CONFIGURED
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
