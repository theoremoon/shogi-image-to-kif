"""Custom starting-position KIF and BOD; no invented moves or history."""

from shogi_image_to_kif.domain.position import HAND_ORDER, JAPANESE, Position


def kanji_number(number: int) -> str:
    digits = "零一二三四五六七八九"
    if number < 10:
        return digits[number]
    tens, ones = divmod(number, 10)
    return (digits[tens] if tens > 1 else "") + "十" + (digits[ones] if ones else "")


def hand_text(hand: dict[str, int]) -> str:
    parts = []
    for piece in HAND_ORDER:
        count = hand.get(piece, 0)
        if count:
            parts.append(JAPANESE[piece] + (kanji_number(count) if count > 1 else ""))
    return "　".join(parts) or "なし"


def to_bod(position: Position) -> str:
    lines = [
        f"後手の持駒：{hand_text(position.hands['w'])}",
        "  ９ ８ ７ ６ ５ ４ ３ ２ １",
        "+---------------------------+",
    ]
    for row in range(9):
        cells = []
        for piece in position.board[row * 9 : row * 9 + 9]:
            if piece is None:
                cells.append(" ・")
            else:
                cells.append(
                    (" " if piece[-1].isupper() else "v") + JAPANESE[piece.upper()]
                )
        lines.append("|" + "".join(cells) + "|" + "一二三四五六七八九"[row])
    lines += [
        "+---------------------------+",
        f"先手の持駒：{hand_text(position.hands['b'])}",
        "先手番" if position.turn == "b" else "後手番",
    ]
    return "\n".join(lines) + "\n"


def to_kif(position: Position) -> str:
    return (
        "#KIF version=2.0 encoding=UTF-8\n"
        + to_bod(position)
        + "手数----指手---------消費時間--\n"
    )
