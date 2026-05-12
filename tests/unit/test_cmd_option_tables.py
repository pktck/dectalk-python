"""Verify the inline-command option-string tables match c_us_cde.h.

Re-parses each ``const unsigned char *NAME[]`` array at test time and
asserts the order + spelling matches our Python literal. Drops the
trailing 0 sentinel before comparing (Python uses tuple length).

Skips when ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd import option_tables as ot

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_FILE = _SRC_ROOT / "src/dapi/src/cmd/c_us_cde.h"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _parse_options(name: str) -> tuple[str, ...]:  # noqa: PLR0912 — preprocessor scanner
    """Return the first matching array (preprocessor-defines pick a variant).

    The Linux build we target leaves HLSYN/CHANGES_AFTER_V43/EPSON_ARM7/
    UNDER_CE/SW_VOLUME/DTEX/_WIN32 undefined, so we strip the bodies of
    those conditional blocks before parsing.
    """
    text = _C_FILE.read_text(encoding="latin-1")
    # The C source may have multiple ``const ... *NAME[]`` blocks gated
    # by #ifdef; the first lexical occurrence is the one that lands in
    # the non-MSDOS, non-EPSON_ARM7 mainline build (which matches the
    # Linux build we're targeting). #ifndef MSDOS comes before #else.
    pattern = rf"\*\s*{re.escape(name)}\s*\[\]\s*=\s*\{{(.+?)\}};"
    m = re.search(pattern, text, re.DOTALL)
    assert m is not None, f"could not find {name} in c_us_cde.h"
    body = m.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    # Strip the body of #if defined(HLSYN)... blocks (off in our build).
    # Use a simple line-based state machine: when we see #if<not> for a
    # define that's known-off, skip until the matching #endif.
    inactive_guards = {"HLSYN", "CHANGES_AFTER_V43", "EPSON_ARM7",
                       "UNDER_CE", "SW_VOLUME", "DTEX", "_WIN32"}  # fmt: skip
    cleaned_lines: list[str] = []
    skip_depth = 0
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#if"):
            # Check whether any inactive guard appears.
            if any(g in stripped for g in inactive_guards):
                skip_depth += 1
                continue
            if skip_depth > 0:
                skip_depth += 1
                continue
        if skip_depth > 0:
            if stripped.startswith("#endif"):
                skip_depth -= 1
            continue
        if stripped.startswith("#"):
            continue
        cleaned_lines.append(line)
    body = "\n".join(cleaned_lines)
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
                    parts.append({"n": "\n", "t": "\t"}.get(body[j + 1], body[j + 1]))
                    j += 2
                else:
                    parts.append(body[j])
                    j += 1
            out.append("".join(parts))
            i = j + 1
        else:
            i += 1
    return tuple(out)


_TABLES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("phoneme_modes", ot.phoneme_modes),
    ("log_options", ot.log_options),
    ("say_options", ot.say_options),
    ("error_options", ot.error_options),
    ("flush_options", ot.flush_options),
    ("punct_options", ot.punct_options),
    ("skip_options", ot.skip_options),
    ("volume_options", ot.volume_options),
    ("lang_options", ot.lang_options),
    ("version_options", ot.version_options),
    ("mode_options", ot.mode_options),
    ("pronounce_options", ot.pronounce_options),
    ("voice_names", ot.voice_names),
    ("index_options", ot.index_options),
    ("gender_options", ot.gender_options),
    ("define_options", ot.define_options),
)


@pytest.mark.parametrize(("name", "py_table"), _TABLES)
def test_option_table_matches_c(name: str, py_table: tuple[str, ...]) -> None:
    """Each option array matches the C source list in order."""
    expected = _parse_options(name)
    assert py_table == expected


def test_voice_names_start_with_paul() -> None:
    """The first voice — speaker ID 0 — must be Perfect Paul."""
    assert ot.voice_names[0] == "paul"


def test_lang_options_preserve_c_typo() -> None:
    """The C source has 'latin_amercian' (sic) — we preserve it
    verbatim so the same parse misses we'd see in C show up here too."""
    assert "latin_amercian" in ot.lang_options


def test_define_options_save_first() -> None:
    """``save`` is the first define-option keyword."""
    assert ot.define_options[0] == "save"


def test_no_table_has_zero_terminator() -> None:
    """Python tuples don't carry the trailing 0 sentinel."""
    for _name, table in _TABLES:
        assert "0" not in table
        assert "" not in table
