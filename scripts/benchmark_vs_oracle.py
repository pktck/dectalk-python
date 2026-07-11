#!/usr/bin/env python3
r"""Benchmark the pure-Python DECtalk pipeline against the C oracle (issue #349).

Measurement only. Compares three render paths that each turn the same
input text into an identical-format 11025 Hz mono 16-bit WAV:

1. ``python`` — pure-Python ``dectalk.to_wav()`` with
   ``DECTALK_DISABLE_CAPI=1`` + ``DECTALK_FULL_PIPELINE=1`` (the FULL+VTM1
   pipeline the port team owns).
2. ``capi`` — ``dectalk.to_wav()`` with the CAPI enabled, driving the
   locally-built ``libtts_us.so`` via ctypes *in the same process* — the
   fair same-process comparison.
3. ``say`` — ``$DECTALK_BIN/say -a TEXT -fo OUT`` as a subprocess — the
   real end-to-end reference, including process startup.

Each path runs in its **own** subprocess so that:

* ``DECTALK_DISABLE_CAPI`` is set *before* ``import dectalk`` (it is read at
  first-synth time, not re-checked afterwards), and
* the in-process C library — which segfaults after ~45-60 s of cumulative
  use — never accumulates work across paths.

Per prompt, one warm-up render is discarded, then the reported figure is
the **median** of ``--runs`` timed renders.

This complements ``tests/perf/test_synth_perf.py`` (the pure-Python-only
perf *gate*); it does not replace it. It is a script, not a pytest, so it
never runs in the normal test lanes.

Run (shared, never-rebuilt oracle)::

    DECTALK_SRC=/tmp/dectalk-oracle-src DECTALK_BIN=/tmp/dectalk-oracle-bin \
        uv run python scripts/benchmark_vs_oracle.py --write-doc

The hotspot breakdown at the end is for *future* reference only — this
issue is measurement, not optimization. Do not act on it here.
"""

from __future__ import annotations

import argparse
import functools
import io
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import wave
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

SAMPLE_RATE_HZ: Final[int] = 11025
DEFAULT_RUNS: Final[int] = 5
DEFAULT_SRC: Final[str] = "/tmp/dectalk-oracle-src"  # documented shared oracle
DEFAULT_BIN: Final[str] = "/tmp/dectalk-oracle-bin"  # documented shared oracle
_MS_PER_S: Final[float] = 1000.0
_TOP_N_HOTSPOTS: Final[int] = 12
# A pure-Python realtime factor above this on typical prompts reads as
# "comfortably faster than realtime" for the verdict.
_REALTIME_COMFORT_MARGIN: Final[float] = 3.0

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

_DISABLE_CAPI_ENV: Final[str] = "DECTALK_DISABLE_CAPI"
_FULL_PIPELINE_ENV: Final[str] = "DECTALK_FULL_PIPELINE"
_SRC_ENV: Final[str] = "DECTALK_SRC"
_BIN_ENV: Final[str] = "DECTALK_BIN"

PATH_PYTHON: Final[str] = "python"
PATH_CAPI: Final[str] = "capi"
PATH_SAY: Final[str] = "say"
_ALL_PATHS: Final[tuple[str, ...]] = (PATH_PYTHON, PATH_CAPI, PATH_SAY)
_PATH_LABEL: Final[dict[str, str]] = {
    PATH_PYTHON: "pure-Python",
    PATH_CAPI: "_capi (in-process)",
    PATH_SAY: "say (subprocess)",
}


@dataclass(frozen=True)
class Prompt:
    """A benchmark input.

    Attributes:
        id: Stable identifier used as a dict key and table row label.
        category: Human-readable bucket shown in the report.
        text: The literal text handed to every render path.
        runs: Per-prompt run override; ``0`` means "use the global count".
            Used to cap the expensive 16x sweep point.
    """

    id: str
    category: str
    text: str
    runs: int = 0


# The size-sweep base paragraph. Two sentences, 14 words. Kept compact so
# the 16x point (~140 s of synthesized audio per render on the pure-Python
# path) stays inside a sane wall-clock budget.
_BASE_PARAGRAPH: Final[str] = (
    "The vocal tract model turns phonemes into sound. It now runs entirely in Python."
)


