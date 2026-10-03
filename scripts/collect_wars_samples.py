"""Collect official Shogi Wars UI examples for local recognition checks."""

import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

from shogi_image_to_kif.recognition.grid import BoardNotFound, load_image
from shogi_image_to_kif.recognition.pipeline import recognize

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data/local-samples"
SOURCE = "https://shogiwars.heroz.jp/qa?locale=ja&num=29"
CASES = [
    ("wars-play", "通常対局", "qa_about-play01.png", [4, 68, 296, 389]),
    ("wars-mate", "詰めバト", "qa_about-play03-mate.png", [5, 80, 297, 399]),
]


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = DEST / "manifest.json"
    existing = json.loads(manifest.read_text()) if manifest.exists() else []
    rows = [row for row in existing if row["id"] not in {c[0] for c in CASES}]
    results = []
    for sample_id, title, filename, bounds in CASES:
        url = "https://image-pona.heroz.jp/web/help/qa/" + filename
        path = DEST / (sample_id + ".png")
        if not path.exists():
            with urlopen(
                Request(url, headers={"User-Agent": "ShogiImageSamples/0.1"}),
                timeout=30,
            ) as response:
                path.write_bytes(response.read())
        image = load_image(path)
        try:
            auto = recognize(image, ocr=False)
            auto_bounds, error = auto["board_bounds"], None
        except BoardNotFound as exc:
            auto_bounds, error = None, str(exc)
        draft = recognize(image, bounds=bounds)
        (DEST / (sample_id + "-draft.json")).write_text(
            json.dumps(draft, ensure_ascii=False, indent=2) + "\n"
        )
        rows.append(
            {
                "id": sample_id,
                "title": title,
                "file": path.name,
                "source_url": SOURCE,
                "image_url": url,
                "retrieved_at": date.today().isoformat(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "image_size": [image.shape[1], image.shape[0]],
                "kind": "official-ui-example",
                "bounds": bounds,
                "distribution": "local-only; not included in repository",
                "rights_holder": "HEROZ / respective rights holders",
                "annotation_status": "reviewed board labels in data/annotations; metadata separate",
            }
        )
        results.append(
            {
                "id": sample_id,
                "auto_bounds": auto_bounds,
                "auto_error": error,
                "manual_bounds": bounds,
                "unknown_squares": draft["board"].count("?"),
                "review_squares": len(draft["review_squares"]),
                "accuracy": None,
            }
        )
    manifest.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    report = {
        "cases": results,
        "note": "Collection diagnostics only; counts are not accuracy. Run setup_wars.py for model construction and labeled evaluation.",
    }
    (ROOT / "docs/wars-collection.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
