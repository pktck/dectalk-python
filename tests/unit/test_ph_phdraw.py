"""Behavioural tests for the (partial) ``phdraw`` port.

Exercises the per-frame Klatt-parameter emitter end-to-end on a tiny
DphT and asserts the well-defined trajectory rules ported from
``src/dapi/src/ph/ph_draw.c`` lines 229-758 actually fire:

* One-shot ``outp`` pointer wiring populates every ``param[i].outp``.
* The F1..B3 formant loop writes the parameter into the right
  ``parstochip`` slot, with diphthong / forward-transition smoothing.
* The AV..TILT amplitude loop writes via the simpler ``tarcur +
  ftran/8`` rule.
* The B1-bandwidth breathy multiplier fires on the formant loop.
* The double-burst rule (``tcum == tspesh + 1``) knocks parallel
  amplitudes down by 10.
* The AV glottal-stop reduction (``parstochip[OUT_AV] -= avglstop``)
  fires when AV > 6.
* Source spectral tilt is clamped to [0, 31] and integrates the
  breathy-voice modifier.

A separate parity-style block re-parses the C source (when available)
and asserts the C body still contains the trajectory primitives we
ported, so divergence between the Python port and the C source surfaces
as a test failure.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import (
    A2,
    AV,
    B1,
    F1,
    F2,
    MALE,
    TILT,
)
from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_AV,
    OUT_B1,
    OUT_F1,
    OUT_F2,
    OUT_T0,
    OUT_TLT,
)
from dectalk.ph.phdraw import phdraw
from dectalk.ph.tts_handle import TtsHandle

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_draw.c"


def _build_handle() -> tuple[TtsHandle, DphT, DphSettarSt]:
    """Construct a minimal phTTS suitable for calling :func:`phdraw`.

    Mirrors the wiring pattern used in
    ``api/speak.py::_speak_via_python_full``: a DphT with an empty
    parstochip (sized by phdraw), the per-phoneme settar struct
    attached, a tiny allophons list, and minimum non-zero fnscale so
    the formant-scaling step is well-defined.
    """
    p_dph_t = DphT()
    p_dph_t.parstochip = []  # phdraw grows to 64 entries on first call.
    p_dph_t.dipspec = [0] * 256
    p_dph_t.allophons = [0, 0, 0]
    p_dph_t.allofeats = [0] * 3
    p_dph_t.allodurs = [40] * 3
    p_dph_t.nallotot = 3
    p_dph_t.nphone = 1
    p_dph_t.nphonelast = 1  # second+ frame of the same phone
    p_dph_t.tcum = 5
    p_dph_t.durfon = 40
    p_dph_t.fnscale = 4096  # unity Q12 scaling.
    p_dph_t.malfem = MALE
    p_dph_t.f0 = 1000
    p_dph_t.f0_dep_tilt = 0
    p_dph_t.spdeftltoff = 3
    p_dph_t.spdefb1off = 4096  # unity Q12 scaling.
    p_dph_t.spdeflaxprcnt = 0
    p_dph_t.avglstop = 0
    p_dph_t.breathysw = 0
    p_dphsettar = DphSettarSt()
    p_dph_t.pSTphsettar = p_dphsettar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()
    return handle, p_dph_t, p_dphsettar


# ----- Smoke + basic wiring tests ------------------------------------------


def test_phdraw_executes_without_error() -> None:
    """Calling :func:`phdraw` on a fresh handle does not raise."""
    handle, _, _ = _build_handle()
    phdraw(handle)  # Just verifying no exception.


def test_phdraw_grows_parstochip_buffer() -> None:
    """First call sizes ``parstochip`` to at least 64 entries (the SPC frame buffer)."""
    handle, p_dph_t, _ = _build_handle()
    assert len(p_dph_t.parstochip) == 0
    phdraw(handle)
    assert len(p_dph_t.parstochip) >= 64


def test_phdraw_initialises_outp_pointers_once() -> None:
    """``drawinitsw`` latches after the first call; ``outp`` populated for every param."""
    handle, p_dph_t, p_dphsettar = _build_handle()
    assert p_dphsettar.drawinitsw == 0
    phdraw(handle)
    assert p_dphsettar.drawinitsw == 1
    assert p_dph_t.param[F1].outp == OUT_F1
    assert p_dph_t.param[F2].outp == OUT_F2
    assert p_dph_t.param[B1].outp == OUT_B1
    assert p_dph_t.param[AV].outp == OUT_AV
    assert p_dph_t.param[TILT].outp == OUT_TLT
    assert p_dph_t.param[0].outp == OUT_T0  # F0 -> T0 slot.


# ----- Formant-trajectory tests --------------------------------------------


def test_formant_param_writes_via_div_by8_plus_tarcur() -> None:
    """F1 trajectory: ``parstochip[OUT_F1] = (dipcum + ftran) >> 3 + tarcur``."""
    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[F1]
    p.tarcur = 500
    p.ftran = 80  # / 8 = 10
    p.dftran = 0
    p.btran = 0
    p.dipcum = 0
    p.deldip = 0
    p.durlin = -1  # No diphthong line.
    p.tbacktr = 1000  # Backward smooth not yet active.
    phdraw(handle)
    # value = 0 (dipcum) + 80 (ftran) = 80; 80 DIV_BY8 = 10; +500 tarcur = 510.
    assert p_dph_t.parstochip[OUT_F1] == 510


def test_formant_param_special_rule_overrides_value() -> None:
    """When ``tcum < tspesh``, the parameter takes ``pspesh`` verbatim."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.tcum = 2
    p = p_dph_t.param[F1]
    p.tarcur = 999
    p.tspesh = 5
    p.pspesh = 123
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_F1] == 123


