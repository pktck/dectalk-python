"""Verify FC_* form-class bit-flag constants from fc_def.tab."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dectalk.dic import form_class_bits as fcb

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/include/fc_def.tab")


def _parse_define(name: str) -> int | None:
    """Return the int value of a ``#define <name> 0x<hex>L``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    pattern = rf"^#define\s+{re.escape(name)}\s+0x([0-9A-Fa-f]+)L?\b"
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            return int(match.group(1), 16)
    return None


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
@pytest.mark.parametrize(
    ("py_attr", "c_name"),
    [
        ("FC_ADJ", "FC_ADJ"),
        ("FC_ADV", "FC_ADV"),
        ("FC_ART", "FC_ART"),
        ("FC_AUX", "FC_AUX"),
        ("FC_BE", "FC_BE"),
        ("FC_BEV", "FC_BEV"),
        ("FC_CONJ", "FC_CONJ"),
        ("FC_ED", "FC_ED"),
        ("FC_HAVE", "FC_HAVE"),
        ("FC_ING", "FC_ING"),
        ("FC_NOUN", "FC_NOUN"),
        ("FC_POS", "FC_POS"),
        ("FC_PREP", "FC_PREP"),
        ("FC_PRON", "FC_PRON"),
        ("FC_SMS", "FC_SMS"),
        ("FC_THAT", "FC_THAT"),
        ("FC_TO", "FC_TO"),
        ("FC_VERB", "FC_VERB"),
        ("FC_WHOW", "FC_WHOW"),
        ("FC_NEG", "FC_NEG"),
        ("FC_INTER", "FC_INTER"),
        ("FC_PART", "FC_PART"),
        ("FC_FUNC", "FC_FUNC"),
        ("FC_CONTR", "FC_CONTR"),
        ("FC_CHARACTER", "FC_CHARACTER"),
        ("FC_NAME", "FC_NAME"),
        ("FC_FC_MARKER", "FC_FC_MARKER"),
        ("FC_HOMOGRAPH", "FC_HOMOGRAPH"),
    ],
)
def test_fc_flag_matches_c(py_attr: str, c_name: str) -> None:
    """Each FC_* bit-flag matches fc_def.tab."""
    c_value = _parse_define(c_name)
    assert c_value is not None
    assert getattr(fcb, py_attr) == c_value


@pytest.mark.parametrize(
    ("py_attr", "c_name", "expected"),
    [
        ("FC_V_ADJ", "FC_V_ADJ", 0),
        ("FC_V_ADV", "FC_V_ADV", 1),
        ("FC_V_NOUN", "FC_V_NOUN", 10),
        ("FC_V_VERB", "FC_V_VERB", 17),
        ("FC_V_HOMOGRAPH", "FC_V_HOMOGRAPH", 31),
    ],
)
def test_fc_v_bit_positions(py_attr: str, c_name: str, expected: int) -> None:
    """FC_V_* bit positions match fc_def.tab."""
    if _C_HEADER.exists():
        text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    else:
        text = ""
    pattern = rf"^#define\s+{re.escape(c_name)}\s+(\d+)\b"
    found = None
    for line in text.splitlines():
        match = re.match(pattern, line)
        if match:
            found = int(match.group(1))
            break
    if found is not None:
        assert found == expected
    assert getattr(fcb, py_attr) == expected


def test_fc_v_positions_match_fc_flags() -> None:
    """Each FC_V_<NAME> is the log2 of the corresponding FC_<NAME> flag."""
    # Spot check a few — verify the bit-position vs mask relationship.
    assert (1 << fcb.FC_V_ADJ) == fcb.FC_ADJ
    assert (1 << fcb.FC_V_NOUN) == fcb.FC_NOUN
    assert (1 << fcb.FC_V_VERB) == fcb.FC_VERB
    assert (1 << fcb.FC_V_HOMOGRAPH) == fcb.FC_HOMOGRAPH


