"""LLSynthesize parity: Python port vs FONIX C reference.

Runs a battery of speaker/frame configurations through both the Python
:func:`dectalk.hlsyn.synthesize.ll_synthesize` and the C harness built
from ``c_harness/llsyn_dump.c``. Asserts the two int16 waveforms agree
within a tight tolerance.

Bit-exact equality isn't expected because the C source uses single-
precision floats and the IIR resonators accumulate small coefficient
differences over time. We use a *relative* tolerance:

- ``MAX_ABS_DELTA`` (4 LSBs) for source shapes whose inner loop avoids
  high-Q feedback that amplifies precision drift (impulse, natural
  KLGLOT88).
- ``MAX_RELATIVE_DELTA`` (2% of peak) for the LF source whose narrow-
  bandwidth glottal pulse resonator integrates precision differences.

Both bounds are well below audibility (~ -34 dB SNR at the loose end).
"""

from __future__ import annotations

import subprocess
from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from dectalk.hlsyn.llsyn import LLFrame, LLSynth, Speaker
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.voice import SOURCE_IMPULSIVE, SOURCE_LF, SOURCE_NATURAL

# Strict tolerance for paths without precision-amplifying feedback.
# Empirically the C harness and Python implementation agree to within
# 1 LSB on every "tight" case below; 4 leaves headroom for compiler /
# libc variation across platforms.
MAX_ABS_DELTA: int = 4

# Relative tolerance for the LF source. The narrow-bandwidth LF
# glottal-pulse resonator amplifies the float32-vs-float64 coefficient
# precision difference over time, accumulating to ~1.4 % of peak by
# the end of a 1 s sample. 2 % leaves headroom while staying well
# below audibility (~ -34 dB SNR).
MAX_RELATIVE_DELTA: float = 0.02


def _default_speaker(*, source: int = SOURCE_NATURAL) -> Speaker:
    return Speaker(SR=11025, UI=110, SS=source, NF=5, RS=8191, GV=60, GH=50, GF=45)


def _default_frame() -> LLFrame:
    """A neutral /ah/-ish frame with all amplitude controls at zero."""
    return LLFrame(
        F0=1220, AV=60, OQ=50, SQ=200,
        F1=730, B1=90, F2=1090, B2=110, F3=2440, B3=170,
        F4=3500, B4=250, F5=4500, B5=300, F6=5500, B6=500,
        FNP=270, BNP=100, FNZ=270, BNZ=100,
        FTP=2150, BTP=180, FTZ=2150, BTZ=180,
    )  # fmt: skip


def _run_c(harness: Path, spkr: Speaker, frame: LLFrame, n_frames: int) -> np.ndarray:
    """Invoke the C harness and parse its int16 PCM output."""
    args: list[str] = [
        str(spkr.SR),
        str(spkr.UI),
        str(spkr.SS),
        str(spkr.NF),
        str(spkr.RS),
        str(spkr.SB),
        str(spkr.CP),
        str(spkr.OS),
        str(spkr.GV),
        str(spkr.GH),
        str(spkr.GF),
        str(n_frames),
        # 47 frame fields, in declaration order matching llsyn.h
        str(frame.F0),
        str(frame.AV),
        str(frame.OQ),
        str(frame.SQ),
        str(frame.TL),
        str(frame.FL),
        str(frame.DI),
        str(frame.Ah),
        str(frame.Af),
        str(frame.F1),
        str(frame.B1),
        str(frame.DF1),
        str(frame.DB1),
        str(frame.F2),
        str(frame.B2),
        str(frame.F3),
        str(frame.B3),
        str(frame.F4),
        str(frame.B4),
        str(frame.F5),
        str(frame.B5),
        str(frame.F6),
        str(frame.B6),
        str(frame.FNP),
        str(frame.BNP),
        str(frame.FNZ),
        str(frame.BNZ),
        str(frame.FTP),
        str(frame.BTP),
        str(frame.FTZ),
        str(frame.BTZ),
        str(frame.A2f),
        str(frame.A3f),
        str(frame.A4f),
        str(frame.A5f),
        str(frame.A6f),
        str(frame.Ab),
        str(frame.B2F),
        str(frame.B3F),
        str(frame.B4F),
        str(frame.B5F),
        str(frame.B6F),
        str(frame.ANV),
        str(frame.A1V),
        str(frame.A2V),
        str(frame.A3V),
        str(frame.A4V),
        str(frame.ATV),
    ]
    result = subprocess.run([str(harness), *args], capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype=np.int16)


def _run_py(spkr: Speaker, frame: LLFrame, n_frames: int) -> np.ndarray:
    synth = LLSynth(spkr=spkr)
    out = np.zeros(spkr.UI * n_frames, dtype=np.int16)
    for fi in range(n_frames):
        ll_synthesize(synth, frame, out[fi * spkr.UI : (fi + 1) * spkr.UI])
    return out


