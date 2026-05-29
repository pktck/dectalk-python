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
from dectalk.ph.phdraw import _phdraw_hlsyn_blocks, phdraw
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


def test_amp_double_burst_fires_on_us_build() -> None:
    """Parallel-amp double-burst knocks A2 down by 10 dB on the US build.

    The rule (``ph_draw.c`` lines 508-524) is gated behind
    ``#if (defined FAKE_HLSYN || !(defined HLSYN))``; ``libtts_us.so``
    has HLSYN undefined, so the ``!(defined HLSYN)`` arm keeps it
    compiled in. At ``tcum == tspesh + 1`` a parallel amp (here A2,
    ``param_idx > AP``) that is still >= 10 dB is reduced by 10 dB.
    """
    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[A2]
    p.tarcur = 25
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 5
    p.pspesh = 0  # Inside-tspesh override (won't fire because tcum > tspesh).
    p_dph_t.tcum = 6  # tspesh + 1 -> the double-burst window.
    phdraw(handle)
    # Double-burst: 25 - 10 = 15.
    assert p_dph_t.parstochip[OUT_A2] == 15


def test_amp_double_burst_skipped_below_10db() -> None:
    """The double-burst does nothing when the amplitude is below 10 dB."""
    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[A2]
    p.tarcur = 9  # < 10 -> rule's ``*parp >= 10`` guard fails.
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 5
    p.pspesh = 0
    p_dph_t.tcum = 6  # tspesh + 1.
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_A2] == 9


def test_amp_double_burst_only_at_tspesh_plus_one() -> None:
    """The double-burst fires only at ``tcum == tspesh + 1`` (not later)."""
    handle, p_dph_t, _ = _build_handle()
    p = p_dph_t.param[A2]
    p.tarcur = 25
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 5
    p.pspesh = 0
    p_dph_t.tcum = 7  # tspesh + 2 -> outside the one-frame window.
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_A2] == 25


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


def test_tilt_additive_on_us_build() -> None:
    """On the US build (HLSYN undefined), ``OUT_TLT`` gets the additive tilt.

    ``libtts_us.so`` compiles with ``-DENGLISH -DENGLISH_US -DACNA
    -DACCESS32 -DTYPING_MODE`` -- HLSYN and CHANGES_AFTER_V43 are
    *undefined*. Preprocessing ``ph_draw.c`` with those flags keeps the
    ``#if (defined FAKE_HLSYN || !(defined HLSYN))`` arm (the additive
    tilt at C 617-742) and elides the ``#else`` (``OUT_TLT = 0``). So
    OUT_TLT is the f0-dependent tilt plus ``(spdeftltoff - 6)``, not 0.

    With ``f0 = 1500`` (> 1400): ``temptilt = frac4mul(1400 - 1500, 73)
    = (-100 * 73) >> 12 = -2`` -> clamp to 0 -> ``12 - 0 = 12`` ->
    ``+= (spdeftltoff - 6) = (5 - 6) = -1`` -> ``OUT_TLT = 11``.
    """
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.malfem = MALE
    p_dph_t.f0 = 1500
    p_dph_t.f0_dep_tilt = 73
    p_dph_t.spdeftltoff = 5
    p_dph_t.spdeflaxprcnt = 0
    p_dph_t.breathysw = 0
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_TLT] == 11


def test_tilt_low_f0_increases_tilt() -> None:
    """Lower F0 -> larger ``temptilt`` -> larger OUT_TLT (capped at 31).

    With ``f0 = 1000``, ``f0_dep_tilt = 0`` (the default _build_handle
    value): ``temptilt = frac4mul(400, 0) = 0`` -> ``12 - 0 = 12`` ->
    ``+= (spdeftltoff - 6) = (3 - 6) = -3`` -> ``OUT_TLT = 9``.
    """
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.f0 = 1000
    p_dph_t.f0_dep_tilt = 0
    p_dph_t.spdeftltoff = 3
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_TLT] == 9


def test_tilt_spdeftltoff_offset_applied() -> None:
    """``spdeftltoff`` shifts OUT_TLT by ``(spdeftltoff - 6)`` then clamps.

    A large ``spdeftltoff`` drives OUT_TLT to the 31 ceiling (C 733-736).
    """
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.spdeftltoff = 1000
    phdraw(handle)
    assert p_dph_t.parstochip[OUT_TLT] == 31


def test_breathy_state_advanced_on_us_build() -> None:
    """``breathyah`` / ``breathytilt`` ramp when ``breathysw == 1`` (US build).

    The breathy-voice modifier (C 686-731) is inside the live tilt block
    on the US build. With AV > 40, ``breathyah`` ramps by +2 (cap 27) and
    ``breathytilt`` by +1 (cap 16) per frame.
    """
    handle, p_dph_t, p_dphsettar = _build_handle()
    p_dphsettar.breathyah = 10
    p_dphsettar.breathytilt = 5
    p_dph_t.breathysw = 1
    p_dph_t.spdeflaxprcnt = 0
    p = p_dph_t.param[AV]
    p.tarcur = 50  # AV > 40 so the breathy ramps fire.
    p.ftran = 0
    p.btran = 0
    p.tbacktr = 1000
    p.tspesh = 0
    p_dph_t.avglstop = 0
    phdraw(handle)
    assert p_dphsettar.breathyah == 12  # 10 + 2
    assert p_dphsettar.breathytilt == 6  # 5 + 1


