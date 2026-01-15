import json
from datetime import datetime
from pathlib import Path
from typing import Any

class ConfigurationAudit:
    """
    Maintains a JSONL audit trail of configuration changes.
    """
    def __init__(self, audit_file: Path):
        self.audit_file = audit_file
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)

    def log_change(self, setting: str, old_val: Any, new_val: Any, source: str = "ui"):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "setting": setting,
            "old_value": str(old_val),
            "new_value": str(new_val),
            "source": source
        }
        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")

    def log_event(self, event_name: str, details: str):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_name,
            "details": details
        }
        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")