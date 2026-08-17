"""Structured JSONL audit logging.

Each line is one complete JSON object. That makes the log both human-readable
and easy to parse later with Python, jq, a SIEM, or another audit tool.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLogger:
    """Write explicit, reviewer-friendly decision records.

    The logger records *rule-based rationale* and evidence. It does not depend
    on hidden model chain-of-thought, so every decision is reproducible.
    """

    def __init__(self, path: str | Path | None = None, echo: bool = False) -> None:
        self.path = Path(path) if path else None
        self.echo = echo
        self.records: list[dict[str, Any]] = []

        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Start each demo run with a clean log so the video is easy to read.
            self.path.write_text("", encoding="utf-8")

    def log(
        self,
        *,
        run_id: str,
        step: int,
        event: str,
        action: str,
        rationale: str,
        reason_code: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Create one structured audit record and optionally write it to disk."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "step": step,
            "event": event,
            "action": action,
            "reason_code": reason_code,
            "rationale": rationale,
            "evidence": evidence or {},
        }
        self.records.append(record)

        line = json.dumps(record, sort_keys=True)
        if self.path:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        if self.echo:
            print(line)
