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

from dectalk.include.usp_codes import USP_DH, USP_TH
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


# ----- HLSyn area-loop tests (ph_draw.c lines 761-907) -----------------------


def test_hlsyn_area_loop_skipped_when_no_tspesh() -> None:
    """Loop is a no-op when neither AREAL/AREAB/TONGUEBODY has tspesh > 0."""
    from dectalk.ph.param_indices import AREAB, AREAL, TONGUEBODY  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    p_dph_t.param[AREAL].tspesh = 0
    p_dph_t.param[AREAB].tspesh = 0
    p_dph_t.param[TONGUEBODY].tspesh = 0
    # Pre-seed the flags so we can detect if the loop touched them.
    p_dph_t.in_brelease = 7
    p_dph_t.in_lclosure = 7
    p_dph_t.target_l = 42
    phdraw(handle)
    assert p_dph_t.in_brelease == 7
    assert p_dph_t.in_lclosure == 7
    assert p_dph_t.target_l == 42


def test_hlsyn_area_loop_pareab_clears_lrelease_when_tspesh_window_expired() -> None:
    """When ``tcum >= tspesh`` and current phone has no consonant feature, the
    PAREAB branch should clear ``in_lrelease`` and ``in_bclosure``."""
    from dectalk.ph.param_indices import AREAB  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    p_dph_t.allophons = [0, 0, 0]
    p_dph_t.nphone = 1
    p_dph_t.param[AREAB].tspesh = 5
    p_dph_t.tcum = 10  # past tspesh
    p_dph_t.in_lrelease = 1
    p_dph_t.in_bclosure = 1
    phdraw(handle)
    assert p_dph_t.in_lrelease == 0
    assert p_dph_t.in_bclosure == 0


