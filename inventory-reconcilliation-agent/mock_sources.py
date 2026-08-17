"""Three independent local HTTP inventory APIs used by the demo.

Why local mock APIs?
- They satisfy the requirement to call three distinct data sources/APIs.
- They are deterministic, free, and require no accounts or API keys.
- They make no internet requests, which keeps the demo safe and repeatable.

The three services intentionally use DIFFERENT response schemas, just like
real warehouse, e-commerce, and supplier systems often do.
"""

from __future__ import annotations

import json
import threading
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote


# Each source has intentionally different stock numbers so reconciliation has
# something real to detect. "age_seconds" simulates freshness/staleness.
WAREHOUSE_DATA = {
    "SKU-RED-CHAIR": {"on_hand": 10, "reserved": 3, "age_seconds": 30},
    "SKU-BLUE-LAMP": {"on_hand": 30, "reserved": 5, "age_seconds": 30},
    "SKU-GREEN-MUG": {"on_hand": 20, "reserved": 2, "age_seconds": 900},
}

ECOMMERCE_DATA = {
    "SKU-RED-CHAIR": {"sellable": 9, "age_seconds": 20},
    "SKU-BLUE-LAMP": {"sellable": 24, "age_seconds": 20},
    "SKU-GREEN-MUG": {"sellable": 12, "age_seconds": 20},
}

SUPPLIER_DATA = {
    "SKU-RED-CHAIR": {"available_to_ship": 40, "age_seconds": 15},
    "SKU-BLUE-LAMP": {"available_to_ship": 80, "age_seconds": 15},
    "SKU-GREEN-MUG": {"available_to_ship": 50, "age_seconds": 15},
}


def _observed_at(age_seconds: int) -> str:
    """Return a current UTC timestamp shifted backwards by age_seconds."""
    return (
        datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    ).isoformat()


def _make_payload(source: str, sku: str, row: dict[str, int]) -> dict:
    """Translate internal fixture data into a source-specific API response."""
    if source == "warehouse":
        return {
            "sku": sku,
            "on_hand": row["on_hand"],
            "reserved": row["reserved"],
            "last_counted_at": _observed_at(row["age_seconds"]),
            "status": "healthy",
        }

    if source == "ecommerce":
        return {
            "product_sku": sku,
            "sellable_quantity": row["sellable"],
            "synced_at": _observed_at(row["age_seconds"]),
            "service_ok": True,
        }

    if source == "supplier":
        return {
            "supplier_sku": sku,
            "available_to_ship": row["available_to_ship"],
            "reported_at": _observed_at(row["age_seconds"]),
            "reachable": True,
        }

    raise ValueError(f"Unknown source: {source}")


class _InventoryHandler(BaseHTTPRequestHandler):
    """HTTP handler shared by all three local services."""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API name
        # Expected route: /inventory/<SKU>
        if not self.path.startswith("/inventory/"):
            self._send_json(404, {"error": "not found"})
            return

        sku = unquote(self.path.split("/inventory/", 1)[1])
        row = self.server.rows.get(sku)  # type: ignore[attr-defined]
        if row is None:
            self._send_json(404, {"error": f"unknown sku: {sku}"})
            return

        payload = _make_payload(
            self.server.source_name,  # type: ignore[attr-defined]
            sku,
            row,
        )
        self._send_json(200, payload)

    def _send_json(self, status: int, payload: dict) -> None:
        """Send a small JSON response with correct HTTP headers."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        """Silence default HTTP access logs; the agent has its own audit log."""
        return


class MockInventoryCluster(AbstractContextManager):
    """Start/stop three independent localhost HTTP services.

    Each service gets its own port and HTTP server instance. The agent therefore
    performs genuine HTTP calls to three distinct endpoints instead of directly
    reading one in-memory dictionary.
    """

    def __init__(self, host: str = "127.0.0.1") -> None:
        self.host = host
        self._servers: list[ThreadingHTTPServer] = []
        self._threads: list[threading.Thread] = []
        self.base_urls: dict[str, str] = {}

    def __enter__(self) -> "MockInventoryCluster":
        configs = [
            ("warehouse", WAREHOUSE_DATA),
            ("ecommerce", ECOMMERCE_DATA),
            ("supplier", SUPPLIER_DATA),
        ]

        for source_name, rows in configs:
            # Port 0 asks the OS for a free local port, avoiding port conflicts.
            server = ThreadingHTTPServer((self.host, 0), _InventoryHandler)
            server.source_name = source_name  # type: ignore[attr-defined]
            server.rows = rows  # type: ignore[attr-defined]

            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            port = server.server_address[1]
            self.base_urls[source_name] = f"http://{self.host}:{port}"
            self._servers.append(server)
            self._threads.append(thread)

        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for server in self._servers:
            server.shutdown()
            server.server_close()

        for thread in self._threads:
            thread.join(timeout=2)

        self._servers.clear()
        self._threads.clear()