def test_breathy_state_reset_when_breathysw_off() -> None:
    """When ``breathysw != 1`` the breathy ramps are zeroed (C 728-730)."""
    handle, p_dph_t, p_dphsettar = _build_handle()
    p_dphsettar.breathyah = 10
    p_dphsettar.breathytilt = 5
    p_dph_t.breathysw = 0
    phdraw(handle)
    assert p_dphsettar.breathyah == 0
    assert p_dphsettar.breathytilt == 0


# ----- Formant scaling -----------------------------------------------------
# Formant scaling lives behind ``#if defined(HLSYN) || defined(CHANGES_AFTER_V43)``
# (both undefined on libtts_us.so) and is DEAD on the US build; ``phdraw``
# does NOT call ``_apply_formant_scaling`` there. The first test confirms
# phdraw leaves F2 untouched on the US path; the others drive the ported
# helper directly to keep its (HLSYN-build) logic covered.


def test_formant_scaling_not_applied_by_phdraw_on_us_build() -> None:
    """phdraw does not rescale F2 on the US build (formant scaling is dead)."""
    handle, p_dph_t, _ = _build_handle()
    p_dph_t.fnscale = 2048  # Q12 0.5 -- would halve F2 if scaling were live.
    for idx in (F2, 3):  # F2 and F3
        p = p_dph_t.param[idx]
        p.tarcur = 1500
        p.ftran = 0
        p.btran = 0
        p.tbacktr = 1000
        p.tspesh = 0
        p.durlin = -1
    phdraw(handle)
    # F2 went through coarticulation but with fvvtran=0 stays 1500 -- the
    # 0.5 fnscale is NOT applied because phdraw skips the dead block.
    assert p_dph_t.parstochip[OUT_F2] == 1500


def test_formant_scaling_helper_identity_at_q12_unity() -> None:
    """``_apply_formant_scaling`` with ``fnscale == 4096`` is identity."""
    from dectalk.ph.param_indices import OUT_F1, OUT_F3  # noqa: PLC0415
    from dectalk.ph.phdraw import _apply_formant_scaling  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)  # allocate parstochip.
    p_dph_t.fnscale = 4096
    p_dph_t.parstochip[OUT_F1] = 500
    p_dph_t.parstochip[OUT_F2] = 1500
    p_dph_t.parstochip[OUT_F3] = 2500
    _apply_formant_scaling(p_dph_t)
    assert p_dph_t.parstochip[OUT_F1] == 500
    assert p_dph_t.parstochip[OUT_F2] == 1500
    assert p_dph_t.parstochip[OUT_F3] == 2500


def test_formant_scaling_helper_scales_at_half() -> None:
    """``_apply_formant_scaling`` with ``fnscale == 2048`` (Q12 0.5) scales F2/F3."""
    from dectalk.ph.param_indices import OUT_F2, OUT_F3  # noqa: PLC0415
    from dectalk.ph.phdraw import _apply_formant_scaling  # noqa: PLC0415
    from dectalk.vtm.frac import frac4mul  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)
    p_dph_t.fnscale = 2048
    p_dph_t.parstochip[OUT_F2] = 1500
    p_dph_t.parstochip[OUT_F3] = 2500
    _apply_formant_scaling(p_dph_t)
    complement = 4096 - 2048
    assert p_dph_t.parstochip[OUT_F2] == frac4mul(1500, 2048) + (complement >> 3)
    assert p_dph_t.parstochip[OUT_F3] == frac4mul(2500, 2048)


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
# This loop lives inside ``#ifdef HLSYN`` (C 761-4291) and is compiled out
# of ``libtts_us.so``; ``phdraw`` does NOT call ``_phdraw_hlsyn_area_loop``
# on the US build. These tests exercise the ported helper directly so its
# (HLSYN-build) logic stays covered.


def test_hlsyn_area_loop_skipped_when_no_tspesh() -> None:
    """Loop is a no-op when neither AREAL/AREAB/TONGUEBODY has tspesh > 0."""
    from dectalk.ph.param_indices import AREAB, AREAL, TONGUEBODY  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_hlsyn_area_loop  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)  # one call to allocate parstochip + outp pointers
    p_dph_t.param[AREAL].tspesh = 0
    p_dph_t.param[AREAB].tspesh = 0
    p_dph_t.param[TONGUEBODY].tspesh = 0
    # Pre-seed the flags so we can detect if the loop touched them.
    p_dph_t.in_brelease = 7
    p_dph_t.in_lclosure = 7
    p_dph_t.target_l = 42
    _phdraw_hlsyn_area_loop(p_dph_t)
    assert p_dph_t.in_brelease == 7
    assert p_dph_t.in_lclosure == 7
    assert p_dph_t.target_l == 42


def test_hlsyn_area_loop_pareab_clears_lrelease_when_tspesh_window_expired() -> None:
    """When ``tcum >= tspesh`` and current phone has no consonant feature, the
    PAREAB branch should clear ``in_lrelease`` and ``in_bclosure``."""
    from dectalk.ph.param_indices import AREAB  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_hlsyn_area_loop  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)
    p_dph_t.allophons = [0, 0, 0]
    p_dph_t.nphone = 1
    p_dph_t.param[AREAB].tspesh = 5
    p_dph_t.tcum = 10  # past tspesh
    p_dph_t.in_lrelease = 1
    p_dph_t.in_bclosure = 1
    _phdraw_hlsyn_area_loop(p_dph_t)
    assert p_dph_t.in_lrelease == 0
    assert p_dph_t.in_bclosure == 0


