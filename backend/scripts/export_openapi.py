import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "docs" / "api" / "openapi.yaml"

spec = app.openapi()
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(
    yaml.safe_dump(spec, allow_unicode=True, sort_keys=False, width=120),
    encoding="utf-8",
)
print(f"saved: {OUTPUT}")
