"""
SideEffect TypedDict and SideEffectProvider protocol.

Any side-effect data source (openFDA, SIDER JSON, etc.) implements this protocol
so the aggregation and pipeline layers are data-source agnostic.
"""
from __future__ import annotations

from typing import List, Optional, Protocol, TypedDict


class SideEffect(TypedDict):
    effect: str
    severity: Optional[str]         # often missing in open data
    probability: Optional[float]    # often missing in open data
    source: str                     # e.g. "openFDA", "SIDER"
    evidence_ref: Optional[str]     # URL / PMID / filename if available


class SideEffectProvider(Protocol):
    def get_side_effects(self, inn: str) -> List[SideEffect]:
        """Return all known side effects for a given INN string."""
        ...
