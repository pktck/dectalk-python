# Phase E parity divergence audit (issue #58)

Diagnostic snapshot for the pure-Python pipeline
(`DECTALK_DISABLE_CAPI=1`) vs. the shipped DECtalk binary on
`tests/parity/test_binary_wav_parity.py`.

## Method

1. Built the C oracle with `scripts/agent_oracle_env.sh` + `scripts/setup_c_oracle.sh`.
2. Rendered the first 15 corpus prompts under three configurations:
   - C binary (`say -a TEXT -fo`) — reference.
   - `DECTALK_DISABLE_CAPI=1` (legacy "approximate" Python path —
     default fallback when C library is absent).
   - `DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1` (the work-in-
     progress "full" Python path through `_speak_via_python_full` —
     `ph_claus.c`'s ported chain).
3. For each prompt computed: sample-count delta, first-differing-
   sample index, L1 / L2 error metrics, peak absolute error, and
   the trailing-silence / leading-silence envelope.
4. For the highest-divergence prompt (`hello world`) and the rate-
   command prompt (`[:rate 250] testing one two three`),
   instrumented `_speak_via_python_full` to dump intermediate
   state at the ARPABET, allophone, allofeats, allodurs, F0-event,
   and frame-count layers.

`_speak_via_python_full` is what Phase E is actually trying to close;
the "approximate" path will be retired once the full path achieves
bit parity. All quantitative numbers below are for the full path
unless otherwise noted.

## Per-prompt divergence (first 15 corpus prompts)

`DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1`. All WAVs are 16-bit
mono PCM at 11025 Hz.

| # | Prompt | C samp | Py samp | Δ samp | Δ ms | first_diff (samp / ms) | L2/sample | max_abs_err |
|---|---|---:|---:|---:|---:|---|---:|---:|
| 0 | `hello world` | 13845 | 10670 | -3175 | -288 | 213 / 19 | 7037 | 34595 |
| 1 | `the quick brown fox` | 19809 | 18260 | -1549 | -141 | 213 / 19 | 5132 | 32046 |
| 2 | `she sells sea shells` | 20093 | 17050 | -3043 | -276 | 213 / 19 | 5142 | 29564 |
| 3 | `one two three four five` | 22933 | 18920 | -4013 | -364 | 348 / 32 | 6367 | 31855 |
| 4 | `supercalifragilisticexpialidocious` | 31169 | 44000 | +12831 | +1163 | 213 / 19 | 3466 | 19995 |
| 5 | `[:rate 250] testing one two three` | 14697 | 34540 | +19843 | +1800 | 710 / 64 | 5162 | 27275 |
| 6 | `DECtalk version 6.2.0` | 32660 | 15730 | **-16930** | -1535 | 852 / 77 | 4643 | 29846 |
| 7 | `this is a test, with a comma, and a period.` | 34932 | 40150 | +5218 | +473 | 213 / 19 | 4276 | 27657 |
| 8 | `the answer is 42` | 21300 | 23540 | +2240 | +203 | 213 / 19 | 4789 | 28329 |
| 9 | `3 point 14` | 18602 | 16830 | -1772 | -161 | 213 / 19 | 5461 | 30519 |
| 10 | `one hundred and one dalmatians` | 24140 | 27500 | +3360 | +305 | 348 / 32 | 4068 | 25812 |
| 11 | `1234567890` | 74905 | 76780 | +1875 | +170 | 348 / 32 | 4955 | 29351 |
| 12 | `hello! how are you?` | 25702 | 16170 | -9532 | -865 | 213 / 19 | 6671 | 31630 |
| 13 | `wait... what just happened?` | 26909 | 22880 | -4029 | -365 | 326 / 30 | 4367 | 27204 |
| 14 | `yes; no; maybe.` | 21442 | 17930 | -3512 | -319 | 329 / 30 | 5548 | 27900 |

**Headline numbers.**

- 0/15 prompts match bit-exactly.
- Sample-count delta sign is inconsistent (sometimes Python is
  longer, sometimes shorter): mean |Δ| = 5856 samples (~531 ms),
  worst |Δ| = 19843 samples (~1.80 s) on the rate-command prompt.
- L2/sample of ~3500-7000 vs C-reference RMS of ~2200-6200 means
  the per-sample noise is comparable in magnitude to the signal —
  i.e. these are not small-amplitude drifts, they are entirely
  different signals after the divergence point.
- `first_diff_idx` is always 213 (~19 ms) or a small multiple of
  ~135 samples (one Klatt frame is 110 samples at 11025 Hz). The
  initial 213-sample silence prefix matches byte-for-byte; divergence
  begins on the first non-silence sample.

## Stage-by-stage trace for `hello world`

Configuration: `DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1`,
default Paul voice, rate=1.0.

### Front-end (text → ARPABET → US allophone codes)

```
ARPABET phones produced:  ['HH', 'AH0', 'L', 'OW1', 'W', 'ER1', 'L', 'D']   (8 phones)
US allophone codes:       [0x1e00, 0x1e09, 0x1e0b, 0x1e18, 0x1e14, 0x1e30, 0x1e00]
                          (SIL, AH, OW, W, ER, D, SIL — 5 phones + 2 sentinels = 7)
```

Three of the eight ARPABET phones (**HH, L, L**) are silently dropped
by `_arpabet_to_us_allophone`. Quick sweep across CMUdict's 39 ARPABET
symbols:

```
PRESENT (36): AA AE AH AO AW AY B CH D DH EH ER EY F G IH IY JH K M
              N OW OY P R S SH T TH UH UW V W Y Z ZH
MISSING  (3): HH, L, NG
```

The `USPhoneme` enum (`src/dectalk/include/phoneme_codes.py`) does
contain entries for `HX` (the C name for /h/), `LL` / `LX` / `EL` /
`LY` (variants of /l/), and `NX` (variant of /ŋ/). The
`_arpabet_to_us_allophone` helper does a *bare-name lookup* into the
enum — there is no ARPABET-to-DECtalk-allophone alias table.

This is the dominant root cause of word-level missing phonemes; in
"hello world" we lose the initial /h/ and both word-final /l/s.

### Allophone durations (`us_phtiming`)

```
allodurs[0:7] = [12, 20, 21, 6, 23, 9, 12]    # one allophone per cell, 6.4ms-frame units
sum = 103 frames
```

With 110-sample (9.977 ms) frames out of `LLSynth` (`spkr.UI=110`),
expected output: 103 × 110 = 11330 samples. Observed Python output:
10670 samples (97 frames). C output: 13845 samples (≈126 frames).

The 97-vs-103 frame gap inside Python is because the final allophone
runs out before its full `durfon=12` (the per-frame `tcum >= durfon`
test pre-increments tcum by 1 each loop), but that's a minor detail
compared with the 126-vs-97 frame gap vs C.

### F0 contour (`phinton` → `pht0draw`)

```
After phinton:
  nf0tot   = 0
  f0tim    = [0, 0, 0, ...]    (all zero)
  f0tar    = [0, 0, 0, ...]    (all zero)
  f0type   = []                (empty)
  f0length = []                (empty)
```

`phinton` produces **zero F0 events** for this clause. Tracing back,
the input it consumes is `allofeats[]` — and `us_phtiming` leaves
`allofeats` populated with all zeros:

```
allofeats: [0, 0, 0, 0, 0, 0, 0]
```

In the C source, `allofeats` is populated by the phoneme-feature
classifier before `phinton` runs (stress markers, vowel/consonant
class, syllable boundary, hat-begin/hat-end). With `allofeats=0`
everywhere, `phinton` sees a clause of unstressed, unmarked
phonemes and emits no rise/fall/glottalize events.

Net effect on `pht0draw`: the f0 baseline + soft init runs but no
phrase-level pitch contour is drawn. The synthesizer emits a
monotone (`OUT_T0` stays near `f0minimum`).

### Frame loop (`phdraw` + `pht0draw` per frame)

97 frames produced (see allodurs above). The loop terminates on
`nphone >= nallotot` — i.e. it does NOT honour the C source's
trailing silence pad. In the C reference, `say -a 'hello world'`
emits 13845 samples, with the last non-zero sample at index 9872 —
that's 3973 samples (~360 ms / ~36 frames) of trailing silence
appended after the final GEN_SIL allophone. Python's GEN_SIL final
allophone has `durfon=12` (≈109 ms), so the trailing silence is
~250 ms short of the C reference.

### LL synthesis (`ll_synthesize`)

`ll_synthesize` is bit-accurate from `LLFrame` to int16 PCM (the
`tests/parity/test_synth_parity.py` corpus confirms this). It is
not the divergence source; the divergence is upstream in
`parstochip_to_llframe_delayed`'s inputs (i.e. `phdraw`'s
`parstochip[]` outputs).

