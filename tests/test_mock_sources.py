"""Integration tests for the three local APIs in inventory_agent.mock_sources."""

from __future__ import annotations

import json
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from inventory_agent import MockInventoryCluster


class MockSourceTests(unittest.TestCase):
    """The mock cluster should expose three distinct, deterministic HTTP APIs."""

    def test_cluster_serves_three_distinct_source_schemas(self):
        with MockInventoryCluster() as cluster:
            self.assertEqual(
                set(cluster.base_urls),
                {"warehouse", "ecommerce", "supplier"},
            )
            self.assertEqual(len(set(cluster.base_urls.values())), 3)

            payloads = {}
            for source, base_url in cluster.base_urls.items():
                with urlopen(f"{base_url}/inventory/SKU-RED-CHAIR") as response:
                    self.assertEqual(response.status, 200)
                    payloads[source] = json.loads(response.read().decode("utf-8"))

        self.assertEqual(payloads["warehouse"]["on_hand"], 10)
        self.assertEqual(payloads["warehouse"]["reserved"], 3)
        self.assertEqual(payloads["ecommerce"]["sellable_quantity"], 9)
        self.assertEqual(payloads["supplier"]["available_to_ship"], 40)

    def test_unknown_sku_returns_http_404(self):
        with MockInventoryCluster() as cluster:
            url = f"{cluster.base_urls['warehouse']}/inventory/UNKNOWN-SKU"
            with self.assertRaises(HTTPError) as caught:
                urlopen(url)

        self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
