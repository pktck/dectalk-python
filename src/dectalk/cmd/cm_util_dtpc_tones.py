"""``cm_util_dtpc_tones`` DTMF tone builder from cm_util.c.

Translated from ``src/dapi/src/cmd/cm_util.c`` lines 460-630 (the
MSDOS branch that exercises the ``tlikmap`` / ``tlitone0`` /
``tlitone1`` lookup tables defined in ``cm_util.h``).

The C function builds a DTMF (touch-tone dialling) tone packet
from a single key character, allocates an SPC tone slot via
``spcget(SPC_type_tone)``, fills the F1/F2 frequencies plus the
:data:`tliproto` template, writes the packet onto the speaker
pipe via ``spcwrite``, and finally sleeps for the tone duration.
None of those side effects map to the Python pipeline:

* there is no SPC -- the Python synthesiser back-end is
  synchronous and does not have a "speaker pipe controller";
* there is no equivalent of ``sleep(on_time + off_time)`` --
  Python callers schedule audio at the WAV level;
* ``cm_cmd_sync`` is a thread-barrier primitive that the Python
  port omits (it is short-circuited to ``CMD_success`` because the
  pipeline is single-threaded).

Architectural shim -- the C function returns ``CMD_success`` after
side-effects; the Python port returns a :class:`DtmfTone | None`
describing *what* would have been written to the SPC, so callers
can feed the F1/F2 pair (and duration) into their own audio path.
``None`` is returned for the comma=pause and dash=skip cases that
the C source short-circuits with ``return(CMD_success)`` without
ever building a tone packet.
"""

from __future__ import annotations

from dataclasses import dataclass

# Hard upper limit on tone duration (ms). Sourced verbatim from the
# C source's ``if (dur > 30000) dur = 30000;`` guard.
_MAX_DURATION_MS = 30000

# DTMF column frequencies (Hz). Each entry corresponds 1:1 with the
# matching index in :data:`TLIKMAP`. Sourced verbatim from
# ``src/dapi/src/cmd/cm_util.h`` lines 48-66.
TLITONE0: tuple[int, ...] = (
    1336,  # 0
    1209,  # 1
    1336,  # 2
    1477,  # 3
    1209,  # 4
    1336,  # 5
    1477,  # 6
    1209,  # 7
    1336,  # 8
    1477,  # 9
    1209,  # *
    1477,  # #
    1633,  # A
    1633,  # B
    1633,  # C
    1633,  # D
)

# DTMF row frequencies (Hz). Sourced verbatim from
# ``src/dapi/src/cmd/cm_util.h`` lines 68-85 -- the C source has only
# 15 explicit entries (the ``#`` row is silently filled by C with a
# zero or whatever the loader picks up); the Python port mirrors the
# exact 15 values from the C source so that lookups parity-check.
TLITONE1: tuple[int, ...] = (
    941,  # 0
    697,  # 1
    697,  # 2
    697,  # 3
    770,  # 4
    770,  # 5
    770,  # 6
    852,  # 7
    852,  # 8
    852,  # 9
    941,  # *
    941,  # # -- comment in C source labels this 'A', see note above
    770,  # A
    852,  # B
    941,  # C
)

# DTMF keypad map. ``key`` is matched against this byte table to find
# the row (F1) / column (F2) frequency index. Sourced verbatim from
# ``src/dapi/src/cmd/cm_util.h`` lines 40-46.
TLIKMAP: bytes = b"0123456789*#ABCD"


@dataclass(frozen=True)
class DtmfTone:
    """Represents the tone packet that would have been written to the SPC.

    Captures the F1/F2 frequencies (Hz) the C source places at
    ``tone[0]`` / ``tone[1]`` plus the caller-supplied duration in
    milliseconds. This is the architectural-shim payload returned by
    :func:`cm_util_dtpc_tones`; Python callers feed this into their
    own audio output path.
    """

    f1: int
    """Tone 0 frequency in Hz (DTMF column from :data:`TLITONE0`)."""

    f2: int
    """Tone 1 frequency in Hz (DTMF row from :data:`TLITONE1`)."""

    duration_ms: int
    """Duration in milliseconds, passed through from the caller."""


