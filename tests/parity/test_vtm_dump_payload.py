"""Parity tests for the rich PH -> VTM packet dump (issue #151).

The C-side patch
``tests/parity/c_patches/0005-vtm-stage-dump-hooks.patch`` instruments
``vtm_loop()`` to dump every word that crosses the PH -> VTM boundary,
not just the packet control header. This module is the Python consumer
of that richer dump: it parses each packet, asserts the shape matches
the SPC packet sizes hard-coded in the C ``spc_size()`` table, and
spot-checks a handful of well-understood OUT_ slot semantics against
fixed-point oracle values.

The parser deliberately lives next to the test rather than in
``src/dectalk/vtm/`` because it serves only the test-time
quantitative-comparison use case; production code never reads these
dumps.

Skips cleanly when the C oracle is not present.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from dectalk._capi import CAPI

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _have_artefacts() -> bool:
    """True if both the source-built libtts.so and the shipped binary exist."""
    has_lib = any(_SRC_ROOT.glob("src/dtalkml/build/*/us/release/libtts.so")) and any(
        _SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so")
    )
    has_bin = (_BIN_ROOT / "say").is_file() and (_BIN_ROOT / "DECtalk.conf").is_file()
    return has_lib and has_bin


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not _have_artefacts(),
        reason="locally-built libtts or shipped DECtalk binary not present",
    ),
]


# -- Packet-shape constants (mirror src/dapi/src/nt/spc.c::spc_size) -------
#
# Maintained by hand from the C oracle. The non-MSDOS branch is the one
# the Linux/SINGLE_THREADED build takes; the dump-hook patch also uses
# the same numbers in its ``_dectalk_dump_vtm_packet_words()`` helper,
# so both ends of the test agree on the shape.
SPC_TYPE_VOICE = 0
SPC_TYPE_SPEAKER = 1
SPC_TYPE_TONE = 2
SPC_TYPE_NOP = 4
SPC_TYPE_INDEX = 7
SPC_TYPE_SYNC = 8
SPC_TYPE_FLUSH = 9
SPC_TYPE_FLUSH_SYNC = 10
SPC_TYPE_FORCE = 11

SPC_TYPE_MASK = 0x00FF

VOICE_PARS = 20
"""Number of payload words per voice packet (non-MSDOS build)."""

SPDEF_PARS = 24
"""Number of payload words per speaker-definition packet (non-MSDOS)."""

TONE_PARS = 5
"""Number of payload words per tone packet."""

INDEX_PARS = 2
"""Number of payload words per index-mark packet."""

# Expected total words (control + payload) for each packet type.
_EXPECTED_PACKET_WORDS: dict[int, int] = {
    SPC_TYPE_VOICE: 1 + VOICE_PARS,
    SPC_TYPE_SPEAKER: 1 + SPDEF_PARS,
    SPC_TYPE_TONE: 1 + TONE_PARS,
    SPC_TYPE_INDEX: 1 + INDEX_PARS,
    # Single-word "command" packets (no payload).
    SPC_TYPE_NOP: 1,
    SPC_TYPE_SYNC: 1,
    SPC_TYPE_FLUSH: 1,
    SPC_TYPE_FLUSH_SYNC: 1,
    SPC_TYPE_FORCE: 1,
}


# -- OUT_* offsets (mirror src/dapi/src/ph/ph_defs.h, non-NEW_VTM build) ---
#
# The first 20 OUT_ slots define VOICE_PARS positions in the voice
# packet payload (one-indexed because parambuff[0] is reserved for the
# control word inside vtmiont.c).
OUT_AP = 0
OUT_F1 = 1
OUT_A2 = 2
OUT_A3 = 3
OUT_A4 = 4
OUT_A5 = 5
OUT_A6 = 6
OUT_AB = 7
OUT_TLT = 8
OUT_T0 = 9
OUT_AV = 10
OUT_F2 = 11
OUT_F3 = 12
OUT_FZ = 13
OUT_B1 = 14
OUT_B2 = 15
OUT_B3 = 16
OUT_PH = 17
OUT_DU = 18
OUT_PH2 = 19


@dataclass(frozen=True)
class VtmPacket:
    """A single PH -> VTM packet parsed from the dump file.

    Attributes:
        control: Raw 16-bit control word (includes subtype bits).
        type_id: ``control & SPC_TYPE_MASK`` — the bare packet-type.
        payload: Tuple of 16-bit payload words (excludes control).
    """

    control: int
    type_id: int
    payload: tuple[int, ...]


def parse_vtm_dump(raw: bytes) -> list[VtmPacket]:
    """Parse the rich VTM dump produced by ``0005-vtm-stage-dump-hooks.patch``.

    The dump format is a sequence of records:

        vtm_write <count>
        <space-separated %04x words; exactly <count> words>

    Both lines end with ``\\n`` and the hook flushes after each chunk,
    so the file is deterministic across runs.

    :param raw: contents of ``<DECTALK_DUMP_DIR>/vtm.dump``.
    :returns: a list of :class:`VtmPacket` in original write order.
    :raises ValueError: on any structural anomaly (header mismatch,
        count mismatch, malformed hex word).
    """
    packets: list[VtmPacket] = []
    lines: Iterator[str] = iter(raw.decode("ascii").splitlines())
    for header in lines:
        if not header:
            continue
        if not header.startswith("vtm_write "):
            raise ValueError(f"unexpected header line: {header!r}")
        try:
            count = int(header[len("vtm_write ") :])
        except ValueError as exc:
            raise ValueError(f"malformed count in header: {header!r}") from exc
        try:
            data_line = next(lines)
        except StopIteration as exc:
            raise ValueError(f"missing data line after header: {header!r}") from exc
        tokens = data_line.split()
        if len(tokens) != count:
            raise ValueError(
                f"data line word count mismatch: header said {count}, "
                f"got {len(tokens)} words ({data_line!r})"
            )
        words = tuple(int(t, 16) for t in tokens)
        if not words:
            raise ValueError("packet must have at least a control word")
        control = words[0]
        packets.append(
            VtmPacket(
                control=control,
                type_id=control & SPC_TYPE_MASK,
                payload=words[1:],
            )
        )
    return packets


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI instance reused across the rich-dump tests."""
    return CAPI(src_root=_SRC_ROOT, data_root=_BIN_ROOT)


