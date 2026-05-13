"""C-source parity test for ``par_dict_udlook`` against par_dict.c.

Re-parses the function body from
``src/dapi/src/cmd/par_dict.c`` and asserts:

- The function signature matches the C declaration.
- The entry pointer is obtained via
  ``((struct dic_entry *)&(UDICT_DATA[UDICT_INDEX[uindex]]))->text``.
- The loop body matches the canonical
  ``if (word[i] == ent[i]) continue;`` /
  ``if (word[i] == '\0') return LOOK_LOWER;`` /
  ``IS_LOWER`` / ``par_dict_where_to_ulook`` sequence.

Then exercises the Python port against the canonical algorithm
with a synthetic ``UDICT_DATA`` / ``UDICT_INDEX`` table built
from a small handful of entries.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.par_dict_udlook import (
    DIC_ENTRY_TEXT_OFFSET,
    LOOK_HIGHER,
    LOOK_LOWER,
    par_dict_udlook,
)
from dectalk.cmd.par_dict_where_to_ulook import par_dict_where_to_ulook
from dectalk.lts.dict_codes import HIT

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/par_dict.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_par_dict_c() -> str:
    """Read par_dict.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_udlook_body() -> str:
    """Return the body of par_dict_udlook from the C source."""
    text = _read_par_dict_c()
    match = re.search(
        r"int\s+par_dict_udlook\s*\([^)]*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "par_dict_udlook body not found in par_dict.c"
    return match.group(1)


def test_signature_matches_c_source() -> None:
    """The C declaration uses (UDICT_ENTRY, UDICT_INDEX, UDICT_DATA, uindex, word)."""
    text = _read_par_dict_c()
    # Match the function definition (multiline-tolerant).
    match = re.search(
        r"int\s+par_dict_udlook\s*\(\s*long\s+UDICT_ENTRY\s*,\s*"
        r"S32\s*\*\s*UDICT_INDEX\s*,\s*"
        r"unsigned\s+char\s*\*\s*UDICT_DATA\s*,\s*"
        r"long\s+uindex\s*,\s*"
        r"unsigned\s+char\s*\*\s*word\s*\)",
        text,
    )
    assert match is not None, "par_dict_udlook signature did not match"


def test_entry_pointer_walks_through_udict_index() -> None:
    """``ent = ((struct dic_entry *)&(UDICT_DATA[UDICT_INDEX[uindex]]))->text``."""
    body = _extract_udlook_body()
    assert re.search(
        r"ent\s*=\s*\(\s*\(\s*struct\s+dic_entry\s*\*\s*\)\s*"
        r"&\s*\(\s*UDICT_DATA\s*\[\s*UDICT_INDEX\s*\[\s*uindex\s*\]\s*\]\s*\)\s*\)\s*->\s*text",
        body,
    )


def test_loop_compares_byte_by_byte_until_nul() -> None:
    """Main loop walks ``ent[i]`` until the terminating NUL."""
    body = _extract_udlook_body()
    assert re.search(r"for\s*\(\s*i\s*=\s*0\s*;\s*ent\s*\[\s*i\s*\]\s*!=\s*'\\0'", body)


def test_c_word_shorter_returns_look_lower() -> None:
    """``if (word[i] == '\\0') return LOOK_LOWER;`` short-circuits."""
    body = _extract_udlook_body()
    assert re.search(
        r"if\s*\(\s*word\s*\[\s*i\s*\]\s*==\s*'\\0'\s*\)\s*\{?\s*return\s*\(?\s*LOOK_LOWER",
        body,
    )


def test_is_lower_short_circuit_uses_par_upper() -> None:
    """The lowercase-entry / uppercase-word short-circuit is present."""
    body = _extract_udlook_body()
    assert re.search(
        r"IS_LOWER\s*\(\s*ent\s*\[\s*i\s*\]\s*\)\s*&&\s*"
        r"\(\s*word\s*\[\s*i\s*\]\s*==\s*par_upper\s*\[\s*ent\s*\[\s*i\s*\]\s*\]\s*\)",
        body,
    )


def test_falls_through_to_where_to_ulook_on_mismatch() -> None:
    """Mid-string mismatch defers to ``par_dict_where_to_ulook``."""
    body = _extract_udlook_body()
    assert re.search(
        r"return\s*\(?\s*par_dict_where_to_ulook\s*\(\s*ent\s*,\s*word\s*\)",
        body,
    )


def test_full_match_returns_hit() -> None:
    """``if (word[i] == '\\0') return HIT;`` after the loop."""
    body = _extract_udlook_body()
    # The post-loop NUL-of-word check returns HIT.
    assert re.search(
        r"if\s*\(\s*word\s*\[\s*i\s*\]\s*==\s*'\\0'\s*\)\s*\{?\s*return\s*\(?\s*HIT",
        body,
    )


def test_default_returns_look_higher() -> None:
    """Fall-through returns LOOK_HIGHER (word longer than entry)."""
    body = _extract_udlook_body()
    # The function returns LOOK_HIGHER as the final-fallthrough exit path.
    assert re.search(r"return\s*\(?\s*LOOK_HIGHER\s*\)?\s*;", body)


# ---- DIC_ENTRY_TEXT_OFFSET matches C struct layout ------------------------


def test_dic_entry_text_offset_matches_c_struct() -> None:
    """The C struct on Linux is ``U32 fc; unsigned char text[128];`` -> text at +4."""
    text = _read_par_dict_c()
    # Pull the active struct definition (non-CHEESY_DICT_COMPRESSION branch).
    struct_match = re.search(
        r"struct\s+dic_entry\s*\{(.+?)\}\s*;",
        text,
        re.DOTALL,
    )
    assert struct_match is not None
    body = struct_match.group(1)
    # The non-CHEESY branch (active on Linux) uses U32 fc.
    assert "U32" in body and "fc" in body, "expected U32 fc field in dic_entry"
    assert "text[128]" in body, "expected text[128] field in dic_entry"
    # sizeof(U32) == 4, no padding before unsigned char[128].
    assert DIC_ENTRY_TEXT_OFFSET == 4


# ---- Algorithmic parity: exercise the Python port against the spec --------


def _build_udict(entries: list[bytes]) -> tuple[list[int], bytes]:
    """Build a synthetic ``(UDICT_INDEX, UDICT_DATA)`` pair.

    Each entry is laid out as 4 bytes of ``fc`` (zero-filled) followed
    by 128 bytes of NUL-padded text -- matching the C struct.
    """
    index: list[int] = []
    data = bytearray()
    for ent in entries:
        index.append(len(data))
        data.extend(b"\x00\x00\x00\x00")  # fc = 0
        padded = ent + b"\x00" * (128 - len(ent))
        data.extend(padded[:128])
    return index, bytes(data)


def test_exact_match_returns_hit() -> None:
    """Equal strings yield HIT."""
    idx, data = _build_udict([b"hello"])
    assert par_dict_udlook(1, idx, data, 0, b"hello") == HIT


def test_uppercase_word_matches_lowercase_entry() -> None:
    """An uppercase word matches a lowercase entry (IS_LOWER short-circuit)."""
    idx, data = _build_udict([b"hello"])
    assert par_dict_udlook(1, idx, data, 0, b"HELLO") == HIT


def test_lowercase_word_does_not_match_uppercase_entry() -> None:
    """Uppercase entry letters require exact-case matching.

    Since IS_LOWER(ent[i]) is False for upper-case entry, the
    short-circuit doesn't fire and the function falls through to
    par_dict_where_to_ulook. With an exact case-folded match,
    where_to_ulook returns LOOK_LOWER.
    """
    idx, data = _build_udict([b"HELLO"])
    assert par_dict_udlook(1, idx, data, 0, b"hello") == LOOK_LOWER


def test_word_shorter_returns_look_lower() -> None:
    """Word ends before entry -> LOOK_LOWER."""
    idx, data = _build_udict([b"hello"])
    assert par_dict_udlook(1, idx, data, 0, b"hel") == LOOK_LOWER


def test_word_longer_returns_look_higher() -> None:
    """Word continues past entry -> LOOK_HIGHER."""
    idx, data = _build_udict([b"hel"])
    assert par_dict_udlook(1, idx, data, 0, b"hello") == LOOK_HIGHER


def test_mid_string_mismatch_falls_through_to_where_to_ulook() -> None:
    """Mid-string mismatch is delegated to par_dict_where_to_ulook."""
    idx, data = _build_udict([b"banana"])
    result = par_dict_udlook(1, idx, data, 0, b"apple")
    expected = par_dict_where_to_ulook(b"banana", b"apple")
    assert result == expected
    assert result == LOOK_LOWER


def test_word_after_entry_alphabetically() -> None:
    """Word > entry on a mid-string mismatch -> LOOK_HIGHER."""
    idx, data = _build_udict([b"apple"])
    result = par_dict_udlook(1, idx, data, 0, b"banana")
    assert result == LOOK_HIGHER


def test_uindex_picks_the_right_entry() -> None:
    """The ``uindex`` parameter selects which entry to compare against."""
    idx, data = _build_udict([b"apple", b"banana", b"cherry"])
    assert par_dict_udlook(3, idx, data, 0, b"apple") == HIT
    assert par_dict_udlook(3, idx, data, 1, b"banana") == HIT
    assert par_dict_udlook(3, idx, data, 2, b"cherry") == HIT
    # Word > all three: each comparison gives LOOK_HIGHER.
    assert par_dict_udlook(3, idx, data, 0, b"zebra") == LOOK_HIGHER


def test_constants_match_c_source() -> None:
    """LOOK_HIGHER / LOOK_LOWER constants match par_dict.c #defines."""
    text = _read_par_dict_c()
    higher_match = re.search(r"#define\s+LOOK_HIGHER\s+(0x[0-9a-fA-F]+)", text)
    lower_match = re.search(r"#define\s+LOOK_LOWER\s+(0x[0-9a-fA-F]+)", text)
    assert higher_match is not None
    assert lower_match is not None
    assert int(higher_match.group(1), 16) == LOOK_HIGHER
    assert int(lower_match.group(1), 16) == LOOK_LOWER
