"""Verify the LTS lsctype table matches l_us_con.c byte-for-byte.

Re-parses ``const U16 lsctype[]`` from the C source at test time
(handling the symbolic flag combinations like ``MIGHT+PR``) and
asserts every value matches our Python literal. Also covers the
``IS_*`` macro translations on ASCII letters.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.lts import char_class as cc

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_con.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_LSCT_NAMES = {
    "IGNORE": cc.IGNORE,
    "BACKUP": cc.BACKUP,
    "NEVER": cc.NEVER,
    "MIGHT": cc.MIGHT,
    "ALWAYS": cc.ALWAYS,
    "PHONEME": cc.PHONEME,
    "TYPE": cc.TYPE,
    "II": cc.II,
    "UU": cc.UU,
    "LS": cc.LS,
    "RS": cc.RS,
    "FB": cc.FB,
    "OO": cc.OO,
    "C": cc.C_BIT,
    "PR": cc.PR,
    "L": cc.L,
    "LC": cc.LC,
}


def _parse_lsctype() -> tuple[int, ...]:
    """Parse the C ``const U16 lsctype[]`` initialiser into a Python tuple."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(r"const\s+U16\s+lsctype\[\]\s*=\s*\{(.*?)\};", text, re.DOTALL)
    assert m is not None
    body = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    values: list[int] = []
    for raw in body.split(","):
        tok = raw.strip()
        if not tok:
            continue
        v = 0
        for piece in re.split(r"\s*[|+]\s*", tok):
            p = piece.strip()
            if p in _LSCT_NAMES:
                v |= _LSCT_NAMES[p]
            elif re.fullmatch(r"\d+", p):
                v |= int(p)
            elif re.fullmatch(r"0x[0-9a-fA-F]+", p):
                v |= int(p, 16)
            else:
                raise ValueError(f"unknown token in lsctype: {p!r}")
        values.append(v)
    return tuple(values)


# ----- Static parity ----------------------------------------------------


def test_lsctype_matches_c_source() -> None:
    """Every entry in lsctype matches the C ``const U16`` declaration."""
    expected = _parse_lsctype()
    assert cc.lsctype == expected


def test_lsctype_has_256_entries() -> None:
    """The C source declares one entry per byte value 0..255."""
    expected_count = 256
    assert len(cc.lsctype) == expected_count


def test_lsctype_entries_fit_in_u16() -> None:
    """No entry exceeds 16 bits — sanity for the ``U16`` declaration."""
    max_u16 = 0xFFFF
    for i, v in enumerate(cc.lsctype):
        assert 0 <= v <= max_u16, f"lsctype[{i}]={v:#x} overflows U16"


# ----- IS_UPPER / char_type macro translations ---------------------------


@pytest.mark.parametrize("ch", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
def test_is_upper_ascii(ch: str) -> None:
    """ASCII A..Z all set the ``UU`` bit."""
    assert cc.is_upper(ord(ch)) is True


@pytest.mark.parametrize("ch", "abcdefghijklmnopqrstuvwxyz0123456789")
def test_is_upper_false_for_lowercase_and_digits(ch: str) -> None:
    """``UU`` is only set on uppercase letters in the US table."""
    assert cc.is_upper(ord(ch)) is False


# Spot-check the TYPE field values for the canonical input categories,
# matching the C source's annotations in l_us_con.c. Note: period, comma
# and question mark are MIGHT (in-word if embedded) — supports things like
# "U.S.A.", "1,234", "what?" — not NEVER.

_TYPE_EXAMPLES: tuple[tuple[str, int], ...] = (
    (" ", cc.NEVER),     # space → NEVER (word boundary)
    ("\t", cc.NEVER),    # tab → NEVER
    ("A", cc.ALWAYS),    # ASCII letter
    ("a", cc.ALWAYS),
    ("5", cc.ALWAYS),    # ASCII digit
    ("'", cc.ALWAYS),    # apostrophe (also has LS+RS for stripping)
    ("!", cc.MIGHT),     # exclamation → in-word if embedded
    (",", cc.MIGHT),     # comma → in-word if embedded (numbers)
    (".", cc.MIGHT),     # period → in-word (U.S.A., decimals)
    ("?", cc.MIGHT),
    (":", cc.MIGHT),
    (";", cc.MIGHT),
)  # fmt: skip


@pytest.mark.parametrize(("ch", "expected"), _TYPE_EXAMPLES)
def test_char_type_examples(ch: str, expected: int) -> None:
    assert cc.char_type(ord(ch)) == expected


def test_l_and_lc_unused_for_us_ascii() -> None:
    """Document a quirk: the L and LC bits are never set for ASCII bytes.

    The C ``ISLOWER`` / ``ISALPHA`` macros that consult those bits are
    only referenced by Latin-American Spanish code (l_la_ru1.c). The
    US LTS classifies characters via the ``ls_char_feat`` table (see
    :mod:`dectalk.lts.char_features`) instead.
    """
    for c in range(0x80):
        assert not (cc.lsctype[c] & cc.L), f"unexpected L bit at byte {c:#x}"
        assert not (cc.lsctype[c] & cc.LC), f"unexpected LC bit at byte {c:#x}"


def test_letters_carry_pr_and_either_oo_or_c() -> None:
    """ASCII letters carry the ``PR`` (printing) bit.

    Vowels (AEIOU) carry ``OO``; most consonants carry ``C_BIT``; the
    letter Y is neither — the C source has the comment "``ALWAYS+PR``
    (-US_V, -C)" reflecting its dual vowel/consonant role.
    """
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz":
        v = cc.lsctype[ord(ch)]
        assert v & cc.PR, f"{ch!r}: missing PR bit"
        if ch.lower() in "aeiou":
            assert v & cc.OO, f"{ch!r}: vowel missing OO"
            assert not (v & cc.C_BIT)
        elif ch.lower() == "y":
            assert not (v & cc.OO)
            assert not (v & cc.C_BIT)
        else:
            assert v & cc.C_BIT, f"{ch!r}: consonant missing C bit"
            assert not (v & cc.OO)
