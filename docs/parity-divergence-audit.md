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

## F0 contour follow-up (issue #75, post-#63 / post-#66)

After #63 (`ph_setallofeats` populating `FSTRESS` / `FWBNEXT` /
`FPERNEXT`) and #66 (wiring `phinton` into `_speak_via_python_full`),
the audit's original prediction — "synthesised pitch is a flat
monotone" — was expected to be closed. A direct re-measurement on
the three reference prompts (`hello world`, `testing one two three`,
`the quick brown fox`) shows it is **not** yet closed: `phinton`
emits only the trailing `F0_RESET` event on every prompt, the
`OUT_T0` register stays clamped at `f0minimum` ± a few Hz of
flutter, and the audible contour is still monotone.

### Method

`_speak_via_python_full` was run on each prompt with the full
pipeline (`DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1`,
default Paul voice). A monkey-patch on `dectalk.ph.phinton.phinton`
captured the post-phinton state (`nf0tot`, `f0tar[]`, `f0type[]`,
`f0length[]`, `f0tim[]`, `allofeats[]`), and a monkey-patch on
`dectalk.ph.pht0draw.pht0draw` recorded the per-frame
`parstochip[OUT_T0]` value (Hz × 10 in the HLSYN code path).
For the C reference, `say -a TEXT -fo` was rendered and its
short-time F0 estimated via autocorrelation on 110-sample
windows (one Klatt frame). Autocorrelation overestimates the
mean F0 of a low-pitched male voice when the second harmonic is
stronger than the fundamental, so the comparison below focuses
on **shape and dynamic range**, not absolute mean.

### Per-prompt summary

Measured against `dev` head ``fbd679d`` (which includes #74's
`init_phclause` ending-silence fix). The new trailing-silence pad
inflates Python sample counts (+612-837 ms) but does not change
the F0 verdict.

| Prompt | C samp | Py samp | Py `nf0tot` | C F0 range (60-350 band) | Py OUT_T0 range |
|---|---:|---:|---:|---|---|
| `hello world` | 13845 | 14520 | 2 | mean 154 std 67, [91, 345] Hz | mean 87 std 7, [50, 91] Hz |
| `testing one two three` | 19099 | 25850 | 2 | mean 183 std 73, [95, 344] Hz | mean 89 std 6, [50, 97] Hz |
| `the quick brown fox` | 19809 | 29040 | 2 | mean 158 std 70, [78, 340] Hz | mean 88 std 5, [50, 94] Hz |

The two events emitted by `phinton` on each prompt are both
`F0_RESET` writes from Rule 7's `phocur == GEN_SIL` branch — one
at the trailing silence, one at the leading silence after the
init_phclause padding:

```
event[0]: f0tim=89-157, f0tar=0, f0type=F0_RESET, f0length=20
event[1]: f0tim=36-38,  f0tar=0, f0type=F0_RESET, f0length=20
```

No hat-rise (`STEP, rule=1`), no stress impulse
(`IMPULSE, rule=21..24`), no continuation rise, no question
gesture, no glottalize. All Rule-1 through Rule-6 branches in
`phinton` short-circuit before reaching `make_f0_command`.

### Root cause: `all_phsort` is not wired into the full pipeline

The C-source feature classifier that sets `FHAT_BEGINS` /
`FHAT_ENDS` on allophones — and counts words into
`pDph_t->number_words` — lives in `ph_sort.c`
(`/tmp/dectalk-src/src/dapi/src/ph/ph_sort.c`):

```c
// ph_sort.c lines 471, 1534, 1659, 1669
pDph_t->number_words = 0;          // init
...
pDph_t->number_words++;            // per word boundary
...
add_feature(pDph_t, FHAT_BEGINS, NEXTPHONE);
add_feature(pDph_t, FHAT_ENDS,   NEXTPHONE);
```

The Python port `dectalk.ph.all_phsort.all_phsort` exists, is
~547 lines, and faithfully mirrors the US-English branches of
`ph_sort.c` (including the `number_words` and FHAT writes — see
`src/dectalk/ph/all_phsort.py:176, 441, 497, 500`). It is
**never called** from `_speak_via_python_full`:

```
$ grep -n 'all_phsort\|ph_sort\|phsort' src/dectalk/api/speak.py
(no matches)
```

`_speak_via_python_full` instead jumps straight from ARPABET
tokens to `pDph_t.allophons[]` via `_arpabet_to_us_allophone`,
skipping the symbol-stream pass that `all_phsort` operates on.
Consequences, observed in the captured state for `hello world`:

```
allofeats (hex): [0x0, 0x0, 0x61, 0x0, 0x101, 0x0, 0x0, 0x0, 0x0, 0x0]
   FHAT_BEGINS: all False
   FHAT_ENDS:   all False
number_words:  0
clausetype:    0  (DECLARATIVE by accident — never explicitly set)
```

`phinton` guards every hat rule with
`if pDph_t.number_words > 2` (ph_inton2.c line 911) and
`if struccur & FHAT_BEGINS` / `FHAT_ENDS` (lines 913, 917) —
both fail vacuously on the current allofeats, so no hat / impulse
events are ever queued. The single trailing `F0_RESET` we observe
comes from Rule 7's final-silence handler (`phocur == GEN_SIL`
branch at the end of the loop).

Downstream, in `pht0draw`, the empty event queue means
`tarhat` and `tarimp` stay 0 every frame:

```python
# pht0draw.py line 506
f0in = p_dph_t.f0minimum + pdphsettar.tarhat + pdphsettar.tarimp
#    = 880               + 0                + 0
#    = 880               (i.e. 88.0 Hz × 10)
```

so `parstochip[OUT_T0] ≈ f0minimum`, modulated only by the
2-pole filter ringing and the ±10 Hz flutter from
`getcosine_tab`. That matches the observed
`mean 88, std 4-6, range [61, 97]` Hz exactly.

### Secondary issue: speaker-definition F0 parameters incomplete

`src/dectalk/api/speak.py:444-448` hand-seeds three F0
parameters from the Paul SPD chip (QU → `f0_lp_filter`,
AP → `f0minimum`, PR → `f0scalefac`). The C function that
populates this group — `ph_vset.c` lines 605-619 — also writes
`size_hat_rise = SPD_HR * 10` and `scale_str_rise = SPD_SR`,
which `phinton` reads at line 376 (`pDphsettar.hatsize =
pDph_t.size_hat_rise`) and line 459 (`temp = pDph_t.scale_str_rise`).
Python leaves both at their `DphT` default of `0`, which would
zero out the hat-rise / stress-rise magnitudes even once
`FHAT_BEGINS` / `FSTRESS` are populated. The audit confirmed by
grep that `size_hat_rise` and `scale_str_rise` are referenced
exactly twice each in Python: at the DphT declaration site and
the phinton read site — never written.

This is a smaller, follow-on fix; it only bites once `all_phsort`
is wired in.

### Tertiary observation: sample count has regressed vs the C reference

Between the original audit and `dev` head ``fbd679d``, sample
counts oscillated:

