"""Bit-parity tests for :func:`dectalk.dic.quote_string.quote_string`.

Mirrors the C source's in-place behavior on a few representative
inputs. ``dic_comm.c``'s ``quote_string`` wraps a NUL-terminated byte
string with matching quotes: single if the string starts with ``"``,
otherwise double.
"""

from __future__ import annotations

import pytest

from dectalk.dic.quote_string import quote_string


@pytest.mark.parametrize(
    ("inp", "expected"),
    [
        (b"hello", b'"hello"'),
        (b'"already-quoted"', b'\'"already-quoted"\''),
        (b"", b'""'),
        (b"'singles inside'", b'"\'singles inside\'"'),
        (b"a", b'"a"'),
    ],
)
def test_quote_string_wraps_correctly(inp: bytes, expected: bytes) -> None:
    """Each case mirrors the C inplace mutation outcome."""
    assert quote_string(inp) == expected


def test_quote_string_picks_single_quote_when_starts_with_double() -> None:
    """Faithful selection rule: ``str[0] == '"'`` -> single quotes."""
    assert quote_string(b'"x') == b'\'"x\''


def test_quote_string_picks_double_quote_otherwise() -> None:
    """Anything not starting with ``"`` gets double quotes."""
    assert quote_string(b"abc") == b'"abc"'
    assert quote_string(b"'leading single") == b'"\'leading single"'
    assert quote_string(b" leading space") == b'" leading space"'