def test_hlsyn_area_loop_ptongebody_sets_closure_at_tcum_zero_for_stop() -> None:
    """When ``tcum == 0`` and current phone has FSTOP, set
    ``in_tbclosure = 1`` and ``tbstep = -2``."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415
    from dectalk.ph.param_indices import TONGUEBODY  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    # A velar stop /K/ has FSTOP set; pick the US allophone code.
    k_code = (PFUSA << 8) | int(USPhoneme["K"])
    p_dph_t.allophons = [0, k_code, 0]
    p_dph_t.nphone = 1
    p_dph_t.param[TONGUEBODY].tspesh = 8
    p_dph_t.tcum = 0
    p_dph_t.in_tbclosure = 0
    p_dph_t.in_tbrelease = 1
    phdraw(handle)
    assert p_dph_t.in_tbclosure == 1
    assert p_dph_t.in_tbrelease == 0
    assert p_dph_t.tbstep == -2


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_hlsyn_area_loop() -> None:
    """C body has the ``for (; np <= &PTONGUEBODY; np++)`` HLSyn area loop."""
    body = _extract_body()
    assert re.search(
        r"for\s*\(\s*;\s*np\s*<=\s*&PTONGUEBODY\s*;\s*np\+\+\s*\)",
        body,
    )


# ----- Per-frame HLSyn state machine tests (ph_draw.c lines 2350-4300) ------


def _build_state_machine_handle(  # noqa: PLR0915 — state setup needs many fields
    *,
    nphone: int = 1,
    allophons: list[int] | None = None,
    allofeats: list[int] | None = None,
    allodurs: list[int] | None = None,
) -> tuple[TtsHandle, DphT, DphSettarSt]:
    """Build a handle with minimal state suitable for the state-machine tests.

    Uses three silent phones (code 0) by default; callers override via kwargs.
    """
    handle, p_dph_t, p_dphsettar = _build_handle()
    if allophons is not None:
        p_dph_t.allophons = allophons
    else:
        p_dph_t.allophons = [0, 0, 0]
    if allofeats is not None:
        p_dph_t.allofeats = allofeats
    else:
        p_dph_t.allofeats = [0] * len(p_dph_t.allophons)
    if allodurs is not None:
        p_dph_t.allodurs = allodurs
    else:
        p_dph_t.allodurs = [40] * len(p_dph_t.allophons)
    p_dph_t.nphone = nphone
    p_dph_t.nphonelast = nphone  # same phone, not start-of-phone
    p_dph_t.tcum = 5
    p_dph_t.nphonetot = len(p_dph_t.allophons)
    p_dph_t.tcumdur = 120
    p_dph_t.area_g = 0
    p_dph_t.area_l = 1000
    p_dph_t.area_b = 1000
    p_dph_t.area_tb = 1000
    p_dph_t.area_n = 0
    p_dph_t.area_flap = 1200
    p_dph_t.target_ag = 400
    p_dph_t.target_l = 1000
    p_dph_t.target_b = 1000
    p_dph_t.target_tb = 1000
    p_dph_t.target_ap = 0
    p_dph_t.agspeed = 2
    p_dph_t.last_area_b = 1000
    p_dph_t.last_area_l = 1000
    p_dph_t.last_area_tb = 1000
    p_dph_t.pressure = 0
    p_dph_t.pressure_drop = 0
    p_dph_t.pressure_gest = 0
    p_dph_t.syl_pressure = 0
    p_dph_t.stress_pulse = 0
    p_dph_t.delta_area_g = 0
    p_dph_t.delta_area_gst = 0
    p_dph_t.delta_area_gstop = 0
    p_dph_t.delta_a_forap = 0
    p_dph_t.nasal_step = 0
    p_dph_t.bstep = 0
    p_dph_t.lstep = 0
    p_dph_t.tbstep = 0
    p_dph_t.in_lclosure = 0
    p_dph_t.in_lrelease = 0
    p_dph_t.in_lfric = 0
    p_dph_t.in_bclosure = 0
    p_dph_t.in_brelease = 0
    p_dph_t.in_tbclosure = 0
    p_dph_t.in_tbrelease = 0
    p_dph_t.last_real_phon = 1000
    p_dph_t.sprate = 180  # normal speed
    p_dph_t.curspdef = [0] * 20  # large enough for SPD_F4=10
    p_dph_t.had_in_phrase_final = 0
    p_dphsettar.nframb = 50  # mid-utterance
    return handle, p_dph_t, p_dphsettar


def test_state_machine_phonestep_incremented_when_same_phone() -> None:
    """``phonestep`` increments each frame when ``nphone == nphonelast``."""
    handle, p_dph_t, _ = _build_state_machine_handle()
    p_dph_t.phonestep = 3
    p_dph_t.nphonelast = p_dph_t.nphone  # same phone
    phdraw(handle)
    assert p_dph_t.phonestep == 4


def test_state_machine_phonestep_reset_on_new_phone() -> None:
    """``phonestep`` resets to 0 when ``nphone != nphonelast``."""
    handle, p_dph_t, _ = _build_state_machine_handle()
    p_dph_t.phonestep = 7
    p_dph_t.nphonelast = p_dph_t.nphone + 1  # different phone
    phdraw(handle)
    assert p_dph_t.phonestep == 0


def test_state_machine_nasal_step_increments_during_nasal() -> None:
    """During a nasal phone, ``nasal_step`` increases and ``area_n`` follows table."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415
    from dectalk.ph.phdraw import _NASALIZATION  # noqa: PLC0415

    m_code = (PFUSA << 8) | int(USPhoneme["M"])
    # Use 5 phones: SIL, M, SIL, SIL, SIL to avoid index-out-of-range
    handle, p_dph_t, _ = _build_state_machine_handle(
        nphone=1,
        allophons=[0, m_code, 0, 0, 0],
        allofeats=[0] * 5,
        allodurs=[40] * 5,
    )
    p_dph_t.nasal_step = 2
    phdraw(handle)
    # nasal_step should have incremented (by +2 from the else branch)
    assert p_dph_t.nasal_step >= 3
    assert p_dph_t.area_n == _NASALIZATION[min(p_dph_t.nasal_step, 12)]


def test_state_machine_nasal_target_ag_set_during_nasal() -> None:
    """During a nasal phone, ``target_ag`` is set to 700."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    m_code = (PFUSA << 8) | int(USPhoneme["M"])
    handle, p_dph_t, _ = _build_state_machine_handle(
        nphone=1,
        allophons=[0, m_code, 0, 0, 0],
        allofeats=[0] * 5,
        allodurs=[40] * 5,
    )
    p_dph_t.target_ag = 0
    phdraw(handle)
    assert p_dph_t.target_ag == 700


def test_state_machine_pressure_builds_for_voiced() -> None:
    """For a voiced phone, ``pressure`` is incremented toward NOM_Sub_Pressure."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    # /V/ is voiced fricative
    v_code = (PFUSA << 8) | int(USPhoneme["V"])
    handle, p_dph_t, _ = _build_state_machine_handle(
        nphone=1,
        allophons=[0, v_code, 0, 0, 0],
        allofeats=[0] * 5,
        allodurs=[40] * 5,
    )
    p_dph_t.pressure = 0
    phdraw(handle)
    assert p_dph_t.pressure == 70


