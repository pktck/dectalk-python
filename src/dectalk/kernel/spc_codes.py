"""Signal-processing-chip (SPC) packet codes from kernel.h.

Translated from ``src/dapi/src/include/kernel.h``. SPC packets are
fixed-size structures the kernel sends to / receives from the SPC
(originally a hardware DSP, now the host CPU). Each packet carries a
type byte (low 8 bits) plus a subtype byte (next 8 bits, already
shifted into position).

- :data:`SPC_TYPE_MASK` — mask for the low byte (type field).
- :data:`SPC_type_*` — the 12 packet-type values
  (voice / speaker / tone / test / nop / digitized / mixed / index
  / sync / flush / flush_sync / force / samples_per_frame / visual).
- :data:`SPC_subtype_*` — sub-types for INDEX packets
  (bookmark / wordpos / start / stop / sentence / volume / noise).
- :data:`SPC_flush_*` — sub-types for FLUSH packets
  (all / until / mask / after).
- :data:`SPC_mode_*` — text vs digital mode flags.
- :data:`MAX_SPC_DATA` / :data:`MAX_SPC_PACKETS` — packet-data
  capacity caps.
- :data:`PHONE_HUGE` — sentinel value bigger than ``NPHON_MAX``.
"""

from __future__ import annotations

from typing import Final

# -- Packet type byte (low 8 bits) ------------------------------------------

SPC_TYPE_MASK: Final[int] = 0x00FF
"""Mask for the SPC packet-type byte (low 8 bits)."""

SPC_type_voice: Final[int] = 0
"""SPC packet type: voice (vocal-tract parameter frame)."""

SPC_type_speaker: Final[int] = 1
"""SPC packet type: speaker change (new voice ID)."""

SPC_type_tone: Final[int] = 2
"""SPC packet type: bare tone (used by tone synthesizer)."""

SPC_type_test: Final[int] = 3
"""SPC packet type: self-test / diagnostic."""

SPC_type_nop: Final[int] = 4
"""SPC packet type: no-op (padding)."""

SPC_type_digitized: Final[int] = 5
"""SPC packet type: pre-recorded digitised audio."""

SPC_type_mixed: Final[int] = 6
"""SPC packet type: mixed (synthesised + digitised)."""

SPC_type_index: Final[int] = 7
"""SPC packet type: index marker (callback trigger)."""

SPC_type_sync: Final[int] = 8
"""SPC packet type: pipeline sync barrier."""

SPC_type_flush: Final[int] = 9
"""SPC packet type: pipeline flush (drop pending audio)."""

SPC_type_flush_sync: Final[int] = 10
"""SPC packet type: flush + sync (drop audio, then resync)."""

SPC_type_force: Final[int] = 11
"""SPC packet type: force (override current speaking)."""

SPC_type_samples_per_frame: Final[int] = 12
"""SPC packet type: report samples-per-frame to host."""

SPC_type_visual: Final[int] = 128
"""SPC packet type: visual feedback (for accessibility)."""

# -- INDEX-packet subtypes (already shifted into position) ------------------

SPC_subtype_bookmark: Final[int] = 0x0100
"""Index packet subtype: bookmark (user-marked position)."""

SPC_subtype_wordpos: Final[int] = 0x0200
"""Index packet subtype: word position."""

SPC_subtype_start: Final[int] = 0x0300
"""Index packet subtype: start of synthesis."""

SPC_subtype_stop: Final[int] = 0x0400
"""Index packet subtype: end of synthesis."""

SPC_subtype_sentence: Final[int] = 0x0500
"""Index packet subtype: sentence boundary."""

SPC_subtype_volume: Final[int] = 0x0600
"""Index packet subtype: volume-change event."""

SPC_subtype_noise: Final[int] = 0x0700
"""Index packet subtype: ambient-noise event."""

# -- FLUSH-packet subtypes --------------------------------------------------

SPC_flush_all: Final[int] = 0
"""Flush subtype: discard everything."""

SPC_flush_until: Final[int] = 1
"""Flush subtype: discard up to the next sync."""

SPC_flush_mask: Final[int] = 2
"""Flush subtype: mask-based selective flush."""

SPC_flush_after: Final[int] = 3
"""Flush subtype: discard everything after the current position."""

# -- Mode flags -------------------------------------------------------------

SPC_mode_text: Final[int] = 0
"""SPC mode: text input."""

SPC_mode_digital: Final[int] = 1
"""SPC mode: digital (pre-encoded phonemes) input."""

# -- Capacity / sentinel constants ------------------------------------------

MAX_SPC_DATA: Final[int] = 32
"""Maximum bytes of data per SPC packet."""

MAX_SPC_PACKETS: Final[int] = 400
"""Maximum number of SPC packets queueable at once."""

PHONE_HUGE: Final[int] = 9999
"""Sentinel value larger than any valid phone index (NPHON_MAX)."""


__all__ = [
    "MAX_SPC_DATA",
    "MAX_SPC_PACKETS",
    "PHONE_HUGE",
    "SPC_TYPE_MASK",
    "SPC_flush_after",
    "SPC_flush_all",
    "SPC_flush_mask",
    "SPC_flush_until",
    "SPC_mode_digital",
    "SPC_mode_text",
    "SPC_subtype_bookmark",
    "SPC_subtype_noise",
    "SPC_subtype_sentence",
    "SPC_subtype_start",
    "SPC_subtype_stop",
    "SPC_subtype_volume",
    "SPC_subtype_wordpos",
    "SPC_type_digitized",
    "SPC_type_flush",
    "SPC_type_flush_sync",
    "SPC_type_force",
    "SPC_type_index",
    "SPC_type_mixed",
    "SPC_type_nop",
    "SPC_type_samples_per_frame",
    "SPC_type_speaker",
    "SPC_type_sync",
    "SPC_type_test",
    "SPC_type_tone",
    "SPC_type_visual",
    "SPC_type_voice",
]
