"""C-source parity test for ``cm_util_dtpc_tones`` against cm_util.c.

Re-parses the MSDOS branch of ``cm_util_dtpc_tones`` (the only
branch that exercises the ``tlikmap`` / ``tlitone0`` / ``tlitone1``
lookup tables -- the Linux branch is a passthrough that drives the
VTM pipe directly with caller-supplied ``iFrequency``/``iDuration``)
via brace-depth tracking and asserts:

- the per-key ``for (j=0; j<sizeof(tlikmap); j++)`` lookup loop,
- the ``tone[0] = tlitone0[j]`` / ``tone[1] = tlitone1[j]`` fills,
- the ``key == ','`` pause early-return,
- the ``key == '-'`` skip early-return.

Plus a small handful of behavioural checks against the Python port
(:func:`dectalk.cmd.cm_util_dtpc_tones.cm_util_dtpc_tones`):

- ``ord('1')`` -> :class:`DtmfTone` with the expected F1/F2 row/column,
- ``ord(',')`` -> ``None`` (pause),
- ``ord('-')`` -> ``None`` (skip),
- duration passthrough.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_util_dtpc_tones import (
    TLIKMAP,
    TLITONE0,
    TLITONE1,
    DtmfTone,
    cm_util_dtpc_tones,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_util.c"
_H_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_util.h"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_c(path: Path) -> str:
    """Read ``path`` with CRLF endings normalised and latin-1 decoded."""
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_msdos_body() -> str:
    """Return the MSDOS-branch body of ``cm_util_dtpc_tones``.

    The function has two definitions in cm_util.c -- one under
    ``#if defined (WIN32) || defined (__osf__) || defined (__linux__)
    ...`` (line ~367) that is a simple vtm-pipe passthrough, and one
    under ``#ifdef MSDOS`` (line ~460) which is the DTMF lookup-table
    implementation. We anchor on the MSDOS signature (the
    second definition) and walk forward via brace depth.
    """
    text = _read_c(_C_FILE)
    matches = list(
        re.finditer(
            r"^int\s+cm_util_dtpc_tones\s*\(\s*LPTTS_HANDLE_T\b",
            text,
            re.MULTILINE,
        )
    )
    # Two definitions exist (Linux passthrough, then MSDOS lookup-table).
    # The MSDOS one is the second match.
    assert len(matches) >= 2, (
        f"expected two cm_util_dtpc_tones definitions in cm_util.c, found {len(matches)}"
    )
    start = matches[1].start()
    body_start = text.index("{", start)
    depth = 1
    i = body_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, "cm_util_dtpc_tones MSDOS body brace-matching failed"
    return text[body_start:i]


# --------------------------------------------------------------------------
# C-source structural tests.
# --------------------------------------------------------------------------


def test_extract_body_is_balanced_and_nonempty() -> None:
    """The brace-depth extractor returns a balanced, non-empty body."""
    body = _extract_msdos_body()
    assert body.startswith("{")
    assert body.endswith("}")
    assert body.count("{") == body.count("}")


def test_c_body_has_tlikmap_lookup_loop() -> None:
    """The MSDOS branch loops over ``sizeof(tlikmap)`` to find the key."""
    body = _extract_msdos_body()
    assert re.search(
        r"for\s*\(\s*j\s*=\s*0\s*;\s*j\s*<\s*sizeof\s*\(\s*tlikmap\s*\)",
        body,
    ), "expected tlikmap lookup loop ``for(j=0;j<sizeof(tlikmap);j++)``"


def test_c_body_fills_tone_zero_and_one_from_tlitone_tables() -> None:
    """``tone[0] = tlitone0[j]`` and ``tone[1] = tlitone1[j]`` set the DTMF pair."""
    body = _extract_msdos_body()
    assert re.search(
        r"tone\s*\[\s*0\s*\]\s*=\s*tlitone0\s*\[\s*j\s*\]",
        body,
    ), "expected ``tone[0] = tlitone0[j]`` assignment"
    assert re.search(
        r"tone\s*\[\s*1\s*\]\s*=\s*tlitone1\s*\[\s*j\s*\]",
        body,
    ), "expected ``tone[1] = tlitone1[j]`` assignment"


def test_c_body_has_comma_pause_early_return() -> None:
    """``key == ','`` short-circuits with ``return(CMD_success)`` after sleeping."""
    body = _extract_msdos_body()
    # ``if (key == ',') { ... return(CMD_success); }`` -- look for both halves.
    assert re.search(r"if\s*\(\s*key\s*==\s*','\s*\)", body), (
        "expected comma=pause early-return guard"
    )


def test_c_body_has_dash_skip_early_return() -> None:
    """``key == '-'`` short-circuits with ``return(CMD_success)``."""
    body = _extract_msdos_body()
    assert re.search(r"if\s*\(\s*key\s*==\s*'-'\s*\)", body), (
        "expected dash=skip early-return guard"
    )


def _strip_block_comments(text: str) -> str:
    """Strip ``/* ... */`` C block comments (used to clean header literals)."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def test_tlikmap_python_matches_c_header() -> None:
    """The Python ``TLIKMAP`` byte table mirrors the C header verbatim."""
    if not _H_FILE.is_file():
        pytest.skip("cm_util.h not available")
    text = _strip_block_comments(_read_c(_H_FILE))
    # ``unsigned char tlikmap[] = { '0', '1', ..., 'D' };``
    match = re.search(
        r"unsigned\s+char\s+tlikmap\s*\[\s*\]\s*=\s*\{(.+?)\}",
        text,
        re.DOTALL,
    )
    assert match is not None, "tlikmap definition not found in cm_util.h"
    chars = re.findall(r"'(.)'", match.group(1))
    expected = "".join(chars).encode("latin-1")
    assert expected == TLIKMAP


