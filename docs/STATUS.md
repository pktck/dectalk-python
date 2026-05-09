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
- CLI with `--play-test`, `--write-test`, `--vowel`, `--phonemes`, `--voice`, `--lang`, `--rate`.
- GitHub Actions CI matrix (Linux/macOS/Windows × Py 3.11/3.12/3.13).
- pre-commit hooks + `scripts/dev_check.sh`.

### Phase 1 — Klatt synthesizer (DONE)
- `hlsyn/reson.py` — pole/zero-pair second-order resonator (per-sample + vectorized via scipy `lfilter`).
- `hlsyn/synth.py` — `Synthesizer` running state, `Coefficients`, A_AV..A_ATV constants, ParamIdx/SpeakerIdx/OutputIdx enums.
- `hlsyn/llsyn.py` — `Speaker`, `LLFrame`, `LLSynth` with all 23 resonators.
- `hlsyn/voice.py` — voicing-source generator (impulse / KLGLOT88 / LF model).
- `hlsyn/sample.py` — per-sample cascade-parallel mixing.
- `hlsyn/synthesize.py` — `ll_synthesize()` (= C `LLSynthesize`).
- `hlsyn/vowels.py` — Klatt-1980 reference vowel frames.
- Verified: `/ah/` synthesis spectrum has peaks at F1=737 Hz / F2=1103 Hz (targets 730 / 1090).

### Phase 2 — US English text pipeline (DONE)
- `dic/lexicon.py` + `data/lexicon_us_full.txt` — bundled full DECtalk dictionary, 15054 entries, generated from the FONIX source via `scripts/build_full_lexicon.py`.
- `dic/dectalk_phonemes.py` — DECtalk phonemic ASCII → ARPABET converter.
- `data/lexicon_us.txt` — small (~290 entry) starter lexicon retained as fallback when the full file isn't present.
- `dic/__init__.py` — `lookup()` with lazy-cached lexicon load.
- `kernel/text.py` — tokenizer with hyphen splitting, currency prefix handling, sentence/clause pause classification.
- `kernel/numbers.py` — `number_to_words()` for integers up to 10**12.
- `lts/rules_us.py` — ~75 rule-based English letter-to-sound rules with stress-digit annotation.
- `ph/phoneme_frames.py` — phoneme → Klatt frame mapping.
- `ph/sequencer.py` — phoneme-stream → frame-stream → audio with linear interpolation between targets.
- `api/speak.py` — `speak()` / `to_wav()` / `text_to_phonemes()` public API.

### Phase 3 — Voices + commands (DONE)
- `data/voices.py` — 9 canonical DECtalk voices (Paul/Betty/Harry/Frank/Dennis/Kit/Ursula/Rita/Willy).
- `cmd/commands.py` — inline `[:cmd value]` parser supporting `[:dv]`, `[:rate]`, `[:phoneme on/off]`, plus stubs for `[:ap]`, `[:pr]`, `[:hs]`, `[:sm]`, `[:emph]`, `[:say]`.
- `speak()` parses commands and applies them per-segment so voice/rate can switch mid-utterance.

### Phase 4 — UK English (DONE)
- `data/lexicon_uk_full.txt` — bundled full DECtalk UK dictionary, 18173 entries, generated from the FONIX source.
- `data/lexicon_uk.txt` — small RP overrides retained as fallback.
- `lookup()` and `speak()` accept a `lang="us"|"uk"` keyword.

### Phase 6 partial — Polish (DONE / partial)
- `ph/prosody.py` — sentence-level F0 declination + per-phoneme stress accent; question contour for `?`-terminated segments.
- Soft-limiter pass in the sequencer prevents int16 saturation on `/S/`-heavy clusters.
- `tests/unit/test_integration.py` — 9 end-to-end tests covering voices, commands, UK vs US, intonation, LTS fallback, numbers.

## Pending

### Phase 5 — Romance + Germanic languages (NOT STARTED)
The DECtalk source ships dictionaries for French, German, Spanish (Castilian), and Latin American Spanish, but they use language-specific extensions to the phoneme alphabet (nasal vowels, front rounded vowels, German `/x ç/`, and others) that our US-tuned converter and Klatt phoneme→frame table don't yet handle. Bundling the raw dictionaries would produce garbled output. Proper multi-language support needs:
- Extended phoneme inventory in `include/phonemes.py` for each language's distinct sounds.
- Per-language entries in `dic/dectalk_phonemes.py` for character → phoneme mapping.
- New `_VOWEL_FORMANTS` / `_CONSONANT_FRAMES` entries in `ph/phoneme_frames.py`.
- Language-aware LTS rules (or none, relying on the dictionary).

### Phase 6 remaining — Line-by-line C parity (PARTIAL)
The `hlsyn/` Klatt module is line-by-line ported. The front-end modules (`dic`, `lts`, `ph`, `kernel`, `cmd`) are clean Python implementations rather than literal C ports. The HLSyn high-level circuit (`circuit.c`, `hlframe.c`, `inithl.c` — anatomical-parameter vocoder) is not ported because the Klatt-direct path already produces audio. Singing mode and full DECtalk parity testing also remain.

## Test counts

- 172 unit + integration tests passing
- ruff lint: clean
- ruff format: clean
- pyright strict: clean (one suppressed warning for scipy missing stubs)
- shellcheck on `scripts/`: clean
- CI matrix: Linux/macOS/Windows × Py 3.11/3.12/3.13

## How to run

```bash
uv sync
uv run python -m dectalk "hello world"
uv run python -m dectalk "[:dv harry] greetings, human" -o harry.wav
scripts/dev_check.sh   # full quality gate
```
