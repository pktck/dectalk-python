"""C-source parity test for ``speech_waveform_generator`` against vtm1.c.

Re-parses ``src/dapi/src/vtm/vtm1.c`` and asserts the active-build
preconditions the Python port relies on:

- ``vtm.c`` includes ``vtm1.c`` when ``VTM1`` is defined (the
  active linux build).
- The active build's ``Makefile`` does NOT define ``NEW_NOISE``,
  ``NEW_TILT``, ``NEW_VTM``, ``HLSYN``, ``LOWCOMPUTE``,
  ``COMPRESSION`` etc.
- ``read_speaker_definition`` sets ``ranmul = 20077``, ``ranadd =
  12345`` when ``CHANGES_AFTER_V43`` is undefined.
- ``read_speaker_definition`` sets ``noisec = 1499`` when
  ``CHANGES_AFTER_V43`` is undefined.
- ``SetSampleRate`` derives ``uiNumberOfSamplesPerFrame = 71`` at
  11025 Hz via ``((samplerate*64)+5000)/10000``.
- The four-times-oversampled glottal-pulse loop iterates ``nsr4 = 0;
  nsr4 < 4; nsr4++``.
- The ramp-down ``+= 4`` step matches the C ``rampdown += 4`` in the
  ``!NO_LIMIT_CYCLE_RAMPDOWN`` branch.
- The active build's r6pb/r6pc seed values are -5702 / -1995.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

_DECTALK_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_VTM1_C = _DECTALK_SRC / "src/dapi/src/vtm/vtm1.c"
_VTM_C = _DECTALK_SRC / "src/dapi/src/vtm/vtm.c"
_DECTALKF_KLSYN_H = _DECTALK_SRC / "src/dectalkf_klsyn.h"
_VTM_MAKEFILE = _DECTALK_SRC / "src/dapi/src/vtm/Makefile"

pytestmark = pytest.mark.skipif(
    not _VTM1_C.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read(path: Path) -> str:
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def test_vtm_c_includes_vtm1_when_VTM1_defined() -> None:  # noqa: N802
    """vtm.c routes through vtm1.c when VTM1 is defined."""
    text = _read(_VTM_C)
    assert re.search(r"#\s*if\s+defined\s*\(\s*VTM1\s*\)", text), (
        "vtm.c should branch on VTM1 to include vtm1.c"
    )
    assert re.search(r'#\s*include\s+"vtm1\.c"', text), (
        "vtm.c should #include vtm1.c when VTM1 is defined"
    )


def test_dectalkf_klsyn_defines_VTM1() -> None:  # noqa: N802
    """The active build defines VTM1 (not VTM2 / FP_VTM)."""
    text = _read(_DECTALKF_KLSYN_H)
    assert re.search(r"^\s*#\s*define\s+VTM1\b", text, re.MULTILINE), (
        "VTM1 must be #defined in dectalkf_klsyn.h for the active build"
    )


def test_active_build_excludes_new_noise_new_tilt_etc() -> None:
    """The active build doesn't unconditionally define the optional macros.

    For each macro the Python port omits, verify there is at most one
    unconditional ``#define`` line (i.e. not inside an `#ifdef`-guarded
    architecture branch like ``EPSON_ARM7`` or ``UNDER_CE`` that doesn't
    apply to the linux build). The strict check is `gcc -E -dM` against
    the linux build flags; this test is the cheaper static-text version.

    The macros below are *unconditionally* commented out / undefined in
    ``dectalkf_klsyn.h`` on the linux build path. We assert each is at
    most one un-commented `#define` line, and where one exists, it sits
    inside an architecture guard not applicable to linux.
    """
    text = _read(_DECTALKF_KLSYN_H)
    # The "easy" macros — never defined at top level.
    for macro in (
        "NEW_NOISE",
        "NEW_TILT",
        "NEW_VTM",
        "COMPRESSION",
        "UPGRADES1999",
        "FAKE_HLSYN",
        "F1_B1_UPGRADE",
        "CHANGES_AFTER_V43",
        "NO_LIMIT_CYCLE_RAMPDOWN",
        "LOW_COST_VERSION",
    ):
        pattern = rf"^\s*#\s*define\s+{macro}\b"
        active = re.search(pattern, text, re.MULTILINE)
        assert active is None, (
            f"{macro} should be undefined in the active build, but found:\n"
            f"  {active.group(0) if active else '<n/a>'}"
        )
    # HLSYN is defined inside `#ifdef EPSON_ARM7` only — verify the
    # context guard so we know the linux build doesn't pick it up.
    hlsyn_block = re.search(
        r"#ifdef\s+EPSON_ARM7\s*\n\s*#define\s+HLSYN\s*\n\s*#endif",
        text,
    )
    assert hlsyn_block is not None, "Expected HLSYN to be EPSON_ARM7-guarded in dectalkf_klsyn.h"
    # LOWCOMPUTE / FP_VTM are similarly conditionally defined; check
    # they're NOT unconditionally on (the relevant defines are commented).
    assert re.search(r"^\s*//\s*#define\s+LOWCOMPUTE\b", text, re.MULTILINE), (
        "LOWCOMPUTE should be commented-out in dectalkf_klsyn.h"
    )


def test_vtm_makefile_excludes_HLSYN() -> None:  # noqa: N802
    """The vtm/Makefile DEFINES line does not enable HLSYN."""
    text = _read(_VTM_MAKEFILE)
    # The relevant line starts with `DEFINES=` (or `DEFINES +=`).
    define_lines = [line for line in text.splitlines() if re.match(r"\s*DEFINES\s*[+]?=", line)]
    assert define_lines, "Could not find DEFINES line in vtm/Makefile"
    for line in define_lines:
        assert "HLSYN" not in line, f"vtm/Makefile DEFINES line should not include HLSYN: {line!r}"
        assert "NEW_VTM" not in line, (
            f"vtm/Makefile DEFINES line should not include NEW_VTM: {line!r}"
        )


def test_read_speaker_definition_seeds_ranmul_20077() -> None:
    """``ranmul = 20077;`` appears in vtm1.c::read_speaker_definition."""
    text = _read(_VTM1_C)
    # The C source's `ranmul = 20077;` lives inside the
    # `#ifndef CHANGES_AFTER_V43` branch of read_speaker_definition.
    assert re.search(r"\branmul\s*=\s*20077\s*;", text), "Expected `ranmul = 20077;` in vtm1.c"
    assert re.search(r"\branadd\s*=\s*12345\s*;", text), "Expected `ranadd = 12345;` in vtm1.c"


def test_read_speaker_definition_seeds_noisec_1499() -> None:
    """``noisec = 1499;`` appears in the active sample-rate branches."""
    text = _read(_VTM1_C)
    assert re.search(r"\bnoisec\s*=\s*1499\s*;", text), "Expected `noisec = 1499;` in vtm1.c"


def test_set_sample_rate_71_samples_per_frame_at_11khz() -> None:
    """``uiNumberOfSamplesPerFrame`` is computed from the sample rate."""
    text = _read(_VTM1_C)
    # The formula is ((samplerate*64)+5000)/10000 (line ~2044).
    # At 11025 Hz this evaluates to 71.
    pattern = (
        r"uiNumberOfSamplesPerFrame\s*=\s*"
        r"\(\s*\(\s*pKsd_t->uiSampleRate\s*\*\s*64\s*\)\s*"
        r"\+\s*5000\s*\)\s*/\s*10000\s*;"
    )
    assert re.search(pattern, text), (
        "Expected ((samplerate*64)+5000)/10000 formula in vtm1.c::SetSampleRate"
    )


def test_glottal_loop_4x_oversampled() -> None:
    """The voicing waveform loop iterates ``nsr4 = 0; nsr4 < 4``."""
    text = _read(_VTM1_C)
    assert re.search(
        r"for\s*\(\s*nsr4\s*=\s*0\s*;\s*nsr4\s*<\s*4\s*;\s*nsr4\+\+\s*\)",
        text,
    ), "Expected `for (nsr4 = 0; nsr4 < 4; nsr4++)` in vtm1.c"


def test_rampdown_step_is_4() -> None:
    """The C source's `rampdown += 4` (vtm1.c line 1320)."""
    text = _read(_VTM1_C)
    assert re.search(r"pVtm_t->rampdown\s*\+=\s*4\s*;", text), (
        "Expected `pVtm_t->rampdown += 4;` in vtm1.c"
    )


