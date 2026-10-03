import json

import pytest
import shogi
import shogi.KIF

from shogi_image_to_kif.cli import main
from shogi_image_to_kif.domain.position import (
    STARTING_SFEN,
    Position,
    parse_hands,
    reviewed_position,
)
from shogi_image_to_kif.exporters.kif import to_bod, to_kif

POSITIONS = [
    STARTING_SFEN,
    STARTING_SFEN.replace("1r5b1", "7b1").replace(" b ", " w "),
    "4k4/9/2+r6/3+b5/4+s4/5+n3/6+l2/7+p1/4K4 w RBGSNL10P2p 1",
    "4k4/9/9/9/9/9/9/9/9 b R2P 1",
    "lnsgk1snl/6g2/p1pppp1pp/5bp2/9/7r1/PPPP1PP1P/2GS1S1R1/LNBK1G1NL b - 1",
]


@pytest.mark.parametrize("sfen", POSITIONS)
def test_kif_roundtrip_with_independent_parser(sfen):
    position = Position.from_sfen(sfen)
    assert Position.from_sfen(position.sfen()) == position
    parsed = shogi.KIF.Parser.parse_str(to_kif(position))[0]
    board = shogi.Board(parsed["sfen"])
    assert Position.from_sfen(board.sfen()) == position
    assert parsed["moves"] == []
    assert (
        "後手番" in to_bod(position)
        if position.turn == "w"
        else "先手番" in to_bod(position)
    )


@pytest.mark.parametrize(
    "sfen",
    [
        "9/9/9/9/9/9/9/9/9 x - 1",
        "9/9/9/9/9/9/9/9/8 b - 1",
        "9/9/9/9/9/9/9/9/9 b 19P 1",
        "9/9/9/9/9/9/9/9/+G8 b - 1",
        "9/9/9/9/9/9/9/9/9 b PP 1",
        "9/9/9/9/9/9/9/9/9 b 0P 1",
        "9/9/9/9/9/9/9/9/9 b - 0",
        "9/9/9/9/9/9/9/9/9 b - nan",
        "9/9/9/9/9/9/9/9/KK7 b - 1",
    ],
)
def test_invalid_position(sfen):
    with pytest.raises(ValueError):
        Position.from_sfen(sfen)


def test_unknown_or_unreviewed_never_exports():
    position = Position.from_sfen(STARTING_SFEN)
    value = {"board": position.board, "hands": position.hands, "turn": position.turn}
    with pytest.raises(ValueError):
        reviewed_position(value)
    value["hands"] = {"b": None, "w": {}}
    with pytest.raises(ValueError):
        reviewed_position(value, True)
    value["hands"] = position.hands
    value["board"][0] = "?"
    with pytest.raises(ValueError):
        reviewed_position(value, True)


def test_cli_export_and_cp932(tmp_path):
    output = tmp_path / "position.kif"
    assert (
        main(
            ["export", "--sfen", POSITIONS[2], "-o", str(output), "--encoding", "cp932"]
        )
        == 0
    )
    assert "encoding=Shift_JIS" in output.read_text(encoding="cp932")
    assert Position.from_sfen(
        shogi.Board(shogi.KIF.Parser.parse_file(str(output))[0]["sfen"]).sfen()
    ) == Position.from_sfen(POSITIONS[2])


def test_cli_draft_requires_confirmation(tmp_path):
    position = Position.from_sfen(STARTING_SFEN)
    path = tmp_path / "draft.json"
    path.write_text(
        json.dumps(
            {"board": position.board, "hands": position.hands, "turn": position.turn}
        )
    )
    with pytest.raises(SystemExit) as error:
        main(["export", "--draft", str(path)])
    assert error.value.code == 2


def test_hand_parser_and_warnings():
    assert parse_hands("R2P3p") == {"b": {"R": 1, "P": 2}, "w": {"P": 3}}
    position = Position.from_sfen("P8/P8/9/9/9/9/9/9/9 b - 1")
    assert len(position.warnings()) == 2
