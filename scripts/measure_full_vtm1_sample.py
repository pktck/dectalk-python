#!/usr/bin/env python3
"""Measure pure-Python FULL+VTM1 parity on a stratified 500-prompt sample.

For each prompt, renders:
  - Python output via ``DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1
    dectalk.to_wav(...)`` (the FULL pipeline renders via vtm1 only
    since the #279 retirement)
  - C binary output via ``$DECTALK_BIN/say -a TEXT -fo OUT``

Records per-prompt sample-delta (Python len - C len) and writes a TSV
with the raw measurements plus a histogram/summary on stdout for the
audit doc.

Used by ``docs/parity-divergence-audit.md`` to decide whether the
``_speak_via_python`` dispatch should default to FULL+VTM1.
"""

# ruff: noqa: D103, PLR0911, PLR0912, PLR0915, PLR2004, SIM105 -- one-off measurement script

from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

# Ensure pure-Python pipeline gating before importing dectalk.
os.environ["DECTALK_DISABLE_CAPI"] = "1"
os.environ["DECTALK_FULL_PIPELINE"] = "1"

# Path bootstrap so the script can be run as ``uv run python scripts/...``.
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

import dectalk  # noqa: E402
from tests.parity._corpus import CORPUS  # noqa: E402

_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _categorize(text: str) -> str:
    """Bucket a prompt by syntactic shape."""
    has_inline = "[" in text and "]" in text
    if has_inline:
        if "[:phoneme" in text.lower() or ":ph on" in text.lower():
            return "phoneme_mode"
        return "inline_cmd"
    if "?" in text:
        return "question"
    if "!" in text:
        return "exclamation"
    if "," in text or ";" in text:
        return "multi_clause"
    if re.search(r"\d", text):
        return "has_number"
    if re.search(r"[A-Z]{3,}", text):
        return "all_caps_run"
    if len(text.split()) == 1:
        return "single_word"
    if len(text.split()) > 10:
        return "long"
    return "plain"


def _stratified_sample(seed: int = 42, total: int = 500) -> list[str]:
    """Stratified sample: rare cats over-sampled so they get signal."""
    rng = random.Random(seed)
    by_cat: dict[str, list[str]] = {}
    for s in CORPUS:
        by_cat.setdefault(_categorize(s), []).append(s)

    targets = {
        "question": 5,
        "exclamation": 2,
        "phoneme_mode": 0,
        "inline_cmd": 11,
        "has_number": 18,
        "all_caps_run": 31,
        "long": 60,
        "single_word": 60,
        "multi_clause": 60,
    }
    out: list[str] = []
    for cat, want in targets.items():
        avail = by_cat.get(cat, [])
        take = min(want, len(avail))
        out.extend(rng.sample(avail, take))

    # Fill the rest with "plain".
    plain = by_cat.get("plain", [])
    needed = total - len(out)
    out.extend(rng.sample(plain, needed))
    return out


def _binary_wav_bytes(text: str) -> bytes:
    """Render via the shipped binary; return WAV bytes."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out = Path(f.name)
    try:
        subprocess.run(
            [str(_BIN_ROOT / "say"), "-a", text, "-fo", str(out)],
            cwd=str(_BIN_ROOT),
            check=True,
            capture_output=True,
            timeout=30,
        )
        return out.read_bytes()
    finally:
        try:
            out.unlink()
        except FileNotFoundError:
            pass


def _python_wav_bytes(text: str) -> bytes:
    """Render via dectalk.to_wav under FULL+VTM1+DISABLE_CAPI."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        out = Path(f.name)
    try:
        dectalk.to_wav(text, out)
        return out.read_bytes()
    finally:
        try:
            out.unlink()
        except FileNotFoundError:
            pass


def _wav_sample_count(b: bytes) -> int:
    """Decode WAV bytes; return the sample frame count."""
    import io  # noqa: PLC0415

    with wave.open(io.BytesIO(b), "rb") as wf:
        return wf.getnframes()


