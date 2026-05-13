"""C-source parity test for ``cm_text_getclause`` against cm_text.c.

Re-parses the body of ``cm_text_getclause`` (line 276, ~1025-line body
in ``src/dapi/src/cmd/cm_text.c``) using brace-depth tracking and
asserts structural invariants of the per-character state machine:

- The ``pipe_value`` U16 read variable is preserved.
- The ``temp_mode`` / ``parser_flag`` state-machine variables are
  preserved.
- The phonemic-mode dispatch checks against the ``0x80`` / ``0x81``
  bracket bytes.
- The clause-boundary character checks via ``MARK_clause`` and the
  ``char_types`` table.
- The index-marker handling via ``pCmd_t->index_counter`` and
  ``par_is_index_set_cm_text``.

Plus behavioural tests of the Python architectural shim.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_text_getclause import (
    BOUNDARY_COMMA,
    BOUNDARY_EXCLAIM,
    BOUNDARY_NONE,
    BOUNDARY_PERIOD,
    BOUNDARY_QUESTION,
    BOUNDARY_SEMICOLON,
    INLINE_DM,
    PHONEMIC_OFF,
    PHONEMIC_ON,
    ClauseSegmentation,
    cm_text_getclause,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_text.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_cm_text_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _skip_quoted(text: str, i: int, quote: str) -> int:
    """Skip a character/string literal starting at ``text[i] == quote``."""
    n = len(text)
    i += 1
    while i < n and text[i] != quote:
        if text[i] == "\\" and i + 1 < n:
            i += 2
        else:
            i += 1
    return i + 1


def _skip_comment(text: str, i: int) -> int:
    """Skip a ``//`` line or ``/* ... */`` block comment starting at ``text[i]``."""
    n = len(text)
    if i + 1 < n and text[i + 1] == "/":
        while i < n and text[i] != "\n":
            i += 1
        return i
    # Block comment.
    i += 2
    while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
        i += 1
    return i + 2


def _extract_body() -> str:
    """Locate the ``cm_text_getclause`` body in cm_text.c via brace tracking.

    The C source contains character literals like ``'{'`` and ``'}'`` and
    string literals containing ``"{"``; brace-counting must skip over those
    (and over ``/* ... */`` block / ``// ...`` line comments).
    """
    text = _read_cm_text_c()
    decl = re.search(r"\bvoid\s+cm_text_getclause\s*\(", text)
    assert decl is not None, "cm_text_getclause declaration not found in cm_text.c"
    brace_start = text.index("{", decl.end())
    depth = 1
    i = brace_start + 1
    n = len(text)
    while i < n and depth > 0:
        ch = text[i]
        if ch in ("'", '"'):
            i = _skip_quoted(text, i, ch)
            continue
        if ch == "/" and i + 1 < n and text[i + 1] in ("/", "*"):
            i = _skip_comment(text, i)
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    assert depth == 0, "Unbalanced braces while extracting cm_text_getclause body"
    return text[brace_start + 1 : i - 1]


# -- Structural assertions on the C body -----------------------------------


def test_c_body_declares_pipe_value() -> None:
    """The C body still declares ``unsigned short int pipe_value``."""
    body = _extract_body()
    assert re.search(r"unsigned\s+short\s+int\s+pipe_value\s*;", body), (
        "expected ``unsigned short int pipe_value;`` in cm_text_getclause body"
    )


def test_c_body_declares_temp_mode_u32() -> None:
    """The C body still declares ``U32 temp_mode``."""
    body = _extract_body()
    assert re.search(r"\bU32\s+temp_mode\s*=\s*0\s*;", body), (
        "expected ``U32 temp_mode = 0;`` in cm_text_getclause body"
    )


def test_c_body_declares_parser_flag_u16() -> None:
    """The C body still declares ``U16 parser_flag``."""
    body = _extract_body()
    assert re.search(r"\bU16\s+parser_flag\s*;", body), (
        "expected ``U16 parser_flag;`` in cm_text_getclause body"
    )


def test_c_body_preserves_parser_flag_across_calls() -> None:
    """The C body still saves and restores ``ret_value.parser_flag``."""
    body = _extract_body()
    # Saved at entry.
    assert re.search(r"parser_flag\s*=\s*pCmd_t\s*->\s*ret_value\.parser_flag", body), (
        "expected ``parser_flag = pCmd_t->ret_value.parser_flag;`` save"
    )
    # Restored back later.
    assert re.search(r"pCmd_t\s*->\s*ret_value\.parser_flag\s*=\s*parser_flag", body), (
        "expected ``pCmd_t->ret_value.parser_flag = parser_flag;`` restore"
    )


