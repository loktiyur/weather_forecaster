import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent


def load_fixture(name: str) -> dict[str, Any]:
    """Load a recorded API response from tests/fixtures/<name>.json."""
    data: dict[str, Any] = json.loads((FIXTURES_DIR / f"{name}.json").read_text())
    return data