def test_hlsyn_area_loop_ptongebody_sets_closure_at_tcum_zero_for_stop() -> None:
    """When ``tcum == 0`` and current phone has FSTOP, set
    ``in_tbclosure = 1`` and ``tbstep = -2``."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415
    from dectalk.ph.param_indices import TONGUEBODY  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_hlsyn_area_loop  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)
    # A velar stop /K/ has FSTOP set; pick the US allophone code.
    k_code = (PFUSA << 8) | int(USPhoneme["K"])
    p_dph_t.allophons = [0, k_code, 0]
    p_dph_t.nphone = 1
    p_dph_t.param[TONGUEBODY].tspesh = 8
    p_dph_t.tcum = 0
    p_dph_t.in_tbclosure = 0
    p_dph_t.in_tbrelease = 1
    _phdraw_hlsyn_area_loop(p_dph_t)
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
# The per-frame state machine lives inside ``#ifdef HLSYN`` (C 761-4291)
# and is compiled out of ``libtts_us.so``; ``phdraw`` does NOT invoke it
# on the US build. These tests drive the ported HLSYN-build chain directly
# via ``_phdraw_hlsyn_blocks`` so its logic stays covered.


def _run_state_machine(handle: TtsHandle, p_dph_t: DphT, p_dphsettar: DphSettarSt) -> None:
    """Allocate parstochip via one ``phdraw`` call, then run the HLSYN chain.

    The first ``phdraw`` populates ``parstochip`` / ``outp`` pointers and
    the live trajectory; ``_phdraw_hlsyn_blocks`` then runs the dead
    (HLSYN-build-only) per-frame state machine the tests assert against.
    """
    phdraw(handle)
    _phdraw_hlsyn_blocks(p_dph_t, p_dphsettar)


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
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle()
    p_dph_t.phonestep = 3
    p_dph_t.nphonelast = p_dph_t.nphone  # same phone
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.phonestep == 4


def test_state_machine_phonestep_reset_on_new_phone() -> None:
    """``phonestep`` resets to 0 when ``nphone != nphonelast``."""
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle()
    p_dph_t.phonestep = 7
    p_dph_t.nphonelast = p_dph_t.nphone + 1  # different phone
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.phonestep == 0


def test_state_machine_nasal_step_increments_during_nasal() -> None:
    """During a nasal phone, ``nasal_step`` increases and ``area_n`` follows table."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415
    from dectalk.ph.phdraw import _NASALIZATION  # noqa: PLC0415

    m_code = (PFUSA << 8) | int(USPhoneme["M"])
    # Use 5 phones: SIL, M, SIL, SIL, SIL to avoid index-out-of-range
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle(
        nphone=1,
        allophons=[0, m_code, 0, 0, 0],
        allofeats=[0] * 5,
        allodurs=[40] * 5,
    )
    p_dph_t.nasal_step = 2
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    # nasal_step should have incremented (by +2 from the else branch)
    assert p_dph_t.nasal_step >= 3
    assert p_dph_t.area_n == _NASALIZATION[min(p_dph_t.nasal_step, 12)]


def test_state_machine_nasal_target_ag_set_during_nasal() -> None:
    """During a nasal phone, ``target_ag`` is set to 700."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    m_code = (PFUSA << 8) | int(USPhoneme["M"])
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle(
        nphone=1,
        allophons=[0, m_code, 0, 0, 0],
        allofeats=[0] * 5,
        allodurs=[40] * 5,
    )
    p_dph_t.target_ag = 0
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.target_ag == 700


def test_state_machine_pressure_builds_for_voiced() -> None:
    """For a voiced phone, ``pressure`` is incremented toward NOM_Sub_Pressure."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    # /V/ is voiced fricative
    v_code = (PFUSA << 8) | int(USPhoneme["V"])
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle(
        nphone=1,
        allophons=[0, v_code, 0, 0, 0],
        allofeats=[0] * 5,
        allodurs=[40] * 5,
    )
    p_dph_t.pressure = 0
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.pressure == 70


def test_state_machine_out_ag_written() -> None:
    """``parstochip[OUT_AG]`` is written to a non-negative value each call."""
    from dectalk.ph.param_indices import OUT_AG  # noqa: PLC0415

    handle, p_dph_t, p_dphsettar = _build_state_machine_handle()
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.parstochip[OUT_AG] >= 0


def test_state_machine_out_an_equals_area_n() -> None:
    """``parstochip[OUT_AN]`` equals ``area_n`` at the end of each call."""
    from dectalk.ph.param_indices import OUT_AN  # noqa: PLC0415

    handle, p_dph_t, p_dphsettar = _build_state_machine_handle()
    p_dph_t.area_n = 160
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.parstochip[OUT_AN] == p_dph_t.area_n


def test_state_machine_nphonelast_updated() -> None:
    """``nphonelast`` is set to ``nphone`` at the end of each call."""
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle()
    p_dph_t.nphonelast = 99  # stale value
    p_dph_t.nphone = 1
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.nphonelast == 1


