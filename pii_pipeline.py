import re
from typing import Dict, Tuple

class PIIPipeline:
    def __init__(self, mode: str = "Strict"):
        self.mode = mode
        self.rules = {
            "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            "ipv4": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
            "ssn": r"\d{3}-\d{2}-\d{4}"
        }

    async def redact(self, text: str) -> Tuple[str, Dict]:
        if self.mode == "Off": 
            return text, {}
        
        redacted_map = {}
        processed = text
        for label, pattern in self.rules.items():
            matches = re.findall(pattern, processed)
            for match in matches:
                placeholder = f"[REDACTED_{label.upper()}_{len(redacted_map)}]"
                redacted_map[placeholder] = match
                processed = processed.replace(match, placeholder)
        
        return processed, redacted_map