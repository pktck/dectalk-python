"""Per-frame OUT_T0 (F0) parity test against the C oracle (issue #149).

The Python PH pipeline produces an F0 contour with much narrower
per-clause variance than the C oracle (~5-8 Hz stdev vs 20-80 Hz on
representative clauses). The global stdev metric is too coarse to
pinpoint *where* the contour goes wrong; this test captures per-frame
``parstochip[OUT_T0]`` from both pipelines, converts each to a single
F0-Hz series, and asserts a tight per-frame max-abs tolerance.

The test is **expected to FAIL** at the time of authoring -- it pins
the F0-contour divergence so subsequent ph_drwt01 / ph_inton0 work can
be measured against a stable parity oracle. Marked ``xfail`` with
``strict=False`` so the suite stays green while the gap is still open;
once contour parity lands, drop the ``xfail`` mark and tighten the
``MAX_ABS_HZ`` tolerance.

C oracle dump format (one line per voice frame, see
``tests/parity/c_patches/0006-vtm-frame-out-t0-dump.patch``):

    vtm_frame <VOICE_PARS> <p0> <p1> ... <p_VOICE_PARS-1>

with ``p_n`` decimal int16 values at the ``OUT_*`` offsets from
``ph_defs.h`` (``OUT_T0 == 9``). In the non-HLSYN production build
the C oracle stores OUT_T0 as a fundamental *period* with
``muldv(400, 1000, f0prime)`` (= ``400000 / f0prime``); F0 in Hz is
``40000 / OUT_T0``. As of issue #227 the Python port matches this
non-HLSYN representation (``pht0draw.py`` step 11), so both sides
convert period→Hz identically with ``40000 / OUT_T0``.

Skips cleanly when the C oracle artefacts (``$DECTALK_SRC`` source
tree + ``$DECTALK_BIN`` shipped binary) are missing.
"""

from __future__ import annotations

import os
import statistics
import tempfile
from pathlib import Path

import pytest

from dectalk._capi import CAPI
from dectalk.ph.param_indices import OUT_T0

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


# Representative prompts (issue #149). Each exercises a different
# slice of the F0-contour state machine: simple SVO, longer clause
# with a trailing-stress pattern, and the canonical pangram.
_PROMPTS: tuple[str, ...] = (
    "hello world",
    "testing one two three",
    "the quick brown fox",
)