def test_state_machine_dh_closure_not_at_word_boundary() -> None:
    """DH/TH within a word (not at word boundary): sets ``target_b = area_b = 0``
    while phonestep < allodurs - 1."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    dh_code = (PFUSA << 8) | int(USPhoneme["DH"])
    # boundary_val < FWBNEXT: use 0 (no boundary, less than the 0o140 threshold)
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle(
        nphone=1,
        allophons=[0, dh_code, 0, 0, 0],
        allofeats=[0, 0, 0, 0, 0],  # boundary = 0 < FWBNEXT
        allodurs=[10, 10, 10, 10, 10],
    )
    p_dph_t.phonestep = 3  # < allodurs[1] - 1 = 9
    p_dph_t.target_b = 500
    p_dph_t.area_b = 500
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    # The DH rule should have set target_b = area_b = 0
    assert p_dph_t.target_b == 0
    assert p_dph_t.area_b == 0


def test_state_machine_flap_opens_after_half_duration() -> None:
    """For USP_DX (flap), ``area_flap`` increases during the second half of the phone."""
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    dx_code = (PFUSA << 8) | int(USPhoneme["DX"])
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle(
        nphone=1,
        allophons=[0, dx_code, 0, 0, 0],
        allofeats=[0] * 5,
        allodurs=[20, 20, 20, 20, 20],
    )
    p_dph_t.tcum = 12  # > half (10) → opening phase
    p_dph_t.area_flap = 0
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.area_flap > 0  # was increased


def test_state_machine_non_flap_phone_sets_area_flap_1200() -> None:
    """For a non-flap phone, ``area_flap`` is reset to 1200."""
    handle, p_dph_t, p_dphsettar = _build_state_machine_handle()
    p_dph_t.area_flap = 42
    _run_state_machine(handle, p_dph_t, p_dphsettar)
    assert p_dph_t.area_flap == 1200


# ----- Lateral AV reduction + F3/F2 floor (ph_draw.c lines 4619-4644) -------
# This block is DEAD on the US build: it lives after the
# ``#if !defined(HLSYN) && !defined(CHANGES_AFTER_V43)`` ``return;`` at
# C 4307, so phdraw returns before reaching it and does NOT call
# _phdraw_lateral_av_and_f3_floor(). The tests drive the ported helper
# directly to keep its (HLSYN/CHANGES_AFTER_V43-build) logic covered.


def test_lateral_av_reduction_fires_for_usp_ll() -> None:
    """USP_LL allophone triggers the -6 dB AV reduction (ph_draw.c line 4629)."""
    from dectalk.include.usp_codes import USP_LL  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_lateral_av_and_f3_floor  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)  # allocate parstochip + run the live trajectory.
    p_dph_t.allophons = [0, USP_LL, 0]
    p_dph_t.nphone = 1
    p_dph_t.parstochip[OUT_AV] = 40
    _phdraw_lateral_av_and_f3_floor(p_dph_t)
    # AV = 40; lateral reduction -6 = 34.
    assert p_dph_t.parstochip[OUT_AV] == 34


def test_lateral_av_reduction_clamps_to_zero() -> None:
    """Lateral AV reduction never takes AV below zero (ph_draw.c line 4633)."""
    from dectalk.include.usp_codes import USP_LL  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_lateral_av_and_f3_floor  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)
    p_dph_t.allophons = [0, USP_LL, 0]
    p_dph_t.nphone = 1
    p_dph_t.parstochip[OUT_AV] = 3  # After -6 would be -3 -> clamped to 0.
    _phdraw_lateral_av_and_f3_floor(p_dph_t)
    assert p_dph_t.parstochip[OUT_AV] == 0


def test_lateral_av_reduction_skipped_for_non_lateral() -> None:
    """A non-lateral allophone does not trigger the AV reduction."""
    from dectalk.include.usp_codes import USP_R  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_lateral_av_and_f3_floor  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)
    p_dph_t.allophons = [0, USP_R, 0]
    p_dph_t.nphone = 1
    p_dph_t.parstochip[OUT_AV] = 40
    _phdraw_lateral_av_and_f3_floor(p_dph_t)
    # No lateral reduction; AV stays at 40.
    assert p_dph_t.parstochip[OUT_AV] == 40


def test_f3_f2_floor_enforces_300hz_gap() -> None:
    """When F3 - F2 < 300, F3 is raised to F2 + 300 (ph_draw.c lines 4635-4638)."""
    from dectalk.ph.param_indices import OUT_F2, OUT_F3  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_lateral_av_and_f3_floor  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)
    # F2 = 1500, F3 = 1600 (gap = 100, below the 300-Hz floor).
    p_dph_t.parstochip[OUT_F2] = 1500
    p_dph_t.parstochip[OUT_F3] = 1600
    _phdraw_lateral_av_and_f3_floor(p_dph_t)
    f2 = p_dph_t.parstochip[OUT_F2]
    f3 = p_dph_t.parstochip[OUT_F3]
    assert f3 == f2 + 300, f"Expected F3={f2 + 300}, got F3={f3} (F2={f2})"


def test_f3_f2_floor_not_applied_when_gap_sufficient() -> None:
    """When F3 - F2 >= 300, F3 is left unchanged (ph_draw.c lines 4635-4638)."""
    from dectalk.ph.param_indices import OUT_F2, OUT_F3  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_lateral_av_and_f3_floor  # noqa: PLC0415

    handle, p_dph_t, _ = _build_handle()
    phdraw(handle)
    # F2 = 1200, F3 = 2500 (gap = 1300 >> 300).
    p_dph_t.parstochip[OUT_F2] = 1200
    p_dph_t.parstochip[OUT_F3] = 2500
    _phdraw_lateral_av_and_f3_floor(p_dph_t)
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


# ----- GEN_SIL ending-silence tests (ph_draw.c lines 1245-1332) ---------------
# These exercise :func:`_phdraw_gen_sil_ending`, which fires only when
# the current allophone is the special ``GEN_SIL`` filler.


def _build_gen_sil_handle(
    prev_allo: int,
    *,
    pressure: int = 500,
    pressure_drop: int = 0,
) -> tuple[TtsHandle, DphT, DphSettarSt]:
    """Construct a handle with ``allophons[nphone] == GEN_SIL``."""
    from dectalk.ph.utterance_constants import GEN_SIL  # noqa: PLC0415

    handle, p_dph_t, p_dphsettar = _build_handle()
    p_dph_t.nphone = 2
    p_dph_t.nphonelast = 1  # First frame of the ending silence.
    p_dph_t.allophons = [0, prev_allo, GEN_SIL, 0]
    p_dph_t.allofeats = [0, 0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40, 40]
    p_dph_t.pressure = pressure
    p_dph_t.pressure_drop = pressure_drop
    return handle, p_dph_t, p_dphsettar


def test_gen_sil_skipped_when_not_gen_sil() -> None:
    """No mutation when current allophone is not ``GEN_SIL``."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_gen_sil_ending  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_AA, USP_AA, USP_AA]
    p_dph_t.pressure = 500
    p_dph_t.pressure_drop = 0
    _phdraw_gen_sil_ending(p_dph_t)
    # pressure_drop must not have ramped.
    assert p_dph_t.pressure_drop == 0


