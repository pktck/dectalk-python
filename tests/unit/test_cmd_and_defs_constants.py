"""Verify Python constants in ``cmd_codes`` and ``defs`` match the C headers.

Parses ``src/dapi/src/include/cmd.h``, ``defs.h``, ``pipe.h``, and
``usa_def.h`` at test time and asserts every Python constant we expose
equals the corresponding ``#define``. This is the same pattern used by
``test_phoneme_codes.py`` — direct, mechanical, fails loudly on drift.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include import cmd_codes as cc
from dectalk.include import defs as dd
from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFUSA

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_CMD_H = _SRC_ROOT / "src/dapi/src/include/cmd.h"
_DEFS_H = _SRC_ROOT / "src/dapi/src/include/defs.h"
_PIPE_H = _SRC_ROOT / "src/dapi/src/include/pipe.h"
_USA_DEF_H = _SRC_ROOT / "src/dapi/src/include/usa_def.h"

pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in (_CMD_H, _DEFS_H, _PIPE_H, _USA_DEF_H)),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# A small expression evaluator for ``#define EXPR`` right-hand sides.
# Supported syntax:
#   - decimal int (123)
#   - hex int (0x1F)
#   - parenthesised arithmetic with + - * / << >>
#   - reference to a previously-defined identifier
def _parse_define(text: str, name: str) -> int | None:
    m = re.search(rf"^#define\s+{re.escape(name)}\s+(.+?)\s*(?:/\*.*|//.*)?$", text, re.MULTILINE)
    if not m:
        return None
    return _eval_expr(m.group(1).strip(), text)


def _eval_expr(expr: str, text: str) -> int | None:
    """Evaluate a C ``#define`` right-hand expression."""

    # Replace identifiers with their values (one level of indirection is
    # enough for everything we test).
    def _ident_repl(match: re.Match[str]) -> str:
        ident = match.group(0)
        # Skip numeric literals.
        if ident[:1].isdigit() or ident in {"x"}:
            return ident
        nested = _parse_define(text, ident)
        if nested is None:
            return ident
        return str(nested)

    substituted = re.sub(r"\b[A-Za-z_][A-Za-z0-9_]*\b", _ident_repl, expr)
    # Hex literals are already evaluable in Python.
    if not re.fullmatch(r"[\d+\-*/() <>x0-9a-fA-FXL]+", substituted):
        return None
    # Convert any C "L" integer suffixes (no-op in Python).
    substituted = re.sub(r"(\d+)L\b", r"\1", substituted)
    try:
        return int(eval(substituted))
    except (SyntaxError, NameError, ValueError):
        return None


# ----- defs.h --------------------------------------------------------------


@pytest.mark.parametrize(
    ("py", "c"),
    [
        ("TRUE", "TRUE"),
        ("FALSE", "FALSE"),
        ("SUCCESS", "SUCCESS"),
        ("FAILURE", "FAILURE"),
        ("HUNGARY", "HUNGARY"),
    ],
)
def test_defs_h_constants(py: str, c: str) -> None:
    """TRUE/FALSE/SUCCESS/FAILURE/HUNGARY match defs.h."""
    text = _DEFS_H.read_text(encoding="latin-1")
    c_value = _parse_define(text, c)
    assert c_value is not None, f"could not parse #define {c} in defs.h"
    assert getattr(dd, py) == c_value


@pytest.mark.parametrize("n", range(16))
def test_defs_h_bit_constants(n: int) -> None:
    """BIT0..BIT15 in defs.h match our Python BIT0..BIT15."""
    text = _DEFS_H.read_text(encoding="latin-1")
    c_value = _parse_define(text, f"BIT{n}")
    assert c_value == 1 << n
    assert getattr(dd, f"BIT{n}") == c_value


@pytest.mark.parametrize("n", range(10))
def test_defs_h_bit00_aliases(n: int) -> None:
    """BIT00..BIT09 zero-padded aliases in defs.h."""
    text = _DEFS_H.read_text(encoding="latin-1")
    c_value = _parse_define(text, f"BIT0{n}")
    assert c_value == 1 << n
    assert getattr(dd, f"BIT0{n}") == c_value


# ----- pipe.h --------------------------------------------------------------


@pytest.mark.parametrize(
    ("py", "c"),
    [
        ("BYTE_PIPE", "BYTE_PIPE"),
        ("WORD_PIPE", "WORD_PIPE"),
        ("DWORD_PIPE", "DWORD_PIPE"),
        ("QWORD_PIPE", "QWORD_PIPE"),
        ("FLOAT_PIPE", "FLOAT_PIPE"),
        ("DOUBLE_PIPE", "DOUBLE_PIPE"),
        ("VOID_PTR_PIPE", "VOID_PTR_PIPE"),
        ("READ_WORD_PIPE_PACKET", "READ_WORD_PIPE_PACKET"),
    ],
)
def test_pipe_h_constants(py: str, c: str) -> None:
    text = _PIPE_H.read_text(encoding="latin-1")
    c_value = _parse_define(text, c)
    assert c_value is not None, f"could not parse #define {c} in pipe.h"
    assert getattr(dd, py) == c_value


# ----- usa_def.h -----------------------------------------------------------


def test_usa_def_null_ascky() -> None:
    text = _USA_DEF_H.read_text(encoding="latin-1")
    assert _parse_define(text, "NULL_ASCKY") == dd.NULL_ASCKY


def test_pusa_macro_matches_c_definition() -> None:
    """``pusa(x)`` reproduces the C macro ``PUSA(x) = (PFUSA<<PSFONT) | x``."""
    assert dd.pusa(0) == (PFUSA << PSFONT)
    assert dd.pusa(17) == ((PFUSA << PSFONT) | 17)
    assert dd.pusa(0xFF) == ((PFUSA << PSFONT) | 0xFF)