def main() -> None:
    if not (_BIN_ROOT / "say").is_file():
        sys.exit(f"DECTALK_BIN={_BIN_ROOT} missing 'say'; run scripts/setup_c_oracle.sh first")

    prompts = _stratified_sample()
    out_tsv = _REPO / "tests" / "parity" / "_full_vtm1_sample_results.tsv"
    out_summary = _REPO / "tests" / "parity" / "_full_vtm1_sample_summary.json"

    t0 = time.time()
    records: list[dict[str, object]] = []
    n_exact = 0
    for i, text in enumerate(prompts):
        try:
            bin_b = _binary_wav_bytes(text)
            py_b = _python_wav_bytes(text)
            bin_n = _wav_sample_count(bin_b)
            py_n = _wav_sample_count(py_b)
            exact = bin_b == py_b
            if exact:
                n_exact += 1
            records.append(
                {
                    "text": text,
                    "cat": _categorize(text),
                    "bin_len": len(bin_b),
                    "py_len": len(py_b),
                    "bin_samples": bin_n,
                    "py_samples": py_n,
                    "delta_samples": py_n - bin_n,
                    "delta_bytes": len(py_b) - len(bin_b),
                    "exact": exact,
                    "error": None,
                }
            )
        except Exception as e:
            records.append(
                {
                    "text": text,
                    "cat": _categorize(text),
                    "bin_len": None,
                    "py_len": None,
                    "bin_samples": None,
                    "py_samples": None,
                    "delta_samples": None,
                    "delta_bytes": None,
                    "exact": False,
                    "error": f"{type(e).__name__}: {e}",
                }
            )
        if (i + 1) % 25 == 0:
            elapsed = time.time() - t0
            print(
                f"  {i + 1}/{len(prompts)}  exact={n_exact}  "
                f"elapsed={elapsed:.1f}s  rate={(i + 1) / elapsed:.2f}/s",
                flush=True,
            )

    # Write TSV.
    with out_tsv.open("w") as f:
        f.write("cat\texact\tdelta_samples\tdelta_bytes\tbin_samples\tpy_samples\terror\ttext\n")
        for r in records:
            f.write(
                f"{r['cat']}\t{r['exact']}\t{r['delta_samples']}\t{r['delta_bytes']}\t"
                f"{r['bin_samples']}\t{r['py_samples']}\t{r['error'] or ''}\t"
                f"{json.dumps(r['text'])}\n"
            )

    # Per-category breakdown.
    by_cat: dict[str, dict[str, object]] = {}
    for r in records:
        cat = str(r["cat"])
        bucket = by_cat.setdefault(cat, {"n": 0, "n_exact": 0, "n_err": 0, "deltas": []})
        bucket["n"] = int(bucket["n"]) + 1  # type: ignore[arg-type]
        if r["exact"]:
            bucket["n_exact"] = int(bucket["n_exact"]) + 1  # type: ignore[arg-type]
        if r["error"]:
            bucket["n_err"] = int(bucket["n_err"]) + 1  # type: ignore[arg-type]
        elif r["delta_samples"] is not None:
            deltas = bucket["deltas"]
            assert isinstance(deltas, list)
            deltas.append(int(r["delta_samples"]))  # type: ignore[arg-type]

    # Histogram of |delta_samples|.
    deltas_all = [d for r in records if isinstance(d := r["delta_samples"], int)]
    abs_deltas = sorted(abs(d) for d in deltas_all)
    bins = [0, 1, 10, 100, 500, 1000, 5000, 10000, 50000, 10_000_000]
    hist = [0] * (len(bins) - 1)
    for d in abs_deltas:
        for i, edge in enumerate(bins[1:]):
            if d < edge:
                hist[i] += 1
                break
        else:
            hist[-1] += 1

    pct_exact = 100 * n_exact / len(prompts)

    def _cat_summary(b: dict[str, object]) -> dict[str, object]:
        deltas = b["deltas"]
        assert isinstance(deltas, list)
        cat_deltas: list[int] = [d for d in deltas if isinstance(d, int)]  # pyright: ignore[reportUnknownVariableType]
        return {
            "n": b["n"],
            "n_exact": b["n_exact"],
            "n_err": b["n_err"],
            "pct_exact": 100 * int(b["n_exact"]) / int(b["n"]),  # type: ignore[arg-type]
            "abs_delta_median": (
                sorted(abs(d) for d in cat_deltas)[len(cat_deltas) // 2] if cat_deltas else None
            ),
            "delta_min": min(cat_deltas) if cat_deltas else None,
            "delta_max": max(cat_deltas) if cat_deltas else None,
        }

    by_category: dict[str, dict[str, object]] = {cat: _cat_summary(b) for cat, b in by_cat.items()}
    summary: dict[str, object] = {
        "n_prompts": len(prompts),
        "n_exact": n_exact,
        "pct_exact": pct_exact,
        "n_err": sum(1 for r in records if r["error"]),
        "abs_delta_p50": abs_deltas[len(abs_deltas) // 2] if abs_deltas else None,
        "abs_delta_p90": abs_deltas[int(0.9 * len(abs_deltas))] if abs_deltas else None,
        "abs_delta_p99": abs_deltas[int(0.99 * len(abs_deltas))] if abs_deltas else None,
        "abs_delta_max": abs_deltas[-1] if abs_deltas else None,
        "abs_delta_mean": (sum(abs_deltas) / len(abs_deltas)) if abs_deltas else None,
        "abs_delta_bins": [{"lt": bins[i + 1], "n": hist[i]} for i in range(len(hist))],
        "by_category": by_category,
        "elapsed_sec": time.time() - t0,
    }
    out_summary.write_text(json.dumps(summary, indent=2))

    print()
    print(f"=== FULL+VTM1 sample results (n={len(prompts)}) ===")
    print(f"  bit-exact: {n_exact}/{len(prompts)} ({pct_exact:.1f}%)")
    print(f"  errors:    {summary['n_err']}")
    abs_mean = summary["abs_delta_mean"]
    mean_str = f"{abs_mean:.1f}" if isinstance(abs_mean, float) else "NA"
    print(
        f"  |delta_samples|  p50={summary['abs_delta_p50']}  "
        f"p90={summary['abs_delta_p90']}  p99={summary['abs_delta_p99']}  "
        f"max={summary['abs_delta_max']}  "
        f"mean={mean_str}"
    )
    print("  abs-delta histogram:")
    for i, h in enumerate(hist):
        lo = bins[i]
        hi = bins[i + 1]
        print(f"    [{lo:>8} .. {hi:>10}): {h}")
    print()
    print("  By category:")
    for cat in sorted(by_category):
        b = by_category[cat]
        print(
            f"    {cat:<14}  n={b['n']:>4}  exact={b['n_exact']:>4} "
            f"({b['pct_exact']:5.1f}%)  err={b['n_err']:>3}  "
            f"|d|_med={b['abs_delta_median']}  "
            f"d_range=[{b['delta_min']}, {b['delta_max']}]"
        )
    print()
    print(f"  raw TSV:    {out_tsv}")
    print(f"  summary:    {out_summary}")
    print(f"  elapsed:    {summary['elapsed_sec']:.1f}s")


if __name__ == "__main__":
    main()
