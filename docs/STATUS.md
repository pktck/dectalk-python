# Implementation status

A live snapshot of what's shipped vs. what's still in the
`/root/.claude/plans/create-a-python-port-smooth-hoare.md` plan. The
plan is the long-term blueprint; this file tracks actual progress.

## Project goalpost: pure-Python bit parity

The project goal is **byte-identical WAV output between
`dectalk.to_wav(text)` (pure Python, no native dependency at runtime)
and the shipped `say` binary**. The stop-hook gate runs
`tests/parity/test_binary_wav_parity.py` with
`DECTALK_DISABLE_CAPI=1` set, which forces the public API through the
Python pipeline (`kernel` -> `cmd` -> `lts` -> `ph` -> `vtm` -> `hlsyn`)
instead of `dectalk._capi`'s ctypes wrapper around `libtts_us.so`.

Today the verifier reports **33/33 prompts diverge** under
`DECTALK_DISABLE_CAPI=1`. The existing Python pipeline (the
"approximate" implementation under Phases 0-6 below) was built before
the bit-parity goal was set; it diverges from the binary at every
stage starting with text normalisation. The `_capi` path is the
**hybrid** state: `dectalk.speak()` and `dectalk.to_wav()` go through
the C library for bit-identical audio when the .so is available, and
fall back to the approximate pipeline when it isn't. CI uses the
hybrid path (33/33 pass); the stop-hook gate uses pure Python (0/33
pass) so the loop keeps porting until the pure-Python path matches.

Stage-boundary milestones reached so far:

- **LTS+dic phoneme stream**: ``dectalk.text_to_dectalk_phonemes``
  produces byte-identical output to ``CAPI.convert_to_phonemes``
  across **3700+ bit-parity corpus prompts** spanning sentence-initial
  stress, function-word destressing (a/and/to/for), plural / -s /
  -ed / -ing / -ness / -ful / -less / -ment / -er / -est / -ly /
  -ive / -tion / -sion / -ify stem stripping with Y->I alternation
  and LTS-fallback for stems missing from the bundled lex,
  n't contractions, syllabic-L/N rules (incl. word-final-T/-D
  context), AH0 reduction with sonorant/sibilant context-gates for
  word-final S/T/N/K/Z/D/V/SH/P/F contexts plus the -fy / -sify
  suffix family (AH0+F/AH0+S+F before stressed AY -> IX),
  IH0 reduction before NG and K, AH0+N+T -> IX after sonorant/
  sibilant prev (with vowel+R vs cluster+R discrimination),
  -ent/-ant / -iful / -ous / -tion morphology, M-in-cluster
  sonorant for AH0+S, dotted-decimal and digit-string expansion
  with C-faithful commas / AND / OR-vowel for digit-only forms,
  sibilant-final plural IX+Z epenthesis, possessive 's IX+Z
  variant, hyphenated # marker, teen MBOUND ``*`` markers, title
  abbreviation overrides, WH-question intonation, first-verbs
  sentence-initial S2 stress, curated VPSTART verb list of ~200
  pure verbs (including -ate / -ize / -ify families), default
  spell-out path (every letter primary-stressed) with FBI-style
  destressed-middle exceptions, and dynamic spell-out via
  ``ls_spel_say_it``. The gate test
  ``tests/parity/test_python_phonemes_vs_c_parity.py`` enforces
  this with strict passes (no xfail).

Path to pure-Python bit parity (per the plan):

- **Phase A.4** (next): patch the C source to emit per-stage
  intermediate dumps so each future port has a stage-boundary oracle.
  `convert_to_phonemes` already gives us the LTS+dic boundary; the
  PH input and VTM input boundaries still need hooks.
- **Phase C** (kernel + cmd): faithful translations of US English
  text normalisation and the command-table parser.
- **Phase D** (lts + dic): faithful translation of the rule-driven
  letter-to-sound engine + the bundled `dtalk_us.dic` dictionary.
  Stage-boundary parity (phoneme stream) is reached; engine-internal
  parity (LTS rule-trace) still pending.
- **Phase E** (ph + vtm): the prosody / intonation engine and the
  vocal tract model that drives the (already bit-accurate) `hlsyn`
  Klatt synthesiser.
- **Phase F**: rewrite the public API + remove the `_capi` scaffold.

Until those phases land the Python output will keep diverging. This
section will track the gap as phases close.

## Hybrid-path state (the "approximate" port — built pre-goalpost)

Everything below describes the approximate-Python pipeline that
predates the bit-parity goalpost. It is intelligible-but-divergent
speech, kept as the runtime fallback when ``_capi`` is unavailable.
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
- **Verified bit-exact (within 1 LSB) against the FONIX C** for 17 frame configurations covering vowels, source-shape variants, aspiration, frication, F0 sweep, spectral tilt, OQ extremes, diplophonia, and F1 transitions.

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
- `tests/unit/test_integration.py` — 9 end-to-end tests covering voices, commands, UK vs US, intonation, LTS fallback, numbers.

## Performance

Measured on a single machine running `dectalk.speak()`:

| Workload | Audio | Wall | Realtime ratio |
|---|---|---|---|
| Raw `ll_synthesize` (10 s) | 10.0 s | 0.84 s | 11.8× |
| Full pipeline (~40-word paragraph) | 6.6 s | 0.61 s | 10.8× |

Synthesizing 1 s of speech costs ~85 ms; the front end adds ~5 ms per
word for tokenization + lexicon lookup + LTS fallback.

## Test counts

- 21543 unit + integration + parity tests passing.
- ruff lint: clean.
- ruff format: clean.
- pyright strict: clean.
- shellcheck on `scripts/`: clean.
- CI matrix: Linux/macOS/Windows × Py 3.11/3.12/3.13.

## Pending (deferred / out of scope)

### HLSyn high-level circuit
The C source includes a parallel "HLSyn" layer (`circuit.c`, `hlframe.c`,
`inithl.c`, `nasalf1x.c`, `brent.c`, `acxf1c.c`) that drives the Klatt
synth from anatomical parameters (vocal-tract areas, lung pressure)
rather than direct formant controls. Our pipeline goes phoneme → Klatt
frame directly, so this layer is unused. Translating it line-by-line
would add a parallel API but no audio improvement.

### Per-language Klatt frame tables
Phase 5 ships the DECtalk dictionaries for FR/DE/SP/LA, but uses the
English-tuned Klatt frame table for synthesis. Native-quality
non-English speech needs language-specific phoneme→formant tables
(nasal vowel formants for French, front-rounded vowel formants for
German, etc.).

## How to run

```bash
uv sync
uv run python -m dectalk "hello world"
uv run python -m dectalk --voice harry "[:rate 80] greetings, human" -o harry.wav
uv run python -m dectalk --lang uk "tomato"
uv run python -m dectalk --sing "HH<200,5> AH<200,7> L<200,8> OW<400,9>"
scripts/dev_check.sh   # full quality gate
```