## Top 3 divergence root causes (ranked by sample-distance impact)

### #1 — Front-end ARPABET → USPhoneme mapping silently drops phonemes

**Where**: `src/dectalk/api/speak.py:189-202` (`_arpabet_to_us_allophone`).

**Symptom**: For `hello world`, 3 of 8 ARPABET phones (HH + 2×L)
drop on the floor. The resulting allophone stream is 5 phones rather
than 8 → ~38% fewer frames → ~3175 fewer samples (-23% sample
count).

**Why**: `_arpabet_to_us_allophone` looks up the bare ARPABET name
(e.g. `"HH"`) directly in `USPhoneme`, but the DECtalk enum names
its allophones in the legacy FONIX scheme (`HX` for /h/, `LL` for
/l/, `NX` for /ŋ/). No alias table is consulted; missing names
return `None` and the caller in `_speak_via_python_full` silently
skips them (`if code is not None: allophons.append(code)`).

**Fix sketch**: introduce an ARPABET→USPhoneme alias dict at module
level in `_arpabet_to_us_allophone`. The known missing aliases are
`HH→HX`, `L→LL`, `NG→NX`. Audit additional ARPABET stress/length
variants the LTS fallback may emit (e.g. `AX`, `IX`, `EL`, `EN`)
to make sure they all resolve.

