"""Small data models shared by the agent, policy, and demo code."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class InventoryObservation:
    """One normalized inventory reading from one source.

    The mock APIs deliberately return different field names. The agent converts
    them into this common shape so it can compare like with like.
    """

    source: str
    sku: str
    available: int
    observed_at: str
    healthy: bool
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logs/results."""
        return asdict(self)


@dataclass(frozen=True)
class ReconciliationResult:
    """Final result returned after the agent finishes one reconciliation run."""

    sku: str
    query_order: list[str]
    observations: list[InventoryObservation]
    discrepancy_detected: bool
    authoritative_source: str
    authoritative_quantity: int
    decision_reason: str
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Return the result as plain Python data for JSON printing."""
        data = asdict(self)
        return data

