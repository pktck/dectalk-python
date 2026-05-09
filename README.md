# dectalk-python

Cross-platform Python port of DECtalk text-to-speech.

Pure-Python with NumPy / SciPy / sounddevice — no compiled binaries to build,
all dependencies install from prebuilt wheels.

## Quick start

```bash
uv sync

# Speak text directly
uv run python -m dectalk "hello world"

# Save to a WAV file
uv run python -m dectalk "the quick brown fox" -o fox.wav

# Pick a voice
uv run python -m dectalk "greetings, human" --voice harry

# Inline DECtalk commands work too
uv run python -m dectalk "[:dv betty][:rate 80] hello again"

# Direct phoneme input (ARPABET)
uv run python -m dectalk --phonemes "HH AH L OW"
```

## Library API

```python
import dectalk

# Simple text -> samples
samples = dectalk.speak("hello world")
dectalk.write_wav(samples, "hello.wav")

# Voices and rate
samples = dectalk.speak("hello", voice="betty", rate=0.8)

# UK English lexicon (drops rhotic /r/, knows "colour", "dance", ...)
dectalk.to_wav("colour, dance, theatre", "uk.wav", lang="uk")

# ARPABET phoneme synthesis
samples = dectalk.synthesize_phonemes(["HH", "AH", "L", "OW"])

# Phoneme stream from text
phones = dectalk.text_to_phonemes("Hello, world!")
# -> ['HH', 'AH0', 'L', 'OW1', 'SIL', 'W', 'ER1', 'L', 'D', 'SIL']
```

## Voices

Nine canonical DECtalk voices are available:

| Name | Description |
|---|---|
| `paul` | Perfect Paul — neutral adult male (default) |
| `betty` | Beautiful Betty — adult female |
| `harry` | Huge Harry — booming low male |
| `frank` | Frail Frank — breathy older male |
| `dennis` | Doctor Dennis — calm, deliberate male |
| `kit` | Kit the Kid — child voice |
| `ursula` | Uppity Ursula — adult female (higher pitch) |
| `rita` | Rough Rita — adult female (rougher) |
| `willy` | Whispery Willy — very breathy male |

## Inline command syntax

DECtalk's `[:cmd value]` directives are recognised inside text:

| Command | Meaning |
|---|---|
| `[:dv NAME]` / `[:name NAME]` | Switch voice |
| `[:rate N]` | Speaking rate, % of nominal (100 = normal, 200 = half speed) |
| `[:phoneme on/off]` | Switch between text and direct ARPABET input |
| `[:say T]`, `[:ap N]`, `[:pr N]`, `[:hs N]`, `[:sm N]`, `[:emph N]` | Recognised; currently no-op |

Unrecognised commands are silently dropped.

## Status

| Phase | Feature | Status |
|---|---|---|
| 0 | Project scaffolding, audio I/O, CI | done |
| 1 | Klatt cascade-parallel synthesizer | done |
| 2 | Text → phoneme pipeline (lexicon + LTS) | done |
| 3 | Multi-voice + inline commands + numbers | done |
| 4 | UK English lexicon overrides | done |
| 5 | Romance + Germanic languages | pending |
| 6a | Sentence-level F0 contour | done |
| 6b | README + examples | done |
| 6c | Polish + remaining line-by-line C translations | partial |

The synthesizer is the line-by-line port of `hlsyn/` (Klatt's
cascade-parallel formant synthesiser). The front-end (text normalization,
LTS, lexicon, command parser) is a clean Python implementation rather
than a literal C translation. The bundled lexicon and voice tables are
reasonable approximations of the FONIX-licensed originals — see
`docs/PLAN.md` for the licensing context.

## Development

```bash
scripts/dev_check.sh   # ruff + ruff-format + pyright strict + pytest + shellcheck
```

Or individually:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -v
```

## Layout

```
src/dectalk/
├── __init__.py         # public API: speak, to_wav, synthesize_phonemes, ...
├── cli.py              # `python -m dectalk` entry
├── api/                # high-level text -> audio
├── cmd/                # [:cmd value] parser
├── kernel/             # text normalization + numbers
├── lts/                # rule-based letter-to-sound fallback
├── ph/                 # phoneme -> Klatt frame mapping + prosody
├── dic/                # lexicon loader
├── hlsyn/              # Klatt cascade-parallel synthesizer (translated)
├── nt/                 # WAV I/O + sounddevice playback
├── include/            # shared types and phoneme inventory
└── data/               # bundled lexicons, voice tables
```
