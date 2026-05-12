"""Verify ``usa_type`` and ``usa_error`` match the C source.

Parses ``usa_type.tab`` and ``usa_err.tab`` (included by
``kernel/usa.c``) at test time and asserts every entry matches our
Python literal byte-for-byte.

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel import usa_tables as ut

_INCLUDE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/include"
_USA_TYPE = _INCLUDE / "usa_type.tab"
_USA_ERR = _INCLUDE / "usa_err.tab"

pytestmark = pytest.mark.skipif(
    not _USA_TYPE.is_file() or not _USA_ERR.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_c_string_array(path: Path, name: str) -> tuple[str, ...]:
    """Parse a ``const ... *NAME[] = { "..", ".." };`` initialiser."""
    text = path.read_text(encoding="latin-1")
    m = re.search(rf"\*\s*{re.escape(name)}\s*\[\]\s*=\s*\{{(.+?)\}};", text, re.DOTALL)
    assert m is not None, f"could not find {name} in {path.name}"
    body = m.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    out: list[str] = []
    i = 0
    while i < len(body):
        c = body[i]
        if c == '"':
            j = i + 1
            parts: list[str] = []
            while j < len(body) and body[j] != '"':
                if body[j] == "\\" and j + 1 < len(body):
                    escape_map = {
                        "n": "\n",
                        "t": "\t",
                        "r": "\r",
                        "0": "\0",
                        "\\": "\\",
                        '"': '"',
                        "'": "'",
                    }
                    parts.append(escape_map.get(body[j + 1], body[j + 1]))
                    j += 2
                else:
                    parts.append(body[j])
                    j += 1
            out.append("".join(parts))
            i = j + 1
        else:
            i += 1
    return tuple(out)


def test_usa_type_has_256_entries() -> None:
    """The C ``usa_type[]`` covers every byte value 0..255."""
    expected = 256
    assert len(ut.usa_type) == expected


def test_usa_type_matches_c_source() -> None:
    """Every entry of ``usa_type`` matches the C initialiser."""
    expected = _parse_c_string_array(_USA_TYPE, "usa_type")
    assert ut.usa_type == expected


def test_usa_error_matches_c_source() -> None:
    """Every entry of ``usa_error`` matches the C initialiser."""
    expected = _parse_c_string_array(_USA_ERR, "usa_error")
    assert ut.usa_error == expected


def test_usa_type_letters_have_uppercase_prefix() -> None:
    """ASCII A..Z all start with ``:`` (the "capital" prefix)."""
    for c in range(ord("A"), ord("Z") + 1):
        assert ut.usa_type[c].startswith(":"), f"byte {c:#x} ({chr(c)!r}): {ut.usa_type[c]!r}"


def test_usa_type_lowercase_no_uppercase_prefix() -> None:
    """ASCII a..z don't start with ``:``."""
    for c in range(ord("a"), ord("z") + 1):
        assert not ut.usa_type[c].startswith(":"), f"byte {c:#x}: {ut.usa_type[c]!r}"


def test_usa_type_digits_are_spoken() -> None:
    """ASCII 0..9 have non-empty spoken-form."""
    for c in range(ord("0"), ord("9") + 1):
        assert ut.usa_type[c], f"digit {chr(c)!r} has no spoken form"


def test_usa_type_undefined_codes_are_empty() -> None:
    """Many control-character and reserved Latin-1 slots are empty."""
    # Spot check a few that the C source leaves blank.
    for c in (0x01, 0x7F, 0x81, 0xA4, 0xD7, 0xF7):
        assert ut.usa_type[c] == "", f"byte {c:#x} unexpectedly populated"


def test_usa_error_has_twelve_messages() -> None:
    """The C ``usa_error[]`` defines 12 error messages."""
    expected = 12
    assert len(ut.usa_error) == expected


def test_usa_error_messages_are_distinct() -> None:
    """No duplicate error messages — a typo would be caught here."""
    assert len(set(ut.usa_error)) == len(ut.usa_error)
