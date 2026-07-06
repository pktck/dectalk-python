# Implementation status

A live snapshot of what's shipped vs. what's still in the
`docs/PLAN.md` blueprint. The plan is the long-term roadmap; this
file tracks actual progress on `dev`.

## Session handoff — read first

**Current `dev` HEAD**: `da81603` — *docs: F0 contour re-audit on
dev head c829010 (issue #75)*.

The workflow overhaul (merged 2026-05-16) is well in the rear-view
mirror; ~30 additional PRs landed in the 2026-05-21/22 burst,
including the per-language `gettar` dispatch heads (UK/FR/GR/LA/SP),
the `phdraw` once-per-phone setup, the inline-command routing fix,
the `[:rate N]` WPM semantics correction, and a wave of diagnostic
audit docs that catalogue every remaining gap to bit-parity. The
repository operates under the issue-driven agent-dispatch protocol
documented in `CLAUDE.md`; every new port has a corresponding GitHub
issue.

### Phase E (PH/VTM) — active work

The pure-Python `_speak_via_python_full` path runs end-to-end:
`parse()` → `phinton` (intonation) → `us_phtiming` (allophone
durations) → `phsettar` (target areas) → `phdraw` (per-frame Klatt
parameter emission) → `parstochip` → `LLFrame` → `hlsyn`. Trailing
silence is now padded by `api/speak.py`. The pipeline produces
non-flat audio with F0 events, but bit-parity vs `libtts_us.so` is
**not yet reached** — the F0 contour re-audit at the bottom of
`docs/parity-divergence-audit.md` (#75, 2026-05-22) measures
`OUT_T0` std at 5-6 Hz vs C oracle 60-83 Hz and traces the gap to
`us_phalloph` not being wired into the full pipeline (Issue G /
#121) and `pDph_t.assertiveness` defaulting to zero (Issue H /
#122).

Major Phase E ports landed (in rough order):

- **`ph_setar.c` dispatch chain**: `gettar` → `us_gettar` →
  `getbegtar` / `getendtar` / `make_dip` / `setloc` / `phsettar`,
  plus the `us_forw_smooth_rules` / `us_back_smooth_rules` /
  `us_special_rules` / `us_special_coartic` smoothing layer and
  the `tarnex` coarticulation block. Non-US locus tables ported.
  Per-language `gettar` dispatch heads **all landed**: `uk_gettar`
  (#106, issue #78), `fr_gettar` (#104, #82), `gr_gettar` (#111,
  #79), `la_gettar` (#112, #80), `sp_gettar` (#110, #81).
- **`ph_sort.c`**: `all_phsort` + `fr_phsort` (commit `7cda308`)
  and wiring into `_speak_via_python_full` + HR/SR scalar load
  (#105 / `909c5ff`).
- **`ph_inton.c`**: full `phinton` US English path (~2080-line C
  function); the `goto skiprules` Rule-9 semantics were corrected
  in #76, Rule 4 nesting bug fixed in #56.
- **`ph_setallofeats`** stop-gap: `allofeats[]` is derived from
  the ARPABET front-end (#66) so `phinton` emits Rule 2 stress
  impulses and Rule 6 final-fall gestures. Rules 1 / 3 / 4 (the
  hat-rise/fall STEP/GLIDE plateau) still don't fire because
  `us_phalloph` isn't wired — see Issue #121.
- **`ph_timng.c`**: `us_phtiming` (per-allophone duration rules)
  and `init_timing` wiring.
- **`ph_draw.c`**: skeleton, HLSyn area loop, initial-silence
  anticipation (lines 929-1244, `1713f9e`), GEN_SIL ending
  silence + regular-phoneme `dcstep` tracker (#61, `1e93aca`),
  per-frame HLSyn state machine (lines 2350-4300), lateral AV
  reduction + F3/F2 floor, once-per-phone setup + FVOWEL
  A2-jamming (#92, issue #71).
- **`ph_drwt02.c`**: `pht0draw` MALE F0 contour generator and
  FEMALE branch (lines 1508-2167).
- **`ph_alloph.c`**: `us_phalloph` (ENGLISH_US allophonic
  substitution pass) **ported but not yet called** from
  `_speak_via_python_full`; wiring tracked as issue #121.
- **HLSyn front-end**: `circuit.c` (`SpeechCircuit` aerodynamic
  solver), `hlframe.c` (HL → LL mapper + `InitializeHLSynthesizer`),
  `nasalf1x.c` (`SetNasals_f1x` nasal pole-zero solver).
- **VTM**: US-Paul `SPD_CHIP` defaults and `VtmT NOM_*` fields.
- **CMD**: `par_match_rule` + `par_process_input` (closes #38);
  `[:rate N]` semantics corrected to absolute WPM rather than
  percentage (#109, `f9d05f4`).

Wiring + adapters:

- `api/speak.py` routes `_speak_via_python_full` through `parse()`
  so inline `[:rate N]` / `[:nb]` directives mutate per-segment
  state instead of being spelled out as words (#67, issue #64);
  emits a trailing-silence pad on the full-pipeline path (#102,
  issue #72).
- `parstochip` → `LLFrame` adapter + per-frame driver loop landed
  (#25); seeds `DphT.fnscale` to 4096 (Q12 unity).
- `lineartilt` LUT + `send_pars` one-frame delay buffer ported.
- `ARPABET → USPhoneme` alias gap fixed (#65); the FONIX enum
  names `HX`/`LL`/`NX` map to `HH`/`L`/`NG`, recovering the
  ~38% of phones previously dropped on common inputs.

### Outstanding `NotImplementedError` shims (7 modules)

`grep -rln "raise NotImplementedError" src/dectalk/` lists only
seven real shims; the earlier list also included files whose only
remaining `NotImplementedError` mention sits in a docstring rather
than a `raise` (now cleared from `ph/all_phsort.py`,
`ph/fr_phsort.py`, `ph/phdraw.py`, and `hlsyn/hlframe.py`):

- `src/dectalk/api/speak.py` (architectural; full Python path
  exists but the shim guards a code path not yet active by
  default).
- `src/dectalk/cmd/par_match_rule.py`,
  `src/dectalk/cmd/par_process_input.py` (residual shims after
  #47 — verify whether the C-faithful path is reachable).
- `src/dectalk/ph/gettar.py`, `getbegtar.py`, `getendtar.py`,
  `make_dip.py` (legacy dispatch heads superseded by the
  `us_gettar` chain but kept as parity test anchors).

`docs/TASKS.md` is regenerated from this set by
`scripts/refresh_tasks.py` and currently matches.

### Audit issues filed against current `dev`

Doc-only diagnostic audits landed in this burst (each is a
fix-target source for subsequent ports):

- **#74 — `init_phclause` defaults vs C oracle** (#77, audit
  embedded in commit `fbd679d`).
- **#75 — F0 contour follow-up + 2026-05-22 re-audit** (#93
  `6a88f29`; #120 `da81603`). Identifies #121 + #122 as the
  next two PH-stage fixes needed to close the F0 dynamic-range
  gap.
- **#83 — VTM-stage divergence vs C oracle** (#103, audit doc
  `docs/vtm-divergence-audit.md`).
- **#84 — `KsdT` defaults vs C oracle** (#100).
- **#85 — `SpdChip` US-Paul voice defaults vs C** (#107
  `1442919`).
- **#86 — Frame-level Klatt parameter parity audit** (#108,
  `docs/frame-parity-audit-issue86.md`).
- **#87 — `parstochip` HL → Klatt frame translator** (#98,
  `docs/c_audit/parstochip.md`).
- **#89 — LTS divergences vs C oracle** (#99,
  `docs/c_audit/lts.md`).
- **#90 — kernel text-normalization vs C oracle** (#101,
  `docs/c_audit/kernel_textnorm.md`).
- **#91 — verify `hlsyn` frame parity hasn't regressed** (#95,
  `docs/hlsyn-parity-verification-issue91.md`).

Open follow-up port issues filed from the F0 re-audit:

- **#121** — Wire `us_phalloph` into `_speak_via_python_full` so
  FHAT_BEGINS / FHAT_ENDS are emitted from stress patterns.
- **#122** — Load `pDph_t.assertiveness` from the SPD chip so
  Rule 6 final-fall gestures carry non-zero magnitude.

### Suggested next steps for a fresh session

1. Land **#121** (wire `us_phalloph`) — it's the single highest-
   leverage Phase E gap. The Python port already exists; the
   patch is a few lines in `api/speak.py:_render_clause_full`
   between `all_phsort` and `ph_setallofeats`.
2. Then **#122** (assertiveness load) — small, but Issue G's
   FHAT bits unmask the zero-magnitude bug in Rule 6.
3. Pick an open audit issue's fix-target (e.g. the `KsdT` /
   `SpdChip` mismatches identified in #84 / #85) — these are
   short, scoped, and each closes a measurable parity gap.
4. Or pick a residual `NotImplementedError` shim from the list
   above; the `cmd/` shims are the most ambiguous (verify
   reachability before porting).
5. Follow the issue-driven dispatch protocol in `CLAUDE.md`:
   create a GitHub issue (or reuse an existing one), branch
   `claude/<slug>-issue-<N>`, agent prompt cites the issue
   number, PR body has `Closes #N`.
6. After every push: subscribe to the PR via
   `mcp__github__subscribe_pr_activity` and kick off a
   background poll for green CI. See `CLAUDE.md` §"CI watch".

## Project goalpost: pure-Python bit parity

The project goal is **byte-identical WAV output between
`dectalk.to_wav(text)` (pure Python, no native dependency at runtime)
and the shipped `say` binary**. The stop-hook gate runs
`tests/parity/test_binary_wav_parity.py` with
`DECTALK_DISABLE_CAPI=1` set, which forces the public API through the
Python pipeline (`kernel` → `cmd` → `lts` → `ph` → `vtm` → `hlsyn`)
instead of `dectalk._capi`'s ctypes wrapper around `libtts_us.so`.

Under `DECTALK_DISABLE_CAPI=1` + `DECTALK_FULL_PIPELINE=1` the
pipeline runs end-to-end and renders through the `vtm1.c`-ported
`speech_waveform_generator` by default (issue #272) — the same
synthesiser the shipped `libtts_us.so` uses. This is the
byte-exact-capable parity path: on `hello world` the default render
is sample-count-exact vs the C binary (13845 == C), F0 is
frame-exact, and the leading 213 samples are byte-identical. Full
byte-parity across the corpus is **not yet reached** — the
2026-05-27 500-prompt audit at the end of
`docs/parity-divergence-audit.md` measured 0/500 bit-exact, and the
remaining gap is body-content divergence, not envelope/length.
Setting `DECTALK_USE_VTM1=0` restores the legacy hlsyn render — it
over-runs the C reference uniformly (`hello world`: 21450 vs 13845
samples) and is retained only as a diagnostic escape hatch after
causing the #254 misdiagnosis. (History: the PR #60 baseline
measured 0/15 corpus prompts at bit-parity with mean |Δsamples| ≈
5856 (~531 ms); the 2026-05-22 F0 re-audit identified #121 /
#122, both since landed.)

The `_capi` path remains the **hybrid** state: `dectalk.speak()`
and `dectalk.to_wav()` go through the C library for bit-identical
audio when `libtts_us.so` is available, and fall back to the
approximate-or-faithful Python pipeline when it isn't. CI uses the
hybrid path for `tests/parity/`; the stop-hook gate uses pure
Python so the loop keeps porting until the pure-Python path
matches.

Stage-boundary milestones reached:

- **LTS + dic phoneme stream**: `dectalk.text_to_dectalk_phonemes`
  produces byte-identical output to `CAPI.convert_to_phonemes`
  across **130000+ bit-parity corpus prompts** spanning
  sentence-initial stress, function-word destressing (a/and/to/for),
  plural / -s / -ed / -ing / -ness / -ful / -less / -ment / -er /
  -est / -ly / -ive / -tion / -sion / -ify stem stripping with
  Y→I alternation and LTS-fallback for stems missing from the
  bundled lex, n't contractions, syllabic-L/N rules (incl.
  word-final-T/-D context), AH0 reduction with sonorant/sibilant
  context-gates for word-final S/T/N/K/Z/D/V/SH/P/F contexts plus
  the -fy / -sify suffix family, IH0 reduction before NG and K,
  AH0+N+T → IX after sonorant/sibilant prev, -ent/-ant / -iful /
  -ous / -tion morphology, M-in-cluster sonorant for AH0+S,
  dotted-decimal and digit-string expansion with C-faithful commas
  / AND / OR-vowel for digit-only forms, sibilant-final plural
  IX+Z epenthesis, possessive 's IX+Z variant, hyphenated #
  marker, teen MBOUND `*` markers, title abbreviation overrides,
  WH-question intonation, first-verbs sentence-initial S2 stress,
  curated VPSTART verb list of ~200 pure verbs (-ate / -ize /
  -ify families), default spell-out (every letter
  primary-stressed) with FBI-style destressed-middle exceptions,
  and dynamic spell-out via `ls_spel_say_it`. The gate test
  `tests/parity/test_python_phonemes_vs_c_parity.py` enforces
  this with strict passes (no xfail). LTS audit (#89) and kernel
  audit (#90) are open to verify edge-case coverage.

Path to pure-Python bit parity (per the plan):

- **Phase A.4** (DONE): per-stage intermediate dump hooks are
  installed. `CAPI.dump_pipeline` exposes `kernel` (0002 patch),
  `cmd` (0003), `ph` (0004), and `vtm` (0005). Each writes a
  text dump (`<stage>_write <count>` + hex words) when
  `DECTALK_DUMP_DIR` is set.
- **Module-inventory gate** (DONE): every module-inventory test
  (`api`/`cmd`/`dic`/`hlsyn`/`kernel`/`lts`/`ph`/`vtm`) carries an
  empty `_DEFERRED` dict. The Python ports surface every
  Linux-active C entry point under its original name. When a new
  Python module lands, removing the corresponding `_DEFERRED`
  entry is part of the acceptance checklist (see
  `docs/PORTING.md`).
- **Phase C** (kernel + cmd): faithful translations of US English
  text normalisation and the command-table parser. Audit #90
  pending.
- **Phase D** (lts + dic): faithful translation of the
  rule-driven letter-to-sound engine + the bundled
  `dtalk_us.dic` dictionary. Stage-boundary parity (phoneme
  stream) is reached; engine-internal parity (LTS rule-trace)
  audit #89 pending.
- **Phase E** (ph + vtm): the prosody / intonation engine and
  the vocal tract model that drives the (already bit-accurate)
  `hlsyn` Klatt synthesiser. *In active development — most of
  the recent dev commits live here.*
- **Phase F**: rewrite the public API + remove the `_capi`
  scaffold.

## Hybrid-path state (the "approximate" port — built pre-goalpost)

Everything below describes the approximate-Python pipeline that
predates the bit-parity goalpost. It is intelligible-but-divergent
speech, kept as the runtime fallback when `_capi` is unavailable.
Phases C-F replace each layer with a faithful translation.

### Phase 0 — Scaffolding (DONE)
- `pyproject.toml` with strict Ruff (Google docstrings) + pyright strict + pytest.
- `src/dectalk/` mirrors the C source layout (`api/cmd/kernel/lts/ph/dic/vtm/hlsyn/nt/include`).
- `nt/audio.py` — WAV writer/reader + `sounddevice` playback at 11025 Hz.
- `include/dectalk.py` — `Voice` enum, `Seq` / `Pparse` dataclasses, debug flags translated from `dectalk.h`.
- CLI with `--play-test`, `--write-test`, `--vowel`, `--phonemes`, `--voice`, `--lang`, `--rate`, `--lexicon`, `--sing`.
- GitHub Actions CI matrix (Linux/macOS/Windows × Py 3.11/3.12/3.13).
- pre-commit hooks + `scripts/dev_check.sh`.

### Phase 1 — Klatt synthesizer (DONE)
- `hlsyn/reson.py` — pole/zero-pair second-order resonator (per-sample + vectorized via scipy `lfilter`).
- `hlsyn/synth.py` — `Synthesizer` running state, `Coefficients`, A_AV..A_ATV constants, ParamIdx/SpeakerIdx/OutputIdx enums.
- `hlsyn/llsyn.py` — `Speaker`, `LLFrame`, `LLSynth` with all 23 resonators.
- `hlsyn/voice.py` — voicing-source generator (impulse / KLGLOT88 / LF model).
- `hlsyn/sample.py` — per-sample cascade-parallel mixing.
- `hlsyn/synthesize.py` — `ll_synthesize()` (= C `LLSynthesize`).
- `hlsyn/init.py` — `ll_init()` (= C `LLInit`); resets state, clears resonators, seeds noise from `spkr.RS`.
- `hlsyn/vowels.py` — Klatt-1980 reference vowel frames.
- HLSyn front-end (`hlframe.c`, `circuit.c`, `nasalf1x.c`) ported in
  Phase E so the back-end can be driven from anatomical parameters
  as well as direct formant controls.
- **Verified bit-exact (within 1 LSB) against the FONIX C** for 17 frame configurations covering vowels, source-shape variants, aspiration, frication, F0 sweep, spectral tilt, OQ extremes, diplophonia, and F1 transitions. Re-verify task tracked as issue #91.

### Phase 2 — US English text pipeline (DONE)
- `dic/lexicon.py` + `data/lexicon_us_full.txt` — bundled full DECtalk dictionary, 15054 entries.
- `dic/dectalk_phonemes.py` — DECtalk phonemic ASCII → ARPABET converter (US table).
- `dic/__init__.py` — `lookup()` with lazy-cached lexicon load + optional `set_extra_lexicon()` for CMUDict integration.
- `kernel/text.py` — tokenizer with hyphen splitting, currency prefix handling, sentence/clause pause classification.
- `kernel/numbers.py` — `number_to_words()` for integers up to 10**12.
- `lts/rules_us.py` — ~75 rule-based English letter-to-sound rules with stress-digit annotation.
- `ph/phoneme_frames.py` — phoneme → Klatt frame mapping.
- `ph/sequencer.py` — phoneme-stream → frame-stream → audio with linear interpolation between targets.
- `api/speak.py` — `speak()` / `to_wav()` / `text_to_phonemes()` public API.

### Phase 3 — Voices + commands + numbers (DONE)
- `data/voices.py` — 9 canonical DECtalk voices (Paul/Betty/Harry/Frank/Dennis/Kit/Ursula/Rita/Willy).
- `cmd/commands.py` — inline `[:cmd value]` parser supporting `[:dv]`, `[:rate]`, `[:phoneme on/off]`, plus stubs for `[:ap]`, `[:pr]`, `[:hs]`, `[:sm]`, `[:emph]`, `[:say]`.
- `kernel/numbers.py` — number-to-words.

### Phase 4 — UK English (DONE)
- `data/lexicon_uk_full.txt` — bundled full DECtalk UK dictionary, 18173 entries.
- `data/lexicon_uk.txt` — small RP overrides retained as fallback layer.
- `lookup()` and `speak()` accept a `lang="us"|"uk"` keyword.

### Phase 5 — Romance + Germanic languages (DONE)
- `dic/dectalk_phonemes_multi.py` — per-language DECtalk → ARPABET converter for SP/LA/FR/DE.
- `data/lexicon_sp_full.txt` (616 entries), `lexicon_la_full.txt` (617), `lexicon_fr_full.txt` (1213), `lexicon_de_full.txt` (8 — DECtalk's German is rule-based with a tiny exception list; this is the actual source data).
- `lang="us"|"uk"|"sp"|"la"|"fr"|"de"` selectable via `speak()`, `to_wav()`, `text_to_phonemes()`, and the CLI `--lang` flag.
- **Quality caveat**: the Klatt phoneme→frame table in `ph/phoneme_frames.py` is calibrated for English. Non-English audio is intelligible but the phoneme-inventory extensions (French nasal vowels, German front rounded vowels) are approximated to the nearest English ARPABET symbol rather than fully modeled. Improving this needs language-specific frame tables.

### Phase 6 — Polish (DONE)
- `ph/prosody.py` — sentence-level F0 declination + per-phoneme stress accent; question contour for `?`-terminated segments.
- `ph/singing.py` + `api/sing.py` — singing mode parsing `PHONEME<duration_ms,tone_number>` syntax. Tone 1 = A2 = 110 Hz, +1 per chromatic semitone.
- Soft-limiter pass in the sequencer prevents int16 saturation on `/S/`-heavy clusters.
- `tests/parity/` — **C-LLSynthesize parity** (17 frame configs, ≤4 LSB or ≤2% relative tolerance) and **end-to-end binary parity** (5 phrases compared against the DECtalk 4.61 Linux binary release).
- `tests/unit/test_integration.py` — end-to-end tests covering voices, commands, UK vs US, intonation, LTS fallback, numbers.

## Performance

Measured on a single machine running `dectalk.speak()`:

| Workload | Audio | Wall | Realtime ratio |
|---|---|---|---|
| Raw `ll_synthesize` (10 s) | 10.0 s | 0.84 s | 11.8× |
| Full pipeline (~40-word paragraph) | 6.6 s | 0.61 s | 10.8× |

Synthesizing 1 s of speech costs ~85 ms; the front end adds ~5 ms per
word for tokenization + lexicon lookup + LTS fallback.

The `perf-bench` CI job specified in `docs/PLAN-CI-STRATEGY.md` §7
remains deferred — tracked as issue #3.

## Test counts

The unit + integration + parity tree contains tens of thousands of
tests (~21K reported pre-Phase-E; the bit-parity corpus alone
contributes ~130K strict-pass prompts that exercise
`tests/parity/test_python_phonemes_vs_c_parity.py` per-prompt).
Run `uv run pytest -n auto --collect-only -q | tail -1` for the
exact current count.

- ruff lint: clean.
- ruff format: clean.
- pyright strict: clean.
- shellcheck on `scripts/`: clean.
- CI matrix: Linux/macOS/Windows × Py 3.11/3.12/3.13.

## Pending (deferred / out of scope for the original port; in scope for Phase E)

### Per-language Klatt frame tables
Phase 5 ships the DECtalk dictionaries for FR/DE/SP/LA, but the
approximate pipeline uses the English-tuned Klatt frame table for
synthesis. Native-quality non-English speech needs language-specific
phoneme→formant tables (nasal vowel formants for French,
front-rounded vowel formants for German, etc.). The per-language
locus tables (`gr_locus_tables`, `fr_locus_tables`, …) and the
matching `*_gettar` dispatch heads (`uk_gettar` / `fr_gettar` /
`gr_gettar` / `la_gettar` / `sp_gettar`, issues #78-#82) are all
ported as part of the Phase E `ph_setar` chain. What's still
needed is the language-specific phoneme → Klatt frame table on
top of those locus tables.

## How to run

```bash
uv sync
uv run python -m dectalk "hello world"
uv run python -m dectalk --voice harry "[:rate 80] greetings, human" -o harry.wav
uv run python -m dectalk --lang uk "tomato"
uv run python -m dectalk --sing "HH<200,5> AH<200,7> L<200,8> OW<400,9>"
scripts/dev_check.sh   # full quality gate
```
