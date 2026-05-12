"""Verify CommandData / WordStruct / IndexInfo dataclasses."""

from __future__ import annotations

from dectalk.lts.word_struct import CommandData, IndexInfo, WordStruct


def test_command_data_default() -> None:
    """CommandData defaults to (0, [0, 0, 0])."""
    cd = CommandData()
    assert cd.command == 0
    assert cd.nextra == [0, 0, 0]


def test_command_data_with_value() -> None:
    """CommandData fields are settable."""
    cd = CommandData(command=0x1F00, nextra=[200, 0, 0])
    assert cd.command == 0x1F00
    assert cd.nextra == [200, 0, 0]


def test_command_data_independent_nextra() -> None:
    """Each CommandData has its own nextra list."""
    a = CommandData()
    b = CommandData()
    a.nextra[0] = 99
    assert b.nextra[0] == 0


def test_word_struct_defaults() -> None:
    """WordStruct defaults all 13 fields to zero."""
    ws = WordStruct()
    fields = ws.__dataclass_fields__
    assert len(fields) == 13
    for name in fields:
        assert getattr(ws, name) == 0


def test_word_struct_construction() -> None:
    """WordStruct fields are settable at construction."""
    ws = WordStruct(
        mode_flag=0x40,
        form_class=0x00000400,  # noun
        dict_index=42,
        homograph=1,
    )
    assert ws.mode_flag == 0x40
    assert ws.form_class == 0x00000400
    assert ws.dict_index == 42
    assert ws.homograph == 1


def test_index_info_default() -> None:
    """IndexInfo defaults to (0, [0, 0, 0])."""
    ii = IndexInfo()
    assert ii.pos == 0
    assert ii.data == [0, 0, 0]


def test_all_use_slots() -> None:
    """All three dataclasses use slots=True."""
    assert not hasattr(CommandData(), "__dict__")
    assert not hasattr(WordStruct(), "__dict__")
    assert not hasattr(IndexInfo(), "__dict__")
