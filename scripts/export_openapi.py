"""Write the API's OpenAPI schema to a file: the contract the frontend types are generated from.

    poetry run python scripts/export_openapi.py frontend/openapi.json

No server is started; the schema comes straight from the FastAPI app.
"""

import json
import sys
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.main import create_app


def _whole_floats_as_ints(value: Any) -> Any:
    """`16.0` → `16`, as JavaScript writes numbers.

    The release tooling (release-please) rewrites this file with JavaScript when it bumps the
    version; the file must come out byte for byte as this script writes it, or the CI check
    "API types are up to date" fails on every release pull request.
    """
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _whole_floats_as_ints(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_whole_floats_as_ints(item) for item in value]
    return value


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/openapi.json")
    schema = _whole_floats_as_ints(create_app(Settings(_env_file=None)).openapi())
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI schema written to {target}")


if __name__ == "__main__":
    main()