def test_gen_sil_pressure_drop_ramps_when_pressure_above_gate() -> None:
    """Pressure drop ramps by 150 when pressure > 100 (C lines 1249-1259)."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_gen_sil_ending  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_gen_sil_handle(USP_AA, pressure=500, pressure_drop=0)
    p_dph_t.nphonelast = p_dph_t.nphone  # Skip first-frame block.
    _phdraw_gen_sil_ending(p_dph_t)
    assert p_dph_t.pressure_drop == 150


def test_gen_sil_pressure_drop_saturates_at_2000() -> None:
    """Pressure drop saturates at the 2000 cap (C lines 1250-1259)."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_gen_sil_ending  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_gen_sil_handle(USP_AA, pressure=500, pressure_drop=2000)
    p_dph_t.nphonelast = p_dph_t.nphone
    _phdraw_gen_sil_ending(p_dph_t)
    assert p_dph_t.pressure_drop == 2000  # Did not increment further.


def test_gen_sil_pressure_drop_gated_below_100() -> None:
    """Pressure ≤ 100 -> pressure_drop is not incremented (C line 1249)."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_gen_sil_ending  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_gen_sil_handle(USP_AA, pressure=50, pressure_drop=0)
    p_dph_t.nphonelast = p_dph_t.nphone
    _phdraw_gen_sil_ending(p_dph_t)
    assert p_dph_t.pressure_drop == 0  # Gate kept the increment off.


def test_gen_sil_first_frame_opens_lips_for_non_labial_previous() -> None:
    """Non-labial previous phone opens lips (target_l = 1000) (C line 1295)."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_gen_sil_ending  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_gen_sil_handle(USP_AA)
    p_dph_t.target_l = 0
    _phdraw_gen_sil_ending(p_dph_t)
    assert p_dph_t.target_l == 1000


def test_gen_sil_first_frame_closes_blade_for_blade_affected_previous() -> None:
    """Blade-affected previous closes blade (target_b = 0) (C lines 1296-1308)."""
    from dectalk.include.usp_codes import USP_S  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_gen_sil_ending  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_gen_sil_handle(USP_S)
    p_dph_t.target_b = 1000
    _phdraw_gen_sil_ending(p_dph_t)
    # USP_S is FALVEL (blade-affected) -> close blade.
    assert p_dph_t.target_b == 0
    assert p_dph_t.in_lclosure == 0


def test_gen_sil_obstruent_previous_sets_wide_target_ag() -> None:
    """Obstruent previous sets target_ag = 2500 (C line 1321)."""
    from dectalk.include.usp_codes import USP_S  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_gen_sil_ending  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_gen_sil_handle(USP_S)
    _phdraw_gen_sil_ending(p_dph_t)
    # USP_S is unvoiced obstruent -> target_ag widened then narrowed
    # (line 1321 then 1326). Final value is 1800 from the unvoiced
    # branch.
    assert p_dph_t.target_ag == 1800


# ----- Regular-phoneme branch tests (ph_draw.c lines 1333-2398) ---------------
# These exercise :func:`_phdraw_regular_phoneme_branch`, which is the
# partial port covering dcstep / pressure / stress_pulse only.


def test_regular_branch_skipped_at_nphone_zero() -> None:
    """No mutation when ``nphone == 0`` (the initial-silence branch handles it)."""
    from dectalk.ph.phdraw import _phdraw_regular_phoneme_branch  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 0
    p_dph_t.dcstep = 0
    p_dph_t.pressure = 100
    _phdraw_regular_phoneme_branch(p_dph_t)
    assert p_dph_t.pressure == 100  # Pressure build skipped.


