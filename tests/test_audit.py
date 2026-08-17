"""Tests for the structured audit logger in inventory_agent.audit."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from inventory_agent import AuditLogger


class AuditTests(unittest.TestCase):
    """Audit records should be complete, ordered, and valid JSONL."""

    def test_log_keeps_structured_record_with_utc_timestamp(self):
        logger = AuditLogger()

        logger.log(
            run_id="run-1",
            step=1,
            event="plan",
            action="query warehouse first",
            reason_code="WMS_FIRST",
            rationale="Warehouse is the primary stock authority.",
            evidence={"sku": "SKU-TEST"},
        )

        record = logger.records[0]
        self.assertEqual(record["run_id"], "run-1")
        self.assertEqual(record["step"], 1)
        self.assertEqual(record["reason_code"], "WMS_FIRST")
        self.assertEqual(record["evidence"], {"sku": "SKU-TEST"})
        self.assertIsNotNone(datetime.fromisoformat(record["timestamp"]).tzinfo)

    def test_file_output_is_valid_jsonl_and_matches_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "audit.jsonl"
            logger = AuditLogger(path)

            for step in (1, 2):
                logger.log(
                    run_id="run-2",
                    step=step,
                    event="request",
                    action="GET source",
                    reason_code="HTTP_QUERY",
                    rationale="Collect source evidence.",
                )

            parsed = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(parsed, logger.records)
        self.assertEqual([record["step"] for record in parsed], [1, 2])
        self.assertEqual(parsed[0]["evidence"], {})


if __name__ == "__main__":
    unittest.main()
