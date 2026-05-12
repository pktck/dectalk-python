"""Verify the function-verbs lookup matches ls_task.c.

Re-parses the ``const verb_words_t verbs[6]`` ENGLISH_US branch and
asserts each entry's word + phoneme string + feature word match
our Python literal.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import S1, S2, USPhoneme
from dectalk.lts import verbs_table as vt

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_FILE = _SRC_ROOT / "src/dapi/src/lts/ls_task.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


_NAMES: dict[str, int] = {
    **{f"US_{m.name}": int(m) for m in USPhoneme},
    "US_OR": int(USPhoneme.OR_),
    "S1": S1,
    "S2": S2,
    "SIL": 0,
}


def _eval(expr: str) -> int:
    """Resolve a single C field expression (e.g. ``US_AA`` or ``0x00820020``)."""
    expr = expr.strip()
    if re.fullmatch(r"0x[0-9a-fA-F]+", expr):
        return int(expr, 16)
    if expr in _NAMES:
        return _NAMES[expr]
    if re.fullmatch(r"\d+", expr):
        return int(expr)
    raise ValueError(f"unknown token: {expr!r}")


def _parse_verbs_us() -> tuple[vt.VerbWord, ...]:
    """Parse the ``#ifdef ENGLISH_US`` branch of the ``verbs[]`` array."""
    text = _C_FILE.read_text(encoding="latin-1")
    # Slice between ENGLISH_US and the next #endif inside the verbs[] block.
    m = re.search(r"const\s+verb_words_t\s+verbs\[6\]\s*=\s*\{(.+?)\};", text, re.DOTALL)
    assert m is not None
    full_body = m.group(1)
    us_match = re.search(r"#ifdef\s+ENGLISH_US\s*\n(.+?)\n\s*#endif", full_body, re.DOTALL)
    assert us_match is not None
    block = us_match.group(1)
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL)
    block = re.sub(r"//.*", "", block)
    out: list[vt.VerbWord] = []
    # Each record: ``{{"word"}, {ph, ph, ph, ph, ph}, 0xfeats},``
    for rec in re.finditer(
        r'\{\s*\{\s*"(?P<word>[^"]+)"\s*\}\s*,\s*\{(?P<ph>[^}]+)\}\s*,\s*(?P<feat>[^},]+)\s*\}',
        block,
    ):
        word = rec.group("word")
        phones_str = rec.group("ph")
        feat_str = rec.group("feat").strip()
        phones = tuple(_eval(p) for p in phones_str.split(","))
        assert len(phones) == 5
        out.append(
            vt.VerbWord(
                word=word,
                phones=(phones[0], phones[1], phones[2], phones[3], phones[4]),
                features=_eval(feat_str),
            )
        )
    return tuple(out)


def test_verbs_matches_c_source() -> None:
    """All six verb records match the C source initialiser."""
    expected = _parse_verbs_us()
    assert vt.verbs == expected


def test_verbs_count_is_six() -> None:
    """The C struct's array length is fixed at 6."""
    expected_count = 6
    assert len(vt.verbs) == expected_count


def test_verbs_word_set_is_function_verbs() -> None:
    """The list covers the six function verbs are/had/is/was/were/will."""
    expected = {"are", "had", "is", "was", "were", "will"}
    assert {v.word for v in vt.verbs} == expected


def test_verbs_features_share_class_high_byte() -> None:
    """All six entries share the upper-half feature word 0x00820000."""
    high_word_mask = 0xFFFF0000
    for v in vt.verbs:
        assert v.features & high_word_mask == 0x00820000


def test_verb_phones_are_padded_to_five() -> None:
    """Each phone tuple has exactly 5 ints (SIL-padded)."""
    expected_length = 5
    for v in vt.verbs:
        assert len(v.phones) == expected_length
