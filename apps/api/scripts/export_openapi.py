"""Export the API contract (Slice 3).

Run from apps/api:   python scripts/export_openapi.py
Writes docs/openapi.json at the repo root, generated from the live FastAPI app,
so the contract can never drift from the code.
"""

import json
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

from app.main import app  # noqa: E402

out = API_DIR.parents[1] / "docs" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
spec = app.openapi()
spec["info"]["description"] = (
    "Hisaab API: dues, cash forecast, what-if scenarios, SMS and Razorpay payment matching, "
    "and a voice/text agent. All money values are strings in rupees."
)
out.write_text(json.dumps(spec, indent=2), encoding="utf-8")
print(f"Wrote {out} ({len(spec['paths'])} paths)")
