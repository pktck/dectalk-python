# Frame-level Klatt parameter parity audit (issue #86)

Research-only diagnostic note. Compares the per-frame Klatt parameter
stream (the `parstochip[]` / `delaypars[]` arrays that feed `vtm_loop`)
between the pure-Python pipeline (`DECTALK_DISABLE_CAPI=1
DECTALK_FULL_PIPELINE=1`) and the C oracle on a 5-prompt micro-corpus.

The earlier sample-level audit
(`docs/parity-divergence-audit.md`, issue #58) identified ARPABET
dropouts, missing `allofeats` and inline-command parsing as gross
dividers; the `send_pars`-vs-`parstochip_to_frames` translator audit
(`docs/c_audit/parstochip.md`) inventoried the unit conversions that
the HL→Klatt translator owes the C side. This note drills one stage
deeper than #58 and asks **which Klatt parameters of the very first
frame already disagree, and why** — i.e. is the parameter mismatch
restricted to known issues, or are there additional silent gaps?

## TL;DR

The two pipelines diverge from **frame 0**. Across every prompt
audited the Python path emits a frame whose F1/F2/F3/T0/AV/TLT/B1 all
disagree with C — the C side has already loaded the speaker
definition (`spdef`) and run `phsettar` for the first allophone before
any frames are written, while the Python side emits a frame using
*defaults* before `phsettar` has set targets and before any speaker
table has been multiplied in.

Three concrete root causes account for almost all of the per-frame
delta:

1. **Speaker definition (`SPD_CHIP`) is never applied per-frame.** The
   C side's `delaypars[OUT_TLT/B1/B2/B3/A2…AB]` reflect bandwidth and
   amplitude floors loaded from the active speaker block; the Python
   path leaves most of those slots at PARAMETER-struct defaults
   (`TLT=5`, `B1=0`).
2. **`phsettar` is run on the wrong frame.** The C side calls
   `phsettar` for allophone `nphone=0` during clause init (before
   `send_pars()` ever fires). The Python driver only calls
   `phsettar` when `nphone` advances inside the per-frame loop, so
   `phdraw`'s smoothing on frame 0 sees default targets.
3. **F0 hard-init produces a different starting `T0`.** C's first
   frame has `T0=326` (~32 Hz baseline + soft-init descent);
   Python's first frame is `T0=500` because `phinton` emitted no F0
   events (issue B from #58) and `pht0draw` falls straight through to
   `f0minimum`.

There are no new "frame counts diverge by N" problems to file beyond
the existing #58 issues — the frame **stream** is wrong from word go
because PH's setup stage is incomplete. Closing #58 issue B
(`allofeats` / `phinton`) fixes #3 above directly; #1 and #2 are new
findings worth their own issues (sketches at the end of this note).

## Reproducibility — instrumentation used

### C side: `[:debug 2200]` inline command (no patch needed)

`ph_claus.c:756` calls `printParameters(pDph_t)` once per frame when
`pKsd_t->debug_switch & PH_DBG && debug_switch & 0x200`. The full
`[:debug] cm_cmd_debug` handler (`cm_copt.c:3554`) is hex-parsed by
`cm_cmd.c:580 case 'h'`, so `[:debug 2200]` sets
`debug_switch = 0x2200 = PH_DBG | 0x200`. Output goes to stdout, one
frame per line:

```
US_HX    0  730  0  0  0  0  0  0  37  326  0 1200 2680  290  400  250  220
```

Columns: `phone AP F1 A2 A3 A4 A5 A6 AB TLT T0 AV F2 F3 FZ B1 B2 B3`.
The values are `delaypars[]` after `send_pars()`'s one-frame shuffle
— i.e. the exact words about to be handed to `spcwrite` → `vtm_loop`.

The existing `0005-vtm-stage-dump-hooks.patch` is **not** suitable
for frame-level Klatt analysis — it only captures the first short of
each VTM packet (the SPC type tag), not the full `VOICE_PARS+1 = 21`
words of the frame. See follow-up issue F below.

### Python side: monkey-patch the frame adapter

`src/dectalk/api/speak.py:608` calls
`parstochip_to_llframe_delayed(p_dph_t.parstochip, previous_parstochip)`
once per frame. Wrapping that callable lets a test driver inspect
each frame's `parstochip[]` without modifying production code:

```python
import dectalk.ph.parstochip_to_frames as ptf

orig = ptf.parstochip_to_llframe_delayed
log: list[list[int]] = []
def wrapped(parstochip, previous, _log=log, _orig=orig):
    _log.append(list(parstochip))
    return _orig(parstochip, previous)
ptf.parstochip_to_llframe_delayed = wrapped

from dectalk import to_wav
to_wav(prompt, "/tmp/out.wav")  # runs the full pipeline
```

The `OUT_*` indices follow `ph_defs.h:531-574`, mirrored in
`src/dectalk/ph/param_indices.py`.

### Reproducer

```bash
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh
mkdir -p /tmp/frame_audit

for prompt in "hi" "hello world" "ah" "the quick brown fox" \
              "[:rate 200]testing"; do
    slug=$(echo "$prompt" | tr ' :[]' '____' | tr -dc 'A-Za-z0-9_')
    (cd "$DECTALK_BIN" && \
     LD_LIBRARY_PATH="$DECTALK_BIN/lib" \
     timeout 8 ./say -a "[:debug 2200]$prompt" \
                     -fo "/tmp/frame_audit/$slug.c.wav") \
         > "/tmp/frame_audit/$slug.c.frames.txt"
done

DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python tools/dump_python_frames.py  # using the snippet above
```

## 5-prompt micro-corpus

Selected to exercise distinct PH-stage code paths:

| # | Prompt | Why |
|---|---|---|
| 1 | `hi` | minimal — 2 phones (HX + AY). Smallest possible PH workload. |
| 2 | `hello world` | the headline divergence prompt from #58; voiced sonorant transitions. |
| 3 | `ah` | a single vowel — isolates target-setting from coarticulation. |
| 4 | `the quick brown fox` | multi-word, multi-stress. Stresses `phinton` if it ran. |
| 5 | `[:rate 200]testing` | inline command + voiceless plosives + sibilant. Stresses the parse() bypass and frication. |

## Frame counts

| Prompt | C frames | Py frames | Δ |
|---|---:|---:|---:|
| `hi` | 137 | 47 | -90 |
| `hello world` | 195 | 132 | -63 |
| `ah` | 128 | 67 | -61 |
| `the quick brown fox` | 279 | 202 | -77 |
| `[:rate 200]testing` | 155 | 45 | -110 |

Python is consistently 30-70 % shorter — consistent with the ARPABET
dropout and short trailing-silence findings from #58. The
`[:rate 200]testing` prompt is the worst because the inline command
is not parsed (issue C from #58); the Python pipeline tokenizes the
literal command text into phones, but `:` is treated as a non-letter
and the rest of `rate 200 testing` produces a degraded phone stream.

## Frame 0 — first-frame divergence

This is the heart of the audit. For each prompt the first emitted
frame already disagrees on most Klatt parameters; the table below
shows the values at frame index 0 (the very first word handed to
`vtm_loop`/`spcwrite`).

Columns: `phone` (C only), `AP` (aspiration), `F1`/`F2`/`F3`/`FZ`
(formant frequencies, Hz), `T0` (fundamental period, deciHz),
`AV` (voicing amplitude), `TLT` (spectral tilt), `B1`/`B2`/`B3`
(formant bandwidths).

### `hi` — frame 0

| side | phone | AP | F1 | TLT | T0 | AV | F2 | F3 | FZ | B1 | B2 | B3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C | US_HX | 0 | **730** | **37** | **326** | 0 | **1200** | **2680** | 290 | **400** | 250 | 220 |
| Py | — | 0 | **459** | **5** | **500** | 0 | **1569** | **2538** | 290 | **0** | 250 | 220 |
| Δ | | 0 | -271 | -32 | +174 | 0 | +369 | -142 | 0 | -400 | 0 | 0 |

### `hello world` — frame 0

| side | phone | AP | F1 | TLT | T0 | AV | F2 | F3 | FZ | B1 | B2 | B3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C | US_HX | 0 | **550** | **36** | **332** | 0 | **1260** | **2600** | 290 | **400** | 250 | 220 |
| Py | — | 0 | **596** | **5** | **500** | 0 | **1194** | **2608** | 290 | **0** | 250 | 220 |
| Δ | | 0 | +46 | -31 | +168 | 0 | -66 | +8 | 0 | -400 | 0 | 0 |

### `ah` — frame 0

| side | phone | AP | F1 | TLT | T0 | AV | F2 | F3 | FZ | B1 | B2 | B3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C | US_AA | 0 | **780** | **12** | **326** | **45** | **1200** | **2670** | 290 | **220** | 190 | 250 |
| Py | — | 0 | **648** | **5** | **500** | 0 | **1530** | **2461** | 290 | **0** | 140 | 290 |
| Δ | | 0 | -132 | -7 | +174 | -45 | +330 | -209 | 0 | -220 | -50 | +40 |

### `the quick brown fox` — frame 0

| side | phone | AP | F1 | TLT | T0 | AV | F2 | F3 | FZ | B1 | B2 | B3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C | US_DH | 0 | **290** | **25** | **335** | **30** | **1300** | **2560** | 290 | **200** | 170 | 170 |
| Py | — | 0 | **312** | **5** | **500** | 0 | **1451** | **2573** | 290 | **0** | 170 | 170 |
| Δ | | 0 | +22 | -20 | +165 | -30 | +151 | +13 | 0 | -200 | 0 | 0 |

### `[:rate 200]testing` — frame 0

| side | phone | AP | F1 | TLT | T0 | AV | F2 | F3 | FZ | B1 | B2 | B3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C | US_T | 0 | **350** | **26** | **322** | 0 | **1600** | **2600** | 290 | **300** | 200 | 250 |
| Py | — | 0 | **365** | **5** | **500** | 0 | **1570** | **2608** | 290 | **0** | 200 | 250 |
| Δ | | 0 | +15 | -21 | +178 | 0 | -30 | +8 | 0 | -300 | 0 | 0 |

### Patterns across all five prompts

- **B1 is always 0 on the Python side.** It matches the C value
  for the first allophone exactly (HX → 400, AA → 220, DH → 200,
  T → 300). The Python `parstochip_to_llframe_delayed` adapter
  defaults B1 to 0 when no previous frame exists (see
  `_DEFAULT_*` block in `parstochip_to_frames.py`).
- **TLT is always 5 on the Python side** vs C values in the 12-37
  range — the Python full pipeline never writes
  `parstochip[OUT_TLT]` because `phdraw`'s tilt branch (driven by
  spdef + AV) hasn't run yet.
- **T0 is always 500 on the Python side** vs C's 322-335 range. C
  runs a soft-init ramp in the first ~3 frames of `pht0draw`
  starting from `f0minimum` (~32-33 Hz) and converging to the
  speaker's voicing floor; Python's `pht0draw` falls straight to
  `f0minimum = 500` because `phinton` produced no events (already
  root-caused as issue B in #58).
- **F1/F2/F3 disagree by ±50-300 Hz** despite the same allophone
  identity. The Python `phsettar` runs only after the per-frame
  loop's `nphone` advance, so frame 0's targets come from a stale
  `tarcur` (still at PARAMETER-struct defaults) rather than the
  values `phsettar(HX)` would have set.

## Sustained divergence — frames 0-7 of `hi`

To check whether frame 0 is just a one-frame startup glitch or
indicative of sustained mismatch, here are the first 8 frames of `hi`
on both sides.

### C side (HX phone, frames 0-7)

```
phone  AP   F1 A2 A3 A4 A5 A6 AB TLT   T0 AV   F2   F3   FZ   B1   B2   B3
US_HX   0  730  0  0  0  0  0  0  37  326  0 1200 2680  290  400  250  220
US_HX  49  730  0  0  0  0  0  0  37  316  0 1200 2680  290  400  250  220
US_HX  53  730  0  0  0  0  0  0  37  306  0 1200 2680  290  387  243  220
US_HX  56  730  0  0  0  0  0  0  38  295  0 1200 2680  290  375  237  220
US_HX  60  730  0  0  0  0  0  0  38  285  0 1200 2680  290  362  231  220
US_HX  60  730  0  0  0  0  0  0  38  276  0 1200 2680  290  350  225  220
US_HX  60  730  0  0  0  0  0  0  38  267  0 1200 2680  290  337  218  220
US_HX  60  730  0  0  0  0  0  0  38  259  0 1200 2680  290  325  212  220
```

C holds F1=730, F2=1200, F3=2680 constant (HX targets), AP ramps
0→49→53→56→60 (frication onset), TLT stays around 37, T0 ramps
326→259 (soft-init descent).

### Python side (same prompt, frames 0-7)

```
AP   F1 TLT    T0 AV    F2    F3   FZ   B1   B2   B3
 0   459   5   500  0  1569  2538  290    0  250  220
 0   459   5   500  0  1551  2547  290    0  243  220
 0   459   5   513  0  1533  2556  290    0  237  220
 3   459   5   608  0  1514  2565  290    0  231  220
 7   459   5   680  0  1496  2574  290    0  225  220
11   459   5   734  0  1478  2583  290    0  218  220
15   459   5   775  0  1459  2591  290    0  218  220
19   459   5   806  0  1441  2600  290    0  218  220
```

Python holds F1=459 constant (an unset PARAMETER-struct default —
**not** an HX target), TLT=5 unchanged, B1=0 unchanged, AP ramps
0→0→0→3→7→11→15→19 (slower onset, delayed by 2 frames), T0 ramps
500→500→513→608→680 (linear from `f0minimum` upward — opposite
direction to C's descent).

The mismatch is therefore **sustained**, not a one-frame artefact.
Every parameter on Python's side either (a) holds at an uninitialised
default or (b) ramps in the wrong direction at the wrong rate.

## Root-cause trace

### #1 Speaker definition (`SPD_CHIP`) is not applied per frame

**C path.** `ph_claus.c:706-741` (`send_pars`) reads
`parstochip[OUT_F1]`, `OUT_B1`, etc. from `phdraw`'s output, which in
turn pulls bandwidth, formant and amplitude floors from `param[]`
*after* the speaker definition has been written to it during clause
init by `ph_vset.c`'s speaker-tuning chain. When `delaypars[OUT_B1]`
is written it carries the speaker's bandwidth limit (HX's 400 Hz
first-formant bandwidth, AA's 220 Hz, etc.).

**Python path.** `src/dectalk/ph/init_pars.py` initialises only
`tcum = -1`. The Python `phdraw` pulls from `param[]` entries whose
`tarcur` field has never been set from a speaker block (no analogue
of `dph_setspeaker_st` / `ph_vset.c` has run). Result: B1=0, TLT=5,
B2/B3 at PARAMETER defaults.

**Where to port.** The C-side speaker activation chain lives in
`${DECTALK_SRC}/src/dapi/src/ph/ph_vset.c` and is called once per
clause from `ph_claus.c:phclause` before the per-frame loop. The
Python equivalent shim is `src/dectalk/ph/hl_speaker.py` (already
ported for HLSyn) but it isn't wired into
`_speak_via_python_full`'s init sequence. The fix is two function
calls in `speak.py` after `init_phclause`: load the speaker block
into `param[]`, then run the speaker-tuning step.

### #2 `phsettar` is not run for the first allophone before frame 0

**C path.** During `phclause` init (around `ph_claus.c:367` and the
surrounding `init_pars()` block) the C code calls `phsettar` for the
first allophone *before* entering the per-frame loop, so when
`send_pars()` fires for frame 0 the `param[].tarcur` slots already
hold HX's target values (`tarcur=730` for F1, etc.).

**Python path.** `src/dectalk/api/speak.py:595-606`:

```python
for _ in range(max_frames):
    p_dph_t.tcum += 1
    if p_dph_t.tcum >= p_dph_t.durfon:
        p_dph_t.nphone += 1
        # ... advance ...
        phsettar(handle)
    pht0draw(handle)
    phdraw(handle)
    frames.append(parstochip_to_llframe_delayed(...))
```

The first iteration *does* advance `nphone` and call `phsettar` —
**but** the loop calls `pht0draw` and `phdraw` immediately afterwards
without running the "init" portion of phdraw that the C code splits
out. The captured frame 0's F1/F2/F3 are whatever `phsettar` left in
`param[]` modulo `phdraw`'s smoothing, which differs from the C
trajectory because C's `phdraw` starts from a fully-populated speaker
table (see #1) while Python's starts from PARAMETER defaults.

The two bugs are coupled: fixing #1 alone will partly improve the
first-frame F1 (it'll start at the speaker's F1 floor instead of
the PARAMETER default 459), but the slope from frame-0 onward will
still be wrong until `phsettar` and the smoothing path see the same
parameter state.

### #3 `T0=500` because `phinton` produced no F0 events

Already documented as issue B in `parity-divergence-audit.md`
(allofeats[] is zero, `phinton` emits no events, `pht0draw` falls
straight through to `f0minimum`). The frame-level audit corroborates
that finding: every prompt's frame 0 has Python `T0=500` (matches
`f0minimum`'s deciHz value) while C's T0 is in the 322-335 range —
i.e. C's `pht0draw`'s "soft init" descent has already started.

## Frame counts vs allophone counts

For each prompt the Python frame count is roughly proportional to the
number of allophones the Python `_arpabet_to_us_allophone` accepts.
`hi` has 2 ARPABET phones (HH, AY1) → `_arpabet_to_us_allophone`
drops HH → Python ends up with 1 phone + 2 sentinels → 47 frames vs
C's 137. This is the #58 issue A symptom and is **not** a new
finding.

## Concrete follow-up issues to file

### Issue D — Run `ph_vset` / speaker-tuning chain before the per-frame loop

> **Title**: PH full pipeline skips `ph_vset.c` / speaker-table
> activation; frame-0 B1/TLT/A2-A6 always at PARAMETER defaults
>
> Scope: port the C-side `phsettar`-loading parts of
> `${DECTALK_SRC}/src/dapi/src/ph/ph_vset.c` (the routine that
> copies the active `SPD_CHIP` block into `param[].tarcur` /
> bandwidth floors), and call it from `_speak_via_python_full`
> after `init_phclause` and before the per-frame loop. Acceptance
> test: after the call, frame-0 `parstochip[OUT_B1]` equals the C
> value for the corresponding first allophone across the 5-prompt
> micro-corpus (`hi` HX → 400, `ah` AA → 220, `the…` DH → 200,
> etc.). Labels: `area/ph`, `size/medium`.

### Issue E — Run `phsettar` + clause-init smoothing before the first frame

> **Title**: First per-frame iteration emits a frame before
> `phsettar(0)` + smoothing has completed; frame-0 F1/F2/F3 are
> 100-300 Hz off
>
> Scope: factor the per-frame loop in `_speak_via_python_full` so
> the first `phsettar(nphone=0)` runs *before* the first
> `phdraw`/`pht0draw` emit, matching `ph_claus.c`'s init+loop
> split. Acceptance: frame-0 F1 matches C to within ±20 Hz for
> every prompt in the corpus once Issue D is also merged. Labels:
> `area/ph`, `size/small`.

### Issue F — Fix the `vtm.dump` patch to capture full Klatt frames

> **Title**: `tests/parity/c_patches/0005-vtm-stage-dump-hooks.patch`
> only dumps the SPC type tag, not the per-frame Klatt parameters
>
> Scope: rewrite the hook in `vtm/vtmiont.c:vtm_loop` to read the
> control word, call `spc_size(control)` to find the packet length,
> and dump all `spc_size` words instead of just `input[0]`. Test:
> `dump_pipeline("hi", ["vtm"])` returns ~140 voice records of 21
> words each rather than ~140 single-word records of `0000`.
> Wider win: this gives the Python side a parity oracle for Klatt
> frames without the `[:debug 2200]` printf trick. Labels:
> `area/ph`, `size/small`.

## Notes on existing follow-ups

The three "honourable mentions" in
`docs/parity-divergence-audit.md` (ARPABET dropouts, `allofeats`/F0,
inline `[:cmd]`) are direct upstream causes of the frame-level
disagreement but are **not duplicated here** — issues A/B/C from
that document already track them. Closing A removes most of the
frame-count delta; closing B fixes #3 of this note (T0=500); D and
E above are new work focused on the parameter-value mismatch at the
first frame, independent of the allophone-count gap.

The `parstochip` translator audit
(`docs/c_audit/parstochip.md`) catalogued the unit-scale conversions
that the Python adapter (`parstochip_to_frames.py`) owes the C side.
That audit's findings are upstream of the present note: even if the
translator emitted exactly the right LLFrame from a given
`parstochip[]`, the `parstochip[]` produced by Python's PH is
already wrong because of D/E/B. Fix order: B → D → E → revisit
parstochip translator findings.

## Boundary of the audit

This note **does not** instrument:

- The `param[]` PARAMETER-struct state evolution inside `phdraw` /
  `phsettar` (would require a Python-side per-call dump beyond
  `parstochip[]`).
- The C-side `pDph_t->stPhsettar` state machine across frames
  (only the resulting `delaypars[]` row is captured).
- VTM-stage post-processing (`vtm_iman`, `vtm_f.c` synthesis loop) —
  `hlsyn`'s LL synthesis is already bit-accurate per
  `tests/parity/test_synth_parity.py`, so divergence below
  `delaypars` is not a current suspect.

These would be useful for narrowing exactly which sub-step of
`phsettar` or `phdraw` differs — material for a follow-up audit
once D and E above are closed and the per-frame delta drops below
the noise floor.

## Refresh — 2026-05-22 (post-phsort / pht0draw landings)

This section re-runs the same 5-prompt instrumentation against
`dev` at `e0db2bc` and records what has changed since the original
audit landed. The original section above is preserved verbatim for
historical comparison — values quoted in this refresh are the
current (live) numbers, captured by the same `[:debug 2200]` printf
trick on the C side and the same `parstochip_to_llframe_delayed`
monkey-patch on the Python side.

The intervening PRs that materially affect the frame stream:

- `b2f4a8f` — derive `allofeats[]` from ARPABET front-end so
  `phinton` emits F0 events (closes the original audit's issue #3 —
  T0 should now be a contour rather than the flat `f0minimum`).
- `38ae183`, `da76b2f` — `pht0draw` F0 contour generator for MALE
  and FEMALE.
- `1713f9e`, `1e93aca` — `phdraw` initial silence anticipation and
  GEN_SIL ending dcstep tracker.
- `7cda308` — `all_phsort` / `fr_phsort` ports.
- `42cc9cb` — once-per-phone setup + FVOWEL A2-jamming.
- `909c5ff` — wire `all_phsort` into `_speak_via_python_full`.
- `1893910` — emit trailing-silence pad on the full-pipeline path.

### Frame counts (refreshed)

| Prompt | C frames | Py frames | Δ (was) |
|---|---:|---:|---:|
| `hi` | 137 | 124 | -13 (was -90) |
| `hello world` | 195 | 224 | +29 (was -63) |
| `ah` | 128 | 144 | +16 (was -61) |
| `the quick brown fox` | 279 | 297 | +18 (was -77) |
| `[:rate 200]testing` | 155 | 165 | +10 (was -110) |

Python now overshoots C by 10-30 frames on four of the five
prompts (still 13 short on `hi`). The sign of the delta is now
**both directions**, where previously Python was uniformly 30-70 %
shorter. The ARPABET-dropout symptom from issue A of #58 is
largely closed by the chain `9954b38 ARPABET-alias gap` → `b2f4a8f
allofeats` → `1893910 trailing pad`.

### Frame 0 — first emitted frame (refreshed)

The same `[:debug 2200]` reproducer + Python adapter dump still
shows the **same first-frame divergence pattern** as the original
audit. Frame-0 values for the 5 prompts:

| Prompt | side | F1 | TLT | T0 | F2 | F3 | B1 |
|---|---|---:|---:|---:|---:|---:|---:|
| `hi` | C  | 730 | 37 | 326 | 1200 | 2680 | 400 |
| `hi` | Py | 459 |  5 | 500 | 1569 | 2539 |   0 |
| `hello world` | C  | 550 | 36 | 332 | 1260 | 2600 | 400 |
| `hello world` | Py | 596 |  5 | 500 | 1194 | 2607 |   0 |
| `ah` | C  | 780 | 12 | 326 | 1200 | 2670 | 220 |
| `ah` | Py | 647 |  5 | 500 | 1529 | 2461 |   0 |
| `the quick brown fox` | C  | 290 | 25 | 335 | 1300 | 2560 | 200 |
| `the quick brown fox` | Py | 313 |  5 | 500 | 1452 | 2573 |   0 |
| `[:rate 200]testing` | C  | 350 | 26 | 322 | 1600 | 2600 | 300 |
| `[:rate 200]testing` | Py | 364 |  5 | 500 | 1569 | 2607 |   0 |

**Findings #1 (speaker definition not applied), #2 (`phsettar`
runs late) and #3 (T0=500) all still hold unchanged** on the
first frame. The B1/TLT defaults and T0=500 are bit-identical to
the original audit, and F1/F2/F3 deltas are within ±20 Hz of the
values originally measured. The `pht0draw` MALE/FEMALE ports
(`38ae183`, `da76b2f`) and `init_clause` (`909c5ff`) fixed the
contour *shape* later in the stream but did **not** advance the
init-ordering of frame 0 — the very first iteration of the
per-frame loop in `speak.py:728-742` still emits before
`phsettar`+`phdraw` have a chance to load HX's speaker-table
values.

### New finding G — Leading `GEN_SIL` allophone is Python-only

`_speak_via_python_full` in `src/dectalk/api/speak.py:496-501`
unconditionally prepends a `GEN_SIL` token to `allophons`:

```python
allophons: list[int] = [GEN_SIL]
for name in arpabet_phones:
    code = _arpabet_to_us_allophone(name)
    if code is not None:
        allophons.append(code)
allophons.append(GEN_SIL)
```

The C oracle's `[:debug 2200]` dump for `hi` shows the very first
emitted frame is **`US_HX`** (no leading `SIL`), then 12 HX
frames, then 53 AY, then 72 SIL:

```
US_HX    0  730  0  0  0  0  0  0  37  326  0 1200 2680  290  400  250  220
...
SIL      0  535  0  0  0  0  0  0   6  352  0 1818 2461  290  140  137  230
```

C's allophone array starts at the first real phone. The C chain
`ph_aloph.c` → `init_phclause` → frame loop zeroes the
`allophons[]` buffer and then fills it from the ARPABET front-end
without a leading-SIL pad — the trailing silence is generated
inline by the `dcstep` / `loadspdef` machinery, not by an explicit
`GEN_SIL` token in `allophons[0]`.

Python's `_render_clause_full` adds **15 leading-SIL frames** for
`hi` (its `allodurs[0]` for the GEN_SIL pad). Those frames carry
the PARAMETER-struct defaults (F1=459, TLT=5, T0=500, B1=0) that
findings #1 and #2 root-cause — and Python is currently emitting
them under a SIL phone tag even though the C side never emits
such a SIL phone at the start of a clause.

This explains the apparent `-13`/`+10..+29` frame-count delta
pattern: Python adds 15 leading-SIL frames that C doesn't, but
Python's vowel-duration timing is shorter than C's (see finding
H below — wrong vowel labels yield wrong `allodurs[]`), so the
two errors partially cancel. Removing the leading
`GEN_SIL` would shift Python's frame count down by ~15 frames,
making the duration-vs-C divergence cleaner.

> **Issue G title proposal**: `_render_clause_full` prepends an
> extra `GEN_SIL` to `allophons[]` that the C oracle does not emit
>
> Scope: drop `allophons: list[int] = [GEN_SIL]` from
> `speak.py:496` (keep the trailing `allophons.append(GEN_SIL)`).
> Verify the C-source frame stream by re-running the
> `[:debug 2200]` dump and confirming `allophons[0]` is the first
> real phone (HX for `hi`, AA for `ah`, etc.). Acceptance: Python
> frame counts on the 5-prompt corpus drop by ~15 frames each;
> frame 0 carries the first real phone identity rather than SIL.
> Labels: `area/ph`, `size/small`.

### New finding H — LTS vowel labels still differ on isolated words

Decoding the Python `allophons[]` via the low byte of each code
(see `src/dectalk/include/phoneme_codes.py`) and comparing to the
C `[:debug 2200]` `phcur` field per frame:

| Prompt | C allophones (post-init) | Py allophones (post-leading-SIL) |
|---|---|---|
| `hi` | HX AY | HX **IH** |
| `hello world` | HX AX LL OW W RR LX D IX | HX **AH** LL OW W **ER LL** D AX |
| `ah` | AA | **AE HX** |
| `the quick brown fox` | DH AX K W IH K B R AW N F AA K S | DH **AH** K W IH K B R AW N F AA K S |
| `[:rate 200]testing` | T EH S T IX NX | T EH S T **IH** NX |

The differences are largely **vowel labels** (AX vs AH, IX vs
IH, AY vs IH for the bare letter `i`), with occasional consonant
shifts (RR LX → ER LL for `hello world`'s "world"). These are
upstream of PH: the ARPABET symbols come out of the LTS / lexicon
lookup chain (`dictionary lookup` → `letter-to-sound` →
`_arpabet_to_us_allophone`) before `_render_clause_full` ever
sees them.

These are not new bugs in the strict sense — issue A of #58
already covered "ARPABET dropouts" — but the **direction** has
shifted: instead of phones being **dropped**, they are now
**relabelled** to a different vowel of the same syllabic class.
The duration-lookup tables for the wrong vowel give different
`allodurs[]`, which is why Python's vowel segments are shorter
than C's even when the consonant frame counts roughly agree.

> **Issue H title proposal**: ARPABET front-end picks the wrong
> vowel label for isolated words (AY→IH for `hi`, AA→AE-HX for
> `ah`, AX→AH for schwa-final words)
>
> Scope: trace LTS / dictionary lookup for the 5-prompt corpus
> and compare to the C `say -a -dump phonemes` output (or the
> `[:phoneme on]` round-trip). Likely root cause is a missing
> `lts_us.rul` entry or an ARPABET stress-marker dropping
> (`AY1` vs `AY`). Acceptance: Python `_arpabet_to_us_allophone`
> output for `hi` is `HH AY1`, for `ah` is `AA1`, etc. — matches
> C's allophone sequence after `phalloph`. Labels: `area/lts`,
> `size/medium`.

### New finding I — `parstochip[OUT_PH]` / `[OUT_PH2]` are never written

`grep -n "OUT_PH\b" src/dectalk/api/speak.py src/dectalk/ph/*.py`
returns no writes; the SPC frame's phone-identity tag (the
`pDph_t->parstochip[OUT_PH] = pDph_t->allophons[pDph_t->nphone];`
line at `ph_claus.c:465`) has no Python equivalent. The current
debug instrumentation prints `SIL` for every frame because
`parstochip[OUT_PH]` defaults to 0 and stays there.

This does not affect audio: VTM's klparse loop reads parameters
0..16 (the actual Klatt values) and ignores 17/19 in audio mode.
It does affect downstream parity-test instrumentation, e.g. any
attempt to reproduce the C `[:debug 2200]` dump from the Python
side will be missing the phone-identity column. The fix is two
lines after the `phsettar(handle)` call in `speak.py:738`:

```python
p_dph_t.parstochip[OUT_PH] = p_dph_t.allophons[p_dph_t.nphone]
p_dph_t.parstochip[OUT_PH2] = (
    p_dph_t.allophons[p_dph_t.nphone + 1]
    if p_dph_t.nphone + 1 < p_dph_t.nallotot else 0
)
```

> **Issue I title proposal**: Python `_render_clause_full` never
> writes `parstochip[OUT_PH]` or `[OUT_PH2]`; SPC frames carry no
> phone identity
>
> Scope: mirror `ph_claus.c:465-472` in `speak.py` after the
> nphone advance. Acceptance: the monkey-patched
> `parstochip_to_llframe_delayed` instrumentation can decode each
> frame's phone code via `row[OUT_PH] & 0xFF`. Labels:
> `area/ph`, `size/small`.

### Summary of the refresh

| Original issue | Status as of 2026-05-22 |
|---|---|
| #1 SPD_CHIP not applied per frame (B1=0 etc) | still open — confirmed |
| #2 `phsettar` runs after the first frame | still open — confirmed |
| #3 T0=500 (no F0 events) | partly closed (`allofeats` + `phinton` now emit events later in the stream) but frame 0 still T0=500 |
| F  vtm.dump captures only SPC type tag | still open — same patch unchanged |
| G  leading GEN_SIL on the Python side | NEW |
| H  LTS picks wrong vowel labels | NEW |
| I  parstochip[OUT_PH]/OUT_PH2 never written | NEW |

Recommended fix order (cheapest → most impactful):

1. I (one-line wiring fix; makes instrumentation legible).
2. G (one-line drop of the leading-SIL pad).
3. D (port `ph_vset.c` so frame 0 has speaker bandwidths/TLT).
4. E (run `phsettar(0)` before the per-frame loop emits frame 0).
5. H (lexicon / LTS work — a separate audit subsystem).

Authored-by: Claude:claude-opus-4-7