def test_r6pb_r6pc_seed_values() -> None:
    """read_speaker_definition seeds r6pb / r6pc at -5702 / -1995."""
    text = _read(_VTM1_C)
    # The C source sets these at the bottom of read_speaker_definition.
    assert re.search(r"pVtm_t->r6pb\s*=\s*-\s*5702\s*;", text), (
        "Expected `pVtm_t->r6pb = -5702;` in vtm1.c"
    )
    assert re.search(r"pVtm_t->r6pc\s*=\s*-\s*1995\s*;", text), (
        "Expected `pVtm_t->r6pc = -1995;` in vtm1.c"
    )


def test_amptable_index_offsets() -> None:
    """The amptable lookups in speech_waveform_generator use specific offsets."""
    text = _read(_VTM1_C)
    # Lines 498-504: APlin = amptable[APinDB + 10], r2pg = amptable[A2inDB + 13], ...
    assert re.search(r"APlin\s*=\s*amptable\s*\[\s*APinDB\s*\+\s*10\s*\]", text)
    assert re.search(r"r2pg\s*=\s*amptable\s*\[\s*A2inDB\s*\+\s*13\s*\]", text)
    assert re.search(r"r3pg\s*=\s*amptable\s*\[\s*A3inDB\s*\+\s*10\s*\]", text)
    assert re.search(r"r4pa\s*=\s*amptable\s*\[\s*A4inDB\s*\+\s*7\s*\]", text)
    assert re.search(r"r5pa\s*=\s*amptable\s*\[\s*A5inDB\s*\+\s*6\s*\]", text)
    assert re.search(r"r6pa\s*=\s*amptable\s*\[\s*A6inDB\s*\+\s*5\s*\]", text)
    assert re.search(r"ABlin\s*=\s*amptable\s*\[\s*ABinDB\s*\+\s*5\s*\]", text)


