import re

class PIIRedactor:
    def __init__(self, mode: str = "Strict"):
        self.mode = mode
        self.patterns = {
            "email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            "ipv4": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
            "ssn": r"\d{3}-\d{2}-\d{4}"
        }

    def redact(self, text: str) -> str:
        if self.mode == "Off": return text
        
        res = text
        for name, pattern in self.patterns.items():
            res = re.sub(pattern, f"[REDACTED_{name.upper()}]", res)
        return res