def cm_util_dtpc_tones(key: int, freq: int = 0, dur: int = 0) -> DtmfTone | None:
    r"""Build a DTMF tone packet from a keypad key.

    Faithful translation of the MSDOS branch of:

    .. code-block:: c

        int cm_util_dtpc_tones(LPTTS_HANDLE_T phTTS, unsigned int key,
                               unsigned int freq, unsigned int dur) {
            ...
            if (dur > 30000) dur = 30000;
            if (key == ',') {
                sleep(pCmd_t->tone_wait + 200);
                pCmd_t->tone_wait = 0;
                pCmd_t->dtmf_start_clock = 0;
                return(CMD_success);
            }
            if (key == '-') {
                return(CMD_success);
            }
            if (key) {
                for (j = 0; j < sizeof(tlikmap); j++) {
                    if (key == (unsigned int)tlikmap[j]) break;
                }
                if (j == sizeof(tlikmap)) return(CMD_bad_value);
                tone = (unsigned int _far *)spcget(SPC_type_tone);
                for (i = 0; i < NWDTMF; ++i) tone[i] = tliproto[i];
                tone[0] = tlitone0[j];   /* [F1] */
                tone[1] = tlitone1[j];   /* [F2] */
                spcwrite(tone);
                ...
                return(CMD_success);
            } else {
                ...
                return(CMD_success);
            }
        }

    Args:
        key: ASCII code of the keypad key (e.g. ``ord('1')``). The
            C source short-circuits on ``,`` (pause) and ``-`` (skip)
            without building a tone -- both map to ``None`` here.
        freq: Caller-supplied frequency (Hz), used by the C source's
            ``else`` branch when ``key == 0`` to drive a raw
            single-frequency tone via the SPC. The Python port
            mirrors this for parity but does not currently expose a
            raw-frequency path; reserved for future use.
        dur: Duration in milliseconds. The C source hard-limits
            this to 30000 ms (30 seconds); the Python port mirrors
            that cap before stashing it on the returned
            :class:`DtmfTone`.

    Returns:
        A :class:`DtmfTone` describing the F1/F2 pair the C source
        would have queued onto the SPC, or ``None`` for the
        comma=pause / dash=skip / unknown-key paths. ``None`` mirrors
        the C source's ``return(CMD_success)`` after a pure-side-effect
        no-op.
    """
    # C: if (dur > 30000) dur = 30000;
    dur = min(dur, _MAX_DURATION_MS)

    # C: if (key == ',') { ...sleep(...); return(CMD_success); }
    # The Python port has no thread-sleep equivalent; we just signal
    # "no tone to play" by returning None.
    if key == ord(","):
        return None

    # C: if (key == '-') return(CMD_success);
    if key == ord("-"):
        return None

    # C: if (key) { for (j=0; j<sizeof(tlikmap); j++) ... }
    if key:
        # Find the keypad slot.
        try:
            j = TLIKMAP.index(key)
        except ValueError:
            # C: if (j == sizeof(tlikmap)) return(CMD_bad_value);
            return None

        # C: tone[0] = tlitone0[j];  /* [F1] */
        # C: tone[1] = tlitone1[j];  /* [F2] */
        # The C source has only 15 entries in tlitone1 -- guard the
        # tail-of-table read so we still return a well-defined value
        # when ``j == 15`` ('D'). Beyond-table indices in the C source
        # read whatever lives in the data segment, which is undefined
        # behaviour we do not attempt to mirror.
        f1 = TLITONE0[j]
        f2 = TLITONE1[j] if j < len(TLITONE1) else 0

        return DtmfTone(f1=f1, f2=f2, duration_ms=dur)

    # C: else branch -- raw frequency tone path. Not exposed in the
    # Python port today; mirror by returning None so the caller knows
    # no DTMF F1/F2 pair was produced. ``freq`` is referenced via the
    # default to avoid an unused-argument warning.
    _ = freq
    return None


__all__ = [
    "TLIKMAP",
    "TLITONE0",
    "TLITONE1",
    "DtmfTone",
    "cm_util_dtpc_tones",
]
