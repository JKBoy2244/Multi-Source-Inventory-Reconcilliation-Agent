"""Focused edge-case tests for inventory_agent.agent planning rules."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from inventory_agent import AuditLogger, InventoryReconciliationAgent
from inventory_agent.models import InventoryObservation


class AgentCaseTests(unittest.TestCase):
    """Check branch boundaries not covered by the main end-to-end scenarios."""

    def setUp(self) -> None:
        self.logger = AuditLogger()
        self.agent = InventoryReconciliationAgent({}, self.logger)

    @staticmethod
    def _observation(source: str, available: int) -> InventoryObservation:
        return InventoryObservation(
            source=source,
            sku="SKU-TEST",
            available=available,
            observed_at=datetime.now(timezone.utc).isoformat(),
            healthy=True,
            raw={},
        )

    def test_low_stock_threshold_boundary_queries_supplier(self):
        warehouse = self._observation(
            "warehouse",
            self.agent.LOW_STOCK_THRESHOLD,
        )

        next_source = self.agent._choose_next_source([warehouse])

        self.assertEqual(next_source, "supplier")
        self.assertEqual(self.logger.records[-1]["reason_code"], "LOW_STOCK_BRANCH")

    def test_matching_first_two_quantities_still_confirm_with_third_source(self):
        observations = [
            self._observation("warehouse", 25),
            self._observation("ecommerce", 25),
        ]

        next_source = self.agent._choose_next_source(observations)

        self.assertEqual(next_source, "supplier")
        self.assertEqual(
            self.logger.records[-1]["reason_code"],
            "THIRD_SOURCE_CONFIRMATION",
        )


if __name__ == "__main__":
    unittest.main()