def test_state_machine_out_ag_written() -> None:
    """``parstochip[OUT_AG]`` is written to a non-negative value each call."""
    from dectalk.ph.param_indices import OUT_AG  # noqa: PLC0415

    handle, p_dph_t, _ = _build_state_machine_handle()
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_AG] >= 0


def test_state_machine_out_an_equals_area_n() -> None:
    """``parstochip[OUT_AN]`` equals ``area_n`` at the end of each call."""
    from dectalk.ph.param_indices import OUT_AN  # noqa: PLC0415

    handle, p_dph_t, _ = _build_state_machine_handle()
    p_dph_t.area_n = 160
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_AN] == p_dph_t.area_n


def test_state_machine_nphonelast_updated() -> None:
    """``nphonelast`` is set to ``nphone`` at the end of each call."""
    handle, p_dph_t, _ = _build_state_machine_handle()
    p_dph_t.nphonelast = 99  # stale value
    p_dph_t.nphone = 1
    phdraw(handle)
    assert p_dph_t.nphonelast == 1


def test_state_machine_dh_closure_not_at_word_boundary() -> None:
    """DH/TH within a word (not at word boundary): sets ``target_b = area_b = 0``
    while phonestep < allodurs - 1."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    dh_code = (PFUSA << 8) | int(USPhoneme["DH"])
    # boundary_val < FWBNEXT: use 0 (no boundary, less than the 0o140 threshold)
    handle, p_dph_t, _ = _build_state_machine_handle(
        nphone=1,
        allophons=[0, dh_code, 0, 0, 0],
        allofeats=[0, 0, 0, 0, 0],  # boundary = 0 < FWBNEXT
        allodurs=[10, 10, 10, 10, 10],
    )
    p_dph_t.phonestep = 3  # < allodurs[1] - 1 = 9
    p_dph_t.target_b = 500
    p_dph_t.area_b = 500
    phdraw(handle)
    # The DH rule should have set target_b = area_b = 0
    assert p_dph_t.target_b == 0
    assert p_dph_t.area_b == 0


def test_state_machine_flap_opens_after_half_duration() -> None:
    """For USP_DX (flap), ``area_flap`` increases during the second half of the phone."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    dx_code = (PFUSA << 8) | int(USPhoneme["DX"])
    handle, p_dph_t, _ = _build_state_machine_handle(
        nphone=1,
        allophons=[0, dx_code, 0, 0, 0],
        allofeats=[0] * 5,
        allodurs=[20, 20, 20, 20, 20],
    )
    p_dph_t.tcum = 12  # > half (10) → opening phase
    p_dph_t.area_flap = 0
    phdraw(handle)
    assert p_dph_t.area_flap > 0  # was increased


def test_state_machine_non_flap_phone_sets_area_flap_1200() -> None:
    """For a non-flap phone, ``area_flap`` is reset to 1200."""
    handle, p_dph_t, _ = _build_state_machine_handle()
    p_dph_t.area_flap = 42
    phdraw(handle)
    assert p_dph_t.area_flap == 1200


# ----- Lateral AV reduction + F3/F2 floor (ph_draw.c lines 4619-4644) -------
# These two unconditional rules are active on the US HLSYN build and are
# ported by _phdraw_lateral_av_and_f3_floor(), called at the end of phdraw().


def test_lateral_av_reduction_fires_for_usp_ll() -> None:
    """USP_LL allophone triggers the -6 dB AV reduction (ph_draw.c line 4629)."""
    from dectalk.include.usp_codes import USP_LL  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[AV]
    p.tarcur = 40
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 0
    p_dph_t.avglstop = 0  # Disable glottal-stop reduction.
    p_dph_t.allophons = [0, USP_LL, 0]
    p_dph_t.nphone = 1
    phdraw(handle)
    # AV from trajectory = 40; lateral reduction -6 = 34.
    assert p_dph_t.parstochip[OUT_AV] == 34