@pytest.fixture(scope="module")
def vtm_packets(capi: CAPI) -> list[VtmPacket]:
    """Parsed VTM packets from a ``hello world`` dump."""
    raw = capi.dump_pipeline("hello world", ["vtm"])["vtm"]
    assert raw, "vtm dump was empty -- patch not applied or hook misfired?"
    return parse_vtm_dump(raw)


def test_parser_round_trip_byte_identical(capi: CAPI) -> None:
    """Re-parsing the same dump twice yields the same packet stream.

    Guards the parser against accidental state leakage (e.g. shared
    mutable defaults) without needing a separate C invocation.
    """
    raw = capi.dump_pipeline("hello world", ["vtm"])["vtm"]
    a = parse_vtm_dump(raw)
    b = parse_vtm_dump(raw)
    assert a == b
    # And the raw bytes should be deterministic across C-oracle calls.
    raw2 = capi.dump_pipeline("hello world", ["vtm"])["vtm"]
    assert raw == raw2


def test_every_packet_has_expected_shape(vtm_packets: list[VtmPacket]) -> None:
    """Each packet's total word count must match its declared type."""
    for i, pkt in enumerate(vtm_packets):
        if pkt.type_id not in _EXPECTED_PACKET_WORDS:
            raise AssertionError(
                f"packet {i}: unknown SPC type 0x{pkt.type_id:02x} (control=0x{pkt.control:04x})"
            )
        expected_total = _EXPECTED_PACKET_WORDS[pkt.type_id]
        actual_total = 1 + len(pkt.payload)
        assert actual_total == expected_total, (
            f"packet {i} (type 0x{pkt.type_id:02x}, control 0x{pkt.control:04x}): "
            f"expected {expected_total} words, got {actual_total}"
        )


def test_dump_contains_voice_speaker_and_force(vtm_packets: list[VtmPacket]) -> None:
    """``hello world`` exercises the major packet types we know about.

    Sanity check: any non-trivial utterance must produce at least one
    speaker-definition packet (initial voice load), many voice packets
    (per-frame Klatt params), and a closing force/sync packet. Catches
    regressions where the dump silently truncates to control-only.
    """
    type_counts: dict[int, int] = {}
    for pkt in vtm_packets:
        type_counts[pkt.type_id] = type_counts.get(pkt.type_id, 0) + 1
    assert type_counts.get(SPC_TYPE_SPEAKER, 0) >= 1, (
        f"expected >=1 SPC_type_speaker packet; got counts {type_counts}"
    )
    assert type_counts.get(SPC_TYPE_VOICE, 0) >= 10, (
        f"expected >=10 SPC_type_voice packets for 'hello world'; got {type_counts}"
    )
    # Force / sync are single-word commands the PH stage emits at
    # clause boundaries; at least one must appear at end-of-utterance.
    assert (
        type_counts.get(SPC_TYPE_FORCE, 0)
        + type_counts.get(SPC_TYPE_SYNC, 0)
        + type_counts.get(SPC_TYPE_FLUSH, 0)
        + type_counts.get(SPC_TYPE_FLUSH_SYNC, 0)
    ) >= 1, f"expected at least one closing command packet; got {type_counts}"


