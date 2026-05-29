"""Verify the LTS spell-vs-say table and decision function.

Two layers:

1. **Static parity** — parse the 26-by-26 ``spell_it`` initialiser
   from ``l_us_spe.c`` at test time and assert every byte equals our
   Python ``bytes`` literal exactly.
2. **Functional behaviour** — exercise :func:`say_it` on edge cases
   that exercise each branch (length, all-vowels, pair-table hits).

Skips when the C source is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.lts import spell_or_say as sos
from dectalk.lts.char_features import is_vowel

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/lts/l_us_spe.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_spell_it() -> bytes:
    """Parse the C ``spell_it[26][26]`` initialiser body into a byte string."""
    text = _C_FILE.read_text(encoding="latin-1")
    m = re.search(
        r"const\s+unsigned\s+char\s+spell_it\[26\]\[26\]\s*=\s*\{(.*?)\};",
        text,
        re.DOTALL,
    )
    assert m is not None, "spell_it initialiser not found in l_us_spe.c"
    body = m.group(1)
    nums = [int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]+", body)]
    assert len(nums) == 26 * 26, f"expected 676 entries, got {len(nums)}"
    return bytes(nums)


# ----- Static parity ------------------------------------------------------


def test_spell_it_matches_c_source() -> None:
    """Every byte of ``spell_it`` matches the C ``spell_it[26][26]`` table."""
    c_bytes = _parse_spell_it()
    assert sos.spell_it == c_bytes


def test_spell_constants_match_ls_defs_h() -> None:
    """``SPELL_BEGIN`` / ``SPELL_END`` numeric values match ``ls_defs.h``."""
    ls_defs = (
        Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/lts/ls_defs.h"
    ).read_text(encoding="latin-1")
    m_end = re.search(r"#define\s+SPELL_END\s+(0x[0-9a-fA-F]+)", ls_defs)
    m_begin = re.search(r"#define\s+SPELL_BEGIN\s+(0x[0-9a-fA-F]+)", ls_defs)
    assert m_end is not None and m_begin is not None
    assert int(m_end.group(1), 16) == sos.SPELL_END
    assert int(m_begin.group(1), 16) == sos.SPELL_BEGIN


def test_spell_it_only_uses_two_bits() -> None:
    """Every entry is in {0, 1, 2, 3} — only ``SPELL_BEGIN | SPELL_END`` set."""
    valid = {0, 1, 2, 3}
    for i, b in enumerate(sos.spell_it):
        assert b in valid, f"spell_it[{i // 26}][{i % 26}]={b:#x} has stray bits"


# ----- say_it function behaviour ------------------------------------------


@pytest.mark.parametrize("word", ["", "A", "Z", "M"])
def test_size_le_1_always_speaks(word: str) -> None:
    """Words of length 0 or 1 are always spoken (C: ``size <= 1``)."""
    assert sos.say_it(word) is True


@pytest.mark.parametrize("word", ["AEIOU", "AEI", "IO", "OE", "EAU"])
def test_all_vowel_words_are_spelled(word: str) -> None:
    """All-vowel tokens are spelled, regardless of length (vowel check runs
    before the ``size > 4`` shortcut)."""
    assert sos.say_it(word) is False


@pytest.mark.parametrize("word", ["HOUSES", "LONGER", "ZEBRAS"])
def test_size_gt_4_with_consonant_speaks(word: str) -> None:
    """5+ letter tokens with any consonant are spoken."""
    assert sos.say_it(word) is True


@pytest.mark.parametrize(
    "word",
    [
        "hello",  # lowercase — non-A-Z
        "Bus",  # mixed case — non-A-Z
        "B-S",  # punctuation in middle
        "1A2",  # digit
        "ABC ",  # trailing space
    ],
)
def test_non_uppercase_az_is_spoken(word: str) -> None:
    """Any character outside A-Z forces 'speak' (early return in the C loop)."""
    assert sos.say_it(word) is True


def test_fbi_is_spelled() -> None:
    """``FBI``: ``spell_it[F][B]`` has SPELL_BEGIN → spelled."""
    assert sos.say_it("FBI") is False


def test_bus_is_spoken() -> None:
    """``BUS`` (and similar): a real word with no flagged pair → spoken."""
    assert sos.say_it("BUS") is True


def test_usa_is_spoken() -> None:
    """``USA``: neither US-start nor AS-end-reverse is flagged → spoken.

    Documents that the DECtalk table doesn't special-case ``USA`` —
    it's pronounced as a word ("oosa") rather than spelled ("U S A").
    """
    assert sos.say_it("USA") is True


def test_say_it_returns_bool() -> None:
    """``say_it`` returns a plain ``bool``, not ``int`` (matters for ``is``)."""
    result = sos.say_it("CAT")
    assert isinstance(result, bool)


# ----- Comparison against the C decision-table for every length-2 pair ---
# For each 2-letter all-caps token, the C function returns:
#   - TRUE  (speak) if spell_it[a][b] has neither SPELL_BEGIN nor SPELL_END
#                   set when used as the start-pair AND the end-pair-reversed
#   - FALSE (spell) otherwise
# We re-derive this from the C table at test time and assert our Python
# function matches for every (A..Z, A..Z) pair — 676 cases.


@pytest.mark.parametrize("a", list(range(26)))
@pytest.mark.parametrize("b", list(range(26)))
def test_all_two_letter_pairs_match_table_logic(a: int, b: int) -> None:
    """Every 2-letter A-Z combination matches the C-table-derived decision."""
    word = chr(ord("A") + a) + chr(ord("A") + b)
    # All-vowels short-circuits to spell. The C library treats Y as a vowel
    # (CFEAT_vowel bit set in ls_char_feat[0x59]), so we must use the same
    # definition rather than a fixed AEIOU set.
    if all(is_vowel(ord(ch)) for ch in word):
        assert sos.say_it(word) is False
        return
    # For 2-letter words, start-pair is (a, b) and end-pair-reverse is (b, a).
    start_flag = sos.spell_it[a * 26 + b] & sos.SPELL_BEGIN
    end_flag = sos.spell_it[b * 26 + a] & sos.SPELL_END
    if start_flag or end_flag:
        assert sos.say_it(word) is False, f"{word}: start={start_flag} end={end_flag}"
    else:
        assert sos.say_it(word) is True