# ----- cmd.h bit-layout constants ------------------------------------------


@pytest.mark.parametrize(
    ("py", "c"),
    [
        ("PUNUSED", "PUNUSED"),
        ("PNEXTRA", "PNEXTRA"),
        ("PFONT", "PFONT"),
        ("PVALUE", "PVALUE"),
        ("PSNEXTRA", "PSNEXTRA"),
        ("PSFONT", "PSFONT"),
        ("PFASCII", "PFASCII"),
        ("PFCONTROL", "PFCONTROL"),
    ],
)
def test_cmd_h_bit_layout(py: str, c: str) -> None:
    text = _CMD_H.read_text(encoding="latin-1")
    c_value = _parse_define(text, c)
    assert c_value is not None, f"could not parse #define {c} in cmd.h"
    assert getattr(cc, py) == c_value


# ----- cmd.h control commands (font-encoded) -------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "RATE",
        "CPAUSE",
        "PPAUSE",
        "LAST_VOICE",
        "LTS_SYNC",
        "NEW_SPEAKER",
        "NEW_PARAM",
        "SAVE",
        "INDEX",
        "INDEX_REPLY",
        "SYNC",
        "BREATH_BREAK",
        "KILL_TASK",
        "FLUSH_SYNC",
        "PITCH_CHANGE",
        "LATIN",
        "PAPAUSE",
        "CNTRLK",
        "RESET",
        "INDEX_BOOKMARK",
        "INDEX_WORDPOS",
        "INDEX_START",
        "INDEX_STOP",
        "WORD_CLASS",
        "INDEX_SENTENCE",
        "INDEX_VOLUME",
        "INDEX_NOISE",
        "PREAMBLE",
    ],
)
def test_cmd_h_control_commands(name: str) -> None:
    """Each ``(PFCONTROL<<PSFONT)+N`` control command matches the C value."""
    text = _CMD_H.read_text(encoding="latin-1")
    c_value = _parse_define(text, name)
    assert c_value is not None, f"could not parse #define {name} in cmd.h"
    assert getattr(cc, name) == c_value


# ----- cmd.h LTS modes and flush states -----------------------------------


@pytest.mark.parametrize(
    ("py", "c"),
    [
        ("LTS_MODE_SET", "LTS_MODE_SET"),
        ("LTS_MODE_CLEAR", "LTS_MODE_CLEAR"),
        ("LTS_MODE_ABS", "LTS_MODE_ABS"),
        ("LTS_DIC_ALTERNATE", "LTS_DIC_ALTERNATE"),
        ("LTS_ACNA_NAME", "LTS_ACNA_NAME"),
        ("LTS_DIC_PRIMARY", "LTS_DIC_PRIMARY"),
        ("LTS_DIC_NOUN", "LTS_DIC_NOUN"),
        ("LTS_DIC_VERB", "LTS_DIC_VERB"),
        ("LTS_DIC_ADJECTIVE", "LTS_DIC_ADJECTIVE"),
        ("LTS_DIC_FUNCTION", "LTS_DIC_FUNCTION"),
        ("LTS_DIC_INTERJECTION", "LTS_DIC_INTERJECTION"),
        ("CMD_FLUSH_TOSS", "CMD_flush_toss"),
        ("CMD_FLUSH_SYNC", "CMD_flush_sync"),
        ("CMD_FLUSH_DONE", "CMD_flush_done"),
        ("CMD_SYNC_CHAR", "CMD_sync_char"),
        ("CMD_SYNC_OUT", "CMD_sync_out"),
    ],
)
def test_cmd_h_lts_and_flush(py: str, c: str) -> None:
    text = _CMD_H.read_text(encoding="latin-1")
    c_value = _parse_define(text, c)
    assert c_value is not None, f"could not parse #define {c} in cmd.h"
    assert getattr(cc, py) == c_value


# ----- cmd.h voice parameter indices --------------------------------------


_SPD_NAMES: tuple[str, ...] = (
    "SPD_SEX", "SPD_SM", "SPD_AS", "SPD_AP", "SPD_PR", "SPD_BR", "SPD_RI",
    "SPD_NF", "SPD_LA", "SPD_HS", "SPD_F4", "SPD_B4", "SPD_F5", "SPD_B5",
    "SPD_P4", "SPD_P5", "SPD_GF", "SPD_GH", "SPD_GV", "SPD_GN", "SPD_G1",
    "SPD_G2", "SPD_G3", "SPD_G4", "SPD_LO", "SPD_FT", "SPD_FL", "SPD_BF",
    "SPD_LX", "SPD_QU", "SPD_HR", "SPD_SR", "SPD_AGO", "SPD_AGVO", "SPD_AGUO",
    "SPD_UNVOW", "SPD_CHINK", "SPD_OQ", "SPD_OS", "SPD_NM", "SPDEF",
)  # fmt: skip


@pytest.mark.parametrize("name", _SPD_NAMES)
def test_cmd_h_voice_param_indices(name: str) -> None:
    """Each ``SPD_*`` voice-parameter index matches cmd.h."""
    text = _CMD_H.read_text(encoding="latin-1")
    c_value = _parse_define(text, name)
    assert c_value is not None, f"could not parse #define {name} in cmd.h"
    assert getattr(cc, name) == c_value


def test_spd_ft_and_fl_are_aliases() -> None:
    """``SPD_FT`` and ``SPD_FL`` are the same index (renamed in C)."""
    assert cc.SPD_FT == cc.SPD_FL == 25
