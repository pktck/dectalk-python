"""Performance benchmark for the synthesizer hot path.

Measures wall-clock time to synthesise a fixed phrase end-to-end via
:func:`dectalk.speak` and asserts:

1. **Drift gate**: the measured median is no more than
   :data:`DRIFT_TOLERANCE` (20%) slower than the committed baseline in
   ``tests/perf/baseline.json``. This catches per-PR regressions.
2. **Absolute gate**: synthesising 1 s of audio takes no more than
   :data:`ABS_SECONDS_PER_AUDIO_SECOND` (0.3 s) of wall-clock. This is
   the PLAN.md `Verification` target — a hard ceiling regardless of
   baseline drift, so a baseline update can't paper over a real
   slowdown.

Forces the pure-Python pipeline via ``DECTALK_DISABLE_CAPI=1`` so the
benchmark measures what the port team actually controls. The CAPI path
is bit-accurate but its perf is dominated by the C library, which the
port doesn't own.

Updating the baseline: when a deliberate perf change lands, run::

    uv run pytest tests/perf/test_synth_perf.py --benchmark-only \\
        --benchmark-json=/tmp/bench.json
    uv run python -m tests.perf.test_synth_perf --update-baseline \\
        /tmp/bench.json

(or hand-edit ``tests/perf/baseline.json``) and commit. The orchestrator
reviews baseline bumps explicitly per ``docs/PLAN-CI-STRATEGY.md`` §10.

This test is marked ``perf`` and is therefore *not* selected by the
default ``pytest`` invocation; the ``perf-bench`` CI job opts in with
``-m perf --benchmark-only``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray

if TYPE_CHECKING:
    from pytest_benchmark.fixture import BenchmarkFixture

# The phrase synthesised by the benchmark. Chosen because:
# - It's the canonical English pangram, so divergences in LTS coverage
#   are immediately visible.
# - At ~1.5 s of synthesised audio it's long enough to amortise per-
#   call setup overhead but short enough to keep the benchmark itself
#   inside ~1 s wall-clock on modern CI runners.
BENCH_PHRASE: str = "the quick brown fox"

# Native sample rate of the Python pipeline (matches the C oracle and
# the hlsyn back-end). Used to convert sample count to audio seconds
# for the absolute-ceiling check below.
SAMPLE_RATE_HZ: int = 11025

# Drift tolerance: the measured median must be no more than 20% slower
# than the committed baseline. Matches docs/PLAN-CI-STRATEGY.md §10.
DRIFT_TOLERANCE: float = 0.20

# Absolute ceiling: synthesising 1 s of audio takes no more than 0.3 s
# of wall-clock. Matches docs/PLAN.md `Verification` target ("synthesis
# of 1 s of speech in <= 0.3 s on a modern laptop"). Acts as a safety
# net regardless of baseline drift.
ABS_SECONDS_PER_AUDIO_SECOND: float = 0.30

BASELINE_PATH: Path = Path(__file__).parent / "baseline.json"


def _load_baseline() -> dict[str, Any]:
    """Load the committed baseline JSON, or return an empty dict if absent.

    Absence is permitted on the first run after the test lands — the
    benchmark still records a measurement; only the drift assertion
    becomes a no-op. CI will fail the absolute-ceiling check if the
    synth is catastrophically slow regardless.
    """
    if not BASELINE_PATH.exists():
        return {}
    with BASELINE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.perf
def test_speak_pangram_perf(benchmark: BenchmarkFixture) -> None:
    """Benchmark `dectalk.speak` on a fixed pangram via the Python pipeline.

    Routes through the approximate Python pipeline by setting
    ``DECTALK_DISABLE_CAPI=1`` — the port team owns this path and a
    regression here is what the perf gate is for. The CAPI path
    (when available) is faster but its perf is dominated by the C
    library, which the port doesn't control.
    """
    # Force the pure-Python pipeline. Restore the previous value at
    # teardown so other tests in the same session aren't affected.
    prev_disable = os.environ.get("DECTALK_DISABLE_CAPI")
    os.environ["DECTALK_DISABLE_CAPI"] = "1"
    try:
        # Defer the import until after the env var is set so the CAPI
        # short-circuit in dectalk.api.speak picks it up on first call.
        from dectalk import speak  # noqa: PLC0415

        # Warm caches: the first call after a fresh import does extra
        # lazy-loading (lexicon parse, voice tables, hlsyn LUTs). Without
        # this, pytest-benchmark's first iteration is an outlier that
        # skews the min/median.
        warmup = speak(BENCH_PHRASE)
        n_samples = int(warmup.size)
        assert n_samples > 0, "warmup synth produced no samples — pipeline broken"

        # pytest-benchmark runs the callable repeatedly (auto-tuned
        # rounds + iterations) and records timing statistics. The
        # plugin returns whatever the inner callable returns; cast to
        # the actual numpy type so the size-equality check below is
        # checkable by pyright.
        result = cast(NDArray[np.int16], benchmark(speak, BENCH_PHRASE))
        assert int(result.size) == n_samples, (
            f"sample count drifted between warmup ({n_samples}) and "
            f"benchmarked call ({int(result.size)}) — non-determinism!"
        )
    finally:
        if prev_disable is None:
            os.environ.pop("DECTALK_DISABLE_CAPI", None)
        else:
            os.environ["DECTALK_DISABLE_CAPI"] = prev_disable

    # ---- Gates --------------------------------------------------------
    # pytest-benchmark exposes timing stats via ``benchmark.stats``,
    # which is set by the plugin after the benchmark runs. The
    # ``.stats.stats`` chain reaches a ``Stats`` object whose
    # attributes are ``cached_property`` floats: ``median``, ``mean``,
    # ``min``, ``stddev``, etc. The plugin's types aren't strictly
    # annotated, so we cast at the boundary. See
    # https://pytest-benchmark.readthedocs.io.
    metadata: Any = benchmark.stats
    assert metadata is not None, "benchmark fixture has no recorded stats"
    stats_obj: Any = metadata.stats
    measured_median: float = float(cast(float, stats_obj.median))
    audio_seconds: float = n_samples / SAMPLE_RATE_HZ
    sec_per_audio_sec: float = measured_median / audio_seconds

    # Absolute ceiling — PLAN.md target. Independent of baseline so a
    # baseline bump can't mask a real slowdown.
    assert sec_per_audio_sec <= ABS_SECONDS_PER_AUDIO_SECOND, (
        f"synthesizer too slow: {measured_median * 1000:.1f} ms wall-clock for "
        f"{audio_seconds:.2f} s of audio = {sec_per_audio_sec:.3f} s/audio-s, "
        f"exceeding the absolute ceiling of {ABS_SECONDS_PER_AUDIO_SECOND:.2f} "
        f"s/audio-s (docs/PLAN.md `Verification` target)."
    )

    # Drift gate — committed baseline. Skip cleanly when no baseline
    # has been recorded yet (first run after this file lands).
    baseline = _load_baseline()
    bench_key = "test_speak_pangram_perf"
    if bench_key not in baseline:
        pytest.skip(
            f"no baseline entry for {bench_key!r} in {BASELINE_PATH}; "
            f"current median = {measured_median * 1000:.2f} ms"
        )
    baseline_median: float = float(baseline[bench_key]["median_seconds"])
    drift_ratio: float = (measured_median - baseline_median) / baseline_median
    assert drift_ratio <= DRIFT_TOLERANCE, (
        f"perf regression: median {measured_median * 1000:.2f} ms vs baseline "
        f"{baseline_median * 1000:.2f} ms = {drift_ratio * 100:+.1f}% drift, "
        f"exceeding tolerance of +{DRIFT_TOLERANCE * 100:.0f}%. "
        f"If this is a known and accepted regression, update "
        f"{BASELINE_PATH.relative_to(Path(__file__).resolve().parents[2])} "
        f"and reference the rationale in the commit body."
    )


def _update_baseline_cli() -> int:
    """CLI entry point: write a new baseline.json from a benchmark run.

    Run via::

        uv run pytest tests/perf/test_synth_perf.py --benchmark-only \\
            --benchmark-json=/tmp/bench.json
        uv run python -m tests.perf.test_synth_perf \\
            --update-baseline /tmp/bench.json

    The benchmark JSON file is pytest-benchmark's machine-readable
    output. We extract the median for each test and rewrite
    ``tests/perf/baseline.json`` keyed by test name (no class/file
    prefix). Intended to be invoked by humans / orchestrator after a
    deliberate perf change; not part of CI.
    """
    parser = argparse.ArgumentParser(description=_update_baseline_cli.__doc__)
    parser.add_argument(
        "--update-baseline",
        metavar="BENCH_JSON",
        required=True,
        type=Path,
        help="Path to pytest-benchmark --benchmark-json output.",
    )
    args = parser.parse_args()

    with args.update_baseline.open("r", encoding="utf-8") as fh:
        bench_data = json.load(fh)

    out: dict[str, dict[str, float | str]] = {}
    for entry in bench_data.get("benchmarks", []):
        name = str(entry["name"])
        stats = entry["stats"]
        out[name] = {
            "median_seconds": float(stats["median"]),
            "mean_seconds": float(stats["mean"]),
            "min_seconds": float(stats["min"]),
            "stddev_seconds": float(stats["stddev"]),
            "rounds": int(stats["rounds"]),
            "machine_info": str(bench_data.get("machine_info", {}).get("node", "unknown")),
            "commit_info": str(bench_data.get("commit_info", {}).get("id", "unknown")),
        }

    with BASELINE_PATH.open("w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"Wrote {len(out)} baseline entries to {BASELINE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(_update_baseline_cli())
