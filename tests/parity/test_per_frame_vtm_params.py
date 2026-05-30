"""Per-frame VTM formant/bandwidth/amplitude/tilt parity vs the C oracle (#263).

Companion to :mod:`tests.parity.test_per_frame_f0`. Where that module pins
the ``OUT_T0`` (F0 period) contour, this one pins the *rest* of the
per-frame voice packet — the formant frequencies (``OUT_F1/F2/F3``),
bandwidths (``OUT_B1/B2/B3``), source amplitudes (``OUT_AV/AP/A2-A6/AB``),
spectral tilt (``OUT_TLT``) and nasal zero (``OUT_FZ``) — for the
``hello world`` prompt on the pure-Python full pipeline
(``DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 DECTALK_USE_VTM1=1``).

Both sides are compared at the ``send_pars()`` / ``delaypars[]`` level: the
C oracle's ``vtm_frames.dump`` (patch ``0006``) records the *post*-``send_pars``
voice packet, so the Python ``parstochip[]`` stream is run through an exact
emulation of ``ph_claus.c`` ``send_pars()`` (one-frame delay of the formant
side + ``lineartilt[]`` LUT on ``OUT_TLT``) before the per-index comparison.

Findings captured at authoring time (issue #263 diagnosis):

* **Exact already** — ``OUT_B1``, ``OUT_B2``, ``OUT_B3``, ``OUT_FZ``,
  ``OUT_A2``, ``OUT_A3``, ``OUT_A5``, ``OUT_AB`` match the oracle on every
  frame for ``hello world``. This module asserts that as a *regression
  guard* (the bandwidth-target chain + delay model are verified bit-exact).
* **Still diverging** — ``OUT_F2`` / ``OUT_F3`` ramp from frame 0 in the
  Python pipeline while the oracle holds the first-phoneme begin-target
  flat through the leading silence + voiced onset (frames 0-10); ``OUT_TLT``
  runs ~10 internal-units low; ``OUT_AP`` and ``OUT_F1`` drift later. These
  are pinned ``xfail`` so the gap is measurable but the suite stays green.
  ``OUT_T0`` divergence is owned by ``test_per_frame_f0`` / the F0 files and
  is deliberately excluded here.

Skips cleanly when the C-oracle artefacts (``$DECTALK_SRC`` source tree +
``$DECTALK_BIN`` shipped binary) are missing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from dectalk._capi import CAPI
from dectalk.ph.parameter_tables import lineartilt

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))

# OUT_* offsets within the dumped voice packet (ph_defs.h; VOICE_PARS == 21
# on this non-NEW_VTM build, so only indices 0..20 are present).
_OUT_AP = 0
_OUT_F1 = 1
_OUT_A2 = 2
_OUT_A3 = 3
_OUT_A5 = 5
_OUT_AB = 7
_OUT_TLT = 8
_OUT_T0 = 9
_OUT_AV = 10
_OUT_F2 = 11
_OUT_F3 = 12
_OUT_FZ = 13
_OUT_B1 = 14
_OUT_B2 = 15
_OUT_B3 = 16

# send_pars() classification (ph_claus.c lines 694-846). The non-delayed
# (current-frame) pars are AV, TLT, T0 (+ NEW_VTM-only cells); everything
# else on the formant side is delayed by one frame.
_DELAYED_IDX = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19})

# Indices verified bit-exact for ``hello world`` (regression guard).
_EXACT_IDX: tuple[tuple[int, str], ...] = (
    (_OUT_B1, "OUT_B1"),
    (_OUT_B2, "OUT_B2"),
    (_OUT_B3, "OUT_B3"),
    (_OUT_FZ, "OUT_FZ"),
    (_OUT_A2, "OUT_A2"),
    (_OUT_A3, "OUT_A3"),
    (_OUT_A5, "OUT_A5"),
    (_OUT_AB, "OUT_AB"),
)


def _have_artefacts() -> bool:
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

_PROMPT = "hello world"


@pytest.fixture(scope="module")
def capi() -> CAPI:
    return CAPI(src_root=_SRC_ROOT, data_root=_BIN_ROOT)


def _oracle_frames(capi: CAPI, text: str) -> list[list[int]]:
    """Per-frame ``delaypars[]`` packets from the oracle's ``vtm_frames.dump``."""
    with tempfile.TemporaryDirectory(prefix="dectalk-vtm-") as dump_dir:
        prev = os.environ.get("DECTALK_DUMP_DIR")
        os.environ["DECTALK_DUMP_DIR"] = dump_dir
        try:
            with capi._instance_lock:
                capi._speak_locked(text, speaker=0, rate=None, encoding=1)
        finally:
            if prev is None:
                os.environ.pop("DECTALK_DUMP_DIR", None)
            else:
                os.environ["DECTALK_DUMP_DIR"] = prev
        dump_path = Path(dump_dir) / "vtm_frames.dump"
        if not dump_path.is_file():
            pytest.skip(
                "vtm_frames.dump not produced; patch 0006 not applied to the "
                "C oracle? Re-run scripts/setup_c_oracle.sh."
            )
        payload = dump_path.read_text("latin-1")

    frames: list[list[int]] = []
    for line in payload.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0] != "vtm_frame":
            continue
        count = int(parts[1])
        frames.append([int(parts[2 + i]) for i in range(count)])
    return frames


