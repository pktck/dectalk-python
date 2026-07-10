#!/usr/bin/env python3
"""Packet-level divergence diff: Python FULL+VTM1 vs the C oracle.

The PARITY-METHOD §2 workhorse (issue #297). Per prompt: renders both
sides, captures the post-``send_pars`` delaypars packet streams (C via
the patch-0006 ``vtm_frames.dump``; Python via a wrapper on
``pump_frames_via_vtm1``), finds the first divergent PCM sample, and
reports per-param packet divergences with phoneme context plus the
vtm1.c:1318 ramp-down-gate (``OUT_PH & PVALUE``) disagreement count.

Usage::

    export DECTALK_SRC=/tmp/dectalk-oracle-src DECTALK_BIN=/tmp/dectalk-oracle-bin
    uv run python scripts/diag_packet_diff.py "prompt text" [more prompts...]

Emits one JSON object per prompt on stdout (line-delimited).
"""

# ruff: noqa: D103, PLR2004 -- diagnostic script; C-layout literals inline

from __future__ import annotations

import os
import sys
from typing import Any

os.environ.setdefault("DECTALK_SRC", "/tmp/dectalk-oracle-src")
os.environ.setdefault("DECTALK_BIN", "/tmp/dectalk-oracle-bin")
# Must be set before `import dectalk` (the #265 trap; PARITY-METHOD §4).
os.environ["DECTALK_DISABLE_CAPI"] = "1"
os.environ["DECTALK_FULL_PIPELINE"] = "1"
os.environ["DECTALK_USE_VTM1"] = "1"

import io
import json
import tempfile
import wave
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from dectalk._capi import CAPI
from dectalk.include.phoneme_codes import USPhoneme

_SRC = Path(os.environ["DECTALK_SRC"])
_BIN = Path(os.environ["DECTALK_BIN"])

PARAM_NAMES: tuple[str, ...] = (
    "AP", "F1", "A2", "A3", "A4", "A5", "A6", "AB", "TLT", "T0",
    "AV", "F2", "F3", "FZ", "B1", "B2", "B3", "PH", "DU", "PH2", "X20",
)  # fmt: skip
# Audio-relevant cells: exclude PH/DU/PH2 metadata (#277) and unused 20.
AUDIO_CELLS: tuple[int, ...] = tuple(i for i in range(20) if i not in (17, 18, 19))

_CODE2NAME: dict[int, str] = {}
for _m in USPhoneme:
    _CODE2NAME.setdefault(int(_m.value), _m.name)


def phname(code: int) -> str:
    return _CODE2NAME.get(code & 0xFF, f"?{code}")


def oracle_capture(capi: CAPI, text: str) -> tuple[NDArray[np.int16], list[list[int]]]:
    with tempfile.TemporaryDirectory(prefix="dectalk-diag-") as dump_dir:
        os.environ["DECTALK_DUMP_DIR"] = dump_dir
        try:
            wav_bytes = capi.speak(text)
        finally:
            os.environ.pop("DECTALK_DUMP_DIR", None)
        frames_path = Path(dump_dir) / "vtm_frames.dump"
        if not frames_path.is_file():
            msg = "vtm_frames.dump not produced (patch 0006 missing?)"
            raise RuntimeError(msg)
        payload = frames_path.read_text(encoding="latin-1")
    frames: list[list[int]] = []
    for line in payload.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "vtm_frame":
            count = int(parts[1])
            frames.append([int(x) for x in parts[2 : 2 + count]])
    with wave.open(io.BytesIO(wav_bytes)) as fh:
        pcm = np.frombuffer(fh.readframes(fh.getnframes()), dtype=np.int16)
    return pcm, frames


def python_capture(text: str) -> tuple[NDArray[np.int16], list[list[int]]]:
    from dectalk.api.speak import (  # noqa: PLC0415
        _speak_via_python_full,  # pyright: ignore[reportPrivateUsage]
    )
    from dectalk.vtm import pump_frames as pf  # noqa: PLC0415

    captured: list[list[int]] = []
    orig = pf.pump_frames_via_vtm1

    def wrap(frames: list[list[int]], *a: object, **k: object) -> NDArray[np.int16]:
        captured.extend([list(fr) for fr in frames])
        return orig(frames, *a, **k)  # type: ignore[arg-type]

    pf.pump_frames_via_vtm1 = wrap
    try:
        pcm = _speak_via_python_full(text, 1.0, None, "us", True)
    finally:
        pf.pump_frames_via_vtm1 = orig
    return pcm, captured