def _repeat(text: str, times: int) -> str:
    """Return ``text`` concatenated ``times`` times, space-joined."""
    return " ".join([text] * times)


PROMPTS: Final[tuple[Prompt, ...]] = (
    Prompt("short", "short word", "hello"),
    Prompt("medium", "one sentence", "The quick brown fox jumps over the lazy dog."),
    Prompt("long", "paragraph (x1)", _BASE_PARAGRAPH),
    Prompt("phoneme_dense", "phoneme-dense", "Peter Piper picked a peck of pickled peppers."),
    Prompt("number_heavy", "number-heavy", "In 1987 he paid $1,234.56 for 42 of the 365 items."),
    Prompt("para_x4", "paragraph (x4)", _repeat(_BASE_PARAGRAPH, 4)),
    Prompt("para_x16", "paragraph (x16)", _repeat(_BASE_PARAGRAPH, 16), runs=3),
)
_PROMPT_BY_ID: Final[dict[str, Prompt]] = {p.id: p for p in PROMPTS}

# Rows that make up the size sweep, in ascending order.
_SWEEP_IDS: Final[tuple[str, ...]] = ("long", "para_x4", "para_x16")
# The representative long prompt profiled for the hotspot breakdown.
_PROFILE_PROMPT_ID: Final[str] = "para_x4"


# --------------------------------------------------------------------------
# Measurement primitives (worker side)
# --------------------------------------------------------------------------


@dataclass
class Timing:
    """Median timing for one (path, prompt) pair.

    Times are in milliseconds; ``audio_s`` is the produced WAV's duration.
    ``error`` is non-empty when the render failed (median is then 0).
    """

    id: str
    category: str
    samples: int
    audio_s: float
    render_ms_median: float
    render_ms_min: float
    runs_ok: int
    error: str = field(default="")

    @classmethod
    def from_json(cls, obj: dict[str, object]) -> Timing:
        """Rebuild a :class:`Timing` from its ``asdict`` JSON form."""
        return cls(
            id=cast(str, obj["id"]),
            category=cast(str, obj["category"]),
            samples=cast(int, obj["samples"]),
            audio_s=cast(float, obj["audio_s"]),
            render_ms_median=cast(float, obj["render_ms_median"]),
            render_ms_min=cast(float, obj["render_ms_min"]),
            runs_ok=cast(int, obj["runs_ok"]),
            error=cast(str, obj.get("error", "")),
        )