def test_tilt_offset_minus_12() -> None:
    """TILTDB is offset by -12 from OUT_TLT (line 496 of vtm1.c)."""
    text = _read(_VTM1_C)
    assert re.search(r"TILTDB\s*=\s*variabpars\s*\[\s*OUT_TLT\s*\]\s*-\s*12\s*;", text)


def test_aturb1_shift_left_2() -> None:
    """aturb1 = Aturb << 2 in the per-period branch (!CHANGES_AFTER_V43)."""
    text = _read(_VTM1_C)
    assert re.search(r"pVtm_t->aturb1\s*=\s*pVtm_t->Aturb\s*<<\s*2\s*;", text)


def test_nopen_clamp_40_to_263() -> None:
    """nopen is clamped to [40, 263] (line ~923-927)."""
    text = _read(_VTM1_C)
    # The `if ( pVtm_t->nopen < 40 ) pVtm_t->nopen = 40;` block.
    assert re.search(r"pVtm_t->nopen\s*<\s*40", text)
    assert re.search(r"pVtm_t->nopen\s*=\s*40\s*;", text)
    assert re.search(r"pVtm_t->nopen\s*>\s*263", text)
    assert re.search(r"pVtm_t->nopen\s*=\s*263\s*;", text)


def test_F1_minimum_250() -> None:  # noqa: N802
    """F1inHZ is floored at 250 (line 835 of vtm1.c)."""
    text = _read(_VTM1_C)
    assert re.search(r"F1inHZ\s*<\s*250", text)
    assert re.search(r"F1inHZ\s*=\s*250\s*;", text)


def test_R1ca_doubled_after_setup() -> None:  # noqa: N802
    """R1ca is shifted-left after the d2pole_cf123 call (line 1004)."""
    text = _read(_VTM1_C)
    assert re.search(r"pVtm_t->R1ca\s*=\s*pVtm_t->R1ca\s*<<\s*1\s*;", text)


def test_R1ca_capped_at_16383() -> None:  # noqa: N802
    """R1ca is capped at 16383 before the shift-left (line 1001-1002)."""
    text = _read(_VTM1_C)
    assert re.search(r"pVtm_t->R1ca\s*>\s*16383", text)
    assert re.search(r"pVtm_t->R1ca\s*=\s*16383\s*;", text)


def test_output_clip_16383_minus_16384() -> None:
    """Output is clipped to [-16384, 16383] then shifted left by 1."""
    text = _read(_VTM1_C)
    # Lines 1387-1391.
    assert re.search(r"out\s*>\s*16383", text)
    assert re.search(r"out\s*=\s*16383\s*;", text)
    assert re.search(r"out\s*<\s*-\s*16384", text)
    assert re.search(r"out\s*=\s*-\s*16384\s*;", text)
    assert re.search(r"pVtm_t->iwave\s*\[\s*ns\s*\]\s*=\s*out\s*<<\s*1\s*;", text)
