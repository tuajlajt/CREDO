"""
Side effects convenience imports.

Re-exports the SideEffect TypedDict and SideEffectProvider protocol from
side_effect_provider.py, plus the openFDA-backed aggregation function.

For aggregation with a custom provider (e.g. SIDER JSON), use
side_effects_aggregate.aggregate_side_effects(provider, inns) directly.
"""
from src.pharmacology.side_effect_provider import SideEffect, SideEffectProvider
from src.pharmacology.side_effects_openfda import (
    aggregate_side_effects,
    get_side_effects_openfda,
)

__all__ = [
    "SideEffect",
    "SideEffectProvider",
    "aggregate_side_effects",
    "get_side_effects_openfda",
]
