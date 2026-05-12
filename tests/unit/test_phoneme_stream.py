"""Verify the phoneme-stream parser matches the C ``usa_arpa[]`` table.

Two layers of tests:

1. Static parity: parse ``src/dapi/src/include/usa_phon.tab`` and assert
   that every 2-byte entry in ``usa_arpa[]`` is mapped in the Python
   ``SLOT_TO_CODE`` table to the matching numeric code. This is the
   ground-truth check — if these pass, the parser will reproduce the C
   library's intended decoding.

2. Live round-trip: when the source-built C library and the C-source
   patch (``0001-expose-convert-to-phonemes-on-linux``) are both
   available, render a few prompts through ``CAPI.convert_to_phonemes``
   and parse the output, asserting it decodes without error and
   produces sensible token sequences for known inputs.

The live tests skip cleanly when the patch hasn't been applied.
"""

from __future__ import annotations

import ctypes
import os
import re
from pathlib import Path

import pytest

from dectalk._capi import CAPI
from dectalk.include.phoneme_codes import (
    BLOCK_RULES,
    COMMA,
    DOUBLCONS,
    EXCLAIM,
    HAT_FALL,
    HAT_RF,
    HAT_RISE,
    HYPHEN,
    LINKRWORD,
    MBOUND,
    NEW_PARAGRAPH,
    PERIOD,
    PPSTART,
    QUEST,
    RELSTART,
    S1,
    S2,
    S3,
    SBOUND,
    SEMPH,
    SPECIALWORD,
    VPSTART,
    WBOUND,
    USPhoneme,
)
from dectalk.include.phoneme_stream import (
    SLOT_TO_CODE,
    PhonemeStreamParseError,
    PhonemeToken,
    format_phoneme_tokens,
    parse_phoneme_stream,
)

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_USA_PHON_TAB = _SRC_ROOT / "src/dapi/src/include/usa_phon.tab"

# Number of entries in usa_arpa[] expected to map to a non-filtered code.
# Codes filtered before output by ls_util.c:1666:
#   - 57..70 (unused extension slots TZ/CZ/LY/RE/X1-X9/Z1)
#   - 71..99 (NUL placeholders)
#   - 100 (BLOCK_RULES — control marker, not a real phoneme)
_FILTERED_CODES: frozenset[int] = frozenset({*range(57, 100), BLOCK_RULES})


# ----- Static parity against the C source ---------------------------------


def _parse_usa_arpa() -> dict[int, bytes]:
    """Parse ``const unsigned char usa_arpa[]`` into ``{code: 2-byte-slot}``."""
    if not _USA_PHON_TAB.is_file():
        pytest.skip(f"{_USA_PHON_TAB} not present; build dectalk-src first")
    text = _USA_PHON_TAB.read_text(encoding="latin-1")
    # Slice from the declaration to the closing brace.
    start = text.index("const unsigned char\tusa_arpa[] =")
    end = text.index("};", start)
    body = text[start:end]
    # Each entry is two single-quoted chars like ``'i', 'y',`` or
    # ``'\'',	' ',``. Also literal NULs like ``0, 0,``.
    entry_pattern = re.compile(
        r"""
        (?:'(?P<a1>(?:\\.|[^'\\]))'|(?P<n1>\d+))   # first byte
        \s*,\s*
        (?:'(?P<a2>(?:\\.|[^'\\]))'|(?P<n2>\d+))   # second byte
        \s*,?
        """,
        re.VERBOSE,
    )
    entries: dict[int, bytes] = {}
    for index, match in enumerate(entry_pattern.finditer(body)):
        b1 = _resolve_byte(match.group("a1"), match.group("n1"))
        b2 = _resolve_byte(match.group("a2"), match.group("n2"))
        entries[index] = bytes((b1, b2))
    return entries


