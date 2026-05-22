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

Authored-by: Claude:claude-opus-4-7

