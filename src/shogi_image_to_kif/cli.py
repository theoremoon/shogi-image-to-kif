"""Local image recognition, review UI, and position export."""

import argparse
import json
import sys
from pathlib import Path

from shogi_image_to_kif.domain.position import Position, parse_hands, reviewed_position
from shogi_image_to_kif.exporters.kif import to_bod, to_kif


def write_output(text, path, encoding="utf-8"):
    if encoding == "cp932":
        text = text.replace("encoding=UTF-8", "encoding=Shift_JIS")
    if path:
        Path(path).write_text(text, encoding=encoding)
    else:
        print(text, end="" if text.endswith("\n") else "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    samples = commands.add_parser("samples", help="収集画像の一覧")
    samples.add_argument(
        "--manifest", type=Path, default=Path("data/samples/manifest.json")
    )
    image = commands.add_parser("recognize", help="画像を読み取り、確認用JSONを生成")
    image.add_argument("image", type=Path)
    image.add_argument(
        "--bounds", nargs=4, type=float, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM")
    )
    image.add_argument(
        "--orientation", choices=["sente_bottom", "gote_bottom"], default="sente_bottom"
    )
    image.add_argument("--turn", choices=["b", "w"])
    image.add_argument("--hands", help="先後両方の持ち駒をSFEN形式で指定。なしは -")
    image.add_argument("--no-ocr", action="store_true")
    image.add_argument("-o", "--output", type=Path)
    export = commands.add_parser("export", help="確認済みJSONまたはSFENから出力")
    source = export.add_mutually_exclusive_group(required=True)
    source.add_argument("--draft", type=Path)
    source.add_argument("--sfen")
    export.add_argument(
        "--reviewed", action="store_true", help="原画像と盤面・持ち駒・手番を確認済み"
    )
    export.add_argument("--format", choices=["kif", "bod", "sfen"], default="kif")
    export.add_argument("--encoding", choices=["utf-8", "cp932"], default="utf-8")
    export.add_argument("-o", "--output", type=Path)
    serve = commands.add_parser("serve", help="ブラウザで画像認識・修正・出力")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--samples", type=Path, default=Path("data/samples"))
    args = parser.parse_args(argv)
    try:
        if args.command == "samples":
            rows = json.loads(args.manifest.read_text())
            for row in rows:
                print(
                    f"{row['id']}\t{row['kind']}\t{row['file']}\t{row['annotation_status']}"
                )
            print(f"{len(rows)} samples")
        elif args.command == "recognize":
            from shogi_image_to_kif.recognition.grid import load_image
            from shogi_image_to_kif.recognition.pipeline import recognize

            draft = recognize(
                load_image(args.image),
                bounds=args.bounds,
                orientation=args.orientation,
                ocr=not args.no_ocr,
            )
            if args.turn:
                draft["turn"] = args.turn
            if args.hands is not None:
                draft["hands"] = parse_hands(args.hands)
            write_output(
                json.dumps(draft, ensure_ascii=False, indent=2) + "\n", args.output
            )
        elif args.command == "export":
            if args.draft:
                draft = json.loads(args.draft.read_text())
                position = reviewed_position(draft, args.reviewed)
            else:
                position = Position.from_sfen(args.sfen)
            for warning in position.warnings():
                print(f"注意: {warning}", file=sys.stderr)
            if args.format != "sfen" and position.move_number != 1:
                print(
                    "注意: 局面図KIF/BODの開始手数は1になります。元の手数を保持する場合はSFENを使用してください",
                    file=sys.stderr,
                )
            text = {
                "kif": to_kif,
                "bod": to_bod,
                "sfen": lambda p: "sfen " + p.sfen() + "\n",
            }[args.format](position)
            write_output(text, args.output, args.encoding)
        else:
            from shogi_image_to_kif.server import serve

            serve(args.port, args.samples)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"エラー: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