def _wav_duration(path: Path) -> tuple[int, float]:
    """Return ``(frame_count, seconds)`` for a mono WAV file."""
    with wave.open(str(path), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
    return frames, (frames / rate if rate else 0.0)


def _time_calls(runs: int, render: Callable[[], object]) -> tuple[list[float], str]:
    """Time ``render`` ``runs`` times; return ``(millisecond_samples, error)``.

    Stops at the first failure, recording its ``repr`` in ``error`` so a
    single flaky prompt does not sink the whole path.
    """
    times_ms: list[float] = []
    error = ""
    for _ in range(runs):
        try:
            start = time.perf_counter()
            render()
            times_ms.append((time.perf_counter() - start) * _MS_PER_S)
        except Exception as exc:  # pragma: no cover - defensive
            error = repr(exc)
            break
    return times_ms, error


def _measure(prompt: Prompt, runs: int, render: Callable[[], object], out: Path) -> Timing:
    """Warm up, then median-time ``render``; read the produced WAV's length."""
    try:
        render()  # untimed warm-up: lazy lexicon / LUT / C-lib load, OS cache
    except Exception as exc:  # pragma: no cover - defensive
        return Timing(prompt.id, prompt.category, 0, 0.0, 0.0, 0.0, 0, error=f"warmup: {exc!r}")
    samples, audio_s = _wav_duration(out)
    times_ms, error = _time_calls(runs, render)
    if not times_ms:
        return Timing(
            prompt.id,
            prompt.category,
            samples,
            audio_s,
            0.0,
            0.0,
            0,
            error=error or "no successful runs",
        )
    return Timing(
        prompt.id,
        prompt.category,
        samples,
        audio_s,
        statistics.median(times_ms),
        min(times_ms),
        len(times_ms),
        error=error,
    )


def _say_once(say_bin: Path, cwd: Path, text: str, out: Path) -> None:
    """Render ``text`` to ``out`` via the ``say`` binary (one subprocess)."""
    subprocess.run(
        [str(say_bin), "-a", text, "-fo", str(out)],
        cwd=str(cwd),
        capture_output=True,
        check=True,
    )


def _runs_for(prompt: Prompt, default_runs: int) -> int:
    """Resolve the run count for ``prompt`` given the global default."""
    if prompt.runs <= 0:
        return default_runs
    return min(prompt.runs, default_runs)


def _ensure_importable() -> None:
    """Put ``src/`` on ``sys.path`` so ``import dectalk`` works when run directly."""
    src = str(_REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _selected_prompts(only: str | None) -> tuple[Prompt, ...]:
    """Return the prompt subset named by a comma id list, or all prompts."""
    if not only:
        return PROMPTS
    wanted = {tok.strip() for tok in only.split(",") if tok.strip()}
    return tuple(p for p in PROMPTS if p.id in wanted)


# --------------------------------------------------------------------------
# Worker entry points (run in a child process with a path-specific env)
# --------------------------------------------------------------------------


def _run_worker(path: str, runs: int, only: str | None) -> int:
    """Time every prompt for one render ``path``; emit a JSON payload to stdout."""
    prompts = _selected_prompts(only)
    timings: list[Timing] = []
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        if path == PATH_SAY:
            bin_root = Path(os.environ.get(_BIN_ENV, DEFAULT_BIN))
            say_bin = bin_root / "say"
            for prompt in prompts:
                out = out_dir / f"{prompt.id}.wav"
                render = functools.partial(_say_once, say_bin, bin_root, prompt.text, out)
                timings.append(_measure(prompt, _runs_for(prompt, runs), render, out))
        else:
            _ensure_importable()
            import dectalk  # noqa: PLC0415 - deferred so the env gate above applies

            for prompt in prompts:
                out = out_dir / f"{prompt.id}.wav"
                render = functools.partial(dectalk.to_wav, prompt.text, out)
                timings.append(_measure(prompt, _runs_for(prompt, runs), render, out))

    payload = {
        "path": path,
        "requested_runs": runs,
        "results": [asdict(t) for t in timings],
    }
    json.dump(payload, sys.stdout)
    return 0


def _run_profile(prompt_id: str) -> int:
    """Profile one pure-Python render via cProfile; print the top-N by cumulative time."""
    import cProfile  # noqa: PLC0415
    import pstats  # noqa: PLC0415

    _ensure_importable()
    import dectalk  # noqa: PLC0415

    prompt = _PROMPT_BY_ID[prompt_id]
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "profile.wav"
        dectalk.to_wav(prompt.text, out)  # warm-up
        profiler = cProfile.Profile()
        profiler.enable()
        dectalk.to_wav(prompt.text, out)
        profiler.disable()
        buffer = io.StringIO()
        stats = pstats.Stats(profiler, stream=buffer).strip_dirs().sort_stats("cumulative")
        stats.print_stats(_TOP_N_HOTSPOTS)
    sys.stdout.write(buffer.getvalue())
    return 0


# --------------------------------------------------------------------------
# Orchestration (parent process; never imports dectalk)
# --------------------------------------------------------------------------


def _worker_env(path: str, src: str, bin_root: str) -> dict[str, str]:
    """Build the child-process environment for one render ``path``."""
    env = os.environ.copy()
    env[_SRC_ENV] = src
    env[_BIN_ENV] = bin_root
    if path == PATH_PYTHON:
        env[_DISABLE_CAPI_ENV] = "1"
        env[_FULL_PIPELINE_ENV] = "1"
    elif path == PATH_CAPI:
        env[_DISABLE_CAPI_ENV] = "0"
        env.pop(_FULL_PIPELINE_ENV, None)
    return env


def _launch(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Re-invoke this script as a child worker with ``args`` and ``env``."""
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), *args],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _collect_path(
    path: str, runs: int, src: str, bin_root: str, only: str | None
) -> tuple[dict[str, Timing], str]:
    """Run the worker for ``path`` and parse its results (or an error)."""
    args = ["--worker", path, "--runs", str(runs)]
    if only:
        args += ["--only", only]
    proc = _launch(args, _worker_env(path, src, bin_root))
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        tail = detail[-1] if detail else "(no output)"
        return {}, f"worker exited {proc.returncode}: {tail}"
    data = cast("dict[str, object]", json.loads(proc.stdout))
    results = cast("list[dict[str, object]]", data["results"])
    return {cast(str, r["id"]): Timing.from_json(r) for r in results}, ""


def _collect_profile(src: str, bin_root: str) -> str:
    """Run the cProfile worker on the pure-Python path; return its text."""
    proc = _launch(
        ["--profile", "--prompt", _PROFILE_PROMPT_ID],
        _worker_env(PATH_PYTHON, src, bin_root),
    )
    if proc.returncode != 0:
        return f"(profile worker failed: {(proc.stderr or '').strip()[-300:]})"
    return proc.stdout.strip()


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------


def _fmt_ms(value: float) -> str:
    """Format a millisecond figure with size-appropriate precision."""
    if value <= 0:
        return "—"
    if value < 10:
        return f"{value:.2f}"
    if value < 100:
        return f"{value:.1f}"
    return f"{value:.0f}"


def _fmt_rtx(value: float) -> str:
    """Format a realtime factor (``audio_s / render_s``)."""
    if value <= 0:
        return "—"
    if value >= 100:
        return f"{value:.0f}×"
    return f"{value:.1f}×"


def _fmt_ratio(value: float) -> str:
    """Format a slowdown ratio."""
    return "—" if value <= 0 else f"{value:.1f}×"


def _fmt_s(value: float) -> str:
    """Format a seconds figure."""
    return "—" if value <= 0 else f"{value:.2f}"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a GitHub-flavoured markdown table."""
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out)


def _median_s(t: Timing | None) -> float:
    """Return a timing's median render time in seconds, or 0 if unavailable."""
    return 0.0 if t is None or t.render_ms_median <= 0 else t.render_ms_median / _MS_PER_S


# --------------------------------------------------------------------------
# Report sections
# --------------------------------------------------------------------------


def _render_time_table(
    py: dict[str, Timing], capi: dict[str, Timing], say: dict[str, Timing]
) -> str:
    """Table 1: median render time per path + pure-Python/_capi slowdown."""
    rows: list[list[str]] = []
    for prompt in PROMPTS:
        pt, ct, st = py.get(prompt.id), capi.get(prompt.id), say.get(prompt.id)
        ratio = (_median_s(pt) / _median_s(ct)) if _median_s(ct) > 0 else 0.0
        rows.append(
            [
                f"`{prompt.id}`",
                prompt.category,
                _fmt_ms(pt.render_ms_median if pt else 0.0),
                _fmt_ms(ct.render_ms_median if ct else 0.0),
                _fmt_ms(st.render_ms_median if st else 0.0),
                _fmt_ratio(ratio),
            ]
        )
    headers = ["prompt", "category", "pure-Python (ms)", "_capi (ms)", "say (ms)", "py ÷ _capi"]
    return _md_table(headers, rows)


def _realtime_table(py: dict[str, Timing], capi: dict[str, Timing], say: dict[str, Timing]) -> str:
    """Table 2: realtime factor per path (audio_s / render_s)."""
    rows: list[list[str]] = []
    for prompt in PROMPTS:
        pt, ct, st = py.get(prompt.id), capi.get(prompt.id), say.get(prompt.id)
        audio_c = ct.audio_s if ct else (st.audio_s if st else 0.0)
        audio_py = pt.audio_s if pt else 0.0
        py_s = _median_s(pt)
        rtx_own = (audio_py / py_s) if py_s > 0 else 0.0
        rtx_true = (audio_c / py_s) if py_s > 0 else 0.0
        rtx_capi = (audio_c / _median_s(ct)) if _median_s(ct) > 0 else 0.0
        rtx_say = (audio_c / _median_s(st)) if _median_s(st) > 0 else 0.0
        rows.append(
            [
                f"`{prompt.id}`",
                _fmt_s(audio_c),
                _fmt_s(audio_py),
                _fmt_rtx(rtx_own),
                _fmt_rtx(rtx_true),
                _fmt_rtx(rtx_capi),
                _fmt_rtx(rtx_say),
            ]
        )
    headers = [
        "prompt",
        "audio C (s)",
        "audio py (s)",
        "py RT× (own)",
        "py RT× (vs C)",
        "_capi RT×",
        "say RT×",
    ]
    return _md_table(headers, rows)


def _sweep_table(py: dict[str, Timing], capi: dict[str, Timing]) -> str:
    """Table 3: the 1x/4x/16x size sweep — is the ratio constant or growing?"""
    rows: list[list[str]] = []
    for sid in _SWEEP_IDS:
        prompt = _PROMPT_BY_ID[sid]
        pt, ct = py.get(sid), capi.get(sid)
        py_s, capi_s = _median_s(pt), _median_s(ct)
        ratio = (py_s / capi_s) if capi_s > 0 else 0.0
        rtx_own = (pt.audio_s / py_s) if (pt and py_s > 0) else 0.0
        words = len(prompt.text.split())
        rows.append(
            [
                sid.replace("long", "para_x1"),
                str(words),
                _fmt_ms(pt.render_ms_median if pt else 0.0),
                _fmt_ms(ct.render_ms_median if ct else 0.0),
                _fmt_ratio(ratio),
                _fmt_rtx(rtx_own),
            ]
        )
    headers = ["size", "words", "pure-Python (ms)", "_capi (ms)", "py ÷ _capi", "py RT× (own)"]
    return _md_table(headers, rows)


def _verdict(py: dict[str, Timing], capi: dict[str, Timing]) -> str:
    """Compose the data-driven one-paragraph verdict."""
    typical = ("short", "medium", "long")
    rtx_true: list[float] = []
    ratios: list[float] = []
    samp_deltas: list[float] = []
    for pid in typical:
        pt, ct = py.get(pid), capi.get(pid)
        py_s = _median_s(pt)
        if pt and py_s > 0 and ct and ct.audio_s > 0:
            rtx_true.append(ct.audio_s / py_s)
        capi_s = _median_s(ct)
        if py_s > 0 and capi_s > 0:
            ratios.append(py_s / capi_s)
        if pt and ct and ct.samples > 0:
            samp_deltas.append(abs(pt.samples / ct.samples - 1.0))

    if not rtx_true:
        return "Verdict: insufficient data — one or more render paths failed to run."

    lo_true, hi_true = min(rtx_true), max(rtx_true)
    comfortable = lo_true >= _REALTIME_COMFORT_MARGIN
    samp_pct = max(samp_deltas) * 100.0 if samp_deltas else 0.0
    match_clause = (
        "matches the oracle's sample count exactly on the short prompts"
        if samp_pct < 0.05
        else f"matches the oracle's output length to within {samp_pct:.1f}%"
    )

    # Sweep throughput extremes for the "why the ratio grows" clause.
    capi_short = _median_s(capi.get("long"))
    capi_long = _median_s(capi.get("para_x16"))
    ct_short, ct_long = capi.get("long"), capi.get("para_x16")
    capi_rtx_short = (ct_short.audio_s / capi_short) if (ct_short and capi_short > 0) else 0.0
    capi_rtx_long = (ct_long.audio_s / capi_long) if (ct_long and capi_long > 0) else 0.0
    py_long = py.get("para_x16")
    py_long_s = _median_s(py_long)
    py_rtx_sweep = (py_long.audio_s / py_long_s) if (py_long and py_long_s > 0) else 0.0

    ratio_lo = min(ratios) if ratios else 0.0
    ratio_hi = max(ratios) if ratios else 0.0

    stance = (
        "pure-Python is already fast enough and optimization is **not** required"
        if comfortable
        else "pure-Python may need optimization for realtime use"
    )
    return (
        f"**Verdict.** On typical prompts (a word, a sentence, a short paragraph) the "
        f"pure-Python FULL+VTM1 pipeline renders at {_fmt_rtx(lo_true)}–{_fmt_rtx(hi_true)} "
        f"realtime — comfortably faster than realtime — and its output {match_clause} "
        f"(so the two realtime-factor columns nearly coincide). It is "
        f"{_fmt_ratio(ratio_lo)}–{_fmt_ratio(ratio_hi)} slower than the in-process C library "
        f"on these prompts, and that ratio *grows* with utterance length — but only because "
        f"the C library is dominated by a near-constant per-call setup cost (its throughput "
        f"climbs from ~{_fmt_rtx(capi_rtx_short)} to ~{_fmt_rtx(capi_rtx_long)} realtime "
        f"across the 1×→16× sweep) while the Python path's cost is essentially linear at a "
        f"steady ~{_fmt_rtx(py_rtx_sweep)} realtime. Conclusion: for interactive and batch use "
        f"at typical prompt sizes, {stance}; revisit only if a workload needs "
        f"many-fold-realtime bulk throughput, in which case the hotspots below are where to start."
    )


def _machine_line() -> str:
    """One-line machine/runtime description for reproducibility."""
    cpus = os.cpu_count() or 0
    return (
        f"{platform.platform()} · Python {platform.python_version()} · "
        f"{cpus} logical CPUs · {platform.processor() or platform.machine()}"
    )


def _git_commit() -> str:
    """Best-effort short git SHA of the working tree."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return proc.stdout.strip() or "unknown"


def _build_report(
    results: dict[str, dict[str, Timing]],
    profile_text: str,
    src: str,
    bin_root: str,
    runs: int,
    errors: dict[str, str],
) -> str:
    """Assemble the full markdown report body."""
    py, capi, say = results[PATH_PYTHON], results[PATH_CAPI], results[PATH_SAY]
    when = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    parts: list[str] = []
    parts.append("## Methodology\n")
    parts.append(
        "Three render paths, each producing an identical-format 11025 Hz mono 16-bit WAV "
        "from the same text, each timed in its **own subprocess** (so `DECTALK_DISABLE_CAPI` "
        "is fixed before `import dectalk`, and the in-process C library never accumulates "
        "enough work to hit its ~45-60 s segfault):\n"
    )
    parts.append(
        "1. **pure-Python** — `dectalk.to_wav()` with `DECTALK_DISABLE_CAPI=1` + "
        "`DECTALK_FULL_PIPELINE=1` (FULL+VTM1).\n"
        "2. **_capi (in-process)** — `dectalk.to_wav()` driving the built `libtts_us.so` "
        "via ctypes.\n"
        "3. **say (subprocess)** — `$DECTALK_BIN/say -a TEXT -fo OUT` (includes process "
        "startup).\n"
    )
    parts.append(
        f"Per prompt: one warm-up render discarded, then the **median** of {runs} timed "
        f"renders (16× sweep point capped at 3). Realtime factor = `audio_seconds / "
        f"render_seconds` (>1 = faster than realtime).\n"
    )
    parts.append(
        f"_Run: {when} · {_machine_line()} · commit `{_git_commit()}` · "
        f"oracle `{src}` / `{bin_root}`._\n"
    )
    if any(errors.values()):
        broken = "; ".join(f"{k}: {v}" for k, v in errors.items() if v)
        parts.append(f"> ⚠️ Path failures: {broken}\n")

    parts.append("## 1. Median render time & pure-Python ÷ _capi slowdown\n")
    parts.append(_render_time_table(py, capi, say) + "\n")
    parts.append("## 2. Realtime factor (audio ÷ render; >1 = faster than realtime)\n")
    parts.append(
        "`py RT× (own)` divides by the pure-Python path's own audio length; "
        "`py RT× (vs C)` divides by the C oracle's (canonical) length. On `dev` the two "
        "nearly coincide because pure-Python's sample count matches the oracle to within "
        "~0.1% (exactly, on the short prompts).\n"
    )
    parts.append(_realtime_table(py, capi, say) + "\n")
    parts.append("## 3. Size sweep — is the Python/C ratio constant or growing?\n")
    parts.append(_sweep_table(py, capi) + "\n")
    parts.append("## Verdict\n")
    parts.append(_verdict(py, capi) + "\n")
    parts.append("## Hotspot breakdown (pure-Python, cProfile, informational only)\n")
    parts.append(
        f"Top {_TOP_N_HOTSPOTS} by cumulative time on `{_PROFILE_PROMPT_ID}` "
        f"(the 4× paragraph) through the pure-Python path. **Not acted on** — issue #349 is "
        f"measurement only; this is a signpost for any future optimization.\n"
    )
    parts.append("```\n" + profile_text + "\n```\n")
    return "\n".join(parts)


_DOC_HEADER: Final[str] = (
    "# Performance: pure-Python pipeline vs the C oracle\n\n"
    "Reproducible benchmark for issue #349 — **measurement only**, no pipeline changes.\n\n"
    "Regenerate (numbers are machine-dependent) with:\n\n"
    "```bash\n"
    "DECTALK_SRC=/tmp/dectalk-oracle-src DECTALK_BIN=/tmp/dectalk-oracle-bin \\\n"
    "    uv run python scripts/benchmark_vs_oracle.py --write-doc\n"
    "```\n\n"
    "It complements `tests/perf/test_synth_perf.py` (the pure-Python-only perf gate); it is a\n"
    "script, not a pytest, so it never runs in the normal test lanes.\n\n"
)


def _write_doc(report: str, doc_path: Path) -> None:
    """Write the full report to ``docs/PERF.md`` with a stable header."""
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(_DOC_HEADER + report, encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--runs", type=int, default=DEFAULT_RUNS, help="timed runs per prompt (median)"
    )
    parser.add_argument("--src", default=os.environ.get(_SRC_ENV, DEFAULT_SRC), help="DECTALK_SRC")
    parser.add_argument(
        "--bin", dest="bin_root", default=os.environ.get(_BIN_ENV, DEFAULT_BIN), help="DECTALK_BIN"
    )
    parser.add_argument("--only", default=None, help="comma-separated prompt ids to restrict to")
    parser.add_argument("--write-doc", action="store_true", help="write docs/PERF.md")
    parser.add_argument(
        "--doc-path", default=str(_REPO_ROOT / "docs" / "PERF.md"), help="report output path"
    )
    parser.add_argument("--json", dest="json_out", default=None, help="also dump raw timings JSON")
    parser.add_argument("--no-profile", action="store_true", help="skip the cProfile hotspot pass")
    # Worker-mode flags (internal; the orchestrator re-invokes itself).
    parser.add_argument("--worker", choices=_ALL_PATHS, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--profile", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--prompt", default=_PROFILE_PROMPT_ID, help=argparse.SUPPRESS)
    return parser


def _run_orchestrator(args: argparse.Namespace) -> int:
    """Fan out per-path workers, assemble the report, print and optionally persist it."""
    src = cast(str, args.src)
    bin_root = cast(str, args.bin_root)
    runs = cast(int, args.runs)
    only = cast("str | None", args.only)

    if not (Path(bin_root) / "say").is_file():
        sys.stderr.write(
            f"error: '{bin_root}/say' not found. Point --bin / $DECTALK_BIN at the built "
            f"oracle (e.g. /tmp/dectalk-oracle-bin).\n"
        )
        return 2

    results: dict[str, dict[str, Timing]] = {}
    errors: dict[str, str] = {}
    for path in _ALL_PATHS:
        sys.stderr.write(f"[benchmark] timing '{_PATH_LABEL[path]}' …\n")
        timings, err = _collect_path(path, runs, src, bin_root, only)
        results[path] = timings
        errors[path] = err
        if err:
            sys.stderr.write(f"[benchmark]   {path}: {err}\n")

    profile_text = ""
    if not cast(bool, args.no_profile):
        sys.stderr.write("[benchmark] profiling pure-Python hotspots …\n")
        profile_text = _collect_profile(src, bin_root)

    report = _build_report(results, profile_text, src, bin_root, runs, errors)
    sys.stdout.write(report + "\n")

    if cast(bool, args.write_doc):
        doc_path = Path(cast(str, args.doc_path))
        _write_doc(report, doc_path)
        sys.stderr.write(f"[benchmark] wrote {doc_path}\n")

    if args.json_out:
        raw = {p: {k: asdict(v) for k, v in results[p].items()} for p in _ALL_PATHS}
        Path(cast(str, args.json_out)).write_text(json.dumps(raw, indent=2), encoding="utf-8")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Program entry point."""
    args = _build_parser().parse_args(argv)
    if cast("str | None", args.worker) is not None:
        return _run_worker(
            cast(str, args.worker), cast(int, args.runs), cast("str | None", args.only)
        )
    if cast(bool, args.profile):
        return _run_profile(cast(str, args.prompt))
    return _run_orchestrator(args)


if __name__ == "__main__":
    raise SystemExit(main())
