import os
import yaml
from pathlib import Path
from typing import Any, Dict
from .schema import SynthMemoryConfig

class ConfigurationLoader:
    """
    Implements the 3-layer configuration hierarchy:
    1. System Defaults (via Pydantic)
    2. Instance Config (~/.synthmemory/config.yaml)
    3. Runtime Overrides (Environment Variables SY_*)
    """
    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir or Path.home() / ".synthmemory")
        self.config_path = self.config_dir / "config.yaml"
        self.presets_dir = self.config_dir / "presets"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.presets_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> SynthMemoryConfig:
        # Layer 1: Defaults
        # Layer 2: File
        file_data = {}
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                file_data = yaml.safe_load(f) or {}

        # Layer 3: Environment Variables
        env_data = self._get_env_overrides()
        
        # Merge logic (Env > File > Defaults)
        merged = self._deep_merge(file_data, env_data)
        return SynthMemoryConfig(**merged)

    def save(self, config: SynthMemoryConfig):
        with open(self.config_path, 'w') as f:
            # Use exclude_unset=False to ensure the full instance config is represented
            yaml.dump(config.dict(), f, default_flow_style=False)

    def _get_env_overrides(self) -> Dict[str, Any]:
        overrides = {}
        for key, value in os.environ.items():
            if key.startswith("SY_"):
                # Convert SY_PERFORMANCE_VECTOR_INDEX_TYPE to ['performance', 'vector_index_type']
                parts = key[3:].lower().split("_")
                curr = overrides
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:
                        curr[part] = self._type_cast(value)
                    else:
                        curr = curr.setdefault(part, {})
        return overrides

    def _type_cast(self, value: str) -> Any:
        if value.lower() in ("true", "yes"): return True
        if value.lower() in ("false", "no"): return False
        try:
            if "." in value: return float(value)
            return int(value)
        except ValueError:
            return value

    def _deep_merge(self, base: dict, override: dict) -> dict:
        for k, v in override.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._deep_merge(base[k], v)
            else:
                base[k] = v
        return base
