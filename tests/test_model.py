"""Unit tests for the dataclasses in inventory_agent.models."""

from __future__ import annotations

import unittest

from inventory_agent.models import InventoryObservation, ReconciliationResult


class ModelTests(unittest.TestCase):
    """The models should serialize cleanly into plain Python data."""

    def test_inventory_observation_to_dict_preserves_all_fields(self):
        observation = InventoryObservation(
            source="warehouse",
            sku="SKU-TEST",
            available=7,
            observed_at="2026-01-01T12:00:00+00:00",
            healthy=True,
            raw={"on_hand": 10, "reserved": 3},
        )

        self.assertEqual(
            observation.to_dict(),
            {
                "source": "warehouse",
                "sku": "SKU-TEST",
                "available": 7,
                "observed_at": "2026-01-01T12:00:00+00:00",
                "healthy": True,
                "raw": {"on_hand": 10, "reserved": 3},
            },
        )

    def test_reconciliation_result_to_dict_serializes_nested_observations(self):
        observation = InventoryObservation(
            source="ecommerce",
            sku="SKU-TEST",
            available=9,
            observed_at="2026-01-01T12:00:00+00:00",
            healthy=True,
            raw={"sellable_quantity": 9},
        )
        result = ReconciliationResult(
            sku="SKU-TEST",
            query_order=["ecommerce"],
            observations=[observation],
            discrepancy_detected=False,
            authoritative_source="ecommerce",
            authoritative_quantity=9,
            decision_reason="fresh and healthy",
            elapsed_ms=1.25,
        )

        data = result.to_dict()

        self.assertEqual(data["sku"], "SKU-TEST")
        self.assertEqual(data["observations"], [observation.to_dict()])
        self.assertEqual(data["authoritative_quantity"], 9)
        self.assertEqual(data["elapsed_ms"], 1.25)


if __name__ == "__main__":
    unittest.main()