def _python_parstochip(text: str) -> list[list[int]]:
    """Per-frame ``parstochip[]`` arrays from the Python full pipeline."""
    from dectalk.ph import parstochip_to_frames as _ptf  # noqa: PLC0415

    captured: list[list[int]] = []
    original = _ptf.parstochip_to_llframe_delayed

    def _wrap(parstochip: list[int], *args: object, **kwargs: object) -> object:
        captured.append(list(parstochip))
        return original(parstochip, *args, **kwargs)  # type: ignore[arg-type]

    saved = {
        k: os.environ.get(k)
        for k in ("DECTALK_DISABLE_CAPI", "DECTALK_FULL_PIPELINE", "DECTALK_USE_VTM1")
    }
    os.environ["DECTALK_DISABLE_CAPI"] = "1"
    os.environ["DECTALK_FULL_PIPELINE"] = "1"
    os.environ["DECTALK_USE_VTM1"] = "1"
    _ptf.parstochip_to_llframe_delayed = _wrap
    try:
        import dectalk  # noqa: PLC0415

        dectalk.speak(text)
    finally:
        _ptf.parstochip_to_llframe_delayed = original
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return captured


def _emulate_send_pars(parstochip: list[list[int]]) -> list[list[int]]:
    """Replicate ``ph_claus.c`` ``send_pars()``: delay + ``lineartilt[]``.

    Produces the ``delaypars[]`` stream the oracle dumps: ``OUT_TLT`` mapped
    through ``lineartilt[]`` (current frame), ``OUT_AV``/``OUT_T0`` current
    frame, and every formant-side index delayed by one frame.
    """
    out: list[list[int]] = []
    for f, cur in enumerate(parstochip):
        prev = parstochip[f - 1] if f > 0 else cur
        dp = [0] * 21
        for i in range(21):
            if i == _OUT_TLT:
                dp[i] = lineartilt[max(0, min(len(lineartilt) - 1, cur[_OUT_TLT]))]
            elif i in _DELAYED_IDX:
                dp[i] = prev[i]
            else:
                dp[i] = cur[i]
        out.append(dp)
    return out


def _aligned(capi: CAPI) -> tuple[list[list[int]], list[list[int]], int]:
    oracle = _oracle_frames(capi, _PROMPT)
    py_delay = _emulate_send_pars(_python_parstochip(_PROMPT))
    n = min(len(oracle), len(py_delay))
    assert n > 0, "no frames captured from one of the pipelines"
    return oracle, py_delay, n


@pytest.mark.parametrize("idx,name", _EXACT_IDX, ids=[n for _, n in _EXACT_IDX])
def test_exact_vtm_param_matches_oracle(capi: CAPI, idx: int, name: str) -> None:
    """Regression guard: these per-frame params are bit-exact on ``hello world``.

    The bandwidth-target chain (``OUT_B1/B2/B3``), nasal zero (``OUT_FZ``) and
    the quiet parallel amplitudes (``OUT_A2/A3/A5/AB``) match the C oracle on
    every frame. If a future PH change regresses any of them this fails loudly
    rather than silently widening the byte divergence.
    """
    oracle, py_delay, n = _aligned(capi)
    mismatches = [
        (f, oracle[f][idx], py_delay[f][idx])
        for f in range(n)
        if oracle[f][idx] != py_delay[f][idx]
    ]
    assert not mismatches, (
        f"{name} regressed: {len(mismatches)}/{n} frames differ; first few {mismatches[:5]}"
    )


@pytest.mark.xfail(
    strict=False,
    reason=(
        "Phase E (issue #263): OUT_F2/F3 ramp from frame 0 while the oracle "
        "holds the first-phoneme begin-target flat through leading silence; "
        "OUT_TLT runs ~10 internal-units low. Target-generation gap "
        "(getbegtar/gettar/make_dip). Pins the divergence for follow-up."
    ),
)
@pytest.mark.parametrize(
    "idx,name",
    [(_OUT_F2, "OUT_F2"), (_OUT_F3, "OUT_F3"), (_OUT_TLT, "OUT_TLT")],
    ids=["OUT_F2", "OUT_F3", "OUT_TLT"],
)
def test_diverging_vtm_param_pins_gap(capi: CAPI, idx: int, name: str) -> None:
    """Pin the still-diverging per-frame params (expected ``xfail``)."""
    oracle, py_delay, n = _aligned(capi)
    first_div = next(
        (
            (f, oracle[f][idx], py_delay[f][idx])
            for f in range(n)
            if oracle[f][idx] != py_delay[f][idx]
        ),
        None,
    )
    assert first_div is None, (
        f"{name} first diverges at frame {first_div[0]}: "
        f"oracle={first_div[1]} python={first_div[2]}"
    )
