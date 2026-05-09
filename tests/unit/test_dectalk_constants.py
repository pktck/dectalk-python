"""Unit tests for the translated `dectalk.h` constants and structs."""

from __future__ import annotations

from dectalk.include.dectalk import (
    LTS_PIPE,
    NINTER,
    NPARAM,
    NSTRING,
    PH_PIPE,
    DebugSection,
    Pparse,
    Seq,
    Voice,
)


def test_voice_ids_match_c_defines() -> None:
    assert Voice.PERFECT_PAUL == 0
    assert Voice.BEAUTIFUL_BETTY == 1
    assert Voice.HUGE_HARRY == 2
    assert Voice.WHISPERY_WILLY == 8
    assert Voice.CRAFTY_CHRIS == 9
    assert Voice.VARIABLE_VAL == 10


def test_pipe_codes_match_c_defines() -> None:
    assert LTS_PIPE == 0x00
    assert PH_PIPE == 0x20


def test_debug_flags_match_c_defines() -> None:
    assert DebugSection.CMD == 0x8000
    assert DebugSection.LTS == 0x4000
    assert DebugSection.PH == 0x2000
    assert DebugSection.VTM == 0x1000


def test_seq_default_init_uses_correct_buffer_sizes() -> None:
    s = Seq()
    assert len(s.s_param) == NPARAM
    assert len(s.s_dflag) == NPARAM
    assert len(s.s_inter) == NINTER
    assert all(d is True for d in s.s_dflag)


def test_pparse_buf_size() -> None:
    p = Pparse()
    assert len(p.p_buf) == 4


def test_nstring_below_byte_limit() -> None:
    # The C comment says "< 256". Verify we kept that constraint.
    assert NSTRING < 256