def test_tlitone0_python_matches_c_header() -> None:
    """The Python ``TLITONE0`` tuple mirrors the C header verbatim."""
    if not _H_FILE.is_file():
        pytest.skip("cm_util.h not available")
    text = _strip_block_comments(_read_c(_H_FILE))
    match = re.search(
        r"short\s+tlitone0\s*\[\s*\]\s*=\s*\{(.+?)\}",
        text,
        re.DOTALL,
    )
    assert match is not None, "tlitone0 definition not found in cm_util.h"
    nums = tuple(int(n) for n in re.findall(r"\b(\d+)\b", match.group(1)))
    assert nums == TLITONE0


def test_tlitone1_python_matches_c_header() -> None:
    """The Python ``TLITONE1`` tuple mirrors the (15-entry) C header verbatim."""
    if not _H_FILE.is_file():
        pytest.skip("cm_util.h not available")
    text = _strip_block_comments(_read_c(_H_FILE))
    match = re.search(
        r"short\s+tlitone1\s*\[\s*\]\s*=\s*\{(.+?)\}",
        text,
        re.DOTALL,
    )
    assert match is not None, "tlitone1 definition not found in cm_util.h"
    nums = tuple(int(n) for n in re.findall(r"\b(\d+)\b", match.group(1)))
    assert nums == TLITONE1


# --------------------------------------------------------------------------
# Behavioural tests for the Python port.
# --------------------------------------------------------------------------


def test_key_1_returns_expected_dtmf_pair() -> None:
    """``ord('1')`` returns the row=697 / column=1209 pair from the C tables.

    DTMF '1' is row 697 Hz, column 1209 Hz -- which in the C table
    layout is ``tlitone0[1] = 1209`` (F1, column) and
    ``tlitone1[1] = 697`` (F2, row).
    """
    tone = cm_util_dtpc_tones(ord("1"), dur=150)
    assert tone is not None
    assert isinstance(tone, DtmfTone)
    assert tone.f1 == 1209
    assert tone.f2 == 697


def test_key_comma_returns_none_for_pause() -> None:
    """The comma=pause path short-circuits to ``None`` (mirrors CMD_success)."""
    assert cm_util_dtpc_tones(ord(","), dur=500) is None


def test_key_dash_returns_none_for_skip() -> None:
    """The dash=skip path short-circuits to ``None`` (mirrors CMD_success)."""
    assert cm_util_dtpc_tones(ord("-"), dur=500) is None


def test_duration_is_passed_through() -> None:
    """The caller-supplied duration is forwarded onto the :class:`DtmfTone`."""
    tone = cm_util_dtpc_tones(ord("5"), dur=250)
    assert tone is not None
    assert tone.duration_ms == 250


def test_duration_is_hard_limited_to_30000_ms() -> None:
    """The C source caps ``dur`` at 30000 ms; the Python port mirrors it."""
    tone = cm_util_dtpc_tones(ord("5"), dur=99999)
    assert tone is not None
    assert tone.duration_ms == 30000


def test_unknown_key_returns_none() -> None:
    """A key not in :data:`TLIKMAP` returns ``None`` (mirrors CMD_bad_value)."""
    assert cm_util_dtpc_tones(ord("Z")) is None


def test_zero_key_returns_none() -> None:
    """The C source's ``else`` branch (key == 0) is mirrored by ``None``.

    The MSDOS C branch builds a raw single-frequency tone here using
    ``freq``; the Python shim returns ``None`` (no DTMF F1/F2 pair).
    """
    assert cm_util_dtpc_tones(0, freq=440, dur=100) is None


def test_all_keypad_keys_resolve_to_known_pair() -> None:
    """Every ASCII byte in :data:`TLIKMAP` (except 'D') yields a valid pair.

    'D' lives at index 15 which is past the end of the 15-entry
    :data:`TLITONE1` tuple; we expect the port to still return a
    :class:`DtmfTone` with a defined (zero) ``f2`` so that callers
    don't trip an ``IndexError``. The other 15 keys must all resolve
    to entries from both tables.
    """
    for index, byte in enumerate(TLIKMAP):
        tone = cm_util_dtpc_tones(byte, dur=100)
        assert tone is not None, f"key {chr(byte)!r} unexpectedly resolved to None"
        assert tone.f1 == TLITONE0[index]
        if index < len(TLITONE1):
            assert tone.f2 == TLITONE1[index]
        else:
            assert tone.f2 == 0