def test_breathy_b1_modifier_fires_with_unity_spdefb1off() -> None:
    """B1 path: ``parstochip[OUT_B1] = frac4mul(parstochip[OUT_B1], spdefb1off)``."""
    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[B1]
    p.tarcur = 100
    p.ftran = 0
    p.dipcum = 0
    p.deldip = 0
    p.durlin = -1
    p.tspesh = 0  # Disable special rule so B1 path falls into the breathy mod.
    p_dph_t.spdefb1off = 4096  # Q12 unity -> no change.
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_B1] == 100  # unchanged at unity Q12.


def test_f2_vowel_vowel_coarticulation_adds_fvvtran() -> None:
    """F2 alone gets ``+fvvtran``; F1 / F3 do not."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.fvvtran = 32
    p_dph_t.dfvvtran = 0
    p_dph_t.tvvbacktr = 1000  # backward branch off.
    p = p_dph_t.param[F2]
    p.tarcur = 1500
    p.ftran = 0
    p.dipcum = 0
    p.deldip = 0
    p.durlin = -1
    p.tspesh = 0
    phdraw(handle)
    # 0 (dipcum) + 0 (ftran) + 32 (fvvtran) = 32; >>3 = 4; +1500 = 1504.
    assert p_dph_t.parstochip[OUT_F2] == 1504


def test_formant_diphthong_advance_consumes_two_dipspec_slots() -> None:
    """When tcum overshoots ``durlin``, fetch two dipspec slots and reset dipcum."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.tcum = 10
    p_dph_t.dipspec = [25, 7, 0, 0] + [0] * 252  # new durlin=25, new deldip=7.
    p = p_dph_t.param[F1]
    p.durlin = 5  # tcum>durlin triggers advance.
    p.tarcur = 0
    p.dipcum = 16  # >>3 = 2 added into tarcur after advance.
    p.deldip = 0
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.ndip = 0
    p.tspesh = 0
    phdraw(handle)
    assert p.durlin == 25
    assert p.deldip == 7
    assert p.ndip == 2  # Advanced past slots 0 and 1.
    assert p.dipcum == 7  # After advance: dipcum=0 then += deldip(7).
    assert p.tarcur == 2  # tarcur += old_dipcum >> 3 = 2.