# Per-frame F0 tolerance in Hz. The C oracle's clause F0 ranges over
# ~80-160 Hz; the Python pipeline currently sticks near a single
# baseline. A tolerance of 5 Hz is generous for a fully-aligned
# contour but still catches the current divergence (which is ~30+ Hz
# at peaks). Once the gap closes, tighten this to ~2 Hz.
MAX_ABS_HZ: float = 5.0


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI instance reused across the per-frame F0 tests."""
    return CAPI(src_root=_SRC_ROOT, data_root=_BIN_ROOT)


def _c_oracle_f0_series(capi: CAPI, text: str) -> list[float]:
    """Capture per-frame F0 in Hz from the C oracle's ``vtm_frames.dump``.

    Calls ``CAPI._speak_locked`` with ``DECTALK_DUMP_DIR`` set so the
    patch under ``tests/parity/c_patches/0006-vtm-frame-out-t0-dump.patch``
    writes ``vtm_frames.dump`` to the temp dir. Parses each
    ``vtm_frame`` line, extracts ``OUT_T0`` (offset 9 in the param
    payload), and converts the period to Hz.
    """
    with tempfile.TemporaryDirectory(prefix="dectalk-f0-") as dump_dir:
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
                "vtm_frames.dump not produced; patch 0006 not applied "
                "to the C oracle? Re-run scripts/setup_c_oracle.sh."
            )
        payload = dump_path.read_bytes().decode("latin-1")

    f0_hz: list[float] = []
    for line in payload.splitlines():
        # Expected layout: "vtm_frame <count> <p0> <p1> ... <p_count-1>"
        parts = line.split()
        if len(parts) < 3 or parts[0] != "vtm_frame":
            continue
        # OUT_T0 == 9, so the value sits at parts[2 + 9] = parts[11].
        out_t0 = int(parts[2 + OUT_T0])
        # Non-HLSYN build: OUT_T0 is the period (samples) produced by
        # ``muldv(400, 1000, f0prime)`` in ph_drwt01.c. F0_Hz =
        # 40000 / period (the muldv factor is 400 * 1000 / 10 deciHz/Hz).
        if out_t0 > 0:
            f0_hz.append(40000.0 / out_t0)
        else:
            f0_hz.append(0.0)
    return f0_hz


def _python_f0_series(text: str) -> list[float]:
    """Capture per-frame F0 in Hz from the Python full-pipeline driver.

    Monkey-patches :func:`dectalk.ph.parstochip_to_frames.parstochip_to_llframe_delayed`
    to record ``parstochip[OUT_T0]`` on each call, then runs
    :func:`dectalk.speak` under ``DECTALK_DISABLE_CAPI=1`` +
    ``DECTALK_FULL_PIPELINE=1`` so the per-frame driver loop executes
    in Python.

    As of issue #227 the Python port matches the non-HLSYN build;
    ``parstochip[OUT_T0]`` is the pitch *period* ``muldv(400, 1000,
    f0prime)`` (``pht0draw.py`` step 11). F0 in Hz is therefore
    ``40000 / OUT_T0`` — identical to the C-oracle conversion.
    """
    # Import lazily so the test module can import without the full
    # pipeline being wired up.
    from dectalk.ph import parstochip_to_frames as _ptf  # noqa: PLC0415

    captured: list[int] = []
    original = _ptf.parstochip_to_llframe_delayed

    def _wrap(parstochip: list[int], *args: object, **kwargs: object) -> object:
        captured.append(parstochip[OUT_T0])
        return original(parstochip, *args, **kwargs)  # type: ignore[arg-type]

    prev_disable = os.environ.get("DECTALK_DISABLE_CAPI")
    prev_full = os.environ.get("DECTALK_FULL_PIPELINE")
    os.environ["DECTALK_DISABLE_CAPI"] = "1"
    os.environ["DECTALK_FULL_PIPELINE"] = "1"
    _ptf.parstochip_to_llframe_delayed = _wrap
    try:
        import dectalk  # noqa: PLC0415 -- gated import (env-dependent dispatch)

        dectalk.speak(text)
    finally:
        _ptf.parstochip_to_llframe_delayed = original
        if prev_disable is None:
            os.environ.pop("DECTALK_DISABLE_CAPI", None)
        else:
            os.environ["DECTALK_DISABLE_CAPI"] = prev_disable
        if prev_full is None:
            os.environ.pop("DECTALK_FULL_PIPELINE", None)
        else:
            os.environ["DECTALK_FULL_PIPELINE"] = prev_full

    # Non-HLSYN path (issue #227): OUT_T0 is the period
    # ``muldv(400, 1000, f0prime)``. F0_Hz = 40000 / period.
    return [40000.0 / t0 if t0 > 0 else 0.0 for t0 in captured]


def _summarize(label: str, series: list[float]) -> str:
    nonzero = [x for x in series if x > 0]
    if not nonzero:
        return f"{label}: all-zero ({len(series)} frames)"
    mean = statistics.mean(nonzero)
    std = statistics.stdev(nonzero) if len(nonzero) > 1 else 0.0
    return (
        f"{label}: n={len(series)} mean={mean:.1f} Hz std={std:.1f} Hz "
        f"min={min(nonzero):.1f} max={max(nonzero):.1f}"
    )


# Prompts whose per-frame F0 is now byte-exact against the C oracle.
# After the #261 F0-dynamics fixes (``size_hat_rise = HR * 10`` and the
# ``f0basefall = BF * 10`` baseline-declination seed in ph_vset.c) the
# Python contour is frame-identical to the oracle on these prompts
# (mean |Δ| == 0.0 Hz across every voiced frame). They are pinned as a
# hard parity assertion. ``the quick brown fox`` joined the exact set
# with the #270 timing fixes: the 258-vs-279 voiced-frame drift was the
# lexicon's sole-secondary stress on quick/brown (C's dictionary
# surfaces them as primary), which shortened every phone of both
# stressed syllables in ``us_phtiming``. With the stress class aligned
# the Python contour is frame-identical (279 voiced frames, max |Δ|
# 0.0 Hz).
_FRAME_EXACT_PROMPTS: frozenset[str] = frozenset(
    {"hello world", "testing one two three", "the quick brown fox"}
)


@pytest.mark.parametrize("prompt", _PROMPTS, ids=lambda p: p.replace(" ", "_"))
def test_per_frame_out_t0_within_tolerance(
    capi: CAPI, prompt: str, request: pytest.FixtureRequest
) -> None:
    """Per-frame OUT_T0 from Python must agree with the C oracle within MAX_ABS_HZ.

    The C oracle and the Python full-pipeline driver run independently;
    the test trims both series to the common prefix length (the two
    pipelines may emit slightly different frame counts during the
    multi-month port) and then asserts the per-frame max-abs F0 delta
    is below :data:`MAX_ABS_HZ`.

    Diagnostic output (rendered on failure) shows mean / std / min /
    max of each series plus the index and magnitude of the worst
    per-frame divergence so future work can target the right phoneme
    window.

    Prompts in :data:`_FRAME_EXACT_PROMPTS` are byte-exact after the
    #261 F0-dynamics fixes and are asserted to ``MAX_ABS_HZ``. The
    remaining prompt(s) diverge on frame count (a timing detail, not the
    F0 contour) and stay xfail until the duration port lands.
    """
    if prompt not in _FRAME_EXACT_PROMPTS:
        request.applymarker(
            pytest.mark.xfail(
                strict=False,
                reason=(
                    "Phase E (audio bit-parity) -- the F0 contour matches the "
                    "oracle frame-for-frame on its leading frames, but a "
                    "frame-count drift (Python emits fewer voiced frames than "
                    "C) from an un-ported timing detail shifts the alignment "
                    "tail. This is a duration/timing gap, not an F0-dynamics "
                    "one. See issues #220 / #149."
                ),
            )
        )

    c_series = _c_oracle_f0_series(capi, prompt)
    py_series = _python_f0_series(prompt)

    # Drop empty heads (silence frames before any voicing) from the
    # comparison so the contour alignment isn't dominated by leading
    # silence that one pipeline emits and the other doesn't.
    c_voiced = [v for v in c_series if v > 0]
    py_voiced = [v for v in py_series if v > 0]
    assert c_voiced, f"C oracle produced no voiced frames for {prompt!r}"
    assert py_voiced, f"Python pipeline produced no voiced frames for {prompt!r}"

    n = min(len(c_voiced), len(py_voiced))
    deltas = [abs(c_voiced[i] - py_voiced[i]) for i in range(n)]
    worst_idx = max(range(n), key=lambda i: deltas[i])
    worst_delta = deltas[worst_idx]
    mean_delta = statistics.mean(deltas)

    detail = "\n".join(
        [
            f"prompt: {prompt!r}",
            _summarize("c_oracle", c_voiced),
            _summarize("python  ", py_voiced),
            f"compared frames: {n} (c={len(c_voiced)} py={len(py_voiced)})",
            f"mean |Δ|: {mean_delta:.1f} Hz",
            f"worst |Δ|: {worst_delta:.1f} Hz at frame {worst_idx} "
            f"(c={c_voiced[worst_idx]:.1f} py={py_voiced[worst_idx]:.1f})",
        ]
    )
    assert worst_delta <= MAX_ABS_HZ, (
        f"per-frame F0 delta exceeds {MAX_ABS_HZ} Hz tolerance\n{detail}"
    )