def _resolve_byte(ascii_char: str | None, numeric: str | None) -> int:
    """Return the byte value from either a C char literal or a decimal int."""
    if ascii_char is not None:
        if ascii_char.startswith("\\"):
            escapes = {"\\'": ord("'"), '\\"': ord('"'), "\\\\": ord("\\"), "\\0": 0}
            return escapes[ascii_char]
        return ord(ascii_char)
    assert numeric is not None
    return int(numeric)


@pytest.fixture(scope="module")
def usa_arpa() -> dict[int, bytes]:
    """Map of phoneme-code → 2-byte ASCII slot parsed from the C header."""
    return _parse_usa_arpa()


def test_usa_arpa_table_size(usa_arpa: dict[int, bytes]) -> None:
    """The C ``usa_arpa[]`` covers codes 0..122 (PHO_SYM_TOT)."""
    assert max(usa_arpa) == 122
    assert min(usa_arpa) == 0


@pytest.mark.parametrize(
    "code",
    sorted(c.value for c in USPhoneme if c.value not in _FILTERED_CODES),
)
def test_allophone_slot_matches(code: int, usa_arpa: dict[int, bytes]) -> None:
    """Each non-filtered US allophone code's slot is in our Python map."""
    c_slot = usa_arpa[code]
    assert c_slot in SLOT_TO_CODE, (
        f"code {code} ({USPhoneme(code).name}) C slot {c_slot!r} missing from SLOT_TO_CODE"
    )
    assert SLOT_TO_CODE[c_slot] == code, (
        f"code {code} ({USPhoneme(code).name}): C slot {c_slot!r} maps "
        f"to {SLOT_TO_CODE[c_slot]} in Python (expected {code})"
    )


@pytest.mark.parametrize(
    "code",
    [
        S3,
        S2,
        S1,
        SEMPH,
        HAT_RISE,
        HAT_FALL,
        HAT_RF,
        SBOUND,
        MBOUND,
        HYPHEN,
        WBOUND,
        PPSTART,
        VPSTART,
        RELSTART,
        COMMA,
        PERIOD,
        QUEST,
        EXCLAIM,
        NEW_PARAGRAPH,
        SPECIALWORD,
        LINKRWORD,
        DOUBLCONS,
    ],
)
def test_control_code_slot_matches(code: int, usa_arpa: dict[int, bytes]) -> None:
    """Each stress / boundary control code's slot is in our Python map."""
    c_slot = usa_arpa[code]
    assert c_slot in SLOT_TO_CODE
    assert SLOT_TO_CODE[c_slot] == code


def test_filtered_codes_not_in_python_map(usa_arpa: dict[int, bytes]) -> None:
    """Codes filtered by ls_util.c must not be in our map either.

    Including them would let stale C output (or a future C change that
    stops filtering) silently decode to a phoneme — better to fail loud.
    """
    for filtered in _FILTERED_CODES:
        if filtered not in usa_arpa:
            continue
        c_slot = usa_arpa[filtered]
        # NUL-filled placeholders for codes 71..99 are not in our map
        # by design (they have no meaning).
        if c_slot == b"\x00\x00":
            continue
        # Codes 57..70 (TZ, CZ, LY, RE, X1..X9, Z1) and 100 (BLOCK_RULES)
        # have ASCII slots in the C table, but ls_util.c filters them out
        # before they hit the output buffer. We deliberately omit them
        # from the parser map so any stray byte trips the parser.
        assert c_slot not in SLOT_TO_CODE, (
            f"filtered code {filtered} has slot {c_slot!r} but it's still "
            f"present in SLOT_TO_CODE — that would mask a real bug"
        )


# ----- Parser unit tests --------------------------------------------------