def test_c_body_writes_pipe_value_to_lts_pipe() -> None:
    """The C body still forwards ``pipe_value`` via the LTS pipe / lts_loop."""
    body = _extract_body()
    # SINGLE_THREADED build: lts_loop(phTTS,&pipe_value).
    assert re.search(r"lts_loop\s*\(\s*phTTS\s*,\s*&\s*pipe_value\s*\)", body), (
        "expected ``lts_loop(phTTS, &pipe_value)`` write in cm_text_getclause"
    )


def test_c_body_uses_pfascii_psfont_bit_packing() -> None:
    """The C body still packs ``(PFASCII << PSFONT) + ch`` for pipe writes."""
    body = _extract_body()
    assert re.search(r"\(\s*PFASCII\s*<<\s*PSFONT\s*\)", body), (
        "expected ``(PFASCII<<PSFONT)`` font-tag shift in pipe writes"
    )


def test_c_body_dispatches_on_phoneme_off_marker() -> None:
    """The C body still flips ``mode`` on the ``PAR_PHONES_OFF_D`` marker."""
    body = _extract_body()
    # The C source's phoneme-mode dispatch flips at PAR_PHONES_ON_D
    # (0x80) and PAR_PHONES_OFF_D (0x81). Both names must still be
    # referenced.
    assert re.search(r"PAR_PHONES_ON_D", body), "expected ``PAR_PHONES_ON_D`` in body"
    assert re.search(r"PAR_PHONES_OFF_D", body), "expected ``PAR_PHONES_OFF_D`` in body"


def test_c_body_checks_dm_byte_0x82() -> None:
    """The C body still treats ``0x82`` as a space-equivalent in clause detection."""
    body = _extract_body()
    # The C source compares ``clausebuf[input_counter-1] == 0x82`` to
    # treat the inline-DM control byte as a clause-flushing whitespace
    # equivalent.
    assert re.search(r"==\s*0x82", body), (
        "expected ``== 0x82`` (inline-DM whitespace equivalence) in body"
    )


def test_c_body_checks_mark_clause_via_char_types() -> None:
    """The C body still uses ``char_types[...] & MARK_clause`` for boundaries.

    The actual subscript can be a nested expression (e.g.
    ``char_types[pCmd_t->clausebuf[pCmd_t->input_counter-2]]``), so we
    just require ``char_types[`` followed by ``MARK_clause`` within a
    reasonable window.
    """
    body = _extract_body()
    assert re.search(r"char_types\s*\[[^\n]*?MARK_clause", body), (
        "expected ``char_types[...] & MARK_clause`` clause-terminator check"
    )


def test_c_body_checks_mark_space_via_char_types() -> None:
    """The C body still uses ``char_types[...] & MARK_space`` for whitespace."""
    body = _extract_body()
    assert re.search(r"char_types\s*\[[^\n]*?MARK_space", body), (
        "expected ``char_types[...] & MARK_space`` whitespace check"
    )


def test_c_body_handles_index_counter() -> None:
    """The C body still references ``pCmd_t->index_counter`` for index markers."""
    body = _extract_body()
    assert re.search(r"pCmd_t\s*->\s*index_counter", body), (
        "expected ``pCmd_t->index_counter`` index-marker handling"
    )


def test_c_body_uses_par_is_index_set_helper() -> None:
    """The C body still drives the index-marker emit via the helper."""
    body = _extract_body()
    assert re.search(r"par_is_index_set_cm_text\s*\(", body), (
        "expected ``par_is_index_set_cm_text(...)`` index-marker emit"
    )


def test_c_body_sets_done_flag() -> None:
    """The C body still drives the ``pCmd_t->done`` flag (0 / 1 / 2)."""
    body = _extract_body()
    # done=1 -- full clause boundary.
    assert re.search(r"pCmd_t\s*->\s*done\s*=\s*1", body)
    # done=2 -- rolling-buffer split.
    assert re.search(r"pCmd_t\s*->\s*done\s*=\s*2", body)


def test_c_body_calls_par_process_input() -> None:
    """The C body still routes flushed clauses through ``par_process_input``."""
    body = _extract_body()
    assert re.search(r"\bpar_process_input\s*\(", body), (
        "expected ``par_process_input(...)`` call after clause boundary"
    )


def test_c_body_flushes_to_lts_loop_via_single_threaded() -> None:
    """The C body still keeps the ``SINGLE_THREADED`` lts_loop fast path."""
    body = _extract_body()
    assert "SINGLE_THREADED" in body, "expected SINGLE_THREADED build branch in body"


# -- Behavioural tests of the Python shim ----------------------------------


def test_python_empty_input_returns_empty_list() -> None:
    """Empty input returns no segmentations."""
    assert cm_text_getclause(b"") == []


def test_python_plain_text_no_boundary_returns_single_segmentation() -> None:
    """Text without clause-terminating punctuation flushes once at end."""
    segments = cm_text_getclause(b"hello world")
    assert len(segments) == 1
    assert segments[0].clause_text == b"hello world"
    assert segments[0].boundary_type == BOUNDARY_NONE


