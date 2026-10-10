"""Write the OpenAPI schema for the frontend's generated types.

python -m scripts.export_openapi ../frontend/openapi.json
"""

import json
import sys

from app.main import app

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    with open(path, "w") as f:
        json.dump(app.openapi(), f, indent=1)
    print(f"Wrote {path}")
