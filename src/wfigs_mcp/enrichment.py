from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class IncidentLocationEnricher(Protocol):
    """Future WFIGS Incident Locations join, keyed only by canonical IRWIN ID."""

    async def get_attributes(self, irwin_id: str) -> Mapping[str, object] | None: ...