| Prompt | original Δsamp (#58) | pre-#74 Δsamp | post-#74 Δsamp |
|---|---:|---:|---:|
| `hello world` | -3175 | +675 | +675 |
| `the quick brown fox` | -1549 | +2411 | +9231 |
| `testing one two three` | n/a | +41 | +6751 |

The original divergence was mostly under-running (Python shorter
than C). PR #66 brought sample counts within ~4 ms on
`testing one two three` and ~60 ms on `hello world`. PR #74's
init_phclause padding (final allodur jumped from 12-15 to 71
frames, see "Allodurs" in the per-prompt summary) over-pads
some prompts by 600-850 ms.

This is **not** an F0-contour blocker — it's an orthogonal
duration regression that issue #75 is not chartered to address.
Issue #72 ("Fix trailing silence") may already cover it. Worth
filing or commenting on if not.

### Concrete follow-up issues to file

Each is self-contained and can be dispatched in parallel.

#### Issue D — Wire `all_phsort` into `_speak_via_python_full`

> **Title**: PH-sort engine `all_phsort` is ported but not called;
> `phinton` sees `number_words=0` and `FHAT_BEGINS`/`FHAT_ENDS`
> are never set → flat-monotone F0
>
> Scope: `_speak_via_python_full` (`src/dectalk/api/speak.py`)
> currently builds `pDph_t.allophons[]` directly from
> `_arpabet_to_us_allophone(arpabet_words)` and never runs the
> upstream symbol-stream pass. The fix is to populate
> `pDph_t.symbols[]` (and the LTS-side scaffolding `all_phsort`
> reads — `cbsymbol`, `dcommacnt`, etc.) and then call
> `all_phsort(handle)` between the LTS / ARPABET emission and
> `init_phclause`. After `all_phsort`, the existing
> `_arpabet_to_us_allophone` fallback can be retired or kept as
> a stop-gap behind a flag.
>
> Acceptance criteria:
> - On `hello world`, `testing one two three`, and `the quick
>   brown fox`, post-`phinton` `nf0tot >= 3` for each prompt.
> - `allofeats` after `all_phsort` includes at least one
>   `FHAT_BEGINS` and one `FHAT_ENDS` bit on each prompt
>   (multi-word, declarative).
> - `pDph_t.number_words` matches the human word count
>   (`hello world` → 2, `testing one two three` → 4,
>   `the quick brown fox` → 4).
> - The per-frame `OUT_T0` std on `hello world` increases from
>   ~4 Hz (current) to > 50 Hz, matching C-oracle dynamic range.
>
> Labels: `area/ph`, `area/api`, `size/large`.

#### Issue E — Load `size_hat_rise` and `scale_str_rise` from SPD chip

> **Title**: `pDph_t.size_hat_rise` and `pDph_t.scale_str_rise`
> are never loaded from the speaker definition
>
> Scope: `src/dectalk/api/speak.py:444-448` seeds three F0
> parameters from `_us_paul_spd`; extend to write
> `pDph_t.size_hat_rise = _us_paul_spd.hr * 10` and
> `pDph_t.scale_str_rise = _us_paul_spd.sr` (or equivalent SPD
> field names — confirm against `ph_vset.c` lines 611-612). The
> `default_us_paul_spd` constructor in
> `src/dectalk/vtm/spd_chip.py` may need the `hr` / `sr` fields
> added if not present.
>
> Acceptance criteria:
> - `pDph_t.size_hat_rise` is non-zero after the speaker-def
>   load, matching the value the C oracle uses for Paul.
> - Unit test asserts the SPD field load.
>
> Labels: `area/ph`, `size/small`.
> Depends on Issue D landing first (otherwise the field is read
> but never used).

#### Issue F — Per-frame F0 trace fixture for future regression tests

> **Title**: Capture per-frame `parstochip[OUT_T0]` from the C
> oracle for the parity corpus prompts
>
> Scope: add a C-side patch (under
> `tests/parity/c_patches/`) that prints `parstochip[OUT_T0]`
> after each `pht0draw` call in `ph_claus.c`, plus a Python
> fixture script that runs the patched binary on the first 15
> corpus prompts and stores the per-frame F0 trace as a `.npz`
> under `tests/parity/data/`. Future intonation-engine PRs can
> then assert per-frame OUT_T0 parity (not just audio L2)
> without re-running the binary.
>
> Labels: `area/parity`, `size/medium`.
> Independent of Issue D; can land in parallel.

### Reproducer

```bash
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh
# Render and capture F0 events + per-frame OUT_T0:
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/f0_audit.py
```

The diagnostic scripts (`/tmp/f0_audit.py`, `/tmp/f0_debug.py`,
`/tmp/f0_contour_compare.py`) live in `/tmp/` to keep this audit
a doc-only PR; their content is embedded verbatim in the
follow-up Issue D body.

## F0 contour follow-up — re-audit after #66 / #94 / #97 (issue #75, 2026-05-22)

Re-measurement on `dev` head `c829010` (after Issues D + E landed —
`all_phsort` wired into `_speak_via_python_full` in commit `909c5ff`,
HR/SR scalars loaded, `ph_setallofeats` populating FSTRESS / FWBNEXT /
FPERNEXT, plus the phinton `goto skiprules` fix in #73, and the
allofeats derivation from ARPABET in #94). The headline finding from
the 2026-05 audit — "synthesised pitch is a flat monotone" — is
**still not closed**. `phinton` now fires actual stress impulses
(Rule 2) and clause-end gestures (Rule 6) instead of just the two
`F0_RESET` events the previous audit captured, but **Rule 1 (hat-rise
STEP) and Rule 3/4 (hat-fall GLIDE/STEP) never fire**, so the
per-frame `OUT_T0` register still clamps at `f0minimum + ±5 Hz of
flutter`.

### Method

Same as the original follow-up audit. Re-measured at dev head
`c829010` with `DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1` and
the Paul voice. Monkey-patches captured (a) the full `make_f0_command`
call sequence with rulenumber, (b) post-`phinton` `f0type` /
`f0tar` / `f0tim` / `f0length` arrays, (c) per-frame
`parstochip[OUT_T0]`, and (d) `allofeats[]` snapshots immediately
after `all_phsort` and again after `ph_setallofeats`.

C-oracle F0 estimated via 110-sample-frame autocorrelation in the
60-350 Hz band. The autocorrelation overestimates absolute mean F0
for a low male voice when the second harmonic dominates the
fundamental, so the comparison below focuses on **dynamic range
(std)** and shape, not absolute mean.

### Per-prompt summary (2026-05-22)

| Prompt | C samp | Py samp | Py `nf0tot` | C F0 std (Hz) | Py OUT_T0 std (Hz) | Py OUT_T0 mean |
|---|---:|---:|---:|---:|---:|---:|
| `hello world`            | 13845 | 24640 | 4 | 83 | **5** | 88 |
| `testing one two three`  | 19099 | 29040 | 3 | 60 | **6** | 90 |
| `the quick brown fox`    | 19809 | 32670 | 5 | 73 | **5** | 89 |

For all three prompts:

- **C oracle**: OUT_T0 std is 60-83 Hz — a real intonation contour
  spanning ~120-356 Hz.
- **Python**: OUT_T0 std is 5-6 Hz — i.e. flat ±0.5 Hz around the
  88 Hz f0minimum baseline, modulated only by the 2-pole filter
  ringing and the ±10 Hz flutter from `getcosine_tab`.

### Which phinton rules fire (per-prompt)

`hello world`:

```
[ 0] type=IMPULSE  rule= 2  tar= 80  delay= 15  length= 25  nphon=2  (stress pulse on "HEL")
[ 1] type=IMPULSE  rule= 2  tar= 50  delay= -3  length= 36  nphon=4  (stress pulse on "WOR")
[ 2] type=IMPULSE  rule= 6  tar=  0  delay= 43  length= 20  nphon=4  (FPERNEXT final-fall, voiced-next path)
[ 3] type=IMPULSE  rule= 6  tar=  0  delay=  7  length= 20  nphon=8  (FPERNEXT final-fall, second voiced-next)
```

`testing one two three`:

```
[ 0] type=IMPULSE  rule= 2  tar= 80  delay= 14  length= 24  nphon=2
[ 1] type=IMPULSE  rule= 6  tar=  0  delay= 13  length= 20  nphon=11
[ 2] type=IMPULSE  rule= 6  tar=  0  delay= 22  length= 20  nphon=14
```

`the quick brown fox`:

```
[ 0] type=IMPULSE  rule= 2  tar= 80  delay= 68  length= 24  nphon=...
[ 1] type=IMPULSE  rule= 2  tar= 53  delay= 54  length= 32  nphon=...
[ 2] type=IMPULSE  rule= 2  tar= 43  delay= 23  length= 31  nphon=...
[ 3] type=IMPULSE  rule= 6  tar=  0  delay= 22  length= 20  nphon=...
[ 4] type=IMPULSE  rule= 6  tar=  0  delay= 46  length= 20  nphon=...
```

Rules **never** fired in any prompt:

| Rule | Type    | Trigger                                                        | Why it doesn't fire                                                            |
|------|---------|----------------------------------------------------------------|--------------------------------------------------------------------------------|
| 1    | STEP    | First stressed syllable when `had_hatbegin == 1`               | `had_hatbegin` is only set by `struccur & FHAT_BEGINS`; FHAT_BEGINS never set  |
| 3    | GLIDE   | End-of-hat when `had_hatend == 1`                              | `had_hatend` is only set by `struccur & FHAT_ENDS`; FHAT_ENDS never set        |
| 4    | STEP    | Same `had_hatend` block, nested in Rule 3                      | Same as Rule 3                                                                 |
| 7    | F0_RESET| End-of-clause `phocur == GEN_SIL` with `hat_loc_re_baseline`   | `hat_loc_re_baseline` never non-zero because Rule 1's `+= hatsize` never runs  |
| GLOTTAL | -    | Glottalize gesture for FGLOTTAL phones                         | (not investigated here — secondary)                                            |

Rules **2** (stress impulse) and **6** (final/comma fall) DO fire,
which is the post-#66/#94 improvement. But these are short transient
impulses that decay back to f0minimum within ~25 frames — they don't
sustain the +18 Hz hat-rise plateau that Rule 1 (STEP) is supposed to
hold across the whole `pDphsettar.hat_loc_re_baseline` plateau.

### Root cause: `us_phalloph` is not wired into the full pipeline

The C-side hat-pattern engine lives in **`ph_aloph1.c`** (translated
into Python as `src/dectalk/ph/us_phalloph.py`, 516 lines, fully
ported with FHAT_BEGINS / FHAT_ENDS writes at lines 441 and 453).
For plain-text input (no explicit `[/...]` markup), `ph_sort.c`'s
HAT_RISE / HAT_FALL token-handling case **does not fire** — it only
catches user-typed phonetic markup. The implicit, stress-pattern-
driven FHAT_BEGINS / FHAT_ENDS writes live entirely inside
`ph_aloph1.c` lines 1338-1448:

```c
// ph_aloph1.c line 1338 — "Rise occurs on first stress of any type in phrase"
if ((hatposition != AT_TOP_OF_HAT)
    && (((curr_instruc & FSTRESS_1) IS_PLUS)
        || (remaining_stresses_til (pDph_t, n, FCBNEXT) > 0)))
{
    curr_outstruc |= FHAT_BEGINS;
    hatposition = AT_TOP_OF_HAT;
}

// ph_aloph1.c lines 1370-1448 — "Fall occurs on emphasized syll / last
// stress of clause / last stress of phrase containing 2+ stresses"
if ((hatposition == AT_TOP_OF_HAT) && ((curr_instruc & FSTRESS_1) IS_PLUS))
{ ... curr_outstruc |= FHAT_ENDS; ... }
```

The Python port `us_phalloph` faithfully mirrors these writes
(`src/dectalk/ph/us_phalloph.py:441,453`). It is **never called** from
`_speak_via_python_full`:

```
$ grep -n 'us_phalloph\|phalloph' src/dectalk/api/speak.py
602:    # In the C reference, phalloph2/make_out_phonol writes the
604:    # allophone. The Python pipeline skips phalloph for now, so we
```

The comment at line 604 says it explicitly: "The Python pipeline
skips phalloph for now, so we derive the minimum feature set phinton
needs (FSTRESS from the ARPABET stress digit, FWBNEXT / FPERNEXT
from word/sentence boundaries) directly from the front-end data".
That minimum feature set is exactly the set that lets Rules 2 and 6
fire — but it does NOT cover FHAT_BEGINS / FHAT_ENDS, which are
stress-pattern-derived, not symbol-derived.

The current orchestration also actively **erases** any FHAT bits
`all_phsort` might have written:

```python
# src/dectalk/api/speak.py:594-599
# Re-zero allofeats since all_phsort's output pass may have written
# FSTRESS_1/FWBNEXT/FHAT_BEGINS bits into sentstruc[] (which aliases
# allofeats[]). ph_setallofeats below re-derives the bits we actually
# use from the ARPABET stream + word grouping.
for i in range(len(p_dph_t.allofeats)):
    p_dph_t.allofeats[i] = 0
```

Even if `all_phsort` did set hat bits (it doesn't on plain text), the
re-zero pass would wipe them — so the orchestration would also need
to be revised to either (a) preserve the hat bits while still
re-deriving the stress/boundary bits, or (b) source all the bits
from `us_phalloph` instead of from `ph_setallofeats`.

### Verification: allofeats at each stage

Captured for `hello world` with monkey-patches at `all_phsort` and
`ph_setallofeats` exit points:

```
after all_phsort: nallotot=0, nphonetot=9, number_words=3, clausetype=0
  allophons (hex):  ['0x1c', '0x9', '0x1b', '0xb', '0x18', '0x14', '0x1b', '0x30', '0x1e00']
  allofeats (hex):  ['0x4', '0x8', '0x0', '0x78', '0x5', '0x101', '0x100', '0x100', '0x100']
  allofeats (decoded): ['-', '-', '-', 'WBN', 'S1', 'S1+PERN', 'PERN', 'PERN', 'PERN']
                       (no HB / HE bits anywhere — confirms ph_sort.c writes nothing without HAT_RISE markup)

after ph_setallofeats: nallotot=10
  allofeats (decoded): ['-', '-', 'S1+WBN', '-', 'S1+PERN', '-', '-', '-', '-', '-']
                       (allofeats zeroed; ph_setallofeats re-derived stress + boundary bits;
                        FHAT_BEGINS / FHAT_ENDS still absent because ph_setallofeats does not
                        synthesise them)
```

Both stages produce zero FHAT bits — the gap is exactly the
`us_phalloph` (ph_aloph1.c) substitution+hat-pattern pass.

### Secondary issue: `assertiveness` parameter never loaded

`pDph_t.assertiveness` defaults to `0` (see `src/dectalk/ph/dph_t.py:192`).
The Paul SPD chip carries AS=100 (full assertiveness). Three places in
`phinton` apply `frac4mul(f0fall, pDph_t.assertiveness)`:

- line 514 (Rule 3 GLIDE down magnitude)
- line 611 (Rule 4 STEP down magnitude)
- line 650 (Rule 6 final-fall IMPULSE magnitude — currently zeroes out
  `tar` in all three measured prompts; see `tar=0` in events [2,3]
  for `hello world`, [1,2] for `testing one two three`, [3,4] for
  `the quick brown fox`)

With `assertiveness == 0`, `frac4mul` returns 0 regardless of the
input `f0fall`. So once Rule 1's hat-rise plateau IS restored, Rule 6
will still emit zero-magnitude final-fall impulses unless
`assertiveness` is also loaded from the SPD chip. Same speaker-def
fix shape as the HR/SR loaders at `src/dectalk/api/speak.py:553-554`
that #94 added.

### Tertiary observation: sample count is now consistently over-long

| Prompt | original Δsamp (#58) | post-#66 Δsamp | post-#74 Δsamp | post-#94 Δsamp (current) |
|---|---:|---:|---:|---:|
| `hello world`            | -3175 |  +675 |  +675 | +10795 |
| `the quick brown fox`    | -1549 | +2411 | +9231 | +12861 |
| `testing one two three`  | n/a   |   +41 | +6751 |  +9941 |

The sample-count gap has **widened** post-#94 — Python is now ~600-1200 ms
over-long on each of the three reference prompts. This appears to be a
side effect of the trailing-silence pad (#72/#74) compounding with the
`us_phtiming` durations on the now-richer allophone stream. The audit
notes this for completeness but it is **not** an F0 blocker — issue
#72 / #74 own the trailing-silence regression. Worth correlating with
the per-frame OUT_T0 trace because the trailing silence inflates the
"frames" denominator in OUT_T0 std measurement, biasing the std
downward (a longer silence segment with no F0 events drags the std
toward 0).

### Concrete follow-up issues to file

Each issue is self-contained and can be dispatched in parallel.
Re-numbered as G/H/I to avoid colliding with the earlier
D/E/F (which are now closed by #94 and the in-flight per-frame
fixture).

#### Issue G — Wire `us_phalloph` into `_speak_via_python_full`

> **Title**: `us_phalloph` (ph_aloph1.c) is ported but not called;
> `phinton` never sees `FHAT_BEGINS` / `FHAT_ENDS` → flat-monotone F0
>
> Scope: `_speak_via_python_full` (`src/dectalk/api/speak.py:586-619`)
> currently runs `all_phsort` for its bookkeeping side-effects
> (`number_words`, `clausetype`) and then **bypasses** `us_phalloph`
> entirely — building `allophons[]` from `_arpabet_to_us_allophone`
> and `allofeats[]` from `ph_setallofeats` instead. The fix is to
> drive the ph stage through `us_phalloph`:
>
> 1. Confirm `all_phsort` populates `phonemes[]` / `sentstruc[]` /
>    `nphonetot` for a plain-text input (it currently does — see
>    captured trace at the top of this section).
> 2. Call `us_phalloph(handle)` immediately after `all_phsort`. This
>    will populate `allophons[]` / `allofeats[]` / `nallotot` with
>    the substitution-applied stream **including** FHAT_BEGINS /
>    FHAT_ENDS bits.
> 3. Retire the manual `_arpabet_to_us_allophone` allophons-fill loop
>    (lines 591-593) and the `allofeats` re-zero + `ph_setallofeats`
>    block (lines 594-619), or keep them behind a fallback flag for
>    inputs `us_phalloph` chokes on (TBD whether any exist).
> 4. The end-of-clause `FPERNEXT | FSENTENDS` marker injection at
>    lines 644-646 may become redundant once `us_phalloph` writes
>    sentence-end markers itself — re-measure and remove if so.
>
> Acceptance criteria:
> - On `hello world`, `testing one two three`, and `the quick brown
>   fox`, at least one allofeats entry has `FHAT_BEGINS` (`0o1000`)
>   set after the ph stage, and at least one has `FHAT_ENDS`
>   (`0o2000`) set.
> - `phinton` emits at least one `STEP` event (`f0type == 2`) per
>   prompt — Rule 1 fires.
> - Per-frame `OUT_T0` std on `hello world` grows from the current
>   ~5 Hz to > 30 Hz (target ~80 Hz to match C, but >30 Hz is the
>   regression-test floor that distinguishes "flat" from "contoured").
>
> Labels: `area/ph`, `area/api`, `size/medium`.
> Depends on: nothing (all dependencies — `all_phsort`, `us_phalloph`,
> `phinton`, `pht0draw` — are landed).

#### Issue H — Load `assertiveness` from the SPD chip

> **Title**: `pDph_t.assertiveness` defaults to 0; phinton Rules
> 3/4/6 emit zero-magnitude F0 falls
>
> Scope: `src/dectalk/api/speak.py:553-554` seeds `size_hat_rise` and
> `scale_str_rise` from the Paul SPD constants. Extend the block to
> also write:
>
> ```python
> p_dph_t.assertiveness = 100  # AS for Paul (p_us_vdf_dectalk43.c line 27)
> ```
>
> Confirm the actual AS value against `p_us_vdf_dectalk43.c` —
> `voice_definitions.py:9` documents AS as "assertiveness (final F0
> fall, %)" with a `Limit(0, 200)` range (`voice_limits.py:29`).
>
> Acceptance criteria:
> - `pDph_t.assertiveness == 100` (or whatever the actual SPD value
>   is) after the speaker-def load.
> - On `hello world` post-Issue-G, the Rule 6 final-fall events
>   carry a non-zero `f0tar` (e.g. matching the C oracle's terminal
>   F0 fall magnitude).
>
> Labels: `area/ph`, `area/api`, `size/small`.
> Depends on: Issue G landing first (otherwise the zero-AS bug is
> masked by the flat-baseline from missing FHAT bits).

#### Issue I — (deferred — per-frame OUT_T0 parity fixture)

The original "Issue F" (per-frame `parstochip[OUT_T0]` capture from
the C oracle, stored as `.npz` under `tests/parity/data/`) remains
valuable as a regression gate for Issues G and H. The audit
recommends filing it as a separate task; the implementation sketch
is in the earlier follow-up section (lines 564-579 above) and
unchanged by the new findings.

### Reproducer (2026-05-22 audit)

```bash
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh

# Per-prompt F0 events + per-frame OUT_T0 + allofeats snapshot:
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    DECTALK_BIN=$DECTALK_BIN uv run python /tmp/f0_audit_re.py

# Rule-firing trace (which phinton rules fire on each prompt):
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/f0_rule_trace.py

# Stage-by-stage allofeats capture (after all_phsort vs after ph_setallofeats):
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/f0_stage_trace.py
```

The three diagnostic scripts live in `/tmp/` to keep this audit a
doc-only PR; their content is embedded verbatim in the body of
follow-up Issues G and H when filed.

## Update 2026-05-22 (post-#97/#102/#107/#118/#120)

Re-run of the 15-prompt parity diagnostic from §"Per-prompt
divergence" on dev head `e0db2bc` (the latest commit after the
PR-set listed in the section title — `da81603` was the previous
audit's head, but PRs #97 / #102 / #107 / #120 and a fix for #87
have landed since). Since the original audit (#58, dev head
~7ca914c), the following landed:

- **#62 / PR #65** — ARPABET → USPhoneme alias gap (HH/L/NG no longer dropped).
- **#63 / PR #66** — `ph_setallofeats` stop-gap so `phinton` sees FSTRESS / FWBNEXT / FPERNEXT.
- **#64 / PR #67** — `_speak_via_python_full` now routes through `parse()`, so `[:rate N]` is consumed by the command dispatcher instead of being spelled out.
- **#71 / PR #94 (commit 909c5ff)** — `phdraw` once-per-phone setup + FVOWEL A2-jam; `all_phsort` wired into `_speak_via_python_full`; HR/SR scalars loaded.
- **#72 / PR #102** — trailing-silence pad on the full-pipeline path (`nfperiod=94`, `nfcomma=16`, `FPERNEXT|FSENTENDS` on `nallotot-2`, `nallotot` re-read after `phinton`).
- **#73** — `phinton` Rule 9 `goto skiprules` fix (partially closed).
- **#85 / PR #107** — SpdChip US-Paul defaults audited against `p_us_vdf1.c paul_8`.
- **#79 / PR #118** — German `gr_gettar` wired with full GR ROM tables (doesn't affect US-Paul corpus).
- **#75 / PR #120** — F0 contour follow-up audit (doc only).
- **#69 / PR #97 (commit 3938c68)** — `phalloph2` chain ported and **wired** into `_render_clause_full`. The manual `_arpabet_to_us_allophone`-based `allophons[]` + `ph_setallofeats` derivation has been replaced by a full `_build_symbols_from_arpabet` → `all_phsort` → `us_phalloph` → `make_out_phonol` chain at lines 497-525 of `src/dectalk/api/speak.py`.

### Method

Same as #58. Each of the first 15 corpus prompts rendered three ways:

- C binary (`say -a TEXT -fo`) — reference.
- `DECTALK_DISABLE_CAPI=1` (legacy approximate path).
- `DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1` (the full pipeline through `_render_clause_full`).

For each prompt: sample-count delta, first-differing-sample index,
L2/sample, peak-abs error, and the lead / content / trail envelope
split. Decomposition: `Δsamples = Δlead + Δcontent + Δtrail`, where
lead = first non-zero index, content = `last_nz - first_nz + 1`,
trail = `total - last_nz - 1`. Also: per-allophone `allodurs[]`
captured via a monkey-patch on `us_phtiming`'s exit.

### Per-prompt divergence (full pipeline, 2026-05-22, post-#97)

| # | Prompt | C samp | Py samp | Δ samp | Δ ms | first_diff | L2/sample | max_abs_err | C rms |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|
| 0 | `hello world` | 13845 | 26840 | +12995 | +1179 | 213 / 19ms | 7489 | 42111 | 5418 |
| 1 | `the quick brown fox` | 19809 | 35750 | +15941 | +1446 | 213 / 19ms | 6237 | 34766 | 4391 |
| 2 | `she sells sea shells` | 20093 | 37510 | +17417 | +1580 | 213 / 19ms | 5445 | 34609 | 4535 |
| 3 | `one two three four five` | 22933 | 39710 | +16777 | +1522 | 348 / 32ms | 7238 | 37807 | 5156 |
| 4 | `supercalifragilisticexpialidocious` | 31169 | 58520 | +27351 | +2481 | 213 / 19ms | 3678 | 21574 | 2283 |
| 5 | `[:rate 250] testing one two three` | 14697 | 23210 | +8513 | +772 | 710 / 64ms | 5663 | 26974 | 4271 |
| 6 | `DECtalk version 6.2.0` | 32660 | 28710 | -3950 | -358 | 852 / 77ms | 5149 | 27646 | 3947 |
| 7 | `this is a test, with a comma, and a period.` | 34932 | 64240 | +29308 | +2658 | 213 / 19ms | 5188 | 33261 | 3634 |
| 8 | `the answer is 42` | 21300 | 36850 | +15550 | +1410 | 213 / 19ms | 5191 | 25621 | 3849 |
| 9 | `3 point 14` | 18602 | 31460 | +12858 | +1166 | 213 / 19ms | 6189 | 31581 | 4552 |
| 10 | `one hundred and one dalmatians` | 24140 | 45320 | +21180 | +1921 | 348 / 32ms | 5187 | 30467 | 3160 |
| 11 | `1234567890` | 74905 | 113960 | +39055 | +3542 | 348 / 32ms | 6004 | 34445 | 4043 |
| 12 | `hello! how are you?` | 25702 | 31240 | +5538 | +502 | 213 / 19ms | 7139 | 43932 | 5473 |
| 13 | `wait... what just happened?` | 26909 | 39710 | +12801 | +1161 | 326 / 30ms | 4636 | 30209 | 3560 |
| 14 | `yes; no; maybe.` | 21442 | 32230 | +10788 | +979 | 329 / 30ms | 6339 | 33962 | 4777 |

**Headline numbers.**

- 0/15 prompts match bit-exactly (unchanged from #58).
- Sign has flipped: 14 of 15 prompts are now **over-long** (only
  `DECtalk version 6.2.0` remains under-running, by 3950 samp).
  Mean |Δ| = 16668 samples (1512 ms), worst |Δ| = 39055 samples
  (3542 ms) on `1234567890`.
- Mean |Δ| has **regressed 2.85×** since #58 (original 5856 samp =
  531 ms). The original divergence was mostly under-running
  (Python shorter than C); the current state is consistently
  over-running by 1-3.5 seconds per prompt.
- `first_diff` index unchanged from #58: always equal to C's
  leading-silence count. The bytes-up-to-first-non-zero still
  match — divergence begins on the first voiced sample.

### Pre-fix vs post-fix sample counts (post-#97/#102/#120 vs #58)

| # | Prompt | C samp | Py #58 | Δ #58 | Py post-fix | Δ post | Net change |
|---|---|---:|---:|---:|---:|---:|---:|
| 0 | `hello world` | 13845 | 10670 | -3175 | 26840 | +12995 | +16170 |
| 1 | `the quick brown fox` | 19809 | 18260 | -1549 | 35750 | +15941 | +17490 |
| 2 | `she sells sea shells` | 20093 | 17050 | -3043 | 37510 | +17417 | +20460 |
| 3 | `one two three four five` | 22933 | 18920 | -4013 | 39710 | +16777 | +20790 |
| 4 | `supercalifragilisticexpialidocious` | 31169 | 44000 | +12831 | 58520 | +27351 | +14520 |
| 5 | `[:rate 250] testing one two three` | 14697 | 34540 | +19843 | 23210 | +8513 | **-11330** |
| 6 | `DECtalk version 6.2.0` | 32660 | 15730 | -16930 | 28710 | -3950 | **-12980** |
| 7 | `this is a test, with a comma, and a period.` | 34932 | 40150 | +5218 | 64240 | +29308 | +24090 |
| 8 | `the answer is 42` | 21300 | 23540 | +2240 | 36850 | +15550 | +13310 |
| 9 | `3 point 14` | 18602 | 16830 | -1772 | 31460 | +12858 | +14630 |
| 10 | `one hundred and one dalmatians` | 24140 | 27500 | +3360 | 45320 | +21180 | +17820 |
| 11 | `1234567890` | 74905 | 76780 | +1875 | 113960 | +39055 | +37180 |
| 12 | `hello! how are you?` | 25702 | 16170 | -9532 | 31240 | +5538 | -4070 |
| 13 | `wait... what just happened?` | 26909 | 22880 | -4029 | 39710 | +12801 | +16830 |
| 14 | `yes; no; maybe.` | 21442 | 17930 | -3512 | 32230 | +10788 | +14300 |

Three prompts net-improved (sign-flipped from under-run to small
over-run): `[:rate 250]` (PR #67 fixed inline command leakage),
`DECtalk version 6.2.0` (smaller |Δ| now), and `hello! how are
you?` (smaller |Δ|). The other 12 prompts grew |Δ| by ~12-37 K
samples (1.1-3.4 s) each. The largest absolute regression is
`1234567890` (+37 180 samp = 3.4 s of extra audio).

### Lead / content / trail decomposition

| # | Prompt | Δ samp | Δ lead | Δ content | Δ trail | C trail | Py trail |
|---|---|---:|---:|---:|---:|---:|---:|
| 0 | `hello world` | +12995 | +830 | +8183 | +3982 | 3972 | 7954 |
| 1 | `the quick brown fox` | +15941 | +1341 | +6295 | +8305 | 4302 | 12607 |
| 2 | `she sells sea shells` | +17417 | +3128 | +6152 | +8137 | 3860 | 11997 |
| 3 | `one two three four five` | +16777 | +1203 | +10916 | +4658 | 3960 | 8618 |
| 4 | `supercalifragilisticexpialidocious` | +27351 | +3555 | +19490 | +4306 | 4302 | 8608 |
| 5 | `[:rate 250] testing one two three` | +8513 | +1270 | +6336 | +907 | 2492 | 3399 |
| 6 | `DECtalk version 6.2.0` | -3950 | +1941 | -10153 | +4262 | 3880 | 8142 |
| 7 | `this is a test, with a comma, and a period.` | +29308 | +1341 | +22324 | +5643 | 3894 | 9537 |
| 8 | `the answer is 42` | +15550 | +1341 | +9925 | +4284 | 3964 | 8248 |
| 9 | `3 point 14` | +12858 | +2235 | +6280 | +4343 | 3902 | 8245 |
| 10 | `one hundred and one dalmatians` | +21180 | +1203 | +11930 | +8047 | 3915 | 11962 |
| 11 | `1234567890` | +39055 | +1203 | +33877 | +3975 | 3985 | 7960 |
| 12 | `hello! how are you?` | +5538 | +830 | -854 | +5562 | 3959 | 9521 |
| 13 | `wait... what just happened?` | +12801 | +1225 | +5987 | +5589 | 3981 | 9570 |
| 14 | `yes; no; maybe.` | +10788 | +1222 | +4102 | +5464 | 4002 | 9466 |

**Aggregate contribution** (sum of absolute deltas across 15
prompts):

- Σ|Δlead|    = 23 868 samples (9.0 %)
- Σ|Δcontent| = 162 804 samples (61.6 %)
- Σ|Δtrail|   = 77 464 samples (29.3 %)

Sign-summed: ΣΔlead = +23 868, ΣΔcontent = +140 790, ΣΔtrail =
+77 464. Every component is positive — Python is uniformly
over-long in every envelope segment.

### Remaining gap ranked by sample-distance contribution

Rank by |Δsamples| and split into trail-dominant vs content-dominant:

| Rank | # | Prompt | |Δsamp| | dominant |
|---|---|---|---:|---|
| 1 | 11 | `1234567890` | 39055 | content (+33877) |
| 2 | 7 | `this is a test, with a comma, and a period.` | 29308 | content (+22324) |
| 3 | 4 | `supercalifragilisticexpialidocious` | 27351 | content (+19490) |
| 4 | 10 | `one hundred and one dalmatians` | 21180 | content (+11930) |
| 5 | 2 | `she sells sea shells` | 17417 | **trail** (+8137) |
| 6 | 3 | `one two three four five` | 16777 | content (+10916) |
| 7 | 1 | `the quick brown fox` | 15941 | **trail** (+8305) |
| 8 | 8 | `the answer is 42` | 15550 | content (+9925) |
| 9 | 0 | `hello world` | 12995 | content (+8183) |
| 10 | 9 | `3 point 14` | 12858 | content (+6280) |
| 11 | 13 | `wait... what just happened?` | 12801 | mixed (Δt+5589, Δc+5987) |
| 12 | 14 | `yes; no; maybe.` | 10788 | **trail** (+5464) |
| 13 | 5 | `[:rate 250] testing one two three` | 8513 | content (+6336) |
| 14 | 12 | `hello! how are you?` | 5538 | **trail** (+5562) |
| 15 | 6 | `DECtalk version 6.2.0` | 3950 | content (-10153) |

Two long-tail categories account for ~91 % of the remaining gap:

1. **Content over-run** (Σ|Δcontent| = 162 804 samp, **61.6 %**).
   `us_phtiming`'s per-allophone durations are 1.4-2× the C
   reference on every prompt. Captured via monkey-patch on
   `us_phtiming` exit:

   | Prompt | C samp | Py allodurs sum (frames × 110) | ratio |
   |---|---:|---:|---:|
   | `hello world` | 13 845 | 238 × 110 = 26 180 | 1.89 × |
   | `she sells sea shells` | 20 093 | 341 × 110 = 37 510 | 1.87 × |
   | `supercalifragilisticexpialidocious` | 31 169 | 532 × 110 = 58 520 | 1.88 × |
   | `this is a test...` | 34 932 | 572 × 110 = 62 920 | 1.80 × |
   | `1234567890` | 74 905 | 1036 × 110 = 113 960 | 1.52 × |
   | `DECtalk version 6.2.0` | 32 660 | 261 × 110 = 28 710 | 0.88 × |

   The 1.5-1.9× ratio is too consistent to be a single bug in a
   specific rule — it points at the **base duration LUT** that
   `us_phtiming` reads (`us_featb` or the per-allophone
   `start_dur` / `end_dur` columns from `p_us_st1.c`) being scaled
   wrong, or a missing per-allophone `gettar` divisor that the C
   source applies. `DECtalk version 6.2.0` is the only prompt
   that's *under*-running on content — and it's the prompt that
   exercises the abbreviation-spell-out path heavily, suggesting
   the front-end emits a different (shorter) phoneme stream there.

2. **Trailing-silence over-pad** (Σ|Δtrail| = 77 464 samp,
   **29.3 %**). `us_phtiming` Rule 1 fires correctly on every
   sentence-final prompt (good — PR #102 closed the original
   drop-out), but the resulting `allodurs[last]` is **84 frames
   on every prompt** (~838 ms). The C reference produces ~36
   frames (~360 ms) on every sentence-final prompt. The Python
   computation: `dpause = nfperiod(94) + perpause(0) +
   asperation(-10 = MIN_ASP_PERIOD) = 84`, then `mlsh1(84,
   sprat1)` is applied. With `sprate=180`, `sprat1` is at Q12
   unity (4096) so `mlsh1` is the identity. The C side ends up
   at ~36 frames, so **the constant 84 ÷ 36 ≈ 2.33× discrepancy
   matches the content-duration ratio above** — strongly
   suggesting the duration-scaling factor in `us_phtiming` /
   `init_timing` is fundamentally a ~2× error against C, not a
   ruleset divergence. `[:rate 250]` is the one prompt where
   `sprat1 < 4096` (rate scaling reduces it), and there
   `allodurs[last] = 22` matches C's 22 — confirming the
   *scaling formula* is correct but the *base* sprate→sprat1
   mapping is off by ~2× at the default 180 WPM.

3. **Leading-frame offset** (Σ|Δlead| = 23 868 samp, 9.0 %). Python
   adds ~830-3555 leading samples to every prompt. The first-diff
   index still matches C, so the leading-zero bytes match
   bit-exactly — the offset comes from one or more *extra silent
   frames* injected before the first voiced sample. The Δ scales
   roughly with content length (longer prompts have more leading
   pad, because `Δlead` here is really "more silent frames before
   the first voiced output", correlating with the content-duration
   inflation).

### Three concrete fix proposals

The top three opportunities, ranked by **(a)** expected Δsample
recovery and **(b)** independence — each can be dispatched in
parallel.

#### Proposal #1 — Audit `us_phtiming` / `init_timing` duration scaling

**Where**: `src/dectalk/ph/us_phtiming.py` + `src/dectalk/ph/init_timing.py`.

**Symptom**: Per-allophone durations are systematically **1.4-1.9×**
the C reference on every prompt in the corpus (Σ|Δcontent| =
162 804 samp = 61.6 % of the total gap). The 2.33× factor on the
trailing-silence default (84 vs 36 frames) is the same scaling
error in concentrated form — it has no per-allophone variation, so
it must come from the speaking-rate path, not the per-phone
duration LUT.

**Why**: `init_timing` builds `sprat0` / `sprat1` / `sprat2` from
the `sprate` field (default 180 WPM). The C source's formula
applies a non-trivial shift (`mlsh1` quantisation) that the Python
port may have inherited at the wrong precision. Concrete evidence:

- With `sprate=180`, Python computes `sprat1 = 4096` (Q12 unity),
  so `mlsh1(84, 4096) = 84` — the trailing pause does not shrink.
- With `sprate=250` (via `[:rate 250]`), `sprat1` shrinks
  proportionally and `allodurs[last]` becomes 22 frames — which
  **matches C exactly**. So the rate-scaling pathway is correct;
  only the baseline `sprate→sprat1` mapping is off.
- The same 1.9× over-shoot affects every duration in the per-allophone
  table — exactly what you'd expect if the base `sprat1` were ~2×
  too high.

Investigation steps before filing the fix:

1. Patch the C source under `tests/parity/c_patches/` to printf
   `sprat0`, `sprat1`, `sprat2` after `init_timing`'s setup call
   in `p_us_tim.c` (line 140 region).
2. Run `say -a 'hello world' -fo` and compare to Python's
   `init_timing` output.
3. The discrepancy will likely point at either a wrong `sprate→sprat1`
   formula in `init_timing.py` or a missing Q12 scaling division.

**Fix sketch**: depends on the C-side trace. Two leading candidates:

- `init_timing` is missing a `>> 1` somewhere on the `sprate=180`
  path that the C source applies (e.g. `sprat1 = (4096 * 180 /
  base_wpm) >> 1` if the C source uses a Q11 internal representation
  but the Python port assumes Q12).
- The `frame_counts.py` `NF*MS` constants are off by 2× (e.g.
  frames-per-millisecond conversion is wrong); inspect alongside.

**Expected parity recovery**: if the duration scaling is corrected
to halve all per-allophone durations on default-rate prompts, the
content over-run shrinks proportionally. A 2× correction recovers
~80 K samples of content over-run (50 % of Σ|Δcontent|), plus
~48 K of trail (84-frame → ~36-frame trailing SIL). **~128 K of
the ~264 K total absolute gap** — the highest-yield fix in the
corpus.

**Issue label sketch**: `area/ph`, `size/medium` (needs C-source
parity-patch infrastructure, but the fix itself is plausibly
small).

**Acceptance criteria**:

- For `hello world`, sum(`allodurs`) drops from 238 frames toward
  ~126 frames (C reference's frame count).
- `allodurs[last]` on every sentence-final prompt drops from 84
  toward 36 frames.
- 15-prompt mean |Δsamp| drops below 8000 samples (from current
  16 668).
- `[:rate 250]` `allodurs[last]` stays at 22 frames (already
  matches C).

#### Proposal #2 — Replace `_arpabet_to_us_allophone` ARPABET mapping with `phalloph2`'s richer code path

**Where**: `src/dectalk/api/speak.py` lines 199-281
(`_arpabet_to_us_allophone` helper).

**Symptom**: Five of the 15 prompts (`hello world` Δcontent +8183,
`one two three four five` +10916, `the answer is 42` +9925,
`3 point 14` +6280, and `[:rate 250]` +6336) have content
over-runs that are too large to be explained by duration scaling
alone (Proposal #1 would still leave 4-6 K samples of residual).
The `phalloph2` chain DOES run (PR #97 wired it), but
`_render_clause_full` still feeds it `arpabet_words` produced by
the bare `_arpabet_to_us_allophone` helper — which lacks the
diphthong-splitting, stress-marker insertion, and onset-cluster
collapsing that `make_out_phonol` performs *inside* the chain.

**Why**: The chain's input is an ARPABET phone stream. The C source's
input is a richer DECtalk-native symbol stream that includes
syllable-internal stress markers (S1, S2), phrase-boundary tokens
(WBOUND, PERIOD, QUEST), and diphthong-segment markers (the LUT
`phalloph2` consumes). `_build_symbols_from_arpabet` (called at
speak.py line 525) projects the ARPABET stream into the symbol
encoding but doesn't inject the diphthong / coarticulation markers
the chain expects. The result: `phalloph2` writes a longer
`allophons[]` than the C source would produce for the same input,
and `us_phtiming` then assigns per-allophone durations to phones
that should have been collapsed into diphthongs.

Concrete: `hello world` post-#97 has 10 allophons. The C source's
internal chain produces 7 (one fewer per dropped diphthong:
`OW` → single allophone, not `OW + W`-onset; `ER` → single
allophone, not `EH + R`-coda).

**Fix sketch**:

1. Audit `_build_symbols_from_arpabet` against `ph_task.c` lines
   437-510 (the C-source ARPABET→symbol encoder). Add diphthong
   segment markers and onset-cluster collapsing.
2. Alternatively: bypass the ARPABET intermediate entirely by
   wiring the LTS / dictionary outputs as **DECtalk-native phone
   codes** directly. The dictionary already has DECtalk codes
   for known words; the LTS module would need a similar code-emit
   path.

**Expected parity recovery**: after Proposal #1 lands, this would
trim a further ~30-50 K samples from Σ|Δcontent| (the residual
beyond the 2× scaling), bringing the corpus mean |Δ| below
~5000 samples.

**Issue label sketch**: `area/api`, `area/ph`, `size/medium`.

**Acceptance criteria**:

- `hello world` post-`phalloph2` `nallotot` drops from 10 to ~7-8
  (matching C-source allophone count).
- Σ|Δcontent| drops below 60 000 samples (from current 162 804).
- No prompt regresses in either content count or audio quality.

#### Proposal #3 — Audit `_render_clause_full` leading-frame budget

**Where**: `src/dectalk/api/speak.py` lines 449-525 + `init_phclause` +
the per-frame loop entry conditions.

**Symptom**: Python's first non-zero sample is consistently ~830-3555
samples (~7.5-32 frames) further into the buffer than C's. The
`first_diff` index matches C exactly, so the **leading-zero bytes
themselves match** — what's growing is the latency between the end
of leading silence and the first voiced output. Lead correlates
weakly with prompt content length (`Δlead` is `+830` for short
prompts like `hello world`, `+3555` for long ones like
`supercalifragilisticexpialidocious`), suggesting the extra latency
is **per-allophone**, not a one-time silence pad.

**Why**: Two candidate sources:

- `init_phclause` may inject a clause-leading silence pad
  (introduced by PR #74) that fires unconditionally rather than
  only between clauses. In single-clause prompts (all 15 in the
  corpus) the pad has no preceding clause to flush, so the pad is
  dead weight.
- The `phalloph2` chain may emit an extra `GEN_SIL` at clause
  start (a duplicate of the explicit leading sentinel) — needs
  inspection of `_build_symbols_from_arpabet` and the chain's
  exit state.

**Fix sketch**: 

1. Print `nallotot`, `allophons[0]`, `allodurs[0]` immediately
   after the `phalloph2` call and compare to the C oracle's
   equivalent printf patch.
2. If the chain emits 2 leading SILs (one from `_build_symbols`,
   one from the chain itself), drop the manual sentinel.
3. If `init_phclause`'s ending-pad is firing at clause-start, gate
   it on a "previous clause exists" flag.

**Expected parity recovery**: ~23 868 samples (~9 % of total gap).
Smaller win than #1 or #2 in absolute terms, but cleanly
separates lead-frame counting from content-frame counting — once
fixed, `Δlead` becomes a regression-test floor for the other two
fixes.

**Issue label sketch**: `area/ph`, `size/small`.

**Acceptance criteria**:

- `Δlead` is ≤ ±220 samples (~2 frames) on every prompt in the
  15-prompt sample.
- No regression in `first_diff` (the leading-zero bytes must
  continue to match C).
- A unit test asserts `init_phclause`'s ending-pad behaviour on
  first-call vs subsequent-call.

### Honourable mentions

- **`DECtalk version 6.2.0` is the only under-running prompt**
  (Δcontent = -10153). The leading silence for this prompt is
  852 samples (vs the typical 213), confirming the C side
  triggers extra front-end work (abbreviation expansion +
  decimal-number parsing for "six point two point zero"). Python
  emits a shorter phoneme stream here. Fixing the
  abbreviation/numeric expansion in the front-end would close this
  gap but might also produce more spelled-out / read-out content,
  shifting this prompt's |Δ| upward before driving it back down
  via Proposals #1/#2.
- **`hello world` content over-run almost quadrupled post-#97**
  (+8183 today vs the original audit's -3175 short-by). The phone
  stream now has all 7 phonemes (HH, AH, L, OW, W, ER, L, D),
  but `us_phtiming` over-shoots their durations. This is the
  cleanest illustration of how PR #97's correct phalloph2 wiring
  exposed an unrelated duration-scaling bug.
- **`[:rate 250] testing one two three` is the only prompt where
  `allodurs[last] = 22 frames matches C**. The same prompt now
  has |Δsamp| = +8513 vs the original audit's +19843. PR #67's
  inline-command parsing fixed the original gap; the remaining
  +8513 is the same duration-scaling bug as the rest of the
  corpus, but reduced ~2× by the WPM=250 scaling. This is direct
  evidence that the scaling formula is correct only above some
  WPM threshold; at the default 180 WPM the formula or its inputs
  are wrong.
- **Approximate path mean |Δ| = 4020 vs full-pipeline 16 668**.
  The legacy approximate path is now closer to the C reference
  than the full pipeline. This is a temporary inversion until the
  duration / leading-frame fixes land; the full pipeline remains
  the strategic target because it has the correct *shape* (it
  emits ~all C phones, the approximate path drops many) — it just
  emits them too slowly.
- **Σ Δ across the 15-prompt corpus = +242 122 samples (~22 s
  total over-run vs 380 s of C output)**. The full pipeline is
  uniformly ~5.8 % too long; closing that ratio is the gating
  metric for Phase E bit-parity work.

### Reproducer

```bash
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh

# Sample-count / envelope diagnostic (replicates the per-prompt table):
REPO_ROOT=$(pwd) DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/parity_diag_15.py 15

# Lead / content / trail breakdown:
REPO_ROOT=$(pwd) DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/parity_diag_breakdown.py 15

# Allophone-duration trace (post-us_phtiming):
REPO_ROOT=$(pwd) DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/trace_allodurs.py
```

The diagnostic scripts (`parity_diag_15.py`,
`parity_diag_breakdown.py`, `trace_allodurs.py`) live in `/tmp/`
to keep this audit a doc-only PR; their content is embedded
verbatim in the body of follow-up Proposals #1-#3 when filed.

Authored-by: Claude:claude-opus-4-7

## Update 2026-05-23 v3 (post-#197 / #195 / #196 / #194 + ~40 merged PRs)

Re-run of the 15-prompt parity diagnostic on dev head `920cada` after
the post-v2 PR wave: form-class disambiguation (#197), Spdefs voice
threading (#195), vtm1 wiring (#196), compound markers (#194), per-
frame OUT_T0 test (#180), per-stage parity tests (#183), expanded
corpus +58 prompts (#182), IX/AX/AH schwa distinction (#185), partial
leading-frame bleed (#190), GEN_SIL prepend removal (#184), LTS
palatalisation / Latinate stress / OUGH / initial-cluster
(#178/179/175/181), LTS vowel mispredictions (#188), non-US
special_coartic (#186), VTM dump hooks (#191), ARPABET schwa /
syllabic-R refinement (#192), FAKE_HLSYN audit + 3 phdraw bug fixes
(#187), abbreviation policy (#174), F4/B4/F5/B5 SpdChip threading
(#177), lexicon re-source w/ form-class (#189).

The headline finding from v2 ("flat-monotone F0") is **closed** — the
per-frame `OUT_T0` std on `hello world` has grown from **5 Hz (v2)**
to **149 Hz (v3)**, even slightly above C's 83 Hz dynamic range. The
F0 intonation engine is now alive: 7-9 events per prompt
(vs 2-5 in v2), including Rule 1 STEP hat-rise events at 80 Hz
and Rule 3/4 GLIDE hat-falls. Proposals G + H from the F0 follow-up
have effectively landed.

The dominant remaining gap has shifted to **per-allophone duration
over-scaling** (Proposal #1 from v2 — still open), now compounded by
two new regressions: a shrunk leading-silence prefix and an enlarged
trailing-silence pad.

### Method

Same as v2. `DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1` against
the C oracle. For each prompt: sample-count delta, first-differing
sample index, lead/content/trail envelope, L2/sample, peak-abs error.
Monkey-patched `us_phtiming` (allodurs capture), `phinton` (F0
event capture), and `pht0draw` (per-frame `parstochip[OUT_T0]`).

### Per-prompt divergence (full pipeline, 2026-05-23 v3, post-#197)

| # | Prompt | C samp | Py samp | Δ samp | Δ ms | first_diff | L2/s | max_abs_err |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | `hello world` | 13845 | 22880 | +9035 | +820 | 2 | 6940 | 40128 |
| 1 | `the quick brown fox` | 19809 | 30470 | +10661 | +967 | 3 | 5833 | 37996 |
| 2 | `she sells sea shells` | 20093 | 33990 | +13897 | +1260 | 213 | 5261 | 29564 |
| 3 | `one two three four five` | 22933 | 35750 | +12817 | +1163 | 2 | 6753 | 35837 |
| 4 | `supercalifragilisticexpialidocious` | 31169 | 49610 | +18441 | +1673 | 213 | 2993 | 16914 |
| 5 | `[:rate 250] testing one two three` | 14697 | 21230 | +6533 | +593 | 710 | 5024 | 24119 |
| 6 | `DECtalk version 6.2.0` | 32660 | 24750 | -7910 | -717 | 57 | 4908 | 27102 |
| 7 | `this is a test, with a comma, and a period.` | 34932 | 55990 | +21058 | +1910 | 3 | 4058 | 27264 |
| 8 | `the answer is 42` | 21300 | 34100 | +12800 | +1161 | 3 | 5078 | 29288 |
| 9 | `3 point 14` | 18602 | 29370 | +10768 | +977 | 213 | 5939 | 34916 |
| 10 | `one hundred and one dalmatians` | 24140 | 40920 | +16780 | +1522 | 2 | 3931 | 26445 |
| 11 | `1234567890` | 74905 | 109670 | +34765 | +3153 | 2 | 5162 | 34538 |
| 12 | `hello! how are you?` | 25702 | 25740 | +38 | +3 | 2 | 6084 | 39035 |
| 13 | `wait... what just happened?` | 26909 | 37730 | +10821 | +981 | 2 | 4467 | 33852 |
| 14 | `yes; no; maybe.` | 21442 | 29920 | +8478 | +769 | 1 | 5783 | 28304 |

**Headline numbers.**

- 0/15 prompts match bit-exactly (unchanged from v2 — the goal of
  `test_binary_wav_parity.py` is still not met).
- Sign mostly over-running (14/15); `DECtalk version 6.2.0` is the
  one under-runner (-7910 samp, an under-running of front-end
  abbreviation/number expansion). `hello! how are you?` is +38
  samp ≈ within 3 ms — by coincidence the Py over-run cancels the
  trailing pad.
- Mean |Δsamp| = **12 987 samples (~1178 ms)**, down from v2's
  **16 668 (~1512 ms)** — a **~22 % improvement** at the sample-
  count level even though no prompt matches yet.
- L2/sample of 3000-7000 vs C-rms of 2200-5400 — the per-sample
  noise still dominates the signal magnitude (i.e. waveform shape
  diverges, not just timing).
- `first_diff_idx` is now mostly **1-3 samples** (was always
  ≥213 in v2). The C reference still emits 213 leading-zero
  samples; the Python output emits voiced signal at sample 2. This
  is a **new regression** vs v2 — the leading-silence prefix has
  been over-trimmed (see §"Leading silence regression" below).

### Lead / content / trail decomposition (v3)

| # | Prompt | Δ samp | Δ lead | Δ content | Δ trail | C trail | Py trail |
|---|---|---:|---:|---:|---:|---:|---:|
| 0 | `hello world` | +9035 | -211 | +6495 | +2751 | 3972 | 6723 |
| 1 | `the quick brown fox` | +10661 | -210 | +3342 | +7529 | 4302 | 11831 |
| 2 | `she sells sea shells` | +13897 | +1219 | +5764 | +6914 | 3860 | 10774 |
| 3 | `one two three four five` | +12817 | -346 | +9412 | +3751 | 3960 | 7711 |
| 4 | `supercalifragilisticexpialidocious` | +18441 | +1327 | +11644 | +5470 | 4302 | 9772 |
| 5 | `[:rate 250] testing one two three` | +6533 | +390 | +5765 | +378 | 2492 | 2870 |
| 6 | `DECtalk version 6.2.0` | -7910 | -795 | -10105 | +2990 | 3880 | 6870 |
| 7 | `this is a test, with a comma, and a period.` | +21058 | -210 | +16916 | +4352 | 3894 | 8246 |
| 8 | `the answer is 42` | +12800 | -210 | +10160 | +2850 | 3964 | 6814 |
| 9 | `3 point 14` | +10768 | +511 | +7224 | +3033 | 3902 | 6935 |
| 10 | `one hundred and one dalmatians` | +16780 | -346 | +10252 | +6874 | 3915 | 10789 |
| 11 | `1234567890` | +34765 | -346 | +32479 | +2632 | 3985 | 6617 |
| 12 | `hello! how are you?` | +38 | -211 | -4267 | +4516 | 3959 | 8475 |
| 13 | `wait... what just happened?` | +10821 | -324 | +6767 | +4378 | 3981 | 8359 |
| 14 | `yes; no; maybe.` | +8478 | -328 | +4669 | +4137 | 4002 | 8139 |

**Aggregate contribution** (sum of |Δ| across 15 prompts):

- Σ|Δlead|    = 6 984 samples (3.6 %) — much smaller share than v2's 23 868 (9.0 %)
- Σ|Δcontent| = 145 261 samples (74.6 %) — up from v2's 61.6 % share
- Σ|Δtrail|   = 62 555 samples (32.1 %) — slightly down from v2's 29.3 %

Sign-summed: ΣΔlead = **-90** (was +23 868 in v2; sign **flipped**),
ΣΔcontent = +116 517 (was +140 790), ΣΔtrail = +62 555 (was
+77 464).

### Per-allophone duration scaling (the dominant remaining gap)

Captured via monkey-patch on `us_phtiming` exit:

| Prompt | C samp | Py Σdurs×110 | ratio (Py/C) | last allodur | Py-trail-pad samp |
|---|---:|---:|---:|---:|---:|
| `hello world` | 13 845 | 22 330 | 1.61× | 72 | 7 920 |
| `the quick brown fox` | 19 809 | 30 580 | 1.54× | 72 | 7 920 |
| `she sells sea shells` | 20 093 | 34 100 | 1.70× | 72 | 7 920 |
| `one two three four five` | 22 933 | 35 860 | 1.56× | 72 | 7 920 |
| `supercalifragilisticexpialidocious` | 31 169 | 49 720 | 1.60× | 72 | 7 920 |
| `[:rate 250] testing one two three` | 14 697 | 21 340 | 1.45× | **39** | 4 290 |
| `DECtalk version 6.2.0` | 32 660 | 24 860 | 0.76× | 72 | 7 920 |
| `this is a test...` | 34 932 | 54 780 | 1.57× | 72 | 7 920 |
| `the answer is 42` | 21 300 | 34 210 | 1.61× | 72 | 7 920 |
| `3 point 14` | 18 602 | 29 480 | 1.58× | 72 | 7 920 |
| `one hundred and one dalmatians` | 24 140 | 41 030 | 1.70× | 72 | 7 920 |
| `1234567890` | 74 905 | 109 780 | 1.47× | 72 | 7 920 |
| `hello! how are you?` | 25 702 | 25 850 | 1.01× | 72 | 7 920 |
| `wait... what just happened?` | 26 909 | 36 520 | 1.36× | 72 | 7 920 |
| `yes; no; maybe.` | 21 442 | 30 030 | 1.40× | 72 | 7 920 |

**Default-rate ratio range: 1.36-1.70×** (down from v2's 1.52-1.89×
— some narrowing). Content-only ratio (excluding the 72-frame
trailing pad, against C's ~36-frame trail removed too) sits at
**1.43-1.64×** on the canonical prompts. Outliers `DECtalk version
6.2.0` (0.76×) and `hello! how are you?` (1.01×) signal front-end
expansion mismatches, not duration scaling.

The trailing pad has changed: was **84 frames** in v2 → now
**72 frames** (-12 frames). C reference: ~36 frames. So the trail
overshoot shrank ~13 % but is still ~2× C.

**`[:rate 250]` regressed.** In v2 the last allodur was 22 frames
(matched C). In v3 it is **39 frames** (no longer matches). Some
PR in the post-v2 wave changed how trailing-pad scaling interacts
with sprate. This is small in absolute samples but is the
single regression in the trailing-pad story.

### F0 contour — closed

Per-frame `OUT_T0` measured by monkey-patching `pht0draw`:

| Prompt | nframes | mean Hz×10 | std Hz×10 | min | max |
|---|---:|---:|---:|---:|---:|
| `hello world`         | 209 | 790 | **149** | 592 | 1008 |
| `the quick brown fox` | 278 | 786 | **143** | 564 |  977 |

v2 audit recorded `std=5` for both prompts — the contour was a flat
line at f0minimum. v3 std=143-149 (i.e. 14-15 Hz of real F0
modulation around 79 Hz baseline) is in line with — actually slightly
above — C oracle's autocorrelation-estimated 60-83 Hz dynamic range.
The `phinton` rule-firing trace for `hello world` shows 7 events:
1 IMPULSE (Rule 2 stress), 2 STEP (Rule 1 hat-rise / Rule 4
hat-fall STEP), 1 type-5 (probably GLOTTAL or new Rule 5), and 3
trailing STEP/F0_RESET. For `the quick brown fox`: 9 events with
4 STEPs at 73/47/43/-61 Hz targets. The flat-monotone v2 finding is
closed.

`allofeats` for `hello world` now shows `FHAT_BEGINS` (`0x1`) and
`FHAT_ENDS` (`0x100` for FPERNEXT, `0x900` for the boundary mix) at
the right allophones; the v2 "no FHAT bits" diagnostic confirms
Issue G has landed.

### Leading silence regression (new in v3)

Captured first non-zero sample index per prompt:

| Prompt | C lead (zeros) | Py lead (zeros) | Δ |
|---|---:|---:|---:|
| `hello world` | 213 | 2 | -211 |
| `the quick brown fox` | 213 | 3 | -210 |
| `she sells sea shells` | 213 | 1432 | +1219 (clause-leading still pads) |
| `one two three four five` | 348 | 2 | -346 |
| `1234567890` | 348 | 2 | -346 |

`hello world` first samples now: `[0, 0, 1, 3, 7, 13, 22, 35, 51, 70, 92, 117, ...]`
(immediate ramp-in from zero), while C oracle stays at zero through
sample 212 then opens with the same ramp shape. Issue #157
(leading-frame bleed PR #190) over-trimmed the leading-silence pad
to the point where the C oracle's 213-sample (≈19 ms) leading
silence is no longer matched. Most prompts now have **~213 fewer
leading samples than C**.

This is small per-prompt (~211 samples ≈ 19 ms) but consistent
across 12/15 prompts and was correctly handled by v2.

### Phinton + F0 events (verification that intonation works)

Captured `phinton`-exit state for `hello world`:

```
nallotot=10
allophons (hex): ['0x1e1c', '0x1e11', '0x1e1b', '0x1e0b', '0x1e18',
                  '0x1e0f', '0x1e1e', '0x1e30', '0x1e11', '0x1e00']
allofeats (hex): ['0x4', '0x8', '0x1', '0x279', '0x5', '0x501',
                  '0x100', '0x100', '0x900', '0x100']
number_words=3
nf0tot=7
  event[0]: IMPULSE  tar= 18  tim=29  len= 5    (Rule 2 stress impulse)
  event[1]: STEP     tar= 80  tim=23  len=30    (Rule 1 HAT-RISE — fires!)
  event[2]: STEP     tar= 50  tim=26  len=29    (Rule 1 second hat)
  event[3]: type5    tar=-293 tim=18  len=38    (GLOTTAL / Rule 5 — type 5 not in original table)
  event[4]: STEP     tar= -8  tim=13  len=20
  event[5]: STEP     tar= -8  tim=13  len=20
  event[6]: STEP     tar= -8  tim= 9  len=20
```

The `tar=80` Rule 1 STEP is exactly the hat-rise plateau the v2
audit identified as missing — it now fires. (Note: `nallotot=10` here
includes the dummy schwa `phinton` inserts at the trailing GEN_SIL;
the `us_phtiming` pre-phinton snapshot showed `nallotot=9`.)

### Top 3 next-action items (ranked by sample-distance contribution)

#### #1 — Per-allophone duration scaling: the **1.43-1.64×** content over-run

**Where**: `src/dectalk/ph/us_phtiming.py` + `src/dectalk/ph/init_timing.py`
(unchanged from v2's Proposal #1).

**Symptom**: Per-allophone durations at default rate sit at
**1.43-1.64×** the C reference on every prompt. Σ|Δcontent| =
**145 261 samples (74.6 %)** of the v3 gap. The 1.64× / 1.70×
worst-case prompts have no obvious distinguishing feature — the
scaling factor is roughly constant within ±10 % across 13 of 15
prompts (the two outliers being abbreviation-rich `DECtalk version
6.2.0` and `hello! how are you?`).

The trailing-pad of **72 frames** (vs C's ~36) is the same
~2× scaling error in concentrated form: with `dpause = nfperiod(94)
+ perpause(0) + asperation(-22) = 72`, then `mlsh1(72, sprat1)` at
default rate gives 72 (no shrink). Why 72 not 84 (v2): some
post-v2 PR (#192 ARPABET schwa-refinement? #189 lexicon re-source?)
changed the asperation default from -10 to -22, shaving 12 frames
off the pad but not addressing the underlying scaling.

**Investigation path** (unchanged from v2 Proposal #1):
1. Patch the C source under `tests/parity/c_patches/` to printf
   `sprat0`, `sprat1`, `sprat2` after `init_timing` in
   `p_us_tim.c` (line 140 region).
2. Compare with Python's `init_timing` output at default sprate=180.
3. The mismatch should point at either a wrong `sprate→sprat1`
   formula or a missing Q12-to-Q11 divide.

**Expected parity recovery**: ~110 K samples (40-50 % of the total
gap). Highest-yield single fix available. Acceptance criteria from
v2 still apply.

**Issue label sketch**: `area/ph`, `size/medium`.

#### #2 — `DECtalk version 6.2.0` front-end under-run (and `hello!` over-fit)

**Where**: front-end abbreviation / numeric-expansion path
(`src/dectalk/cmd/` or `src/dectalk/dic/`).

**Symptom**: `DECtalk version 6.2.0` is the only prompt where Python
*under*-runs (Δsamp = -7910, Δcontent = -10 105) and the ratio
inverts to **0.76×**. The C oracle's 296-frame output contains
about 12 spoken "words" (DEC, talk, version, six, point, two,
point, zero) plus liaisons; Python's 11-allophone phoneme stream
suggests fewer words being expanded. `hello! how are you?` content
ratio is 1.01× (essentially equal to C) only because the front-end
emits a *similar* phoneme count for this short prompt — but the
phones themselves are wrong, yielding the L2/sample = 6084 (highest
in the corpus).

**Why**: PR #174 (abbreviation policy) and #189 (lexicon re-source)
changed how multi-component tokens like "DECtalk" are split. Likely
the "DECtalk" abbreviation is now being spelled as a single lexicon
entry instead of as D-E-C-talk letter-spell. Similarly the "6.2.0"
version-string parser may be reading "six twenty" rather than "six
point two point zero".

**Investigation path**:
1. Capture C-oracle ARPABET stream for the two prompts (patch
   `p_lts.c` printf, or read from the `phalloph2` dump hooks added
   by #191).
2. Diff against the Python ARPABET stream from
   `_render_clause_full`.
3. The fix is likely a one-line lexicon override or an
   abbreviation-detection-rule tweak.

**Expected parity recovery**: ~10-20 K samples on the two outlier
prompts. Won't move the corpus mean much, but closes the only
under-running prompt and isolates Proposal #1's effect (which is
masked by the under-runner pulling Σ|Δ| downward).

**Issue label sketch**: `area/cmd`, `area/dic`, `size/small`.

#### #3 — Leading-silence regression: PR #190 over-trimmed the prefix

**Where**: `src/dectalk/api/speak.py` first-frame-consumed logic
(introduced by #190, lines 800-825).

**Symptom**: C oracle emits **213-348 zero samples** before the
first voiced sample. Python now emits **1-3 zero samples**, then
ramps directly into the voiced signal. Affects 12 of 15 prompts,
each costing ~211-346 samples (-19 to -32 ms). Total contribution:
~3 700 samples × 12 prompts ≈ -4 100 samples (small in absolute
terms — Σ|Δlead| is 6 984 samples = 3.6 %).

**Why**: PR #190 (leading-frame bleed partial fix) consumes the
first synthesizer frame on every clause to model `ph_claus.c`'s
`delaypars[]` initialization. But the C oracle keeps **two** silent
Klatt frames (213 samples = ~1.93 frames) before the first
non-zero output — likely the `init_phclause` ending-silence (#74)
plus the `delaypars` first frame combined. Python's `init_phclause`
pad either fires later or has been consumed by #190.

**Investigation path**:
1. C-oracle trace: patch `ph_claus.c::send_pars` to printf its
   frame index on each call to `spcwrite`, and compare to Python's
   per-frame trace.
2. The fix is likely to preserve **one** leading silent frame
   (not zero) — either by NOT consuming the first frame on the
   first clause, or by adding an explicit 1-2-frame silent prefix
   before the per-frame loop.

**Expected parity recovery**: ~4 100 samples in lead (Σ|Δlead|
drops toward ~600 ≈ ±42 samples residual). Per-prompt
`first_diff` moves back from sample 2 toward sample 213+ — meaning
the leading-zero bytes match byte-for-byte again, which is a
regression-test floor for #1 and #2.

**Issue label sketch**: `area/ph`, `size/small`. Cleanest of the
three; smallest yield but most likely to land quickly.

### Other notable changes since v2

- **F0 contour: closed.** v2's Proposals G + H were the dominant
  qualitative complaint; they have effectively landed (whether via
  the named issues or via the cumulative effect of #195 / #186 /
  #192). OUT_T0 std on `hello world` grew from 5 → 149 Hz.
- **Trailing pad shrunk 84 → 72 frames** (~13 %). Still ~2× C's
  ~36 frames. The shrink correlates with #192 (ARPABET schwa /
  syllabic-R refinement) or #185 (IX/AX/AH schwa distinction)
  changing `asperation` defaults — investigate which PR.
- **`[:rate 250]` trailing pad regressed** (22 frames in v2 →
  39 frames in v3). The previously-matching prompt no longer
  matches C. Small absolute regression but worth noting because it
  argues the underlying duration-scaling formula is *not* sprate-
  invariant the way v2 inferred.
- **Mean |Δsamp| improved 22 %** (16 668 → 12 987). Most prompts
  shrank by 2-7 K samples. `1234567890` improved 4 K samples
  (39 055 → 34 765), still the worst-case prompt.
- **`hello world` improved 31 %** (12 995 → 9 035 samp). It would
  improve another ~50 % if Proposal #1 lands; ~6 % more from
  Proposal #3.
- **`approximate path` parity vs full pipeline**: not re-measured;
  v2 had approximate path closer to C than the full pipeline. Worth
  re-measuring in v4 once Proposal #1 lands — the full pipeline
  should regain the parity-test lead.

### Reproducer

```bash
export AGENT_SLUG=audit-2026-05-23-v3
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh

# 15-prompt sample-count + envelope diagnostic:
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/parity_diag_v3.py

# Allodurs trace (per-prompt frame counts):
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/trace_allodurs_v3.py

# Per-frame OUT_T0 + phinton-event capture:
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python /tmp/f0_trace_v3.py
```

Scripts live in `/tmp/` to keep this audit a doc-only PR; their
content is embedded in the body of follow-up issues if any of
Proposals #1-#3 above are filed for dispatch.

Authored-by: Claude:claude-opus-4-7