**Estimated parity recovery**: every prompt containing /h/, /l/,
or /ŋ/ improves substantially. Likely the single largest single-
edit improvement available.

### #2 — `allofeats` never populated, so `phinton` emits no F0 events

**Where**: `src/dectalk/api/speak.py:_speak_via_python_full` orchestration
between `us_phtiming` and `phinton` (lines ~341-373).

**Symptom**: `nf0tot=0` after `phinton`; the F0 contour has no
rise / fall / hat / question gestures. The synthesised pitch is a
flat monotone at `f0minimum` regardless of sentence shape.

**Why**: in the C reference, the front-end populates `allofeats[i]`
with a packed flags word (stress bit, syllable/word boundary,
hat-begin/hat-end, vowel class) for each allophone before
`phinton` runs. The Python orchestrator does not perform this step
— the `allofeats` array stays initialised to zero from
`init_phclause`.

**Fix sketch**: port the C-side allofeats classifier (lives in
`/tmp/dectalk-src/src/dapi/src/ph/ph_setar.c` or `ph_inton*.c` —
needs source-reading to confirm) and wire it after `us_phtiming`
and before `init_clause` / `phinton`. Once `allofeats` carries
stress + boundary markers, `phinton` produces the F0 events that
`pht0draw` consumes; pitch contour comes back to life.

**Estimated parity recovery**: F0 contour drives the `OUT_T0`
parameter, which `ll_synthesize` uses for excitation frequency
in voiced regions. Restoring it makes voiced phones audibly
correct but doesn't change frame counts; expect substantial
L2/sample reduction but still no bit parity until #1 + #3 are
also closed.

### #3 — Inline `[:cmd ...]` directives are not parsed on the full-pipeline path

**Where**: `src/dectalk/api/speak.py:_speak_via_python_full` lines 272-276.

**Symptom**: `[:rate 250] testing one two three` produces 34540
Python samples vs 14697 C samples (+19843 sample diff, ~+1.8 s of
extra audio). The Python pipeline spells out the literal command
text as if it were words.

**Why**: `_speak_via_python_full` calls `tokenize(text)` directly,
bypassing the `parse(text)` segmenter that the legacy approximate
path uses. `tokenize` treats `[:`, `rate`, `250`, `]` as plain
words → `lts()` LTS-falls them → they become `R EY1 T T UW1
HH AH1 N D R AH0 D F IH1 F T IY0` ("rate two hundred and fifty")
before the actual content phones.

In the C reference, the same inline command is consumed by the
front-end's command dispatcher (sets the WPM, doesn't emit any
phones).

**Fix sketch**: rewrite the front-end of `_speak_via_python_full`
to call `parse()` (or its DECtalk-native equivalent under
`src/dectalk/cmd/`) so inline commands mutate per-segment state
without bleeding into the allophone stream. Then pump each
segment's text through the existing tokenize + ARPABET-to-
allophone pipeline with the segment's rate / voice applied.

