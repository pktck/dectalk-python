"""Verify the LTS math-mode tables match ``l_us_ma1.c`` byte-for-byte.

Two layers:

1. **Static parity** — parse the C source's ``math_table`` and
   ``ascky_tab`` initialiser bodies at test time, and assert each
   Python entry equals the C entry exactly.
2. **Functional behaviour** — exercise :func:`do_math` and
   :func:`flush_ascky` on known inputs.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import (
    BLOCK_RULES,
    COMMA,
    HYPHEN,
    MBOUND,
    PFUSA,
    PPSTART,
    S1,
    S2,
    SBOUND,
    SEMPH,
    VPSTART,
    WBOUND,
    USPhoneme,
)
from dectalk.lts import math_mode as mm

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_ma1.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# A symbol table mapping every name the C source uses inside
# (PFUSA << PSFONT) + <name> to its numeric value.
_NAME_TO_CODE: dict[str, int] = {
    **{f"US_{m.name}": int(m) for m in USPhoneme},
    "US_OR": int(USPhoneme.OR_),
    "BLOCK_RULES": BLOCK_RULES,
    "S1": S1,
    "S2": S2,
    "SEMPH": SEMPH,
    "SBOUND": SBOUND,
    "MBOUND": MBOUND,
    "HYPHEN": HYPHEN,
    "WBOUND": WBOUND,
    "PPSTART": PPSTART,
    "VPSTART": VPSTART,
    "COMMA": COMMA,
    "PFUSA": PFUSA,
    "PSFONT": PSFONT,
}


def _parse_char_literal(s: str) -> int:
    """Convert a C char literal (``'a'``, ``'\\''``, ``'\\\\'``, ``'\\t'``) to its byte."""
    s = s.strip()
    if not (s.startswith("'") and s.endswith("'")):
        raise ValueError(f"not a char literal: {s!r}")
    inner = s[1:-1]
    esc = {"\\'": 0x27, "\\\\": 0x5C, "\\0": 0, "\\n": 10, "\\t": 9, "\\r": 13, '\\"': 0x22}
    return esc.get(inner, ord(inner[-1]))


def _parse_math_table() -> list[tuple[int, bytes]]:
    """Parse ``const struct math_symbols math_table[] = { ... };``."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"const\s+struct\s+math_symbols\s+math_table\[\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert m is not None, "math_table not found"
    body = m.group(1)
    # Each entry: {'<char>', "<ascky>"} or {0, 0}
    entries: list[tuple[int, bytes]] = []
    for em in re.finditer(r"\{\s*(?:('[^']*'|0))\s*,\s*((?:\"[^\"]*\")|0)\s*\}", body):
        sym, pron = em.group(1), em.group(2)
        if sym == "0":
            break  # sentinel
        c = _parse_char_literal(sym)
        # Unwrap the pronunciation string literal: "pl'^s" -> b"pl'^s"
        assert pron.startswith('"') and pron.endswith('"')
        entries.append((c, pron[1:-1].encode("latin-1")))
    return entries


def _parse_ascky_tab() -> list[tuple[int, int]]:
    """Parse ``const ASCKY_TAB ascky_tab[] = { ... };``."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"const\s+ASCKY_TAB\s+ascky_tab\[\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert m is not None, "ascky_tab not found"
    body = m.group(1)
    # Each entry: {'<char>', (PFUSA <<PSFONT)+<NAME>}
    entries: list[tuple[int, int]] = []
    for em in re.finditer(
        r"\{\s*('[^']*'|'\\.')\s*,\s*\(\s*PFUSA\s*<<\s*PSFONT\s*\)\s*\+\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}",
        body,
    ):
        sym, name = em.group(1), em.group(2)
        c = _parse_char_literal(sym)
        if name not in _NAME_TO_CODE:
            raise ValueError(f"unknown phoneme name in ascky_tab: {name!r}")
        composite = (PFUSA << PSFONT) | _NAME_TO_CODE[name]
        entries.append((c, composite))
    return entries


# ----- Static parity ----------------------------------------------------


def test_math_table_matches_c() -> None:
    """Each entry in ``math_table`` matches the C source exactly."""
    c_entries = _parse_math_table()
    assert len(c_entries) == len(mm.math_table), (
        f"math_table size mismatch: C={len(c_entries)} Py={len(mm.math_table)}"
    )
    for (c_sym, c_pron), (py_sym, py_pron) in zip(c_entries, mm.math_table, strict=True):
        assert c_sym == py_sym, f"symbol differs: C={c_sym:#x} Py={py_sym:#x}"
        assert c_pron == py_pron, f"pron for {chr(c_sym)!r} differs: C={c_pron!r} Py={py_pron!r}"


def test_ascky_tab_matches_c() -> None:
    """Each entry in ``ascky_tab`` matches the C source exactly."""
    c_entries = _parse_ascky_tab()
    assert len(c_entries) == len(mm.ascky_tab), (
        f"ascky_tab size mismatch: C={len(c_entries)} Py={len(mm.ascky_tab)}"
    )
    for (c_sym, c_code), (py_sym, py_code) in zip(c_entries, mm.ascky_tab, strict=True):
        assert c_sym == py_sym, f"ascky sym differs: C={c_sym:#x} Py={py_sym:#x}"
        assert c_code == py_code, (
            f"ascky code for {chr(c_sym)!r} differs: C={c_code:#x} Py={py_code:#x}"
        )


# ----- Functional behaviour --------------------------------------------


def test_do_math_plus_yields_plus_phonemes() -> None:
    """``do_math('+')`` expands to "plus" = P L (S1) AH S."""
    codes = mm.do_math(ord("+"))
    # ASCKY "pl'^s" -> [P, L (i.e. LL), S1, AH, S]
    assert codes == [
        (PFUSA << PSFONT) | int(USPhoneme.P),
        (PFUSA << PSFONT) | int(USPhoneme.LL),
        (PFUSA << PSFONT) | S1,
        (PFUSA << PSFONT) | int(USPhoneme.AH),
        (PFUSA << PSFONT) | int(USPhoneme.S),
    ]


def test_do_math_equals_yields_equals_phonemes() -> None:
    """``do_math('=')`` expands to "equals" = (S1) IY K W L Z."""
    codes = mm.do_math(ord("="))
    # ASCKY "'ikwLz" -> [S1, IY, K, W, EL, Z]
    assert codes == [
        (PFUSA << PSFONT) | S1,
        (PFUSA << PSFONT) | int(USPhoneme.IY),
        (PFUSA << PSFONT) | int(USPhoneme.K),
        (PFUSA << PSFONT) | int(USPhoneme.W),
        (PFUSA << PSFONT) | int(USPhoneme.EL),
        (PFUSA << PSFONT) | int(USPhoneme.Z),
    ]


def test_do_math_non_symbol_returns_empty() -> None:
    """Non-math characters return an empty list (the C version returns false)."""
    assert mm.do_math(ord("a")) == []
    assert mm.do_math(ord("Z")) == []
    assert mm.do_math(ord(" ")) == []


@pytest.mark.parametrize("sym", ["+", "-", "*", "/", "^", "<", ">", "=", "%", "."])
def test_every_math_symbol_yields_phonemes(sym: str) -> None:
    """Every entry in math_table produces a non-empty phoneme list."""
    assert mm.do_math(ord(sym)) != [], f"math symbol {sym!r} produced no phonemes"


def test_flush_ascky_word_boundary() -> None:
    """ASCKY space byte produces a WBOUND token."""
    codes = mm.flush_ascky(b" ")
    assert codes == [(PFUSA << PSFONT) | WBOUND]


def test_flush_ascky_skips_unknown_bytes() -> None:
    """Bytes not in ascky_tab are silently skipped (matches C behaviour)."""
    # 0xff is not in the table.
    codes = mm.flush_ascky(b"\xff")
    assert codes == []


def test_flush_ascky_empty_input() -> None:
    assert mm.flush_ascky(b"") == []
