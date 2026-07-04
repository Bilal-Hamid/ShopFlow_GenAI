"""Export the live FastAPI OpenAPI 3.1 schema to ``openapi.json``.

Run whenever the API surface changes so the checked-in spec stays current:

    uv run python scripts/export_openapi.py
"""

import json
import sys
from pathlib import Path

# Ensure the backend package root is importable when run as a script.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

from app.main import app  # noqa: E402

OUTPUT = _BACKEND_ROOT / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUTPUT.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} (openapi {schema['openapi']}, {len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
