"""Shared helpers for the per-stage parity tests.

The :mod:`test_stage_parity_*` modules each focus on one boundary in
the DECtalk pipeline (kernel / cmd / lts / ph-allofeats /
ph-allophons / vtm). They share:

- Detection of the C oracle artefacts (source-built libtts + shipped
  ``say`` binary) so each test can skip cleanly when those aren't on
  the runner.
- A module-scoped :class:`dectalk._capi.CAPI` fixture that owns the
  ``DECTALK_DUMP_DIR`` plumbing.
- Parsers for the line-oriented dump format the C hooks emit (one
  ``<stage>_write <count>`` header per chunk, followed by a line of
  hex words / bytes).

Keeping these in a single module avoids drift between the six test
files as the dump format evolves.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from dectalk._capi import CAPI

SRC_ROOT: Path = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
BIN_ROOT: Path = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def have_artefacts() -> bool:
    """True iff both the source-built libtts and the shipped binary exist."""
    has_lib = any(SRC_ROOT.glob("src/dtalkml/build/*/us/release/libtts.so")) and any(
        SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so")
    )
    has_bin = (BIN_ROOT / "say").is_file() and (BIN_ROOT / "DECtalk.conf").is_file()
    return has_lib and has_bin


def make_capi() -> CAPI:
    """Construct a CAPI bound to the auto-detected oracle roots."""
    return CAPI(src_root=SRC_ROOT, data_root=BIN_ROOT)


def parse_word_dump(payload: bytes, header: str) -> list[list[int]]:
    """Parse a ``<header> <count>\n<hex words>\n`` dump into chunks of ints.

    Used for ``cmd`` / ``ph`` / ``vtm`` dumps, where each chunk is a
    sequence of 16-bit hex words.

    :param payload: raw bytes from ``<DECTALK_DUMP_DIR>/<stage>.dump``.
    :param header: the literal token the C hook writes before each
        chunk (e.g. ``"cmd_write"``).
    :returns: a list of chunks; each chunk is a list of int tokens.
        An empty payload yields an empty list. Malformed records raise
        :class:`ValueError`.
    """
    chunks: list[list[int]] = []
    lines = payload.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].decode("ascii", errors="strict").strip()
        if not line:
            i += 1
            continue
        parts = line.split()
        if len(parts) != 2 or parts[0] != header:
            raise ValueError(f"unexpected header line {line!r} in {header!r} dump")
        count = int(parts[1])
        i += 1
        if count == 0:
            chunks.append([])
            continue
        if i >= len(lines):
            raise ValueError(f"missing payload line after {line!r}")
        body = lines[i].decode("ascii", errors="strict").strip()
        tokens = [int(tok, 16) for tok in body.split()]
        if len(tokens) != count:
            raise ValueError(
                f"chunk length mismatch: header said {count}, got {len(tokens)} tokens"
            )
        chunks.append(tokens)
        i += 1
    return chunks


def parse_byte_dump(payload: bytes, header: str) -> list[list[int]]:
    """Parse the ``kernel.dump`` byte-oriented variant.

    Same shape as :func:`parse_word_dump`, but tokens are 8-bit hex
    bytes — used for the kernel-stage dump where chunks are raw
    pre-tokenized bytes leaving the kernel.
    """
    return parse_word_dump(payload, header)


# Module-level fixture factory: tests import it to get a CAPI shared
# across all parametrized cases in their module (the CAPI startup cost
# is ~200 ms and we don't want to pay it per-prompt).
@pytest.fixture(scope="module")
def stage_capi() -> CAPI:
    """Module-scoped CAPI for per-stage parity tests."""
    return make_capi()
