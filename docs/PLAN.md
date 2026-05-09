# Python port of DECtalk

## Context

The repository is currently empty (just `README.md` and `.gitignore`). The user wants a **feature-complete Python port of DECtalk 4.2CD** that runs cross-platform without requiring the user to compile any binaries. They want a **direct line-by-line translation** of the FONIX C source covering **all 6 languages** (US/UK English, Spanish, French, German, Latin American Spanish), with **WAV output and live playback**, packaged as `dectalk`.

DECtalk is a classic formant-based TTS engine from DEC, famous as Stephen Hawking's voice. The 4.2CD source consists of ~10 C modules under `src/dapi/srcold/` that form a pipeline: text → command parser (CMD) → text normalization (KERNEL) → letter-to-sound rules (LTS) → dictionary lookup (dic) → phoneme processing & intonation (PH) → vocal tract model (VTM) → Klatt cascade-parallel formant synthesizer (hlsyn) → audio I/O (NT). Voices, phoneme tables, and language data are mostly C tables; the dictionary is text-based.

**Scale**: ~100K+ lines of C across ~400 source files. Time estimates throughout this plan are **Claude Code orchestrator time, not human developer time** — Claude does all the translation, agents run in parallel, and the orchestrator's bottleneck is reviewing diffs and resolving cross-cutting issues between batches. Rough total: **1.5-2 weeks of orchestrated session time** for feature-complete + multi-language. The plan delivers usable speech in Phase 2, then expands breadth (more languages, voices) and depth (parity with original) in later phases. Each phase ends with something demoable.

**License caveat acknowledged by user**: 4.2CD is proprietary FONIX. The user accepted that a line-by-line translation cannot be legally redistributed without FONIX permission and is suitable only for private/personal use unless that permission is obtained. The same restriction applies to the **data files** (dictionaries `DIC_*.txt`, abbreviation tables, voice parameter tables) — they're part of the same proprietary release and inherit its license. The plan reflects the user's choice; this note is preserved so the constraint isn't lost.

## Stack

- **Python 3.11+** (modern type hints, `match` statements help when mirroring C `switch` blocks)
- **uv** — package/project manager. `uv init`, `uv add`, `uv sync`, `uv run` for everything; lockfile is `uv.lock`
- **NumPy** — vectorized array ops for the synthesizer's inner loops; ships as wheels on all platforms (no user compilation)
- **SciPy** — `scipy.signal` for IIR filtering, resampling; same wheel story
- **sounddevice** — cross-platform live playback (PortAudio bindings, prebuilt wheels)
- **Standard library** — `wave` for WAV I/O, `struct`, `array`, `dataclasses`, `enum`
- **pytest** — test runner (run via `uv run pytest`)
- **Ruff** — linter + formatter; pydocstyle rules with Google docstring convention; `ruff format` (Black-compatible) for formatting
- **pyright** — strict-mode type checker; runs in CI

No Cython, no C extensions written by us. All third-party deps are pure-Python or come with maintainer-provided wheels.

## Code-quality requirements

These apply to **every** Python file in the project, including translated modules:

- **Type hints everywhere**: annotate all public and private function signatures (parameters and return types). NumPy arrays use `numpy.typing.NDArray[np.int16]` etc.
- **No implicit `Any`** and **no explicit `Any`** without a comment justifying the use. Prefer `object`, `Unknown` (via `typing.cast`), or precise unions.
- **pyright strict mode** is the gate. Configure in `pyproject.toml` under `[tool.pyright]` with `typeCheckingMode = "strict"`. CI fails on type errors.
- **Narrow suppressions only**: `# pyright: ignore[reportSpecificError]` with an inline comment explaining why. Never blanket `# type: ignore` or file-level disables.
- **Ruff config** in `pyproject.toml` under `[tool.ruff]`. Enable rule sets including `D` (pydocstyle) with `convention = "google"` so all public symbols carry Google-style docstrings (Args / Returns / Raises sections). Use `ruff format` for formatting.
- **Pre-commit / CI**: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, and `uv run pytest` all run in CI; any failure blocks merge.
- **Translation note**: when a C function uses `void *` opaque handles, model as a typed wrapper class — not as `Any` — so pyright keeps its grip on the call graph.

### Shell scripts

Any helper scripts (e.g. `scripts/run_ci.sh`, `scripts/regen_dict.sh`, release helpers) must:

