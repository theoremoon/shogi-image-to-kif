"""Image-independent position model. Unknown values are never silently exported."""

import re
from collections import Counter
from dataclasses import dataclass, field

HAND_ORDER = "RBGSNLP"
LIMITS = dict(zip("KRBGSNLP", (2, 2, 2, 4, 4, 4, 4, 18)))
PIECES = {p for p in "PLNSGBRKplnsgbrk"} | {"+" + p for p in "PLNSBRplnsbr"}
JAPANESE = dict(
    zip(
        ("P", "L", "N", "S", "G", "B", "R", "K", "+P", "+L", "+N", "+S", "+B", "+R"),
        (
            "歩",
            "香",
            "桂",
            "銀",
            "金",
            "角",
            "飛",
            "玉",
            "と",
            "杏",
            "圭",
            "全",
            "馬",
            "龍",
        ),
    )
)
STARTING_SFEN = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"


def parse_hands(value: str) -> dict[str, dict[str, int]]:
    hands = {"b": {}, "w": {}}
    if value == "-":
        return hands
    if not value or not re.fullmatch(
        r"(?:[1-9][0-9]*[RBGSNLPrbgsnlp]|[RBGSNLPrbgsnlp])+", value
    ):
        raise ValueError("持ち駒はSFEN形式（例: 2R3Pr、なしは -）で指定してください")
    for count, piece in re.findall(r"([0-9]*)([RBGSNLPrbgsnlp])", value):
        side = "b" if piece.isupper() else "w"
        if piece.upper() in hands[side]:
            raise ValueError("持ち駒の駒種が重複しています")
        hands[side][piece.upper()] = int(count or 1)
    validate_hands(hands)
    return hands


def validate_hands(hands):
    if not isinstance(hands, dict) or set(hands) != {"b", "w"}:
        raise ValueError("先後両方の持ち駒を確認してください")
    for hand in hands.values():
        if not isinstance(hand, dict):
            raise ValueError("持ち駒が不明です。なしの場合も明示してください")
        for piece, count in hand.items():
            if (
                piece not in HAND_ORDER
                or type(count) is not int
                or not 0 <= count <= LIMITS[piece]
            ):
                raise ValueError("持ち駒の駒種・枚数が不正です")


@dataclass
class Position:
    board: list[str | None]
    hands: dict[str, dict[str, int]]
    turn: str
    move_number: int = 1
    validate_counts: bool = field(default=True, kw_only=True, repr=False)

    def __post_init__(self):
        if len(self.board) != 81 or any(
            p is not None and p not in PIECES for p in self.board
        ):
            raise ValueError("盤面は81マスの確定した駒または空マスで指定してください")
        if self.turn not in ("b", "w"):
            raise ValueError("手番を確認してください")
        if type(self.move_number) is not int or self.move_number < 1:
            raise ValueError("手数は1以上の整数です")
        validate_hands(self.hands)
        totals = Counter(p[-1].upper() for p in self.board if p)
        for hand in self.hands.values():
            totals.update(hand)
        for piece, count in totals.items():
            if self.validate_counts and count > LIMITS[piece]:
                raise ValueError(
                    f"{JAPANESE[piece]}の総数が上限を超えています（{count}枚）"
                )
        for side in ("K", "k"):
            if self.validate_counts and self.board.count(side) > 1:
                raise ValueError("同じ側の玉が2枚以上あります")

    @classmethod
    def from_sfen(cls, sfen: str):
        parts = sfen.strip().removeprefix("sfen ").split()
        if len(parts) != 4:
            raise ValueError("SFENは盤面・手番・持ち駒・手数の4項目です")
        board = []
        ranks = parts[0].split("/")
        if len(ranks) != 9:
            raise ValueError("SFENの盤面は9段必要です")
        for rank in ranks:
            cells = []
            i = 0
            while i < len(rank):
                char = rank[i]
                if char in "123456789":
                    cells.extend([None] * int(char))
                else:
                    if char == "+":
                        i += 1
                        if i >= len(rank):
                            raise ValueError("成駒の表記が不正です")
                        char += rank[i]
                    if char not in PIECES:
                        raise ValueError("SFENに不正な駒があります")
                    cells.append(char)
                i += 1
            if len(cells) != 9:
                raise ValueError("SFENの各段は9マス必要です")
            board.extend(cells)
        try:
            number = int(parts[3])
        except ValueError as exc:
            raise ValueError("手数が不正です") from exc
        return cls(board, parse_hands(parts[2]), parts[1], number)

    def sfen(self) -> str:
        ranks = []
        for start in range(0, 81, 9):
            text, empty = "", 0
            for piece in self.board[start : start + 9]:
                if piece is None:
                    empty += 1
                else:
                    if empty:
                        text += str(empty)
                        empty = 0
                    text += piece
            ranks.append(text + (str(empty) if empty else ""))
        hand = ""
        for side in ("b", "w"):
            for piece in HAND_ORDER:
                count = self.hands[side].get(piece, 0)
                if count:
                    hand += (str(count) if count > 1 else "") + (
                        piece if side == "b" else piece.lower()
                    )
        return f"{'/'.join(ranks)} {self.turn} {hand or '-'} {self.move_number}"

    def warnings(self) -> list[str]:
        warnings = []
        totals = Counter(p[-1].upper() for p in self.board if p)
        for hand in self.hands.values():
            totals.update(hand)
        for piece, count in totals.items():
            if count > LIMITS[piece]:
                warnings.append(f"{JAPANESE[piece]}が{count}枚あります")
        for king in ("K", "k"):
            if self.board.count(king) > 1:
                warnings.append("同じ側の玉が2枚以上あります")
        for side, upper in (("先手", True), ("後手", False)):
            for col in range(9):
                pawn = "P" if upper else "p"
                if sum(self.board[r * 9 + col] == pawn for r in range(9)) > 1:
                    warnings.append(f"{side}の{9 - col}筋に二歩があります")
            for index, piece in enumerate(self.board):
                if not piece or piece[-1].isupper() != upper or piece.startswith("+"):
                    continue
                distance = index // 9 if upper else 8 - index // 9
                if (piece.upper() in ("P", "L") and distance == 0) or (
                    piece.upper() == "N" and distance < 2
                ):
                    warnings.append(
                        f"{side}の{9 - index % 9}{index // 9 + 1}に行き所のない駒があります"
                    )
        return warnings


def reviewed_position(draft: dict, reviewed: bool = False) -> Position:
    if not reviewed:
        raise ValueError("盤面・持ち駒・手番を確認後、確認済みとして出力してください")
    return Position(
        draft["board"], draft["hands"], draft["turn"], draft.get("move_number", 1)
    )