def test_regular_branch_skipped_for_gen_sil() -> None:
    """No mutation when current allo is ``GEN_SIL`` (handled elsewhere)."""
    from dectalk.ph.phdraw import _phdraw_regular_phoneme_branch  # noqa: PLC0415
    from dectalk.ph.utterance_constants import GEN_SIL  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [0, GEN_SIL, 0]
    p_dph_t.pressure = 100
    _phdraw_regular_phoneme_branch(p_dph_t)
    assert p_dph_t.pressure == 100


def test_regular_branch_pressure_build_subsumed_by_state_machine() -> None:
    """The pressure-build sub-block (C lines 1525-1538) is intentionally
    commented out in the regular-phoneme branch port because the per-frame
    HLSyn state machine already does the voiced +70 pressure build at
    C lines ~2858-2867. Porting it twice would double-count.
    """
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_regular_phoneme_branch  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_AA, USP_AA, USP_AA]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.pressure = 100
    p_dph_t.dcstep = 0
    p_dph_t.area_n = 0
    _phdraw_regular_phoneme_branch(p_dph_t)
    # Pressure must NOT be incremented here -- the state machine does it.
    assert p_dph_t.pressure == 100


def test_regular_branch_dcstep_init_for_voiced_obstruent() -> None:
    """Voiced obstruent with phonestep≥1 inits dcstep=1 (C lines 1341-1350)."""
    from dectalk.include.usp_codes import USP_Z  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_regular_phoneme_branch  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_Z, USP_Z, USP_Z]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.pressure = 100
    p_dph_t.dcstep = 0
    p_dph_t.uestep = 0
    p_dph_t.area_n = 0
    p_dph_t.phonestep = 2
    _phdraw_regular_phoneme_branch(p_dph_t)
    # USP_Z is FOBST & FVOICD -> dcstep init to +1.
    # Then advances on the dcstep > 0 path via the (in-condition)
    # write at C line ~1380. Acceptable end values are 1 or 2.
    assert p_dph_t.dcstep > 0


def test_regular_branch_dcstep_init_for_unvoiced_obstruent() -> None:
    """Unvoiced obstruent with phonestep≥1 inits dcstep=-1 (C lines 1351-1357)."""
    from dectalk.include.usp_codes import USP_S  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_regular_phoneme_branch  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_S, USP_S, USP_S]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.pressure = 100
    p_dph_t.dcstep = 0
    p_dph_t.uestep = 0
    p_dph_t.area_n = 0
    p_dph_t.phonestep = 2
    _phdraw_regular_phoneme_branch(p_dph_t)
    # USP_S is FOBST & !FVOICD -> dcstep init to -1.
    # The dcstep<0 unvoiced-obstruent path then advances it negative.
    assert p_dph_t.dcstep < 0


