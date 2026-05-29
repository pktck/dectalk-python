#!/usr/bin/env python3
"""Standalone OUT_T0 parity check for issue #227 (pht0draw period fix).

Runs the pure-Python full pipeline and the C oracle on a couple of
prompts, dumps per-frame ``parstochip[OUT_T0]`` from both sides, and
reports mean / max |Δ| in the *raw OUT_T0 representation* (the value the
vtm1 synth consumes directly).

After the #227 fix the Python side emits OUT_T0 as the pitch *period*
``muldv(400, 1000, f0prime)`` — exactly the C non-HLSYN representation —
so both sides are directly comparable as raw OUT_T0 integers.

This is a one-off measurement tool, not a pytest. Run it before/after
the fix (stash to compare). Requires the C oracle artefacts; honours
$DECTALK_SRC / $DECTALK_BIN.

Usage:
    DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 DECTALK_USE_VTM1=1 \
        uv run python scripts/verify_out_t0_parity.py
"""

# This one-off measurement script drives the C oracle through the same
# private CAPI entry points the parity-test harness uses
# (CAPI._instance_lock / CAPI._speak_locked) to capture per-frame dumps.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import os
import statistics
import tempfile
from pathlib import Path

from dectalk._capi import CAPI
from dectalk.ph.param_indices import OUT_T0

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))

_PROMPTS: tuple[str, ...] = ("hello world", "she sells sea shells")


def _c_oracle_out_t0(capi: CAPI, text: str) -> list[int]:
    """Per-frame raw OUT_T0 from the C oracle's ``vtm_frames.dump``."""
    with tempfile.TemporaryDirectory(prefix="dectalk-t0-") as dump_dir:
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
            raise SystemExit(
                "vtm_frames.dump not produced; the C oracle was built "
                "without patch 0006. Re-run scripts/setup_c_oracle.sh."
            )
        payload = dump_path.read_bytes().decode("latin-1")

    out: list[int] = []
    for line in payload.splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0] != "vtm_frame":
            continue
        out.append(int(parts[2 + OUT_T0]))
    return out


def _python_out_t0(text: str) -> list[int]:
    """Per-frame raw OUT_T0 from the Python full pipeline.

    Monkeypatches the parstochip->LLFrame delayed converter to record
    ``parstochip[OUT_T0]`` per frame, then runs ``dectalk.speak`` with
    the pure-Python / full-pipeline / vtm1 env knobs.
    """
    from dectalk.ph import parstochip_to_frames as _ptf  # noqa: PLC0415

    captured: list[int] = []
    original = _ptf.parstochip_to_llframe_delayed

    def _wrap(parstochip: list[int], *args: object, **kwargs: object) -> object:
        captured.append(parstochip[OUT_T0])
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
        import dectalk  # noqa: PLC0415 -- gated import (env-dependent dispatch)

        dectalk.speak(text)
    finally:
        _ptf.parstochip_to_llframe_delayed = original
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return captured


def _summ(label: str, series: list[int]) -> str:
    nz = [x for x in series if x > 0]
    if not nz:
        return f"{label}: all-zero ({len(series)} frames)"
    return (
        f"{label}: n={len(series)} voiced={len(nz)} "
        f"mean={statistics.mean(nz):.1f} min={min(nz)} max={max(nz)}"
    )


def main() -> None:
    """Run both pipelines on the prompts and print OUT_T0 |Δ| stats."""
    capi = CAPI(src_root=_SRC_ROOT, data_root=_BIN_ROOT)
    for prompt in _PROMPTS:
        c = _c_oracle_out_t0(capi, prompt)
        py = _python_out_t0(prompt)
        # Compare on voiced frames (OUT_T0 > 0), common prefix length.
        cv = [v for v in c if v > 0]
        pv = [v for v in py if v > 0]
        n = min(len(cv), len(pv))
        if n == 0:
            print(f"\n=== {prompt!r} ===")
            print(_summ("c_oracle", c))
            print(_summ("python  ", py))
            print("NO common voiced frames")
            continue
        deltas = [abs(cv[i] - pv[i]) for i in range(n)]
        worst_idx = max(range(n), key=lambda i: deltas[i])
        print(f"\n=== {prompt!r} (raw OUT_T0) ===")
        print(_summ("c_oracle", c))
        print(_summ("python  ", py))
        print(f"compared voiced frames: {n} (c={len(cv)} py={len(pv)})")
        print(f"mean |Δ|: {statistics.mean(deltas):.1f}")
        print(
            f"max  |Δ|: {max(deltas)} at frame {worst_idx} (c={cv[worst_idx]} py={pv[worst_idx]})"
        )


if __name__ == "__main__":
    main()