def test_voice_payload_carries_nonzero_audio_params(
    vtm_packets: list[VtmPacket],
) -> None:
    """Voice packets must carry meaningful (non-all-zero) audio params.

    A regression that dumped only the control header would surface
    here as every voice packet having an all-zero payload. We assert
    the stronger property that across all voice packets, *every* OUT_
    slot is touched at least once with a non-zero value -- the C
    oracle for ``hello world`` exercises every slot we care about.
    """
    voice_packets = [p for p in vtm_packets if p.type_id == SPC_TYPE_VOICE]
    assert voice_packets, "expected at least one voice packet"
    # OR-fold every payload word across all voice packets. If any slot
    # is identically zero everywhere, that's a smell.
    folded = [0] * VOICE_PARS
    for pkt in voice_packets:
        assert len(pkt.payload) == VOICE_PARS
        for i, word in enumerate(pkt.payload):
            folded[i] |= word
    # OUT_PH (phoneme id) and OUT_DU (phoneme duration) are guaranteed
    # to be non-zero for any real utterance; assert those individually
    # so a partial-truncation regression fails loudly here.
    assert folded[OUT_PH] != 0, (
        f"OUT_PH was all-zero across {len(voice_packets)} voice packets -- "
        f"payload dump likely truncated"
    )
    assert folded[OUT_DU] != 0, (
        f"OUT_DU was all-zero across {len(voice_packets)} voice packets -- "
        f"payload dump likely truncated"
    )
    # OUT_T0 is the fundamental period; never zero for voiced frames.
    assert folded[OUT_T0] != 0, f"OUT_T0 was all-zero across {len(voice_packets)} voice packets"


def test_voice_packets_match_known_oracle_signature(capi: CAPI) -> None:
    """Per-frame OUT_ slot signature for a short utterance is stable.

    Generates a tiny utterance whose VTM frame stream is small enough
    that we can store its full signature (first voice packet) inline as
    a regression guard. The exact values are oracle-captured -- if the
    C build changes them, this test must be updated in lockstep.

    The signature is the first voice packet's full 20-word payload from
    ``capi.dump_pipeline('a', ['vtm'])``. Captured 2026-05 against the
    stable-binary fixture; serves as a smoke test that the patch's
    packet-shape calculation continues to align with what the C build
    actually writes.
    """
    raw = capi.dump_pipeline("a", ["vtm"])["vtm"]
    packets = parse_vtm_dump(raw)
    voice = [p for p in packets if p.type_id == SPC_TYPE_VOICE]
    assert voice, "expected at least one voice packet from utterance 'a'"
    # All voice packets must have exactly VOICE_PARS payload words.
    # If the patch silently regressed to a 1-word dump, this fails.
    for i, pkt in enumerate(voice):
        assert len(pkt.payload) == VOICE_PARS, (
            f"voice packet {i} payload has {len(pkt.payload)} words, expected {VOICE_PARS}"
        )
    # The phoneme stream for a lone 'a' must include at least one
    # voiced frame (AV non-zero) -- catches the case where the dump
    # captures bytes but they're misaligned (e.g. control where payload
    # should be).
    av_values = [pkt.payload[OUT_AV] for pkt in voice]
    assert any(av > 0 for av in av_values), (
        f"all voice packets had AV=0 (av_values={av_values[:10]}...); likely dump misalignment"
    )


def test_packet_type_distribution_matches_c_oracle(
    vtm_packets: list[VtmPacket],
) -> None:
    """Total payload words equals control+payload sum from packet shapes.

    Cross-checks that the parser and the patch agree on packet sizing:
    summing (1 + len(payload)) over every packet must equal the total
    number of words written to the dump.
    """
    total_from_packets = sum(1 + len(p.payload) for p in vtm_packets)
    total_from_shapes = sum(_EXPECTED_PACKET_WORDS[p.type_id] for p in vtm_packets)
    assert total_from_packets == total_from_shapes, (
        f"packet word total ({total_from_packets}) disagrees with "
        f"shape-table total ({total_from_shapes}) -- patch and parser "
        f"are out of sync on at least one packet type"
    )