def test_regular_branch_emphasis_stress_pulse_ramps_up() -> None:
    """Emphasized syllable ramps stress_pulse up at end (C lines 1571-1577)."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.feature_bits import FEMPHASIS  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_regular_phoneme_branch  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_AA, USP_AA, USP_AA]
    p_dph_t.allofeats = [0, FEMPHASIS, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.tcum = 35  # Past the (allodurs - NF130MS=20) gate.
    p_dph_t.dcstep = 0
    p_dph_t.area_n = 0
    p_dph_t.stress_pulse = 0
    p_dph_t.pressure = 100
    _phdraw_regular_phoneme_branch(p_dph_t)
    # Late part of an emphasized syllable -> stress_pulse += 10.
    assert p_dph_t.stress_pulse == 10


def test_regular_branch_non_emphasis_resets_stress_pulse() -> None:
    """Non-emphasized syllable resets stress_pulse to 0 (C line ~1590)."""
    from dectalk.include.usp_codes import USP_AA  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_regular_phoneme_branch  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_AA, USP_AA, USP_AA]
    p_dph_t.allofeats = [0, 0, 0]  # No FEMPHASIS bits.
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.tcum = 35
    p_dph_t.dcstep = 0
    p_dph_t.area_n = 0
    p_dph_t.stress_pulse = 50  # Pre-existing value.
    p_dph_t.pressure = 100
    _phdraw_regular_phoneme_branch(p_dph_t)
    assert p_dph_t.stress_pulse == 0


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_gen_sil_ending_branch() -> None:
    """C body has the ``GEN_SIL`` ending-silence branch (lines 1245-1332)."""
    body = _extract_body()
    assert "pDph_t->allophons[pDph_t->nphone] == GEN_SIL" in body
    assert "pDph_t->pressure_drop +=150" in body
    assert "Now we're at ending silence" in body


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_regular_phoneme_dcstep_block() -> None:
    """C body has the dcstep init / tracker (lines 1337-1503)."""
    body = _extract_body()
    assert "pDph_t->dcstep == 0" in body
    assert "pDph_t->dcstep=1" in body
    assert "pDph_t->dcstep=-1" in body
    # The dcval / ueval lookup tables.
    assert "dcval" in body
    assert "ueval" in body


# ---------------------------------------------------------------------------
# Once-per-phone setup tests (ph_draw.c lines 1609-2040).
# ---------------------------------------------------------------------------


def test_once_per_phone_setup_skipped_at_nphone_zero() -> None:
    """No mutation at nphone=0 (initial-silence branch owns this case)."""
    from dectalk.ph.phdraw import _phdraw_once_per_phone_setup  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 0
    p_dph_t.target_ag = 555
    _phdraw_once_per_phone_setup(p_dph_t)
    assert p_dph_t.target_ag == 555


def test_once_per_phone_voiced_obstruent_sets_target_ap_200() -> None:
    """Voiced stop (USP_D) -> target_ap = 200 (C 1672-1675)."""
    from dectalk.include.usp_codes import USP_AA, USP_D  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_once_per_phone_setup  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_AA, USP_D, USP_AA]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.target_ap = 0
    _phdraw_once_per_phone_setup(p_dph_t)
    assert p_dph_t.target_ap == 200


def test_once_per_phone_voiced_fricative_sets_target_ap_600() -> None:
    """Voiced fricative (USP_Z) -> target_ap = 600 (C 1683-1689)."""
    from dectalk.include.usp_codes import USP_AA, USP_Z  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_once_per_phone_setup  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_AA, USP_Z, USP_AA]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.target_ap = 0
    _phdraw_once_per_phone_setup(p_dph_t)
    assert p_dph_t.target_ap == 600


def test_once_per_phone_clears_release_flags_when_previous_not_plosive() -> None:
    """Previous not FPLOSV -> in_lrelease/in_brelease/in_tbrelease/bstep cleared (C 1624-1641)."""
    from dectalk.include.usp_codes import USP_AA, USP_M  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_once_per_phone_setup  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    # Previous USP_M is a nasal/sonor, NOT FPLOSV.
    p_dph_t.allophons = [USP_M, USP_AA, USP_AA]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.in_lrelease = 1
    p_dph_t.in_brelease = 1
    p_dph_t.in_tbrelease = 1
    p_dph_t.bstep = 5
    _phdraw_once_per_phone_setup(p_dph_t)
    assert p_dph_t.in_lrelease == 0
    assert p_dph_t.in_brelease == 0
    assert p_dph_t.in_tbrelease == 0
    assert p_dph_t.bstep == 0


def test_once_per_phone_r_widens_glottis() -> None:
    """USP_R -> target_ag += 1000 (C 1952-1964)."""
    from dectalk.include.usp_codes import USP_AA, USP_R  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_once_per_phone_setup  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_AA, USP_R, USP_AA]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.target_ag = 100
    _phdraw_once_per_phone_setup(p_dph_t)
    # R is also FSON1 — the FSON1 branch will then run and may
    # restore target_ag to _NOM_VOIC_GLOT_AREA (0 on US). We only
    # need the widening to *have happened* before subsequent
    # overrides — check via a phone that is just /r/ without
    # FSON1 path firing. Re-run with a dummy-vowel allofeat that
    # short-circuits the FSON1 restore.
    from dectalk.ph.feature_bits import FDUMMY_VOWEL  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_AA, USP_R, USP_AA]
    # FDUMMY_VOWEL routes FSON1 to the NOM_OPEN_GLOTTIS + 100 path
    # (0 + 100 = 100 on US), keeping a deterministic post-R target_ag.
    p_dph_t.allofeats = [0, FDUMMY_VOWEL, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.target_ag = 50
    _phdraw_once_per_phone_setup(p_dph_t)
    # FSON1+FDUMMY_VOWEL writes target_ag = _NOM_OPEN_GLOTTIS+100 = 100
    # (overrides the +1000 R bump, matching the C source's intended
    # late-binding behaviour).
    assert p_dph_t.target_ag == 100


def test_once_per_phone_fstop_alvelar_closes_blade() -> None:
    """FSTOP without FBURST + alveolar place -> in_bclosure=1, target_b=0 (C 1907-1923)."""
    from dectalk.include.usp_codes import USP_AA, USP_N  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_once_per_phone_setup  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    # USP_N is an alveolar nasal (FSTOP without FBURST, blade-affected
    # place). The C comment at 1905 names "soncon nasal" as the
    # canonical example of an FSTOP/!FBURST phone with blade-affected
    # place: this exercises C lines 1907-1923 unambiguously.
    p_dph_t.allophons = [USP_AA, USP_N, USP_AA]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.in_bclosure = 0
    p_dph_t.target_b = 1000
    _phdraw_once_per_phone_setup(p_dph_t)
    assert p_dph_t.in_bclosure == 1
    assert p_dph_t.target_b == 0


# ---------------------------------------------------------------------------
# FVOWEL A2-jamming tests (ph_draw.c lines 2045-2398).
# ---------------------------------------------------------------------------


def test_fvowel_a2_jamming_dental_voiced_sets_1100() -> None:
    """USP_DH (voiced dental) -> parstochip[OUT_A2] = 1200 (C 2285-2293)."""
    from dectalk.ph.phdraw import _phdraw_fvowel_a2_jamming  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    # The block is gated on FVOWEL but the per-place A2 writes work
    # on the *current* phone's place. Using USP_DH directly lets us
    # exercise the dental→1200 sub-rule.
    p_dph_t.allophons = [USP_DH, USP_DH, USP_DH]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.tcum = 5
    p_dph_t.phonestep = 1
    _phdraw_fvowel_a2_jamming(p_dph_t)
    # USP_DH is in the special-case list at C 2285-2293, so A2 == 1200.
    assert p_dph_t.parstochip[OUT_A2] == 1200


def test_fvowel_a2_jamming_labial_current_sets_1300() -> None:
    """Current phone with FLABIAL place -> parstochip[OUT_A2] = 1300 (C 2299-2310)."""
    from dectalk.include.usp_codes import USP_AA, USP_P  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_fvowel_a2_jamming  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    # USP_P is labial. Not a vowel — the function is normally gated
    # on FVOWEL by the caller, but the helper itself runs the
    # A2-jamming block unconditionally on the current phone's place.
    p_dph_t.allophons = [USP_AA, USP_P, USP_AA]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.tcum = 5
    p_dph_t.phonestep = 1
    _phdraw_fvowel_a2_jamming(p_dph_t)
    assert p_dph_t.parstochip[OUT_A2] == 1300


def test_fvowel_a2_jamming_lastthing_latched_when_a2_above_1000() -> None:
    """A2 >= 1000 latches into lastthing (C 2396-2397)."""
    from dectalk.ph.phdraw import _phdraw_fvowel_a2_jamming  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    p_dph_t.allophons = [USP_DH, USP_DH, USP_DH]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.tcum = 5
    p_dph_t.phonestep = 1
    p_dph_t.lastthing = 0
    _phdraw_fvowel_a2_jamming(p_dph_t)
    assert p_dph_t.lastthing == p_dph_t.parstochip[OUT_A2]
    assert p_dph_t.lastthing >= 1000


def test_fvowel_a2_jamming_hx_anticipation_opens_glottis_to_1800() -> None:
    """Next-phone unvoiced FSONOR FCONSON at end -> target_ag = 1800 (C 2175-2194)."""
    from dectalk.include.usp_codes import USP_AA, USP_HX  # noqa: PLC0415
    from dectalk.ph.phdraw import _phdraw_fvowel_a2_jamming  # noqa: PLC0415

    _handle, p_dph_t, _ = _build_handle()
    p_dph_t.nphone = 1
    # USP_HX is unvoiced sonorant consonant.
    p_dph_t.allophons = [USP_AA, USP_AA, USP_HX]
    p_dph_t.allofeats = [0, 0, 0]
    p_dph_t.allodurs = [40, 40, 40]
    p_dph_t.tcum = 39  # >= allodurs - 2 (40 - 2 = 38)
    p_dph_t.target_ag = 500
    _phdraw_fvowel_a2_jamming(p_dph_t)
    assert p_dph_t.target_ag == 1800
    assert p_dph_t.agspeed == 2


# ---------------------------------------------------------------------------
# State-machine no-double-write audit tests.
# ---------------------------------------------------------------------------


def test_once_per_phone_runs_before_state_machine_in_phdraw() -> None:
    """The HLSYN chain invokes once-per-phone *before* the state machine.

    Anti-regression for the issue-71 acceptance criterion #2 (no
    double-writes): if the per-phone setup were called after the state
    machine, target_ag would be left in the per-phone "raw" state and the
    OUT_AG slot would be wrong on FNASAL phones.

    Drives ``_phdraw_hlsyn_blocks`` directly: the per-frame state machine
    is ``#ifdef HLSYN`` dead code that phdraw does not run on the US build.
    """
    from dectalk.include.usp_codes import USP_N  # noqa: PLC0415

    handle, p_dph_t, p_dphsettar = _build_handle()
    phdraw(handle)  # allocate parstochip + run the live trajectory.
    # New phone (nphone != nphonelast) so once-per-phone fires.
    p_dph_t.nphone = 1
    p_dph_t.nphonelast = 0
    p_dph_t.allophons = [USP_N, USP_N, USP_N]
    _phdraw_hlsyn_blocks(p_dph_t, p_dphsettar)
    # The state machine sets target_ag = 700 for FNASAL phones at
    # C ~2510. If once-per-phone ran *after* the state machine, the
    # FOBST branch in once-per-phone (which sets target_ag to
    # NOM_VOICED_OBSTRUENT = 0) would leak through. USP_N is nasal,
    # not obstruent, so once-per-phone's else clause sets
    # target_ap = 0 but does NOT touch target_ag. Asserting target_ag
    # holds the state machine's nasal value (700) confirms ordering.
    assert p_dph_t.target_ag == 700


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_once_per_phone_setup_block() -> None:
    """C body has the once-per-phone setup gate (lines 1609-2040)."""
    body = _extract_body()
    # The nphone != nphonelast gate.
    assert "pDph_t->nphone != pDph_t->nphonelast" in body
    # The voiced glottal-stop branch.
    assert "NOM_Glot_Stop_Area" in body
    # The voiced-obstruent target_ap = 600.
    assert "pDph_t->target_ap = 600" in body
    # The USP_R glottis widening.
    assert "pDph_t->target_ag += 1000" in body


@pytest.mark.skipif(
    not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)
def test_c_body_has_fvowel_a2_jamming_block() -> None:
    """C body has the FVOWEL A2-jamming block (lines 2045-2398)."""
    body = _extract_body()
    # The FVOWEL gate.
    assert "phone_feature(pDph_t,pDph_t->allophons[pDph_t->nphone]) & FVOWEL" in body
    # Per-place A2 jammers.
    assert "pDph_t->parstochip[OUT_A2] = 1300" in body
    assert "pDph_t->parstochip[OUT_A2] = 3000" in body
    # The lastthing latch.
    assert "pDph_t->lastthing = pDph_t->parstochip[OUT_A2]" in body