- Start with `#!/usr/bin/env bash` and `set -euo pipefail`.
- Follow the [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html): 2-space indent, functions at top, `main` at bottom, lowercase-with-underscores for locals.
- Pass `shellcheck` with zero warnings. Per-line suppressions only via `# shellcheck disable=SCxxxx` with a one-line reason directly above.
- Be idempotent where practical (re-runs don't break or duplicate state).
- CI runs `shellcheck scripts/*.sh` alongside the Python checks.

## Repository layout

Mirror the C source tree so the line-by-line correspondence stays obvious during translation, but use Python conventions (snake_case, packages, `__init__.py`):

```
dectalk-python/
├── pyproject.toml
├── README.md
├── src/dectalk/
│   ├── __init__.py              # Public API: TTS class, speak(), to_wav()
│   ├── cli.py                   # `python -m dectalk "Hello world"` entry point
│   ├── api/                     # mirrors src/dapi/  (ttsapi.c, init.c)
│   ├── cmd/                     # mirrors src/CMD/   (cm_cmd.c et al.) — inline command parser
│   ├── kernel/                  # mirrors src/KERNEL/ — text normalization, abbrev expansion
│   ├── lts/                     # mirrors src/LTS/   — letter-to-sound rules per language
│   ├── ph/                      # mirrors src/PH/    — phoneme features, intonation, durations
│   ├── dic/                     # mirrors src/dic/   — pronunciation dictionary loader
│   ├── vtm/                     # mirrors src/VTM/   — vocal tract model
│   ├── hlsyn/                   # mirrors src/hlsyn/ — Klatt cascade-parallel synthesizer
│   ├── nt/                      # mirrors src/NT/    — audio I/O (WAV writer, sounddevice playback)
│   ├── include/                 # mirrors src/INCLUDE/ — shared structs, enums, constants
│   └── data/
│       ├── dic/                 # text dictionaries: DIC_US.txt, DIC_UK.txt, etc.
│       ├── abbrev/              # TTSAbbr1.tab, TTSabbr2.tab, USER.TAB
│       └── voices/              # Paul, Betty, Harry, Frank, Dennis, Kit, Ursula, Rita, Wendy
└── tests/
    ├── unit/                    # per-module tests
    ├── parity/                  # output comparison vs reference (when available)
    └── audio/                   # short-phrase audio regression tests
```

## Translation methodology

Each C file maps to a Python file with the same basename. Translation rules:

| C construct | Python equivalent |
|---|---|
| `struct foo { ... }` | `@dataclass class Foo:` |
| `enum { A, B }` | `class X(IntEnum):` |
| `static` global | module-level variable |
| `static` function | module-level function with `_` prefix |
| Pointers to structs | direct object refs |
| Pointer arithmetic on arrays | NumPy array views / slices |
| `malloc`/`free` | rely on GC; no manual free |
| Bit-packed flags | `IntFlag` |
| `#define` macros | module constants or small functions |
| `switch`/`case` | `match`/`case` (3.10+) |
| `goto` | refactor to early returns / loops (small handful of cases in DECtalk) |
| `void *` opaque handles | typed wrapper class (never `Any` — pyright strict forbids it) |
| Function pointers | `Callable[..., T]` with full parameter typing |
| Fixed-size C arrays | `numpy.typing.NDArray[np.intN]` with shape comment, or `tuple[int, ...]` for small fixed sizes |

Translate each file alongside the original. **Do not** sprinkle "// originally line N" or "ported from X" comments — they rot and add noise. Add a comment only when WHY a translation choice differs from the obvious is non-obvious (e.g., "guard against negative pitch from rounding; original C relied on signed wraparound"). One commit per translated file or small group of related files.

## Parallelization with agents

The translation work is highly parallelizable: most C files in a module are sibling leaves once shared headers are translated, and each of the 6 languages has an independent body of LTS/PH/dictionary code. Use Claude Code's `Agent` tool to dispatch translation work in parallel rather than serially.

### Coordination model

The session running this plan acts as **orchestrator** — never translates files directly past Phase 0. It:

1. Owns the shared interface layer (`include/`, public API stubs) and edits it solo so type contracts don't drift
2. Dispatches **batches** of translator agents (≤ 5 in parallel) at module boundaries
3. Reviews each agent's output (read the diff, run pyright + tests on what they produced)
4. Resolves any cross-file fixups itself before launching the next batch

Each translator agent runs with `isolation: "worktree"` so parallel agents don't trample each other's working tree. The orchestrator merges completed worktrees into the feature branch one at a time, running CI between merges.

### Agent prompt contract

Every translator agent receives a self-contained brief with:

- **Goal**: "Translate `<C source path>` to `<Python target path>` per the project's translation rules"
- **Inputs**: absolute path to the C file, absolute path(s) to already-translated dependency headers it must import from
- **Type contract**: the expected public function signatures (parameter types + return types) it must produce, copied from the dependency headers
- **Hard rules**: pyright strict mode passes, Google docstrings on every public symbol, no `Any`, no `# type: ignore`, no narration comments, `uv run pytest tests/unit/<module>` passes if a stub test exists
- **Hands-off list**: files it must not touch (anything outside its target file + the test sibling)
- **Acceptance**: run `uv run ruff check <file> && uv run pyright <file> && uv run pytest <test>` and report results

Agents are told to **stop and report blockers** rather than guessing — this prevents one agent's misinterpretation of a C idiom from cascading into others.

### Where parallelism wins

| Phase | Parallelizable unit | Suggested concurrency |
|---|---|---|
| Phase 0 | Header files (`INCLUDE/*.h`) — many small, independent | 3 agents on disjoint header groups |
| Phase 1 | `hlsyn/` leaf files (`voice`, `reson`, `circuit`) before `synth` | 3 in parallel, then `synth` solo |
| Phase 1 | `VTM/` files | 3 agents on disjoint groups |
| Phase 2 | `LTS/` US English rule files (~50, independent) | 4-5 agents, ~10 files each |
| Phase 2 | `dic` loader, `KERNEL/usa.c`, `PH/` US — weakly coupled | 3 agents on disjoint files |
| Phase 3 | `CMD/` files (~40) and voice parameter tables (9 voices) | 4-5 agents on disjoint files |
| Phase 4 | UK LTS + UK PH + UK dictionary | 3 agents in parallel |
| Phase 5 | **The big win**: ES, LA, FR, DE are fully independent languages | 4 agents in parallel, one per language; each spawns its own LTS sub-batch |
| Phase 6 | Singing, normalization edge cases, performance, parity tests | 3-4 agents on disjoint deliverables |

### Where parallelism does NOT help

- The Klatt `synth.py` top-level frame loop — single coherent file, must be authored holistically
- Public API design (`__init__.py`, `cli.py`) — single source of truth, do solo
- Anything touching `include/` after Phase 0 — solo to prevent type drift
- Performance optimization passes — need a single mind tracing a profile

### Risk mitigation

- **Interface drift**: Phase 0 hardens `include/` first; downstream agents only import from there, never define cross-cutting types
- **Merge conflicts**: worktrees + non-overlapping file assignments; orchestrator merges serially
- **Quality variance**: every agent's output goes through the same gate (`ruff` + `pyright` + `pytest`) before merge — failures bounce back to the same agent via `SendMessage` with the failing diagnostics, not silently fixed by the orchestrator
- **Context fragmentation**: cap at 5 concurrent agents; brief them with the same translation rules table so they apply consistent idioms

### Throughput estimate

All time estimates in this plan assume **Claude Code does the work**, with the orchestrator session dispatching parallel agents. Mechanical translation is fast for an LLM; the real bottleneck is the orchestrator's review-and-merge loop between agent batches. Sum of phase estimates: ~7-10 days of orchestrated session time. Roll-up: **1.5-2 weeks elapsed** for feature-complete + multi-language, accounting for debugging cycles (especially audio-quality tuning in Phase 1) and review overhead. Phases 2, 3, and 5 — the bulk of LTS/dictionary/language work — are embarrassingly parallel and benefit most from the agent strategy; Phase 1 is the schedule-critical path because audio quality requires careful iteration.

## Implementation phases

Each phase ends with a working artifact that can be tested.

### Phase 0 — Scaffolding (~half a day)

- **First action**: copy this plan to `/home/user/dectalk-python/docs/PLAN.md` so it lives in the repo (creating `docs/` if needed). The plan is the canonical reference for every translator agent in later phases.
- `uv init` the project; configure `pyproject.toml` (project metadata, deps via `uv add numpy scipy sounddevice`, dev deps via `uv add --dev pytest ruff pyright`)
- Configure `[tool.ruff]` with the `D` (pydocstyle) rule set under `convention = "google"`, plus core lint sets; `[tool.pyright]` with `typeCheckingMode = "strict"`
- Package layout (`src/dectalk/...`), pytest config under `[tool.pytest.ini_options]`
- Translate `INCLUDE/` headers: shared structs (TTS_PARAMS, voice tables, phoneme records, frame structs), enums, constants — all fully type-annotated
- Translate `NT/` audio I/O: WAV writer using stdlib `wave`; live playback wrapper around `sounddevice`
- CI scaffolding: GitHub Actions matrix for Linux/macOS/Windows × Py 3.11/3.12/3.13/3.14, running `uv run ruff check`, `uv run ruff format --check`, `uv run pyright`, `uv run pytest`, plus `shellcheck scripts/*.sh`
- Pre-commit hooks via [`pre-commit`](https://pre-commit.com/) wired to ruff, ruff-format, pyright, and shellcheck so the same gates run locally before push

**Deliverable**: `uv run python -c "from dectalk.nt import write_wav; ..."` works; `uv run python -m dectalk --play-test` plays a tone through speakers; CI green on all three OSes.

### Phase 1 — Klatt synthesizer (~1-2 days)

Highest-risk phase: audio quality depends on getting filters and glottal pulses exactly right. Budget extra debugging time if synth output sounds wrong.

- Translate `hlsyn/` module: cascade-parallel formant synthesizer (~5K LOC)
  - `voice.c` (glottal pulse modeling) → `voice.py`
  - `reson.c` (formant resonator filter) → `reson.py`
  - `circuit.c` (cascade/parallel routing) → `circuit.py`
  - `synth.c` (top-level frame loop) → `synth.py`
- Translate `VTM/` module: phoneme→formant target computation (~8K LOC)
- **Performance is non-negotiable here**: the per-sample inner loop runs ~110k times/second of audio. A literal Python translation will be 50–200× too slow. Strategy:
  1. Frame-level loop (200 Hz) stays plain Python — readable, tracks the C code
  2. Per-sample resonator filters are rewritten as `scipy.signal.lfilter` calls or vectorized NumPy difference equations operating on whole-frame buffers
  3. Glottal pulse generator vectorized over the frame
  4. Profile after each module lands; budget: synthesizing 1 s of speech in ≤ 0.3 s on a modern laptop

**Deliverable**: Given a hand-crafted sequence of Klatt frames, produce intelligible vowel sounds and basic syllables. Unit tests with known formant inputs producing expected spectra.

### Phase 2 — US English pipeline (~2-3 days)

- Translate `dic/` dictionary loader; convert `DIC_US.txt` to a runtime data structure
- Translate `LTS/` US English files (~50 files): grapheme-to-phoneme rules
- Translate `PH/` US English files: stress, duration, intonation contour generation
- Translate `KERNEL/usa.c` and related: text normalization, sentence segmentation
- Wire up `api/ttsapi.c` → Python public API

**Deliverable**: `dectalk speak "Hello world"` produces recognizable US English speech with default Perfect Paul voice.

### Phase 3 — Command syntax + voices (~1 day)

- Translate `CMD/` (~40 files): `[:cmd value]` inline command parser
- Translate voice parameter tables for all 9 canonical voices (Perfect Paul, Beautiful Betty, Huge Harry, Frail Frank, Doctor Dennis, Kit the Kid, Uppity Ursula, Rough Rita, Whispery Willy)
- Wire commands: `[:rate]`, `[:ap]`, `[:pr]`, `[:dv]`, `[:phoneme on]`, `[:hs]`, `[:sm]`, `[:emph]`, etc.

**Deliverable**: `dectalk speak "[:dv harry][:rate 200] Greetings, human."` works; phoneme-direct mode works.

### Phase 4 — UK English (~half a day)

- Translate `LTS/` UK files, `PH/` UK files, `DIC_UK.TXT`
- Add UK-specific abbreviations
- Validate against UK pronunciation samples

**Deliverable**: `[:lang uk]` switches to UK English.

### Phase 5 — Romance + Germanic languages (~2-3 days)

- Per-language work (Spanish Castilian, Latin American Spanish, French, German): translate `LTS/` rules (~50 files each), `PH/` intonation files, dictionary, abbreviation tables. With 4 language-agents running in parallel and each spawning its own LTS sub-batch, all four languages land in roughly the same wall time as Phase 4 took for UK alone.
- Phoneme-inventory extensions: French nasal vowels (`/ɑ̃ ɛ̃ ɔ̃ œ̃/`), French uvular `/ʁ/`, German front rounded vowels (`/y ø/`), German `/x ç/`. Audit Phase 1 phoneme→formant tables and extend.
- Per-language acceptance set: 50 hand-picked sentences listened to and rated for intelligibility before declaring a language done.

**Deliverable**: All 6 languages selectable via `[:lang xx]` command.

### Phase 6 — Polish & parity (~1-2 days)

- Singing mode (tone numbers, fixed-pitch phoneme syntax)
- Edge cases in text normalization (currency, dates, phone numbers, URLs)
- Performance pass: profile hot loops, push more into NumPy
- Parity test suite: run identical inputs through Python port and reference C build, diff WAV outputs (if user has access to a 4.2CD build)

**Deliverable**: Feature-complete release-candidate.

## Public API design

The translated internals are mechanical; layer a Pythonic API on top so library users don't deal with the C struct shapes:

```python
from typing import Literal
import dectalk

Voice = Literal["paul", "betty", "harry", "frank", "dennis", "kit", "ursula", "rita", "willy"]
Lang = Literal["us", "uk", "es", "la", "fr", "de"]

# One-shot
dectalk.speak("Hello world")                 # plays through speakers
dectalk.to_wav("Hello world", "hello.wav")   # writes WAV

# Object API
tts: dectalk.TTS = dectalk.TTS(voice="paul", rate=180, lang="us")
samples = tts.synthesize("[:phoneme on] hh ax l ow")   # returns NDArray[np.int16]
tts.play(samples)
tts.write_wav(samples, "out.wav")

# CLI
# $ uv run python -m dectalk "Hello world" -o out.wav
# $ uv run python -m dectalk --voice betty --rate 200 "Hello"
```

`TTS.synthesize` is the boundary: it accepts text + commands, runs the full pipeline, returns `NDArray[np.int16]` PCM samples at 11025 Hz (DECtalk's native rate). All public types use `Literal`/enums, never bare `str`, so callers get pyright-checked argument validation.

## Critical files to create first (Phase 0)

- `/home/user/dectalk-python/docs/PLAN.md` — copy of this plan; canonical reference checked into the repo before any other work
- `/home/user/dectalk-python/pyproject.toml` — uv project metadata, deps, entry point, `[tool.ruff]`, `[tool.pyright]`, `[tool.pytest.ini_options]`
- `/home/user/dectalk-python/uv.lock` — created by `uv sync`, committed
- `/home/user/dectalk-python/.python-version` — pin Python 3.11+
- `/home/user/dectalk-python/src/dectalk/__init__.py` — public API stubs (typed)
- `/home/user/dectalk-python/src/dectalk/include/tts_params.py` — translate `INCLUDE/dectalk.h` voice IDs and core structs
- `/home/user/dectalk-python/src/dectalk/include/phonemes.py` — ARPABET phoneme inventory
- `/home/user/dectalk-python/src/dectalk/nt/audio.py` — WAV writer + sounddevice playback
- `/home/user/dectalk-python/src/dectalk/cli.py` — argparse-based CLI entry
- `/home/user/dectalk-python/tests/unit/test_audio.py` — round-trip a sine wave through WAV + playback
- `/home/user/dectalk-python/.github/workflows/ci.yml` — Linux/macOS/Windows matrix; runs ruff + pyright + pytest via `uv run`, plus `shellcheck`
- `/home/user/dectalk-python/.pre-commit-config.yaml` — same gates as CI for local pre-push runs
- `/home/user/dectalk-python/scripts/dev_check.sh` — bash helper that runs the full local check (`set -euo pipefail`, Google Shell Style Guide compliant, shellcheck-clean)

## Verification

End-to-end testing strategy:

1. **Unit tests per module** (pytest). Each translated C file gets a sibling test file. Aim for ≥80% line coverage on translated code.
2. **Synthesizer correctness**: feed canonical Klatt parameter frames (e.g., from Klatt 1980 paper Appendix examples) and verify the spectral output matches expected formant peaks within tolerance using `scipy.signal.welch`.
3. **Phoneme regression**: a fixed list of words/phrases → expected phoneme strings. Catches LTS rule regressions.
4. **Audio regression**: short canned phrases ("hello world", "the quick brown fox", "[:dv harry][:rate 250] hi") rendered to WAV and compared (RMS difference threshold) against a checked-in reference WAV.
5. **Cross-platform CI**: GitHub Actions on Linux + macOS + Windows verifies install + test suite + at least one synthesized WAV per platform.
6. **Manual listening**: at the end of each phase, render the standard "harvard sentences" corpus and listen for intelligibility regressions.
7. **Parity vs original** (Phase 6 only, optional): if a working 4.2CD reference build is available, diff WAV outputs for a fixed corpus.

Run with:
- `uv run pytest -v` — unit tests
- `uv run ruff check . && uv run ruff format --check .` — lint + format
- `uv run pyright` — strict type check
- `uv run python -m dectalk "Hello world"` — smoke test
- `uv run python -m dectalk --self-test` — audio regression set
