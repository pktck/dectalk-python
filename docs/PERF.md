# Performance: pure-Python pipeline vs the C oracle

Reproducible benchmark for issue #349 — **measurement only**, no pipeline changes.

Regenerate (numbers are machine-dependent) with:

```bash
DECTALK_SRC=/tmp/dectalk-oracle-src DECTALK_BIN=/tmp/dectalk-oracle-bin \
    uv run python scripts/benchmark_vs_oracle.py --write-doc
```

It complements `tests/perf/test_synth_perf.py` (the pure-Python-only perf gate); it is a
script, not a pytest, so it never runs in the normal test lanes.

## Methodology

Three render paths, each producing an identical-format 11025 Hz mono 16-bit WAV from the same text, each timed in its **own subprocess** (so `DECTALK_DISABLE_CAPI` is fixed before `import dectalk`, and the in-process C library never accumulates enough work to hit its ~45-60 s segfault):

1. **pure-Python** — `dectalk.to_wav()` with `DECTALK_DISABLE_CAPI=1` + `DECTALK_FULL_PIPELINE=1` (FULL+VTM1).
2. **_capi (in-process)** — `dectalk.to_wav()` driving the built `libtts_us.so` via ctypes.
3. **say (subprocess)** — `$DECTALK_BIN/say -a TEXT -fo OUT` (includes process startup).

Per prompt: one warm-up render discarded, then the **median** of 5 timed renders (16× sweep point capped at 3). Realtime factor = `audio_seconds / render_seconds` (>1 = faster than realtime).

_Run: 2026-07-11 05:49 UTC · Linux-6.18.5-x86_64-with-glibc2.39 · Python 3.11.15 · 4 logical CPUs · x86_64 · commit `a628a8c` · oracle `/tmp/dectalk-oracle-src` / `/tmp/dectalk-oracle-bin`._

## 1. Median render time & pure-Python ÷ _capi slowdown

| prompt | category | pure-Python (ms) | _capi (ms) | say (ms) | py ÷ _capi |
| --- | --- | --- | --- | --- | --- |
| `short` | short word | 93.7 | 37.1 | 46.0 | 2.5× |
| `medium` | one sentence | 335 | 37.0 | 46.5 | 9.0× |
| `long` | paragraph (x1) | 523 | 37.1 | 50.9 | 14.1× |
| `phoneme_dense` | phoneme-dense | 288 | 37.0 | 46.0 | 7.8× |
| `number_heavy` | number-heavy | 891 | 37.3 | 46.0 | 23.9× |
| `para_x4` | paragraph (x4) | 2095 | 43.2 | 57.1 | 48.5× |
| `para_x16` | paragraph (x16) | 8389 | 82.2 | 95.6 | 102.0× |

## 2. Realtime factor (audio ÷ render; >1 = faster than realtime)

`py RT× (own)` divides by the pure-Python path's own audio length; `py RT× (vs C)` divides by the C oracle's (canonical) length. On `dev` the two nearly coincide because pure-Python's sample count matches the oracle to within ~0.1% (exactly, on the short prompts).

| prompt | audio C (s) | audio py (s) | py RT× (own) | py RT× (vs C) | _capi RT× | say RT× |
| --- | --- | --- | --- | --- | --- | --- |
| `short` | 0.96 | 0.96 | 10.2× | 10.2× | 25.8× | 20.9× |
| `medium` | 3.39 | 3.39 | 10.1× | 10.1× | 91.7× | 73.0× |
| `long` | 5.78 | 5.79 | 11.1× | 11.1× | 156× | 114× |
| `phoneme_dense` | 3.15 | 3.15 | 11.0× | 11.0× | 85.1× | 68.5× |
| `number_heavy` | 9.67 | 9.67 | 10.9× | 10.9× | 259× | 210× |
| `para_x4` | 23.15 | 23.18 | 11.1× | 11.1× | 537× | 406× |
| `para_x16` | 92.63 | 92.73 | 11.1× | 11.0× | 1126× | 969× |

## 3. Size sweep — is the Python/C ratio constant or growing?

| size | words | pure-Python (ms) | _capi (ms) | py ÷ _capi | py RT× (own) |
| --- | --- | --- | --- | --- | --- |
| para_x1 | 14 | 523 | 37.1 | 14.1× | 11.1× |
| para_x4 | 56 | 2095 | 43.2 | 48.5× | 11.1× |
| para_x16 | 224 | 8389 | 82.2 | 102.0× | 11.1× |

## Verdict

**Verdict.** On typical prompts (a word, a sentence, a short paragraph) the pure-Python FULL+VTM1 pipeline renders at 10.1×–11.1× realtime — comfortably faster than realtime — and its output matches the oracle's output length to within 0.1% (so the two realtime-factor columns nearly coincide). It is 2.5×–14.1× slower than the in-process C library on these prompts, and that ratio *grows* with utterance length — but only because the C library is dominated by a near-constant per-call setup cost (its throughput climbs from ~156× to ~1126× realtime across the 1×→16× sweep) while the Python path's cost is essentially linear at a steady ~11.1× realtime. Conclusion: for interactive and batch use at typical prompt sizes, pure-Python is already fast enough and optimization is **not** required; revisit only if a workload needs many-fold-realtime bulk throughput, in which case the hotspots below are where to start.

## Hotspot breakdown (pure-Python, cProfile, informational only)

Top 12 by cumulative time on `para_x4` (the 4× paragraph) through the pure-Python path. **Not acted on** — issue #349 is measurement only; this is a signpost for any future optimization.

```
15339928 function calls in 8.746 seconds

   Ordered by: cumulative time
   List reduced from 243 to 12 due to restriction <12>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        1    0.000    0.000    8.746    8.746 speak.py:3751(to_wav)
        1    0.000    0.000    8.745    8.745 speak.py:1105(_speak_via_python)
        1    0.001    0.001    8.745    8.745 speak.py:399(_speak_via_python_full)
        1    0.008    0.008    8.744    8.744 speak.py:604(_render_clause_full)
        1    0.100    0.100    8.337    8.337 pump_frames.py:105(pump_frames_via_vtm1)
     3599    3.966    0.001    8.224    0.002 speech_waveform_generator.py:93(speech_waveform_generator)
  1595560    0.799    0.000    1.459    0.000 frac.py:74(frac1mul)
  1393859    0.701    0.000    1.210    0.000 frac.py:42(frac4mul)
  3832935    1.140    0.000    1.140    0.000 filters.py:15(two_pole_filter)
  2989419    0.659    0.000    0.659    0.000 frac.py:36(_to_s32)
  2989419    0.510    0.000    0.510    0.000 frac.py:30(_to_s16)
  1196620    0.223    0.000    0.223    0.000 speech_waveform_generator.py:81(_to_s16)
```