def int16w(v: int) -> int:
    m = v & 0xFFFF
    return m - 0x10000 if m >= 0x8000 else m


def diff_prompt(capi: CAPI, text: str) -> dict[str, Any]:
    c_pcm, c_pk = oracle_capture(capi, text)
    py_pcm, py_pk_raw = python_capture(text)
    py_pk = [[int16w(v) for v in row] for row in py_pk_raw]

    out: dict[str, Any] = {
        "text": text,
        "n_pk_c": len(c_pk),
        "n_pk_py": len(py_pk),
        "n_samp_c": int(c_pcm.size),
        "n_samp_py": int(py_pcm.size),
    }

    # OUT_T0 sanity gate on the Python capture (PARITY-METHOD §4).
    f0s = [40000.0 / p[9] for p in py_pk if p[9] > 0]
    span = (max(f0s) - min(f0s)) if f0s else 0.0
    sanity: dict[str, Any] = {
        "span_hz": round(span, 1),
        "mean_hz": round(sum(f0s) / len(f0s), 1) if f0s else 0.0,
    }
    if span <= 5.0:
        sanity["WARN"] = "flat F0 — wrong pipeline? discard"
    out["f0_sanity"] = sanity

    # First divergent PCM sample.
    n = min(c_pcm.size, py_pcm.size)
    neq = np.nonzero(c_pcm[:n] != py_pcm[:n])[0]
    if neq.size == 0 and c_pcm.size == py_pcm.size:
        out["pcm"] = "BYTE-EXACT"
        return out
    first = int(neq[0]) if neq.size else n
    out["first_div_sample"] = first
    out["first_div_frame"] = first // 71
    out["n_div_samples"] = int(neq.size)

    # Per-param packet diffs (audio-relevant cells only).
    npk = min(len(c_pk), len(py_pk))
    params: dict[str, dict[str, Any]] = {}
    for cell in AUDIO_CELLS:
        divs = [
            (j, c_pk[j][cell], py_pk[j][cell])
            for j in range(npk)
            if c_pk[j][cell] != py_pk[j][cell]
        ]
        if not divs:
            continue
        j0, cv, pv = divs[0]
        params[PARAM_NAMES[cell]] = {
            "first_pk": j0,
            "n_div": len(divs),
            "max_abs": max(abs(c - p) for _, c, p in divs),
            "first_c": cv,
            "first_py": pv,
            # Phoneme context at first divergence (delayed PH metadata cell).
            "ph_ctx": phname(py_pk[j0][17]) if len(py_pk[j0]) > 17 else "?",
            "div_pks": [j for j, _, _ in divs[:12]],
        }
    out["params"] = dict(sorted(params.items(), key=lambda kv: kv[1]["first_pk"]))

    # Ramp-down-gate divergence: packets where the vtm1.c:1318 silence
    # gate (OUT_PH & PVALUE == 0) disagrees between the two sides.
    gate_div = [
        j for j in range(npk) if ((c_pk[j][17] & 0xFF) == 0) != ((py_pk[j][17] & 0xFF) == 0)
    ]
    if gate_div:
        out["ph_gate_div"] = {"n": len(gate_div), "pks": gate_div[:10]}

    # Context rows around the first packet-level divergence.
    if params:
        jf = min(p["first_pk"] for p in params.values())
        rows: list[dict[str, Any]] = []
        for j in range(max(0, jf - 1), min(npk, jf + 3)):
            rows.append(
                {
                    "pk": j,
                    "ph": phname(py_pk[j][17]) if len(py_pk[j]) > 17 else "?",
                    "c": {PARAM_NAMES[i]: c_pk[j][i] for i in AUDIO_CELLS},
                    "py": {PARAM_NAMES[i]: py_pk[j][i] for i in AUDIO_CELLS},
                }
            )
        out["ctx"] = rows
    return out


def main() -> None:
    capi = CAPI(src_root=_SRC, data_root=_BIN)
    for text in sys.argv[1:]:
        try:
            res: dict[str, Any] = diff_prompt(capi, text)
        except Exception as e:
            res = {"text": text, "error": f"{type(e).__name__}: {e}"}
        print(json.dumps(res))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
