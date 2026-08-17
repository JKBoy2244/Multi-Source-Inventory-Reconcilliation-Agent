"""The rule-based inventory reconciliation agent.

The important property is ADAPTIVITY: after every source response, the agent
chooses what to query next based on the evidence it has already seen.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .audit import AuditLogger
from .models import InventoryObservation, ReconciliationResult


class InventoryReconciliationAgent:
    """Reconcile one SKU across warehouse, e-commerce, and supplier APIs."""

    # Explicit policy constants. They are also documented in README.md.
    LOW_STOCK_THRESHOLD = 10
    MAX_FRESH_AGE_SECONDS = 300
    DISCREPANCY_TOLERANCE = 0

    # Higher number = stronger domain authority for "our sellable stock".
    AUTHORITY_PRIORITY = {
        "warehouse": 3,
        "ecommerce": 2,
        "supplier": 1,
    }

    def __init__(
        self,
        source_urls: dict[str, str],
        logger: AuditLogger,
        timeout_seconds: float = 2.0,
    ) -> None:
        self.source_urls = source_urls
        self.logger = logger
        self.timeout_seconds = timeout_seconds
        self._step = 0
        self._run_id = ""

    def reconcile(self, sku: str) -> ReconciliationResult:
        """Run one complete adaptive reconciliation for a SKU."""
        started = time.perf_counter()
        self._step = 0
        self._run_id = uuid.uuid4().hex[:12]
        observations: list[InventoryObservation] = []
        query_order: list[str] = []

        # We start at WMS because it owns physical on-hand/reserved inventory.
        next_source: str | None = "warehouse"
        self._audit(
            event="plan",
            action="query warehouse first",
            reason_code="WMS_FIRST",
            rationale=(
                "Start with warehouse because physical on-hand minus reservations "
                "is the strongest domain signal for our current sellable stock."
            ),
            evidence={"sku": sku},
        )

        while next_source is not None:
            observation = self._query_and_normalize(next_source, sku)
            observations.append(observation)
            query_order.append(next_source)

            self._audit(
                event="observation",
                action=f"record {next_source} result",
                reason_code="SOURCE_RESULT",
                rationale=(
                    "Normalize the source-specific response into one comparable "
                    "available-quantity field before deciding what to check next."
                ),
                evidence=observation.to_dict(),
            )

            next_source = self._choose_next_source(observations)

        discrepancy = self._has_discrepancy(observations)
        winner, reason = self._choose_authoritative(observations)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        self._audit(
            event="final_decision",
            action=f"trust {winner.source}",
            reason_code="AUTHORITY_SELECTED",
            rationale=reason,
            evidence={
                "query_order": query_order,
                "discrepancy_detected": discrepancy,
                "chosen_quantity": winner.available,
                "elapsed_ms": elapsed_ms,
            },
        )

        return ReconciliationResult(
            sku=sku,
            query_order=query_order,
            observations=observations,
            discrepancy_detected=discrepancy,
            authoritative_source=winner.source,
            authoritative_quantity=winner.available,
            decision_reason=reason,
            elapsed_ms=elapsed_ms,
        )

    def _choose_next_source(
        self,
        observations: list[InventoryObservation],
    ) -> str | None:
        """Plan the next query from evidence already collected.

        This is the part that proves the workflow is not a fixed three-call
        sequence.
        """
        seen = {item.source for item in observations}
        warehouse = next(
            (item for item in observations if item.source == "warehouse"),
            None,
        )

        if len(observations) == 1 and warehouse:
            if not warehouse.healthy or not self._is_fresh(warehouse):
                self._audit(
                    event="plan",
                    action="query ecommerce next",
                    reason_code="WMS_UNTRUSTWORTHY",
                    rationale=(
                        "Warehouse is stale or unhealthy, so check the customer-"
                        "facing e-commerce source before relying on its quantity."
                    ),
                    evidence={
                        "warehouse_healthy": warehouse.healthy,
                        "warehouse_fresh": self._is_fresh(warehouse),
                    },
                )
                return "ecommerce"

            if warehouse.available <= self.LOW_STOCK_THRESHOLD:
                self._audit(
                    event="plan",
                    action="query supplier next",
                    reason_code="LOW_STOCK_BRANCH",
                    rationale=(
                        "Warehouse reports low stock, so check supplier availability "
                        "next because replenishment information is most useful now."
                    ),
                    evidence={
                        "warehouse_available": warehouse.available,
                        "low_stock_threshold": self.LOW_STOCK_THRESHOLD,
                    },
                )
                return "supplier"

            self._audit(
                event="plan",
                action="query ecommerce next",
                reason_code="NORMAL_STOCK_BRANCH",
                rationale=(
                    "Warehouse stock is not low, so compare against the customer-"
                    "facing e-commerce quantity next."
                ),
                evidence={
                    "warehouse_available": warehouse.available,
                    "low_stock_threshold": self.LOW_STOCK_THRESHOLD,
                },
            )
            return "ecommerce"

        if len(observations) == 2:
            if self._has_discrepancy(observations):
                remaining = next(
                    source
                    for source in ("warehouse", "ecommerce", "supplier")
                    if source not in seen
                )
                self._audit(
                    event="plan",
                    action=f"query {remaining} next",
                    reason_code="DISCREPANCY_TRIANGULATION",
                    rationale=(
                        "The first two normalized quantities disagree, so query "
                        "the remaining independent source to triangulate before "
                        "selecting an authority."
                    ),
                    evidence={
                        item.source: item.available for item in observations
                    },
                )
                return remaining

            remaining = next(
                source
                for source in ("warehouse", "ecommerce", "supplier")
                if source not in seen
            )
            self._audit(
                event="plan",
                action=f"query {remaining} next",
                reason_code="THIRD_SOURCE_CONFIRMATION",
                rationale=(
                    "The first two quantities agree, but the reconciliation policy "
                    "requires evidence from all three independent systems. Query "
                    "the remaining source as a confirmation check."
                ),
                evidence={
                    item.source: item.available for item in observations
                },
            )
            return remaining

        # Three sources have been checked, so the agent has enough evidence.
        self._audit(
            event="plan",
            action="stop querying",
            reason_code="THREE_SOURCES_CHECKED",
            rationale=(
                "All three independent sources have been checked; move from "
                "collection to authority selection."
            ),
            evidence={"sources_seen": sorted(seen)},
        )
        return None

    def _query_and_normalize(
        self,
        source: str,
        sku: str,
    ) -> InventoryObservation:
        """Call one source over HTTP and convert its schema to the common model."""
        url = f"{self.source_urls[source]}/inventory/{sku}"

        self._audit(
            event="request",
            action=f"GET {source}",
            reason_code="HTTP_QUERY",
            rationale=(
                "Execute the next planned source check and collect evidence for "
                "the reconciliation decision."
            ),
            evidence={"source": source, "url": url},
        )

        try:
            with urlopen(url, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"{source} request failed: {exc}") from exc

        if source == "warehouse":
            available = int(payload["on_hand"]) - int(payload["reserved"])
            observed_at = payload["last_counted_at"]
            healthy = payload["status"] == "healthy"
        elif source == "ecommerce":
            available = int(payload["sellable_quantity"])
            observed_at = payload["synced_at"]
            healthy = bool(payload["service_ok"])
        elif source == "supplier":
            available = int(payload["available_to_ship"])
            observed_at = payload["reported_at"]
            healthy = bool(payload["reachable"])
        else:
            raise ValueError(f"Unsupported source: {source}")

        return InventoryObservation(
            source=source,
            sku=sku,
            available=available,
            observed_at=observed_at,
            healthy=healthy,
            raw=payload,
        )

    def _choose_authoritative(
        self,
        observations: list[InventoryObservation],
    ) -> tuple[InventoryObservation, str]:
        """Apply explicit authority rules to the collected observations."""
        eligible = [
            item
            for item in observations
            if item.healthy and self._is_fresh(item)
        ]

        if not eligible:
            raise RuntimeError(
                "No healthy, fresh source is available; manual review required."
            )

        # max(..., key=priority) implements the documented source hierarchy.
        winner = max(
            eligible,
            key=lambda item: self.AUTHORITY_PRIORITY[item.source],
        )

        excluded = [
            item.source
            for item in observations
            if item not in eligible
        ]
        reason = (
            f"{winner.source} is authoritative because it is healthy and fresh, "
            f"and its domain-priority rank "
            f"({self.AUTHORITY_PRIORITY[winner.source]}) is the highest among "
            f"eligible sources. Priority is warehouse > ecommerce > supplier "
            f"for our own sellable stock."
        )
        if excluded:
            reason += f" Excluded as stale/unhealthy: {', '.join(excluded)}."

        return winner, reason

    def _has_discrepancy(
        self,
        observations: list[InventoryObservation],
    ) -> bool:
        """Return True when normalized quantities differ beyond tolerance."""
        quantities = [item.available for item in observations]
        if len(quantities) < 2:
            return False
        return max(quantities) - min(quantities) > self.DISCREPANCY_TOLERANCE

    def _is_fresh(self, observation: InventoryObservation) -> bool:
        """Check whether the source timestamp is inside the freshness window."""
        observed = datetime.fromisoformat(observation.observed_at)
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        return age <= self.MAX_FRESH_AGE_SECONDS

    def _audit(
        self,
        *,
        event: str,
        action: str,
        reason_code: str,
        rationale: str,
        evidence: dict,
    ) -> None:
        """Increment the step counter and write one audit record."""
        self._step += 1
        self.logger.log(
            run_id=self._run_id,
            step=self._step,
            event=event,
            action=action,
            reason_code=reason_code,
            rationale=rationale,
            evidence=evidence,
        )

