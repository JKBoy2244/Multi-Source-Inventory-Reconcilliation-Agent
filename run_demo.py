"""Run the complete end-to-end demo from one command.

Usage:
    python run_demo.py
    python run_demo.py SKU-BLUE-LAMP
    python run_demo.py SKU-GREEN-MUG
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from inventory_agent import (
    AuditLogger,
    InventoryReconciliationAgent,
    MockInventoryCluster,
)


def main() -> int:
    """Start three APIs, run the agent, print the decision, then shut down."""
    sku = sys.argv[1] if len(sys.argv) > 1 else "SKU-RED-CHAIR"
    log_path = Path("logs/reconciliation.jsonl")

    # echo=True puts every structured decision on-screen for the video while
    # also writing the exact same record to the JSONL audit file.
    logger = AuditLogger(log_path, echo=True)

    print("\n=== Starting three local inventory APIs ===")
    with MockInventoryCluster() as cluster:
        agent = InventoryReconciliationAgent(cluster.base_urls, logger)
        result = agent.reconcile(sku)

    print("\n=== Final reconciliation result ===")
    print(json.dumps(result.to_dict(), indent=2))
    print(f"\nAudit log: {log_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