def test_lateral_av_reduction_clamps_to_zero() -> None:
    """Lateral AV reduction never takes AV below zero (ph_draw.c line 4633)."""
    from dectalk.include.usp_codes import USP_LL  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[AV]
    p.tarcur = 3  # After -6 would be -3 -> clamped to 0.
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 0
    p_dph_t.avglstop = 0
    p_dph_t.allophons = [0, USP_LL, 0]
    p_dph_t.nphone = 1
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_AV] == 0


def test_lateral_av_reduction_skipped_for_non_lateral() -> None:
    """A non-lateral allophone does not trigger the AV reduction."""
    from dectalk.include.usp_codes import USP_R  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[AV]
    p.tarcur = 40
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 0
    p_dph_t.avglstop = 0
    p_dph_t.allophons = [0, USP_R, 0]
    p_dph_t.nphone = 1
    phdraw(handle)
    # No lateral reduction; AV trajectory result is 40.
    assert p_dph_t.parstochip[OUT_AV] == 40


def test_f3_f2_floor_enforces_300hz_gap() -> None:
    """When F3 - F2 < 300, F3 is raised to F2 + 300 (ph_draw.c lines 4635-4638)."""
    from dectalk.ph.param_indices import OUT_F2, OUT_F3  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    # F2 = 1500, F3 = 1600 (gap = 100, below the 300-Hz floor).
    p_f2 = p_dph_t.param[F2]
    p_f2.tarcur = 1500
    p_f2.ftran = 0
    p_f2.btran = 0
    p_f2.tbacktr = 1000
    p_f2.tspesh = 0
    p_f2.dipcum = 0
    p_f2.deldip = 0
    p_f2.durlin = -1
    p_f3 = p_dph_t.param[3]  # F3 param index
    p_f3.tarcur = 1600
    p_f3.ftran = 0
    p_f3.btran = 0
    p_f3.tbacktr = 1000
    p_f3.tspesh = 0
    p_f3.dipcum = 0
    p_f3.deldip = 0
    p_f3.durlin = -1
    phdraw(handle)
    f2 = p_dph_t.parstochip[OUT_F2]
    f3 = p_dph_t.parstochip[OUT_F3]
    assert f3 == f2 + 300, f"Expected F3={f2 + 300}, got F3={f3} (F2={f2})"


def test_f3_f2_floor_not_applied_when_gap_sufficient() -> None:
    """When F3 - F2 >= 300, F3 is left unchanged (ph_draw.c lines 4635-4638)."""
    from dectalk.ph.param_indices import OUT_F2, OUT_F3  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    # F2 = 1200, F3 = 2500 (gap = 1300 >> 300).
    p_f2 = p_dph_t.param[F2]
    p_f2.tarcur = 1200
    p_f2.ftran = 0
    p_f2.btran = 0
    p_f2.tbacktr = 1000
    p_f2.tspesh = 0
    p_f2.dipcum = 0
    p_f2.deldip = 0
    p_f2.durlin = -1
    p_f3 = p_dph_t.param[3]  # F3 param index
    p_f3.tarcur = 2500
    p_f3.ftran = 0
    p_f3.btran = 0
    p_f3.tbacktr = 1000
    p_f3.tspesh = 0
    p_f3.dipcum = 0
    p_f3.deldip = 0
    p_f3.durlin = -1
    phdraw(handle)
    f2 = p_dph_t.parstochip[OUT_F2]
    f3 = p_dph_t.parstochip[OUT_F3]
    assert f3 - f2 >= 300


