"""Dump-feed control: the Python VTM1 is byte-exact given the C's own packets.

Issue #284's acceptance artifact. The control experiment feeds the C
oracle's **own** post-``send_pars`` voice packets (``vtm_frames.dump``,
patch 0006) through :func:`dectalk.vtm.pump_frames.pump_frames_via_vtm1`
and asserts the produced PCM is **byte-identical to the oracle's WAV
for the whole utterance**. This isolates the VTM stage from PH-side
parameter generation: any failure here is a synthesizer-internal
divergence (state seeding, integer arithmetic, filter memory handling),
not a packet-content one.

History: before #284 this control diverged at sample 214 on ``hello
world`` (C=656 vs Py=660, the second sample of the first audible
frame). Root causes, both in the synth *seed* rather than the sample
loop:

1. ``SynthState.T0``/``nopen`` defaulted to 100/40 instead of the C
   ``calloc`` zeros, so the first pitch-synchronous update fired 100
   ticks late (C fires it on the very first tick via ``nper == T0 ==
   0``), skewing every later pitch-period boundary.
2. ``default_us_paul_spd()`` missed the ``setspdef()`` (``ph_vset.c``)
   chip derivations: ``fnscale = (200-HS)*41 = 4100`` (not 4096),
   ``F4/F5`` chip words pre-scaled by fnscale (3303/3653, not
   3300/3650), ``nopen1 = 4000+160*(100-RI) = 8800`` (not 0) and
   ``aturb = BR+9 = 9`` (not 0).

With both fixed, the dump-fed control is byte-exact end-to-end on every
audited prompt (11 prompts, ~183K samples, zero diffs at fix time).

The companion test pins the oracle's ``SPC_type_speaker`` chip packet
(captured via the patch-0005 ``vtm.dump`` hook) against
:func:`~dectalk.vtm.spd_chip.default_us_paul_spd` word-for-word, so a
speaker-seed regression is named directly instead of via PCM drift.

Skips cleanly when the C oracle artefacts are missing.
"""

from __future__ import annotations

import io
import os
import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest

from dectalk._capi import CAPI
from dectalk.vtm.pump_frames import pump_frames_via_vtm1
from dectalk.vtm.spd_chip import default_us_paul_spd

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _have_artefacts() -> bool:
    """True if both the source-built libtts and the shipped binary exist."""
    has_lib = any(_SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    has_bin = (_BIN_ROOT / "say").is_file() and (_BIN_ROOT / "DECtalk.conf").is_file()
    return has_lib and has_bin


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not _have_artefacts(),
        reason="locally-built libtts or shipped DECtalk binary not present",
    ),
]


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI instance reused across the dump-feed tests."""
    return CAPI(src_root=_SRC_ROOT, data_root=_BIN_ROOT)


def _oracle_capture(capi: CAPI, text: str) -> tuple[np.ndarray, list[list[int]], list[int]]:
    """Render ``text`` via the oracle and capture (PCM, voice frames, spdef).

    Uses ``DECTALK_DUMP_DIR`` so the patch-0006 hook writes
    ``vtm_frames.dump`` (full 21-word voice payloads) and the patch-0005
    hook writes ``vtm.dump`` (every packet incl. the SPC_type_speaker
    chip block). The WAV returned by ``capi.speak`` is the same render.
    """
    with tempfile.TemporaryDirectory(prefix="dectalk-dumpfeed-") as dump_dir:
        prev = os.environ.get("DECTALK_DUMP_DIR")
        os.environ["DECTALK_DUMP_DIR"] = dump_dir
        try:
            wav_bytes = capi.speak(text)
        finally:
            if prev is None:
                os.environ.pop("DECTALK_DUMP_DIR", None)
            else:
                os.environ["DECTALK_DUMP_DIR"] = prev

        frames_path = Path(dump_dir) / "vtm_frames.dump"
        chunks_path = Path(dump_dir) / "vtm.dump"
        if not frames_path.is_file() or not chunks_path.is_file():
            pytest.skip(
                "vtm dump files not produced; patches 0005/0006 not applied "
                "to the C oracle? Re-run scripts/setup_c_oracle.sh."
            )
        frames_payload = frames_path.read_text(encoding="latin-1")
        chunks_payload = chunks_path.read_text(encoding="latin-1")

    with wave.open(io.BytesIO(wav_bytes)) as fh:
        pcm = np.frombuffer(fh.readframes(fh.getnframes()), dtype=np.int16)

    frames: list[list[int]] = []
    for line in frames_payload.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "vtm_frame":
            count = int(parts[1])
            frames.append([int(x) for x in parts[2 : 2 + count]])

    # First SPC_type_speaker packet payload from the chunk dump (hex
    # words; word 0 is the control word, subtype bits stripped).
    spdef: list[int] = []
    lines = chunks_payload.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("vtm_write "):
            continue
        if i + 1 >= len(lines):
            break
        words = [int(tok, 16) for tok in lines[i + 1].split()]
        if words and (words[0] & 0x00FF) == 1:  # SPC_type_speaker
            spdef = [w - 0x10000 if w & 0x8000 else w for w in words[1:]]
            break

    return pcm, frames, spdef


# Prompts for the byte-exact dump-feed gate. Deliberately spans the
# #270 count-exact audit set's variety (voiced onsets, stops, clusters,
# spelled-out letters) without re-rendering all six every CI run.
_PROMPTS: tuple[str, ...] = (
    "hello world",
    "a box of cats",
    "BBC",
)


@pytest.mark.parametrize("text", _PROMPTS)
def test_vtm1_dump_feed_byte_exact(capi: CAPI, text: str) -> None:
    """Oracle packets through the Python VTM reproduce the oracle WAV exactly.

    The pass bar is whole-utterance byte equality -- not a prefix
    length. A divergence at sample N means a VTM-internal state or
    arithmetic difference (see module docstring for the #284 history),
    and the failure message names the first diverging sample and frame
    to restart the diagnosis at the right spot.
    """
    pcm, frames, _ = _oracle_capture(capi, text)
    assert frames, f"oracle produced no voice frames for {text!r}"

    py = pump_frames_via_vtm1(frames)

    assert py.size == pcm.size, (
        f"sample-count mismatch for {text!r}: pump {py.size} vs oracle {pcm.size} "
        f"({len(frames)} voice frames x 71)"
    )
    neq = np.nonzero(py != pcm)[0]
    if neq.size:
        first = int(neq[0])
        lo = max(0, first - 2)
        pytest.fail(
            f"dump-fed PCM diverges for {text!r} at sample {first} "
            f"(frame {first // 71}, offset {first % 71}); "
            f"{neq.size}/{pcm.size} samples differ. "
            f"C[{lo}:{first + 6}]={pcm[lo : first + 6].tolist()} "
            f"Py[{lo}:{first + 6}]={py[lo : first + 6].tolist()}"
        )


# C SPD_CHIP field order (viphdefs.h lines 306-331). The chip stores
# the *frequency* in r4cb/r5cb and the *bandwidth* in r4cc/r5cc; the
# Python SpdChip consumers use the swapped convention (frequency in
# r4cc/r5cc), so the comparison below crosses the pairs over.
_SPD_CHIP_FIELDS: tuple[str, ...] = (
    "r4cb", "r4cc", "r5cb", "r5cc", "r4pb", "r5pb", "t0jit",
    "r5ca", "r4ca", "r3ca", "r2ca", "r1ca", "nopen1", "nopen2",
    "aturb", "fnscale", "afgain", "rnpgain", "azgain", "apgain",
    "notused", "osgain", "speaker", "sex",
)
_PY_SWAPPED: dict[str, str] = {"r4cb": "r4cc", "r4cc": "r4cb", "r5cb": "r5cc", "r5cc": "r5cb"}


def test_default_paul_spd_matches_oracle_chip_packet(capi: CAPI) -> None:
    """``default_us_paul_spd()`` equals the oracle's SPC_type_speaker packet.

    Pins every chip word -- including the ``setspdef()`` derivations
    ``fnscale=(200-HS)*41``, ``F4/F5*fnscale>>12``, ``nopen1=4000+
    160*(100-RI)`` and ``aturb=BR+9`` -- against the packet the C PH
    stage actually streams, so the speaker seed can never silently
    drift from the oracle again (issue #284).
    """
    _, _, spdef = _oracle_capture(capi, "hello world")
    assert len(spdef) >= len(_SPD_CHIP_FIELDS), (
        f"spdef packet too short: {len(spdef)} words (expected >= {len(_SPD_CHIP_FIELDS)})"
    )

    chip = default_us_paul_spd()
    mismatches: list[str] = []
    for idx, c_field in enumerate(_SPD_CHIP_FIELDS):
        py_field = _PY_SWAPPED.get(c_field, c_field)
        py_value = int(getattr(chip, py_field))
        c_value = spdef[idx]
        if py_value != c_value:
            mismatches.append(
                f"chip[{idx}] {c_field} (py .{py_field}): C={c_value} py={py_value}"
            )
    assert not mismatches, "SpdChip drift vs oracle spdef packet:\n" + "\n".join(mismatches)