def test_parse_hello_world_known_bytes() -> None:
    """The exact byte string for 'hello world' decodes as expected."""
    raw = b"hxaxll' ow  w ' rrlld "
    tokens = parse_phoneme_stream(raw)
    expected = [
        PhonemeToken(int(USPhoneme.HX), "HX"),
        PhonemeToken(int(USPhoneme.AX), "AX"),
        PhonemeToken(int(USPhoneme.LL), "LL"),
        PhonemeToken(S1, "S1"),
        PhonemeToken(int(USPhoneme.OW), "OW"),
        PhonemeToken(WBOUND, "WBOUND"),
        PhonemeToken(int(USPhoneme.W), "W"),
        PhonemeToken(S1, "S1"),
        PhonemeToken(int(USPhoneme.RR), "RR"),
        PhonemeToken(int(USPhoneme.LL), "LL"),
        PhonemeToken(int(USPhoneme.D), "D"),
    ]
    assert tokens == expected


def test_format_round_trip() -> None:
    """``format_phoneme_tokens`` produces a human-readable string."""
    tokens = parse_phoneme_stream(b"hxaxll' ow  w ' rrlld ")
    assert format_phoneme_tokens(tokens) == "HX AX LL S1 OW WBOUND W S1 RR LL D"


def test_parse_empty() -> None:
    """An empty buffer parses to an empty token list."""
    assert parse_phoneme_stream(b"") == []


def test_odd_length_raises() -> None:
    with pytest.raises(PhonemeStreamParseError, match="not a multiple"):
        parse_phoneme_stream(b"hxa")


def test_unrecognised_slot_raises() -> None:
    with pytest.raises(PhonemeStreamParseError, match="unrecognised"):
        # "@@" is not in the table and would never appear in real output.
        parse_phoneme_stream(b"hx@@")


# ----- Live round-trip via the C library ----------------------------------


def _have_libtts_with_convert() -> bool:
    """True iff libtts_us.so exists AND exports ConvertToPhonemes."""
    candidates = sorted(_SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    if not candidates:
        return False
    try:
        lib = ctypes.CDLL(str(candidates[-1]))
        getattr(lib, "TextToSpeechConvertToPhonemes")  # noqa: B009
    except (OSError, AttributeError):
        return False
    return True


_LIVE_REASON = (
    "libtts_us.so or TextToSpeechConvertToPhonemes missing — "
    "run `uv run python scripts/apply_c_patches.py`"
)


@pytest.fixture(scope="module")
def capi() -> CAPI:
    if not _have_libtts_with_convert():
        pytest.skip(_LIVE_REASON)
    return CAPI()


@pytest.mark.parametrize(
    "text",
    [
        "hello world",
        "the quick brown fox",
        "one two three four five",
        "supercalifragilisticexpialidocious",
        "this is a test, with a comma, and a period.",
    ],
)
def test_live_round_trip_parses(text: str, capi: CAPI) -> None:
    """The C library's actual output for these prompts decodes cleanly."""
    raw = capi.convert_to_phonemes(text)
    tokens = parse_phoneme_stream(raw)
    assert len(tokens) > 0


def test_live_hello_world_token_sequence(capi: CAPI) -> None:
    """``hello world`` produces the documented token sequence."""
    tokens = parse_phoneme_stream(capi.convert_to_phonemes("hello world"))
    names = [t.name for t in tokens]
    # HX AX LL stressed OW, word boundary, W stressed RR LL D.
    assert names == ["HX", "AX", "LL", "S1", "OW", "WBOUND", "W", "S1", "RR", "LL", "D"]


def test_live_comma_appears_in_output(capi: CAPI) -> None:
    """Text with a comma yields a COMMA token in the parsed stream."""
    tokens = parse_phoneme_stream(capi.convert_to_phonemes("hello, world"))
    assert any(t.code == COMMA for t in tokens), [t.name for t in tokens]


def test_live_period_appears_in_output(capi: CAPI) -> None:
    """Text ending in a period yields a PERIOD token."""
    tokens = parse_phoneme_stream(capi.convert_to_phonemes("hello world."))
    assert any(t.code == PERIOD for t in tokens), [t.name for t in tokens]
