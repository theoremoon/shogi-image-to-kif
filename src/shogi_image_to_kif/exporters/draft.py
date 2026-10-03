"""Shared draft export for the local server and browser runtime."""

from shogi_image_to_kif.domain.position import Position, reviewed_position
from shogi_image_to_kif.exporters.kif import to_bod, to_kif


def export_draft(value):
    notes = []
    if value.get("preview") is True:
        draft = value["draft"]
        board = [None if piece == "?" else piece for piece in draft["board"]]
        unknown = draft["board"].count("?")
        if unknown:
            notes.append(f"未判別{unknown}マスを空マスとして出力")
        turn = draft.get("turn") or "b"
        if not draft.get("turn") or draft.get("default_turn"):
            notes.append("手番未指定：先手番で出力")
        hands = {side: draft.get("hands", {}).get(side) or {} for side in ("b", "w")}
        for side, name in (("b", "先手"), ("w", "後手")):
            if draft.get("hands", {}).get(side) is None or side in draft.get(
                "default_hands", []
            ):
                notes.append(f"{name}の持ち駒未指定：なしで出力")
        position = Position(
            board,
            hands,
            turn,
            draft.get("move_number", 1),
            validate_counts=False,
        )
    else:
        position = reviewed_position(value["draft"], value.get("reviewed") is True)
    return {
        "kif": to_kif(position),
        "bod": to_bod(position),
        "sfen": "sfen " + position.sfen(),
        "warnings": notes + position.warnings(),
    }
