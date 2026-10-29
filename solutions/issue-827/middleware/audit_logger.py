"""
ICH Q14 Analytical Procedure Compliance & Immutable Audit Logger.
Enforces the mandatory four-tuple integrity constraint:
  - actor (str)
  - timestamp (ISO-8601 UTC)
  - delta (dict of state mutations)
  - operation_id (unique traceable ID)
"""
from typing import Dict, Any, List
import json
import os
from datetime import datetime, timezone


class ICHQ14AuditLogger:
    REQUIRED_FIELDS = frozenset({"actor", "timestamp", "delta", "operation_id"})

    def __init__(self, log_path: str):
        self.log_path = log_path
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)

    def log_entry(self, actor: str, delta: Dict[str, Any], operation_id: str, timestamp: str = None) -> Dict[str, Any]:
        if not actor or not isinstance(actor, str):
            raise ValueError("actor must be a non-empty string")
        if not isinstance(delta, dict):
            raise ValueError("delta must be a dictionary")
        if not operation_id or not isinstance(operation_id, str):
            raise ValueError("operation_id must be a non-empty string")

        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        entry = {
            "actor": actor,
            "timestamp": timestamp,
            "delta": delta,
            "operation_id": operation_id
        }

        # Validate completeness
        missing = self.REQUIRED_FIELDS - set(entry.keys())
        if missing:
            raise ValueError(f"Missing required ICH Q14 audit fields: {missing}")

        # Append to log file
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def read_entries(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.log_path):
            return []
        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
        return entries
