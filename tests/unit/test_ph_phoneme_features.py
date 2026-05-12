"""Verify ph_defs.h per-phoneme feature bits."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.ph import phoneme_features as pf

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_defs.h")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> <int>``. C uses octal."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    octal = rf"^#define\s+{re.escape(name)}\s+0(\d+)\b"
    hexp = rf"^#define\s+{re.escape(name)}\s+0x([0-9A-Fa-f]+)\b"
    dec = rf"^#define\s+{re.escape(name)}\s+(\d+)\b"
    for line in text.splitlines():
        m = re.match(octal, line)
        if m:
            return int(m.group(1), 8)
        m = re.match(hexp, line)
        if m:
            return int(m.group(1), 16)
        m = re.match(dec, line)
        if m:
            return int(m.group(1))
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name"),
    [
        ("FSYLL", "FSYLL"),
        ("FVOICD", "FVOICD"),
        ("FVOWEL", "FVOWEL"),
        ("FSON1", "FSON1"),
        ("FSONOR", "FSONOR"),
        ("FOBST", "FOBST"),
        ("FPLOSV", "FPLOSV"),
        ("FNASAL", "FNASAL"),
        ("FCONSON", "FCONSON"),
        ("FSONCON", "FSONCON"),
        ("FSON2", "FSON2"),
        ("FBURST", "FBURST"),
        ("FSTMARK", "FSTMARK"),
        ("FSTOP", "FSTOP"),
        ("FSEMIV", "FSEMIV"),
        ("FDIPTH", "FDIPTH"),
        ("FLABIAL", "FLABIAL"),
        ("FDENTAL", "FDENTAL"),
        ("FPALATL", "FPALATL"),
        ("FALVEL", "FALVEL"),
        ("FVELAR", "FVELAR"),
        ("FGLOTTAL", "FGLOTTAL"),
        ("F2BACKI", "F2BACKI"),
        ("F2BACKF", "F2BACKF"),
        ("FWBEND", "FWBEND"),
        ("FHAT_ROOF", "FHAT_ROOF"),
        ("MASKFRONT", "MASKFRONT"),
        ("WORDFEAT", "WORDFEAT"),
        ("F_TIME_RISE", "F_TIME_RISE"),
        ("F_NOUN", "F_NOUN"),
        ("F_ADJ", "F_ADJ"),
        ("F_VERB", "F_VERB"),
        ("F_FUNC", "F_FUNC"),
        ("F_IRESET", "F_IRESET"),
        ("FMAXIMUM", "FMAXIMUM"),
    ],
)
def test_feature_bit_matches_c(py_attr: str, c_name: str) -> None:
    """Each feature bit matches ph_defs.h."""
    c_value = _parse_define(c_name)
    assert c_value is not None, f"{c_name} not in ph_defs.h"
    assert getattr(pf, py_attr) == c_value


def test_manner_bits_form_powers_of_two() -> None:
    """The manner-of-articulation bits are single-bit flags 1..0o100000."""
    manner = [
        pf.FSYLL,
        pf.FVOICD,
        pf.FVOWEL,
        pf.FSON1,
        pf.FSONOR,
        pf.FOBST,
        pf.FPLOSV,
        pf.FNASAL,
        pf.FCONSON,
        pf.FSONCON,
        pf.FSON2,
        pf.FBURST,
        pf.FSTMARK,
        pf.FSTOP,
        pf.FSEMIV,
        pf.FDIPTH,
    ]
    for v in manner:
        assert v > 0
        assert v & (v - 1) == 0, f"{v:#o} is not a single-bit flag"
    # All distinct.
    assert len(set(manner)) == len(manner)


def test_place_bits_collide_with_manner_intentional() -> None:
    """``FLABIAL == FSYLL == 1`` and similar — by design.

    The C source uses two reads of the same bit positions through
    different table fields. Verifies the Python port preserves the
    numerical overlap.
    """
    assert pf.FLABIAL == pf.FSYLL == 0o1
    assert pf.FDENTAL == pf.FVOICD == 0o2
    assert pf.FPALATL == pf.FVOWEL == 0o4
    assert pf.FALVEL == pf.FSON1 == 0o10
    assert pf.FVELAR == pf.FSONOR == 0o20
    assert pf.FGLOTTAL == pf.FOBST == 0o40


def test_bladeaffected_composite() -> None:
    """``BLADEAFFECTED`` is the OR of FDENTAL / FPALATL / FALVEL."""
    assert pf.BLADEAFFECTED == (pf.FDENTAL | pf.FPALATL | pf.FALVEL)


def test_pos_tags_distinct() -> None:
    """The four part-of-speech tags are pairwise distinct."""
    pos = {pf.F_NOUN, pf.F_ADJ, pf.F_VERB, pf.F_FUNC}
    assert len(pos) == 4


def test_wordfeat_mask_covers_high_16() -> None:
    """``WORDFEAT`` masks the upper 16 bits of a 32-bit ``sentstruc`` entry."""
    assert pf.WORDFEAT == 0xFFFF0000