def test_python_returns_dataclass_results() -> None:
    """Output entries are :class:`ClauseSegmentation` instances."""
    segments = cm_text_getclause(b"hi.")
    assert all(isinstance(s, ClauseSegmentation) for s in segments)


def test_python_period_boundary_splits_clauses() -> None:
    """Text with ``.`` followed by space produces a period boundary."""
    segments = cm_text_getclause(b"Hello. World")
    assert len(segments) == 2
    assert segments[0].boundary_type == BOUNDARY_PERIOD
    assert segments[0].clause_text.endswith(b".")
    assert segments[1].boundary_type == BOUNDARY_NONE
    # The shim doesn't trim leading whitespace (the C source leaves it in
    # the clause buffer too); callers normalise downstream.
    assert segments[1].clause_text.strip() == b"World"


def test_python_period_at_end_of_input_is_a_boundary() -> None:
    """A ``.`` at end-of-input is a complete clause boundary."""
    segments = cm_text_getclause(b"Hello.")
    assert len(segments) == 1
    assert segments[0].boundary_type == BOUNDARY_PERIOD
    assert segments[0].clause_text == b"Hello."


def test_python_exclaim_boundary_recognised() -> None:
    """A ``!`` followed by whitespace produces an exclamation boundary."""
    segments = cm_text_getclause(b"Hi! there")
    assert len(segments) == 2
    assert segments[0].boundary_type == BOUNDARY_EXCLAIM


def test_python_question_boundary_recognised() -> None:
    """A ``?`` followed by whitespace produces a question boundary."""
    segments = cm_text_getclause(b"What? now")
    assert len(segments) == 2
    assert segments[0].boundary_type == BOUNDARY_QUESTION


def test_python_comma_boundary_recognised() -> None:
    """A ``,`` followed by whitespace produces a comma boundary.

    The ``char_types`` table marks ``,`` with ``MARK_clause`` (the C
    source's clause-boundary mask), so it produces a boundary just
    like ``.`` does -- the *higher-level* punct-mode logic decides
    whether to actually pause on it.
    """
    segments = cm_text_getclause(b"yes, please")
    assert len(segments) == 2
    assert segments[0].boundary_type == BOUNDARY_COMMA


def test_python_semicolon_boundary_recognised() -> None:
    """A ``;`` followed by whitespace produces a semicolon boundary."""
    segments = cm_text_getclause(b"a; b")
    assert len(segments) == 2
    assert segments[0].boundary_type == BOUNDARY_SEMICOLON


def test_python_period_without_following_space_is_not_a_boundary() -> None:
    """Mid-word ``.`` (e.g. URL host) is not a clause boundary."""
    segments = cm_text_getclause(b"www.example.com")
    assert len(segments) == 1
    assert segments[0].boundary_type == BOUNDARY_NONE


def test_python_multiple_clauses_in_sequence() -> None:
    """Several boundaries split into several segmentations."""
    segments = cm_text_getclause(b"One. Two? Three!")
    assert len(segments) == 3
    assert segments[0].boundary_type == BOUNDARY_PERIOD
    assert segments[1].boundary_type == BOUNDARY_QUESTION
    assert segments[2].boundary_type == BOUNDARY_EXCLAIM


def test_python_phoneme_mode_short_circuits() -> None:
    """``phoneme_mode=True`` keeps the entire input as one segmentation."""
    # Inside a [:phoneme arpabet on] block the C body holds the whole
    # phonemic span until 0x81 closes it -- clause punctuation inside
    # doesn't split.
    segments = cm_text_getclause(b"aa. bb. cc", phoneme_mode=True)
    assert len(segments) == 1
    assert segments[0].clause_text == b"aa. bb. cc"
    assert segments[0].boundary_type == BOUNDARY_NONE


def test_python_dataclass_defaults_match_shape() -> None:
    """Default :class:`ClauseSegmentation` fields match the C source's idle state."""
    seg = ClauseSegmentation(clause_text=b"")
    assert seg.parser_flag == 0
    assert seg.mode == 0
    assert seg.index_markers == []
    assert seg.boundary_type == BOUNDARY_NONE


def test_python_boundary_constants_match_ascii_codes() -> None:
    """Boundary-type constants are the literal ASCII byte values."""
    assert ord(".") == BOUNDARY_PERIOD
    assert ord("!") == BOUNDARY_EXCLAIM
    assert ord("?") == BOUNDARY_QUESTION
    assert ord(",") == BOUNDARY_COMMA
    assert ord(";") == BOUNDARY_SEMICOLON


def test_python_phonemic_bracket_constants_are_correct() -> None:
    """Phonemic-mode brackets match the C source's literal bytes (0x80/0x81)."""
    assert PHONEMIC_ON == 0x80
    assert PHONEMIC_OFF == 0x81
    assert INLINE_DM == 0x82
