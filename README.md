# dectalk-python

Cross-platform Python port of DECtalk text-to-speech.

Pure-Python with NumPy / SciPy / sounddevice — no compiled binaries to build,
all dependencies install from prebuilt wheels.

> **Status:** Phase 0 (scaffolding + audio I/O) complete. Synthesizer and
> language pipelines arrive in subsequent phases. See [`docs/PLAN.md`](docs/PLAN.md)
> for the full implementation plan.

## Quick start

```bash
# install
uv sync

# play a 1 s 440 Hz sine through your speakers
uv run python -m dectalk --play-test

# write a 1 s 440 Hz sine to a WAV file
uv run python -m dectalk --write-test out.wav
```

## Development

```bash
scripts/dev_check.sh   # ruff + ruff-format + pyright + pytest + shellcheck
```

Or run the gates individually:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -v
```

## Layout

The package mirrors the DECtalk 4.2CD source-tree module layout so the
translation correspondence stays obvious. See `docs/PLAN.md` for details.