**Estimated parity recovery**: a single prompt's |Δsamples| drops
from ~20k to ~1-3k. Out of the 15-prompt sample only one prompt
hits this code path, but the corpus has ~hundreds of inline-
command variants further down the list (rate, voice presets,
phoneme mode).

## Honourable mentions (smaller-impact but real)

- **Trailing silence is too short.** Python's final GEN_SIL gets
  `durfon=12` (~109 ms); C pads ~360 ms of trailing zeros. Suspect
  `init_phclause` / `init_timing` does not emit the C's
  end-of-clause silence pad; needs a comparison of `allodurs[last]`
  vs the C reference's `pDph_t->allodurs[nallotot-1]`.
- **Leading silence is *correct*.** Both C and Python emit exactly
  213 leading-zero samples on `hello world` and on most other
  prompts. The first-diff index of 213 (or a small frame multiple)
  consistently signals "silence prefix matches; first voiced frame
  diverges immediately". This rules out WAV-header / sample-rate
  drift as a divergence source.
- **`HH` / `L` / `NG` dropouts cascade into `us_phtiming` and
  `phsettar`** — those modules run on a degraded allophone stream
  and produce shorter `allodurs` than they would for the
  complete phone set. Fixing #1 will *also* improve cumulative
  duration metrics measured downstream.

## Concrete follow-up issues to file

Each of the three top causes is a self-contained port / fix task.
Filing them as separate issues lets them be dispatched in parallel.

### Issue A — ARPABET → USPhoneme alias table

> **Title**: `_arpabet_to_us_allophone` silently drops HH, L, NG
> (and possibly others) — add alias table
>
> Scope: 5-20 lines in `src/dectalk/api/speak.py`. Add a module-
> level `_ARPABET_ALIASES: dict[str, USPhoneme]` mapping the
> CMUdict ARPABET symbols that don't have a direct enum entry.
> Known: `HH→HX`, `L→LL`, `NG→NX`. Audit `EL`, `EN`, `AX`, `IX`,
> `EM`, `DX`, `Q` (LTS fallback may emit these). Add a unit test
> that every symbol the `lts` module can output resolves.
> Labels: `area/ph`, `size/small`.

### Issue B — Populate `allofeats` before `phinton` (port `ph_setallofeats`)

> **Title**: PH-stage `allofeats[]` is all-zero on the full Python
> path; `phinton` emits no F0 events
>
> Scope: port the C-side allofeats classifier from
> `/tmp/dectalk-src/src/dapi/src/ph/` (likely `ph_setar.c` or a
> dedicated `ph_setallofeats.c`; needs source-reading to locate)
> and call it from `_speak_via_python_full` between
> `us_phtiming(handle)` and `init_clause(p_dph_t)`. Acceptance
> test: after the call, `allofeats[]` matches the C reference for
> the 15-prompt parity sample, and `phinton` writes a non-zero
> `nf0tot` for every clause that contains a stressed vowel.
> Labels: `area/ph`, `size/medium`.

### Issue C — Route `_speak_via_python_full` through `parse()` for inline commands

> **Title**: Full-pipeline path bypasses `parse()`; `[:rate N]` /
> `[:nb]` / `[:phoneme on]` directives leak into the phone stream
>
> Scope: replace the `tokenize(text)` call at line 273 of
> `src/dectalk/api/speak.py` with a per-segment loop matching the
> legacy approximate path's segment walk (see lines 449-487). For
> each segment, apply its `rate` to `wpm` and its `voice` to
> `voice_preset` *before* running `init_phclause` + `us_phtiming`
> + `phinton` + the per-frame loop. Bonus: `phoneme on` segments
> should pass `seg.body.split()` straight to the allophone mapper
> without re-tokenisation.
> Labels: `area/api`, `size/medium`.

## Reproducer

```bash
# Once oracle is ready:
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh

# Diagnostic diff for the first 15 prompts under either path.
# Approximate (default) path:
DECTALK_DISABLE_CAPI=1 uv run python /tmp/parity_diag.py 15

# Full pipeline (work-in-progress port):
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/parity_diag.py 15
```

The `parity_diag.py` script that generated the numbers in this
report is reproduced in the issue body when each of A/B/C is
filed; it is intentionally not committed under `scripts/` to keep
the audit a doc-only PR.
