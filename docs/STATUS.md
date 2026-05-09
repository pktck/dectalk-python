# Implementation status

A live snapshot of what's shipped vs. what's still in the original
`docs/PLAN.md`. The plan is the long-term blueprint; this file tracks
actual progress.

## Shipped

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

- 236 unit + integration + parity tests passing (210 unit, 18 LLSynthesize parity, 5 binary parity, 3 LLFrame structure / multi-language).
- ruff lint: clean (with two narrow `# noqa` suppressions for justified Unicode and lazy-import patterns).
- ruff format: clean.
- pyright strict: clean (one suppressed warning for scipy missing stubs).
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
