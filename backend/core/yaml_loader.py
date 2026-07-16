"""YAML configuration loader (foundation only)."""

from pathlib import Path
from typing import Any

import yaml


def load_yaml_config(path: Path) -> dict[str, Any]:
    """Load a YAML configuration file. Returns empty dict if file is missing."""
    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    return data if isinstance(data, dict) else {}
