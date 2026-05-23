"""Frame-dump instrumentation parity for the OUT_PH/OUT_DU/OUT_PH2 cells.

The C reference (``ph_claus.c`` lines 465-472) writes the current
phoneme code, current duration, and next phoneme code into the
``parstochip[]`` output buffer each time the per-frame driver advances
``nphone``. These cells are consumed by debug / SAPI instrumentation
readers (frame dumps), not by the Klatt synthesiser itself; ``LLFrame``
has no corresponding fields so the ``parstochip → LLFrame`` adapter
drops them. But agents performing frame-by-frame parity comparisons
between Python and C dumps need these cells populated to match.

Issue #141.
"""

from __future__ import annotations

import numpy as np
import pytest

from dectalk.hlsyn.llsyn import LLFrame
from dectalk.ph.param_indices import OUT_DU, OUT_PH, OUT_PH2
from dectalk.ph.spdef_chip import SpdChip


def _run_full_pipeline(text: str, monkeypatch: pytest.MonkeyPatch) -> list[list[int]]:
    """Run ``_render_clause_full`` and capture parstochip snapshots.

    Monkey-patches ``parstochip_to_llframe_delayed`` (the per-frame
    adapter the driver calls right after ``phdraw``) so we see the
    parstochip state at the same instant the C reference would have
    emitted an SPC frame. Returns one snapshot per emitted frame.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

    import dectalk.ph.parstochip_to_frames as ptf  # noqa: PLC0415
    from dectalk.api.speak import _render_clause_full  # noqa: PLC0415

    snapshots: list[list[int]] = []
    real = ptf.parstochip_to_llframe_delayed

    def _capture(
        parstochip: list[int],
        previous: list[int] | None,
        spd_chip: SpdChip | None = None,
    ) -> LLFrame:
        snapshots.append(list(parstochip))
        return real(parstochip, previous, spd_chip)

    # Patch BOTH the source module and the alias inside speak.py: the
    # driver loop binds the name at function-define time via ``from
    # ... import ...``, so patching just the source module won't catch
    # the call site.
    monkeypatch.setattr(ptf, "parstochip_to_llframe_delayed", _capture)
    import dectalk.api.speak as speak_mod  # noqa: PLC0415

    if hasattr(speak_mod, "parstochip_to_llframe_delayed"):
        monkeypatch.setattr(speak_mod, "parstochip_to_llframe_delayed", _capture)

    samples = _render_clause_full(
        text,
        rate=1.0,
        voice=None,
        lang="us",
        lts_fallback=True,
    )
    assert isinstance(samples, np.ndarray)
    assert samples.size > 0, f"{text!r} produced no audio"
    return snapshots


def test_parstochip_out_ph_is_written(monkeypatch: pytest.MonkeyPatch) -> None:
    """``parstochip[OUT_PH]`` is set to a non-zero phoneme code.

    Mirrors ``ph_claus.c:465`` -- ``pDph_t->parstochip[OUT_PH] =
    pDph_t->allophons[pDph_t->nphone]``. The first allophone in the
    stream is a GEN_SIL sentinel (code 0), but later allophones are
    real phonemes (non-zero codes), so somewhere in the snapshot
    stream we expect OUT_PH > 0.
    """
    snaps = _run_full_pipeline("hello world", monkeypatch)
    out_ph_values = {snap[OUT_PH] for snap in snaps}
    # The trailing GEN_SIL sentinel sits at code 0 and consumes a
    # large fraction of the trailing frames, so 0 will appear --
    # but at least one real phoneme should have left a non-zero
    # imprint.
    nonzero = {v for v in out_ph_values if v != 0}
    assert nonzero, (
        f"parstochip[OUT_PH] stayed 0 across all {len(snaps)} frames -- "
        "ph_claus.c:465 mirror is missing"
    )


def test_parstochip_out_du_matches_durfon_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """``parstochip[OUT_DU]`` is set to the current allophone duration.

    Mirrors ``ph_claus.c:466`` -- ``pDph_t->parstochip[OUT_DU] =
    pDph_t->allodurs[pDph_t->nphone]``. Durations are clause-frame
    counts (positive small integers, typically 5..200).
    """
    snaps = _run_full_pipeline("hello world", monkeypatch)
    out_du_values = {snap[OUT_DU] for snap in snaps}
    nonzero = {v for v in out_du_values if v != 0}
    assert nonzero, (
        f"parstochip[OUT_DU] stayed 0 across all {len(snaps)} frames -- "
        "ph_claus.c:466 mirror is missing"
    )
    # Sanity-bound: per-allophone frame durations are small integers,
    # nominally 1..400 frames (~6.4 ms..2.5 s). A runaway value here
    # would indicate the wrong cell is being written.
    assert all(0 <= v <= 1000 for v in out_du_values), (
        f"parstochip[OUT_DU] out of plausible range: {sorted(out_du_values)[:5]}.."
        f"{sorted(out_du_values)[-5:]}"
    )


def test_parstochip_out_ph2_mirrors_next_allophone(monkeypatch: pytest.MonkeyPatch) -> None:
    """``parstochip[OUT_PH2]`` is written to next-allophone code or 0.

    Mirrors ``ph_claus.c:467-472`` -- when ``nphone+1 > nallotot``,
    OUT_PH2 is 0; otherwise it is ``allophons[nphone+1]``.
    """
    snaps = _run_full_pipeline("hello world", monkeypatch)
    out_ph2_values = {snap[OUT_PH2] for snap in snaps}
    nonzero = {v for v in out_ph2_values if v != 0}
    assert nonzero, (
        f"parstochip[OUT_PH2] stayed 0 across all {len(snaps)} frames -- "
        "ph_claus.c:469/472 mirror is missing"
    )
