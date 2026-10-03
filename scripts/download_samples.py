"""Download the curated manifest, preserving originals and recording SHA-256."""

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = ROOT / "data/samples/manifest.json"
rows = json.loads(manifest.read_text())
for row in rows:
    target = manifest.parent / row["file"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(target.suffix + ".part")
        subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--fail",
                "--location",
                "--retry",
                "2",
                "--max-time",
                "60",
                row["download_url"],
                "--output",
                str(temporary),
            ],
            check=True,
        )
        temporary.replace(target)
    row["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    row["bytes"] = target.stat().st_size
    print(row["id"], target.name, row["bytes"])
manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
