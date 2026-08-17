"""End-to-end tests for the adaptive reconciliation behaviour."""

from __future__ import annotations

import unittest

from inventory_agent import (
    AuditLogger,
    InventoryReconciliationAgent,
    MockInventoryCluster,
)


class InventoryAgentTests(unittest.TestCase):
    """Tests hit real localhost HTTP servers, not mocked Python functions."""

    def _run(self, sku: str):
        logger = AuditLogger()
        with MockInventoryCluster() as cluster:
            agent = InventoryReconciliationAgent(cluster.base_urls, logger)
            result = agent.reconcile(sku)
        return result, logger.records

    def test_default_demo_detects_discrepancy_and_trusts_warehouse(self):
        """Low stock should cause supplier-second, then e-commerce triangulation."""
        result, records = self._run("SKU-RED-CHAIR")

        self.assertEqual(
            result.query_order,
            ["warehouse", "supplier", "ecommerce"],
        )
        self.assertTrue(result.discrepancy_detected)
        self.assertEqual(result.authoritative_source, "warehouse")
        self.assertEqual(result.authoritative_quantity, 7)
        self.assertTrue(
            any(
                row["reason_code"] == "DISCREPANCY_TRIANGULATION"
                for row in records
            )
        )

    def test_high_stock_changes_the_query_order(self):
        """High stock should choose e-commerce second instead of supplier."""
        result, _ = self._run("SKU-BLUE-LAMP")

        self.assertEqual(
            result.query_order,
            ["warehouse", "ecommerce", "supplier"],
        )
        self.assertTrue(result.discrepancy_detected)
        self.assertEqual(result.authoritative_source, "warehouse")
        self.assertEqual(result.authoritative_quantity, 25)

    def test_stale_warehouse_can_lose_authority(self):
        """Freshness rule must override the normal warehouse-first priority."""
        result, _ = self._run("SKU-GREEN-MUG")

        self.assertEqual(result.query_order[0:2], ["warehouse", "ecommerce"])
        self.assertTrue(result.discrepancy_detected)
        self.assertEqual(result.authoritative_source, "ecommerce")
        self.assertEqual(result.authoritative_quantity, 12)


if __name__ == "__main__":
    unittest.main()

