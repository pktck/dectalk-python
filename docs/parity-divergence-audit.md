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