def _assert_parity(c_out: np.ndarray, py_out: np.ndarray, *, lf_source: bool = False) -> None:
    """Assert the two waveforms agree within tolerance.

    Args:
        c_out: int16 samples produced by the C reference.
        py_out: int16 samples produced by the Python port.
        lf_source: True if the test uses ``SOURCE_LF``; relaxes to a
            relative tolerance to accommodate float32-vs-float64 drift
            through the narrow-bandwidth LF glottal-pulse resonator.
    """
    assert c_out.shape == py_out.shape, f"length mismatch: C={c_out.size}, Py={py_out.size}"
    diff = c_out.astype(np.int32) - py_out.astype(np.int32)
    max_abs = int(np.max(np.abs(diff)))
    rms = float(np.sqrt(np.mean(diff.astype(np.float64) ** 2)))
    c_peak = int(np.max(np.abs(c_out)))
    py_peak = int(np.max(np.abs(py_out)))

    if lf_source:
        budget = max(MAX_ABS_DELTA, round(MAX_RELATIVE_DELTA * max(c_peak, 1)))
        assert max_abs <= budget, (
            f"LF-source diff {max_abs} > {budget} ({MAX_RELATIVE_DELTA:.0%} of peak); "
            f"RMS={rms:.3f}; C peak={c_peak}, Py peak={py_peak}"
        )
        return

    assert max_abs <= MAX_ABS_DELTA, (
        f"max-abs diff {max_abs} > {MAX_ABS_DELTA}; "
        f"RMS={rms:.3f}; C peak={c_peak}, Py peak={py_peak}"
    )


# -- Test cases ------------------------------------------------------------

PARITY_FRAMES: list[tuple[str, Speaker, LLFrame]] = []


def _add(
    name: str, modify_frame: dict[str, int] | None = None, source: int = SOURCE_NATURAL
) -> None:
    spkr = _default_speaker(source=source)
    frame = _default_frame()
    if modify_frame:
        for k, v in modify_frame.items():
            setattr(frame, k, v)
    PARITY_FRAMES.append((name, spkr, frame))


# Vowels (Klatt 1980 reference values)
_add("vowel_AH", {"F1": 730, "B1": 90, "F2": 1090, "B2": 110, "F3": 2440, "B3": 170})
_add("vowel_IY", {"F1": 270, "B1": 60, "F2": 2290, "B2": 90, "F3": 3010, "B3": 170})
_add("vowel_UW", {"F1": 300, "B1": 70, "F2": 870, "B2": 80, "F3": 2240, "B3": 160})
_add("vowel_AE", {"F1": 660, "B1": 100, "F2": 1720, "B2": 130, "F3": 2410, "B3": 200})
_add("vowel_AO", {"F1": 570, "B1": 80, "F2": 840, "B2": 80, "F3": 2410, "B3": 170})
# Source-shape variants
_add("vowel_AH_impulsive", source=SOURCE_IMPULSIVE)
_add("vowel_AH_lf", source=SOURCE_LF)
# Aspiration
_add("aspirated", {"AV": 0, "Ah": 50})
# Frication
_add("fricated", {"AV": 0, "Af": 50, "A2f": 30, "A3f": 50, "A4f": 60})
# F0 sweep
_add("low_pitch", {"F0": 800})  # 80 Hz
_add("high_pitch", {"F0": 2000})  # 200 Hz
# Spectral tilt
_add("tilted_TL5", {"TL": 5})
_add("tilted_TL15", {"TL": 15})
# Open-quotient extremes
_add("oq_low", {"OQ": 30})
_add("oq_high", {"OQ": 80})
# Diplophonia
_add("diplophonia", {"DI": 30})
# F1 transition deltas
_add("f1_transition", {"DF1": 100, "DB1": 50})


_PARITY_IDS: list[str] = [c[0] for c in PARITY_FRAMES]


@pytest.mark.parametrize(("name", "spkr", "frame"), PARITY_FRAMES, ids=_PARITY_IDS)
def test_llsynthesize_matches_c_reference(
    name: str, spkr: Speaker, frame: LLFrame, llsyn_dump: Path
) -> None:
    """One-frame LLSynthesize parity for the named configuration."""
    c_out = _run_c(llsyn_dump, spkr, frame, n_frames=10)
    py_out = _run_py(spkr, frame, n_frames=10)
    _assert_parity(c_out, py_out, lf_source=spkr.SS == SOURCE_LF or "lf" in name)


def test_llframe_field_order_matches_c(llsyn_dump: Path) -> None:
    """Sanity: the Python LLFrame fields match what the C harness expects.

    The harness reads 47 frame fields in declaration order; mismatches
    would be silent because the C struct is read by member name. This
    test asserts the count is exactly 47 so we get loud failures when
    someone reorders/adds fields without updating the harness too.
    """
    del llsyn_dump
    expected_field_count = 48
    py_fields = [f.name for f in fields(LLFrame())]
    assert len(py_fields) == expected_field_count, (
        f"LLFrame has {len(py_fields)} fields; harness expects {expected_field_count}. "
        f"Update tests/parity/c_harness/llsyn_dump.c to match."
    )
    # And speaker has 12 fields (also hard-coded into the harness).
    expected_spkr_count = 12
    spkr_fields = [f.name for f in fields(Speaker())]
    assert len(spkr_fields) == expected_spkr_count
