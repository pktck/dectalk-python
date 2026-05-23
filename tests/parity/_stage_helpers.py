"""Shared helpers for per-stage parity tests (issue #150).

The per-stage parity test family compares intermediate pipeline state
between the C oracle (via ``CAPI.dump_pipeline``) and the Python port,
stage by stage, so failing stages pinpoint where divergence starts.

Each per-stage test module ``test_stage_<name>_parity.py`` imports the
small prompt corpus and artefact-availability check from here so the
skip conditions and selected prompts stay in sync across stages.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def have_oracle() -> bool:
    """True when both the locally-built libtts and the shipped binary exist."""
    has_lib = any(_SRC_ROOT.glob("src/dtalkml/build/*/us/release/libtts.so")) and any(
        _SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so")
    )
    has_bin = (_BIN_ROOT / "say").is_file() and (_BIN_ROOT / "DECtalk.conf").is_file()
    return has_lib and has_bin


# A small, representative prompt set used by every per-stage parity test.
# Kept small (5 prompts) because each prompt costs one full ``speak()``
# call against the C library -- the test family runs 6 stages x |corpus|
# round-trips, so doubling this multiplies CI wall-clock for limited
# extra signal at the stage-boundary monitoring level.
#
# Picked to exercise different front-end paths:
#   - ``hello world``                       baseline phonotactics
#   - ``the quick brown fox``               longer sentence + multi-word prosody
#   - ``one two three``                     digit / number normalisation
#   - ``hello, world.``                     clause + sentence-final punct
#   - ``computer``                          single noun, syllable boundaries
STAGE_CORPUS: tuple[str, ...] = (
    "hello world",
    "the quick brown fox",
    "one two three",
    "hello, world.",
    "computer",
)


# Skip marker every per-stage parity test should compose with its own
# pytestmark. Keeps the skip reason text identical across files.
skipif_no_oracle = pytest.mark.skipif(
    not have_oracle(),
    reason="locally-built libtts or shipped DECtalk binary not present",
)


_TOKEN_LINE_RE = re.compile(rb"^[0-9a-f]+(?:\s+[0-9a-f]+)*$")


def parse_token_dump(payload: bytes, *, header_prefix: bytes) -> list[int]:
    """Flatten a per-chunk hex token dump into a single list of ints.

    The dump format produced by every per-stage C hook in
    ``tests/parity/c_patches/`` alternates lines:

        <header_prefix> <count>
        <space-separated %02x or %04x tokens>

    This helper concatenates all token lines into one list of ints,
    ignoring chunk boundaries (which carry no semantic meaning — they're
    just whatever buffering granularity the C code happens to use).
    Header-prefix mismatches raise so a missing patch surfaces clearly.

    :param payload: Raw bytes from ``CAPI.dump_pipeline(...)[stage]``.
    :param header_prefix: e.g. ``b"kernel_write"`` or ``b"cmd_write"``.
    :returns: Flat list of token values (ints parsed from hex).
    """
    tokens: list[int] = []
    for raw_line in payload.split(b"\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(header_prefix):
            continue
        if not _TOKEN_LINE_RE.match(line):
            msg = f"unexpected dump line for prefix {header_prefix!r}: {line!r}"
            raise ValueError(msg)
        for tok in line.split():
            tokens.append(int(tok, 16))
    return tokens


__all__ = [
    "STAGE_CORPUS",
    "have_oracle",
    "parse_token_dump",
    "skipif_no_oracle",
]