def test_fc_m_aliases() -> None:
    """``FC_M_*`` aliases share values with the corresponding ``FC_*`` flags."""
    assert fcb.FC_M_SUBCONJ == fcb.FC_SMS
    assert fcb.FC_M_WHO == fcb.FC_WHOW
    assert fcb.FC_M_CONT == fcb.FC_CONTR
    # Newly-added FC_M_<NAME> aliases of the matching FC_<NAME>.
    pairs = [
        (fcb.FC_M_ADJ, fcb.FC_ADJ),
        (fcb.FC_M_ADV, fcb.FC_ADV),
        (fcb.FC_M_ART, fcb.FC_ART),
        (fcb.FC_M_AUX, fcb.FC_AUX),
        (fcb.FC_M_BE, fcb.FC_BE),
        (fcb.FC_M_BEV, fcb.FC_BEV),
        (fcb.FC_M_CONJ, fcb.FC_CONJ),
        (fcb.FC_M_ED, fcb.FC_ED),
        (fcb.FC_M_HAVE, fcb.FC_HAVE),
        (fcb.FC_M_ING, fcb.FC_ING),
        (fcb.FC_M_NOUN, fcb.FC_NOUN),
        (fcb.FC_M_POS, fcb.FC_POS),
        (fcb.FC_M_PREP, fcb.FC_PREP),
        (fcb.FC_M_PRON, fcb.FC_PRON),
        (fcb.FC_M_THAT, fcb.FC_THAT),
        (fcb.FC_M_TO, fcb.FC_TO),
        (fcb.FC_M_VERB, fcb.FC_VERB),
        (fcb.FC_M_NEG, fcb.FC_NEG),
        (fcb.FC_M_INTER, fcb.FC_INTER),
        (fcb.FC_M_PART, fcb.FC_PART),
        (fcb.FC_M_FUNC, fcb.FC_FUNC),
        (fcb.FC_M_CHARACTER, fcb.FC_CHARACTER),
        (fcb.FC_M_FC_MARKER, fcb.FC_FC_MARKER),
        (fcb.FC_M_HOMOGRAPH, fcb.FC_HOMOGRAPH),
    ]
    for fc_m, fc in pairs:
        assert fc_m == fc


def test_fc_m_extras_are_distinct() -> None:
    """``FC_M_REF`` / ``FC_M_REFR`` / ``FC_M_CONTRACTION`` are new bits."""
    assert fcb.FC_M_REF == 0x00200000
    assert fcb.FC_M_REFR == 0x04000000
    assert fcb.FC_M_CONTRACTION == 0x40000000
    # Single-bit flags.
    for v in (fcb.FC_M_REF, fcb.FC_M_REFR, fcb.FC_M_CONTRACTION):
        assert v & (v - 1) == 0


def test_fc_flags_are_single_bit() -> None:
    """All FC_* flags are single-bit values (powers of two)."""
    flags = [
        fcb.FC_ADJ,
        fcb.FC_ADV,
        fcb.FC_ART,
        fcb.FC_AUX,
        fcb.FC_BE,
        fcb.FC_BEV,
        fcb.FC_CONJ,
        fcb.FC_ED,
        fcb.FC_HAVE,
        fcb.FC_ING,
        fcb.FC_NOUN,
        fcb.FC_POS,
        fcb.FC_PREP,
        fcb.FC_PRON,
        fcb.FC_SMS,
        fcb.FC_THAT,
        fcb.FC_TO,
        fcb.FC_VERB,
        fcb.FC_WHOW,
        fcb.FC_NEG,
        fcb.FC_INTER,
        fcb.FC_PART,
        fcb.FC_FUNC,
        fcb.FC_CONTR,
        fcb.FC_CHARACTER,
        fcb.FC_NAME,
        fcb.FC_FC_MARKER,
        fcb.FC_HOMOGRAPH,
    ]
    for f in flags:
        assert f > 0
        assert (f & (f - 1)) == 0, f"{f:#x} is not a single bit"
    assert len(set(flags)) == len(flags)
