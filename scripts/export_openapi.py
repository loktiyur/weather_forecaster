"""Write the API's OpenAPI schema to a file: the contract the frontend types are generated from.

    poetry run python scripts/export_openapi.py frontend/openapi.json

No server is started; the schema comes straight from the FastAPI app.
"""

import json
import sys
from pathlib import Path

from app.config import Settings
from app.main import create_app


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "frontend/openapi.json")
    schema = create_app(Settings(_env_file=None)).openapi()
    target.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI schema written to {target}")


if __name__ == "__main__":
    main()