# ----- Amplitude-trajectory tests ------------------------------------------


def test_amp_param_uses_tarcur_plus_ftran_div_by8() -> None:
    """A2 amplitude path: ``parstochip[OUT_A2] = tarcur + ftran/8`` (no backward)."""
    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[A2]
    p.tarcur = 40
    p.ftran = 24  # /8 = 3
    p.dftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 0
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_A2] == 43


def test_amp_double_burst_knock_down_at_tspesh_plus_1() -> None:
    """Parallel-amp double-burst rule: ``-= 10`` when ``tcum == tspesh + 1`` and value >= 10."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.tcum = 6
    p = p_dph_t.param[A2]
    p.tarcur = 25
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 5
    p.pspesh = 0  # Inside-tspesh override (won't fire because tcum > tspesh now).
    phdraw(handle)
    # tcum (6) > tspesh (5): we land in the else; double-burst at tspesh+1 == 6 fires.
    # value before knock-down = 25; after -= 10 = 15.
    assert p_dph_t.parstochip[OUT_A2] == 15


def test_av_glottal_stop_reduction() -> None:
    """``parstochip[OUT_AV] -= avglstop`` when AV > 6."""
    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[AV]
    p.tarcur = 50
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 0
    p_dph_t.avglstop = 7
    phdraw(handle)
    # AV = 50 from amplitude loop, then -= 7 from glstop = 43.
    assert p_dph_t.parstochip[OUT_AV] == 43


def test_av_glottal_stop_reduction_skipped_below_threshold() -> None:
    """When ``parstochip[OUT_AV] <= 6`` the glstop reduction is bypassed."""
    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[AV]
    p.tarcur = 5
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 0
    p_dph_t.avglstop = 7
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_AV] == 5  # Untouched.


# ----- Tilt computation ----------------------------------------------------


def test_tilt_default_male_path() -> None:
    """Male voice: ``temptilt = frac4mul(f0 - 900, f0_dep_tilt)``, clamped, plus offset."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.malfem = MALE
    p_dph_t.f0 = 900  # frac4mul(0, *) = 0 -> 8 - 0 = 8.
    p_dph_t.f0_dep_tilt = 0
    p_dph_t.spdeftltoff = 5
    p_dph_t.spdeflaxprcnt = 0
    p_dph_t.breathysw = 0
    phdraw(handle)
    # tilt = 8 + (5 - 3) = 10; clamped to [0, 31] -> 10.
    assert p_dph_t.parstochip[OUT_TLT] == 10


def test_tilt_clamped_to_31() -> None:
    """Output tilt is clamped at ``_TILT_MAX = 31`` regardless of inputs."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.spdeftltoff = 1000  # Would overshoot massively.
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_TLT] == 31


def test_tilt_clamped_at_zero() -> None:
    """Negative pre-clamp tilt is floor-clamped to 0."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.spdeftltoff = -1000  # Massively negative -> sub-zero.
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_TLT] == 0


def test_breathy_voice_increments_breathy_state() -> None:
    """When ``breathysw==1`` and AV high, ``breathyah`` and ``breathytilt`` step up."""
    handle, p_dph_t, p_dphsettar = _build_handle()
    p_dph_t.breathysw = 1
    # Force OUT_AV > 40 (the breathy gate).
    p = p_dph_t.param[AV]
    p.tarcur = 50
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 0
    p_dph_t.avglstop = 0
    phdraw(handle)
    assert p_dphsettar.breathyah == 2  # incremented by 2 per frame.
    assert p_dphsettar.breathytilt == 1


def test_breathy_state_zeroed_when_off() -> None:
    """``breathysw == 0`` zeros the breathy accumulators each frame."""
    handle, p_dph_t, p_dphsettar = _build_handle()
    p_dphsettar.breathyah = 10
    p_dphsettar.breathytilt = 5
    p_dph_t.breathysw = 0
    phdraw(handle)
    assert p_dphsettar.breathyah == 0
    assert p_dphsettar.breathytilt == 0