def test_tombuchler_block_is_callable_no_op() -> None:
    """``_phdraw_tombuchler_modulation_dead_code`` is a callable no-op."""
    from dectalk.ph.phdraw import _phdraw_tombuchler_modulation_dead_code  # noqa: PLC0415

    result = _phdraw_tombuchler_modulation_dead_code()
    assert result is None


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_tombuchler_dead_block() -> None:
    """C body has the ``#ifdef TOMBUCHLER`` guard (dead code on US HLSYN build)."""
    body = _extract_body()
    assert "TOMBUCHLER" in body


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_lateral_av_reduction() -> None:
    """C body has USP_LL in the lateral AV reduction check (ph_draw.c lines 4621-4629)."""
    body = _extract_body()
    assert "USP_LL" in body
    assert re.search(r"parstochip\[OUT_AV\]\s*-=\s*6", body)


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_f3_f2_floor() -> None:
    """C body has the 300-Hz F3/F2 floor rule (ph_draw.c lines 4635-4638)."""
    body = _extract_body()
    assert re.search(
        r"parstochip\[OUT_F3\]\s*-\s*pDph_t->parstochip\[OUT_F2\]\s*<\s*300",
        body,
    )


# ----- Initial-silence anticipation tests (ph_draw.c lines 929-1244) --------
# These exercise :func:`_phdraw_initial_silence_anticipation`, which fires
# only when ``nphone == 0``. Each test sets up a fresh DphT with
# ``nphone = 0`` and a specific feature on ``allophons[1]`` (the next
# phone), then asserts the expected HLSyn-state pre-positioning.


def _build_init_silence_handle(
    next_allo: int,
    next_feat_override: int | None = None,
) -> tuple[TtsHandle, DphT, DphSettarSt]:
    """Construct a handle with ``nphone == 0`` for initial-silence tests.

    Args:
        next_allo: The allophone code to place at ``allophons[1]``.
            For tests that need a synthetic phone with custom features
            (not in the real US allophone table), the caller can
            monkey-patch ``phone_feature`` via the override.
        next_feat_override: If set, force ``phone_feature(next_allo)``
            to return this value (used by tests that need a specific
            feature bitmap without depending on the US allophone table).
    """
    handle, p_dph_t, p_dphsettar = _build_handle()
    p_dph_t.nphone = 0
    p_dph_t.nphonelast = -1  # Force the once-per-phone init block to fire.
    p_dph_t.allophons = [0, next_allo, 0]
    p_dph_t.allofeats = [0, 0, 0]
    return handle, p_dph_t, p_dphsettar


def test_initial_silence_defaults_set_when_first_frame() -> None:
    """First frame of nphone==0 sets the documented HLSyn defaults."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_initial_silence_anticipation  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_init_silence_handle(USP_AA)
    # Pre-populate with sentinel values that should be reset.
    p_dph_t.last_real_phon = 5
    p_dph_t.area_g = 999
    p_dph_t.in_lclosure = 1
    # Call the anticipation block directly so the per-frame state
    # machine (which would mutate pressure further) doesn't run.
    _phdraw_initial_silence_anticipation(p_dph_t)
    assert p_dph_t.last_real_phon == 1000
    # The "next voiced -> vowel" sub-branch zeros area_g (line 1160).
    assert p_dph_t.area_g == 0
    # in_lclosure is zeroed by the defaults block (940-963) and the
    # voiced-next sub-block (1112).
    assert p_dph_t.in_lclosure == 0
    # Pressure default from C line 947 (the voiced-vowel branch
    # doesn't touch pressure).
    assert p_dph_t.pressure == 200


def test_initial_silence_skipped_when_nphone_nonzero() -> None:
    """No mutation when ``nphone != 0``."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415

    handle, p_dph_t, _ = _build_init_silence_handle(USP_AA)
    p_dph_t.nphone = 1  # Override -- not in initial silence.
    p_dph_t.nphonelast = 1
    p_dph_t.last_real_phon = 5
    p_dph_t.area_g = 999
    phdraw(handle)
    # Defaults block must not fire.
    assert p_dph_t.last_real_phon == 5


