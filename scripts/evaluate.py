"""Evaluate reviewed samples without mixing template references into held-out results."""

import argparse
import json
from pathlib import Path

from shogi_image_to_kif.domain.position import Position
from shogi_image_to_kif.recognition.grid import load_image
from shogi_image_to_kif.recognition.pipeline import recognize

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation.json")
    args = parser.parse_args()
    rows = json.loads((ROOT / "data/samples/manifest.json").read_text())
    results = []
    for row in rows:
        if row["annotation_status"] != "reviewed":
            continue
        draft = recognize(load_image(ROOT / "data/samples" / row["file"]), ocr=False)
        expected = Position.from_sfen(row["sfen"]).board
        errors = [i for i, (a, b) in enumerate(zip(draft["board"], expected)) if a != b]
        results.append(
            {
                "sample_id": row["id"],
                "template_source": row.get("template_source", False),
                "correct_squares": 81 - len(errors),
                "errors": errors,
                "review_squares": draft["review_squares"],
                "board_exact_match": not errors,
            }
        )
    heldout = [row for row in results if not row["template_source"]]
    report = {
        "samples": results,
        "heldout_boards": len(heldout),
        "heldout_correct_squares": sum(row["correct_squares"] for row in heldout),
        "heldout_total_squares": 81 * len(heldout),
        "heldout_exact_boards": sum(row["board_exact_match"] for row in heldout),
        "scope": "盤面のみ。手番は手入力、持ち駒はOCR未評価。同系統の字体を含む小規模評価。SNS全般の精度を表さない。",
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