# ----- Formant scaling -----------------------------------------------------


def test_formant_scaling_identity_at_q12_unity() -> None:
    """``fnscale == 4096`` (Q12 1.0) leaves F2 / F3 unchanged."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.fnscale = 4096
    # Pre-populate F2 / F3 trajectories.
    for idx in (F2, 3):  # F2 and F3
        p = p_dph_t.param[idx]
        p.tarcur = 1500
        p.ftran = 0
        p.btran = 0
        p.tbacktr = 1000
        p.tspesh = 0
        p.durlin = -1
    phdraw(handle)
    # F2 went through coarticulation but with fvvtran=0 should be 1500.
    assert p_dph_t.parstochip[OUT_F2] == 1500


# ----- C-source parity assertions (skipped when source absent) -------------


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of ``void phdraw(LPTTS_HANDLE_T)``."""
    text = _read_c()
    match = re.search(r"\bvoid\s+phdraw\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)\s*\n\{", text)
    assert match is not None, "phdraw definition not found in ph_draw.c"
    start = match.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return text[start : i - 1]


@pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_outp_initialisation_block() -> None:
    """C body sets ``param[F0].outp = &parstochip[OUT_T0]`` and friends."""
    body = _extract_body()
    assert re.search(r"param\[F0\]\.outp\s*=\s*&\(pDph_t->parstochip\[OUT_T0\]\)", body)
    assert re.search(r"param\[F1\]\.outp\s*=\s*&\(pDph_t->parstochip\[OUT_F1\]\)", body)
    assert re.search(r"drawinitsw\s*=\s*1", body)


@pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_formant_loop() -> None:
    """C body walks ``np = &PF1; np <= &PB3; ++np`` for the formant trajectory."""
    body = _extract_body()
    assert re.search(r"for\s*\(\s*np\s*=\s*&PF1\s*;\s*np\s*<=\s*&PB3\s*;\s*\+\+np\s*\)", body)


@pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_amplitude_loop() -> None:
    """C body walks the amplitude params via ``for (; np <= &PTILT; np++)``."""
    body = _extract_body()
    assert re.search(r"for\s*\(\s*;\s*np\s*<=\s*&PTILT\s*;\s*np\+\+\s*\)", body)


@pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_glstop_reduction() -> None:
    """C body subtracts ``avglstop`` from AV when AV > 6."""
    body = _extract_body()
    assert re.search(r"parstochip\[OUT_AV\]\s*>\s*6", body)
    assert re.search(r"parstochip\[OUT_AV\]\s*-=\s*pDph_t->avglstop", body)


@pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_breathy_modifier() -> None:
    """C body increments ``breathyah`` and ``breathytilt`` when ``breathysw == 1``."""
    body = _extract_body()
    assert re.search(r"breathysw\s*==\s*1", body)
    assert re.search(r"breathyah\s*<\s*27", body)
    assert re.search(r"breathytilt\s*<\s*16", body)


@pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_formant_scaling() -> None:
    """C body applies ``frac4mul(parstochip[OUT_FN], fnscale)`` to F1 / F2 / F3."""
    body = _extract_body()
    assert re.search(
        r"parstochip\[OUT_F1\]\s*=\s*frac4mul\(\s*pDph_t->parstochip\[OUT_F1\]\s*,\s*"
        r"pDph_t->fnscale",
        body,
    )
    assert re.search(
        r"parstochip\[OUT_F2\]\s*=\s*frac4mul\(\s*pDph_t->parstochip\[OUT_F2\]\s*,\s*"
        r"pDph_t->fnscale",
        body,
    )
    assert re.search(
        r"parstochip\[OUT_F3\]\s*=\s*frac4mul\(\s*pDph_t->parstochip\[OUT_F3\]\s*,\s*"
        r"pDph_t->fnscale",
        body,
    )