def test_initial_silence_voiced_vowel_next_opens_glottis() -> None:
    """Voiced vowel next-phone branch (C lines 1107, 1154-1167)."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_initial_silence_anticipation  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_init_silence_handle(USP_AA)
    _phdraw_initial_silence_anticipation(p_dph_t)
    # FVOWEL & FVOICD next -> area_g = 0, agspeed = 1, area_l = 1000.
    assert p_dph_t.area_g == 0
    assert p_dph_t.agspeed == 1
    assert p_dph_t.area_l == 1000
    assert p_dph_t.area_b == 1000
    assert p_dph_t.target_l == 1000
    assert p_dph_t.area_n == 0
    assert p_dph_t.nasal_step == 0


def test_initial_silence_dh_next_clamps_target_b_to_zero() -> None:
    """USP_DH next-phone triggers the special closure rule (C lines 1226-1242)."""
    from dectalk.ph.phdraw import _phdraw_initial_silence_anticipation  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_init_silence_handle(USP_DH)
    _phdraw_initial_silence_anticipation(p_dph_t)
    assert p_dph_t.target_b == 0


def test_initial_silence_th_next_clamps_target_b_to_zero() -> None:
    """USP_TH next-phone triggers the special closure rule (C lines 1226-1242)."""
    from dectalk.ph.phdraw import _phdraw_initial_silence_anticipation  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_init_silence_handle(USP_TH)
    _phdraw_initial_silence_anticipation(p_dph_t)
    assert p_dph_t.target_b == 0


def test_initial_silence_unvoiced_next_opens_glottis_wide() -> None:
    """Unvoiced next-phone -> area_g = target_ag = 1410 (C lines 1216-1224)."""
    from dectalk.ph.phdraw import _phdraw_initial_silence_anticipation  # noqa: PLC0415

    # USP_TH is unvoiced fricative (FOBST but not FVOICD).
    _handle, p_dph_t, _ = _build_init_silence_handle(USP_TH)
    _phdraw_initial_silence_anticipation(p_dph_t)
    # The unvoiced-else branch fires (line 1218); but the DH/TH
    # special-rule below it sets target_b = 0 -- doesn't touch area_g.
    assert p_dph_t.area_g == 1410
    assert p_dph_t.target_ag == 1410


def test_initial_silence_m_next_drops_lips() -> None:
    """USP_M next-phone (nasal labial) zeros area_l + target_l (C line 1200-1206)."""
    from dectalk.include.usp_codes import USP_M as _USP_M  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_initial_silence_anticipation  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_init_silence_handle(_USP_M)
    _phdraw_initial_silence_anticipation(p_dph_t)
    # FNASAL + FVOICD; USP_M sets target_ag = NOM_VOIC_GLOT_AREA = 0.
    assert p_dph_t.target_ag == 0
    # The /m/ branch (else of line 1185) zeros lips.
    assert p_dph_t.area_l == 0
    assert p_dph_t.target_l == 0
    # nasal_step = 7, area_n = 200 (set before /m/ branch).
    assert p_dph_t.nasal_step == 7
    assert p_dph_t.target_narea == 240


def test_initial_silence_n_next_sets_target_ag() -> None:
    """USP_N next-phone sets target_ag to NOM_VOIC_GLOT_AREA (C lines 1172-1183).

    Also exercises the UK_N-bug branch: because the C source's
    ``== UK_N`` comparison is against the unshifted small integer
    32 (l_all_ph.h:163), it never matches a US allophone (which
    carries the PFUSA font prefix). The ``else`` branch fires and
    zeros the lips, not the blade.
    """
    from dectalk.include.usp_codes import USP_N as _USP_N  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_initial_silence_anticipation  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_init_silence_handle(_USP_N)
    _phdraw_initial_silence_anticipation(p_dph_t)
    # USP_N matches the C source's `==USP_N` branch (line 1173).
    assert p_dph_t.target_ag == 0  # NOM_VOIC_GLOT_AREA on US.
    # The UK_N comparison never matches on the US path -> lips zeroed.
    assert p_dph_t.area_l == 0
    assert p_dph_t.target_l == 0


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_initial_silence_branch() -> None:
    """C body has the ``nphone == 0`` branch (ph_draw.c lines 929-1244)."""
    body = _extract_body()
    assert "pDph_t->nphone == 0" in body
    assert "in intial silence anticipate" in body
    # Sanity-check a few of the unique field writes we ported.
    assert "pDph_t->last_real_phon = 1000" in body
    assert re.search(r"pDph_t->target_ag\s*=\s*400", body)
    assert "USP_DH" in body
    assert "USP_TH" in body


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_initial_silence_nom_constants() -> None:
    """C body references the NOM_* VTM constants the port mirrors."""
    body = _extract_body()
    assert "NOM_VOIC_GLOT_AREA" in body
    assert "NOM_Open_Glottis" in body
    assert "NOM_VOICED_OBSTRUENT" in body
    assert "NOM_Fricative_Opening" in body
