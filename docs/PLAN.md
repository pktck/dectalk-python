# Line-by-line C-to-Python port for WAV bit parity with the binary

## Context

The Python port that exists today is two different things stacked on
top of each other:

- **The synthesizer back-end** (`src/dectalk/hlsyn/`, ~1.5K lines) is a
  faithful translation of the C Klatt synthesizer. The parity test
  `tests/parity/test_synth_parity.py` asserts byte-identical output
  when both sides receive identical Klatt frames.
- **The front end** (`kernel/`, `lts/`, `dic/`, `ph/`, `cmd/`,
  `vtm/` — ~4.7K lines) is **not a translation**. It is an
  approximation written from first principles that produces
  intelligible-but-divergent speech. The audit in
  `docs/c_audit/prosody.md` documents the structural mismatch: linear
  declination vs. impulse-driven gestures, flat-multiplier durations
  vs. per-phoneme-class rules, 41 ARPABET codes vs. 71 allophones,
  no foot/syllable structure, no comma gesture, no phrase-position
  decay, no phrase-final lengthening rule, and so on.

The user has now stated the binding requirement: **the final Python
output must be byte-identical to the DECtalk binary's WAV output**.
This is not "sounds close" — it is bit parity at the sample level.
Achieving this requires translating the C front end faithfully,
module by module, with the C source as the single source of truth.

Decisions confirmed with the user (via AskUserQuestion):

- **Language scope**: US English only first. Other languages follow
  once US is at bit parity.
- **Parity oracle**: hybrid. Per-module unit tests use ctypes against
  a locally built C library as the oracle; end-to-end gating compares
  Python's WAV output against the binary's WAV output byte-for-byte.
- **Existing approximate code**: replaced wholesale. `kernel/`,
  `lts/`, `dic/`, `ph/`, `cmd/`, `vtm/` get torn down and rebuilt
  from C; `hlsyn/` stays.

### Critical: which branch of `dectalk/dectalk` to follow

The upstream repository has two relevant branches that differ
substantially. Both are present locally at `/tmp/dectalk-src`:

| | `master` | `develop` |
|---|---|---|
| Commits | 3 (2020-08 → 2022-08) | 1 squashed (HEAD: 2026-03-29) |
| README description | "Literally just the source code dumped into the /src folder" | "Working Linux/Windows binaries (i386, x86_64 and aarch64), MacOS/iOS" |
| Source layout | `src/dapi/srcold/{API,KERNEL,LTS,PH,…}/` (mixed-case dump from the Bruckert release) | `src/dapi/src/{api,kernel,lts,ph,cmd,vtm,dic,include,hlsyn}/` (lowercase, reorganised) |
| Build system | None functional — original VS6 `.DSP`/`.DSW` only | autoconf (`autogen.sh`, `configure.ac`) + Dockerfile + GitHub Actions CI in `.github/workflows/build.yml` |
| File count | 4 511 | 2 993 (cleanup: removed Windows build artefacts, .DS_Store, sample binaries) |
| Top-level extras | none | `Dockerfile`, `docker-compose.yml`, `devops/`, `ports/emscripten/` |

`master` is the unmodified historical snapshot. `develop` is the
maintained line that builds today: it has cleaned-up directory
casing, working autotools, Docker, and the Linux/Windows/Mac CI
that produces the redistributed binaries.

The binary at `/tmp/dectalk-binary-stable/say` reports version
`6.2.0-1015-azure` in its `strings` output, matching the Azure CI
infrastructure used by develop's GitHub Actions workflow (`.github/
workflows/build.yml`). **For bit parity, the port must reference
`develop`, not `master`.**

Caveat: develop is a single squashed commit, so there is no
intermediate git history to bisect if our locally-built
`libtts_us.so` diverges from the shipped binary. If Phase A.3
detects a divergence, the fallback is to fetch the exact artefact
from the binary's GitHub Actions run (run ID embedded in the
version string `1015-azure`) rather than rebuild it ourselves.

The Phase-3 prosody audit at `docs/c_audit/prosody.md` cites
`srcold/` paths (master layout). For the line-by-line port that
audit serves only as a high-level reading guide; all citations in
the new translation must use develop's `src/dapi/src/<module>/`
paths.

## Scope

C-source scope on develop (US English only):

| Module | Files | Rough line count | Phase |
|---|---|---|---|
| INCLUDE | shared headers | ~3K | C |
| KERNEL | 10 | ~2K | C |
| CMD | 45 | ~15K | C |
| LTS | 119 (US: ~60 rule files + tables) | ~50K | D |
| dic | dictionary loader + `dtalk_us.dic` data | ~5K + 600KB data | D |
| PH | 104 (US: ~58 files including all p_us_*) | ~40K | E |
| VTM | 35 | ~15K | E |
| API | 8 | ~3K | F |

Total US-English C scope: ~343 files, ~130K source lines plus data
tables. Realistic effort: **3–5 months of focused orchestrator
time** (using parallel translator agents for the independent leaf
files like LTS rule tables).

End state: a pure-Python port whose `dectalk.speak(text)` output is
byte-identical to `/tmp/dectalk-binary-stable/say -a "<text>" -fo
out.wav` for a documented test corpus, with no runtime C dependency.

## Approach

### Phase A — Build the C source as an oracle (≈3–5 days)

A.1 **Switch the C reference to the develop branch.**

```bash
cd /tmp/dectalk-src && git checkout develop
```

Develop's module layout is `src/dapi/src/{kernel,lts,ph,cmd,vtm,dic,
include}/` (lowercase, no `srcold/` prefix). Update all c-audit
references to point at develop paths going forward.

A.2 **Build `libtts_us.so` on the local Linux host.**

Follow the develop branch's README:

```bash
cd /tmp/dectalk-src/src
./autogen.sh
./configure --enable-language=us
make -j
```

Acceptance gate: `libtts_us.so` produced and `nm -D libtts_us.so |
grep TextToSpeech` lists the expected entry points
(`TextToSpeechStartup`, `TextToSpeechSpeak`, `TextToSpeechShutdown`,
plus the `TextToSpeechConvertToPhonemes`-style boundary probes from
`TTSAPI.H`).

If autoconf misbehaves on the local host, the develop branch ships
a `Dockerfile` and `docker-compose.yml`; fall back to building in
Docker and copying `libtts_us.so` out.

If the build needs proprietary FONIX licensing stubs (likely
suspects: `API/crypt2.c`, `API/decstd97.c`), stub them with
no-op wrappers and document.

A.3 **Confirm source-build output matches the shipped binary.**

This is the linchpin. The C source must produce a WAV byte-identical
to `/tmp/dectalk-binary-stable/say` output, otherwise the bit-parity
goal is unreachable (the binary and the buildable source disagree).

Test: a small script (`scripts/verify_source_matches_binary.py`)
that renders 10 prompts via both the freshly built `libtts_us.so` and
the shipped `say` binary, asserting byte-identical WAVs.

If they diverge, bisect develop's git history to find the binary's
exact build commit. Document the commit hash and either pin
`/tmp/dectalk-src` to it or keep a patch series on top.

A.4 **Add per-module dump hooks to the C source.**

Each Python module needs a parity test that runs the same input
through ctypes-wrapped-C and through Python, then asserts equal
output. For that to work the C side has to be able to **emit
intermediate state at module boundaries**. The dump points:

- After **KERNEL**: text-normalised tokens (numbers expanded,
  abbreviations resolved, sentence-segmented).
- After **CMD**: parsed command stream — body segments interleaved
  with `[:rate]`, `[:dv]`, `[:lang]`, etc. control codes.
- After **LTS + dic**: ARPABET phoneme sequence with stress digits
  and word/syllable boundary feature bits.
- After **PH**: per-phoneme prosody plan — duration, F0 contour,
  amplitude envelope, stress class.
- After **VTM**: Klatt frame plan — the (frame, sample_count) list
  fed to the synthesiser. The hlsyn parity tests already cover the
  step from frame plan to audio.

Implementation: add a `_dectalk_dump_<stage>(FILE *fp, ...)`
function in each module, called when an env var
`DECTALK_DUMP_STAGES=kernel,cmd,...` is set. Format: a deterministic
text serialisation (one record per line, tab-separated) so Python's
parity tests can `subprocess.run` the C harness and parse the dump
trivially.

The dump hooks live on a patch in our /tmp clone, not upstream. Keep
the patch under `tests/parity/c_harness/dump_hooks.patch` so it can
be reapplied if `/tmp/dectalk-src` is re-cloned.

A.5 **Wrap the C library in Python via ctypes.**

New module `src/dectalk/_capi/` (private; not part of the public
API, present only during the porting period). Provides:

- `_capi.startup() / _capi.shutdown()` — wrap the C lifecycle.
- `_capi.speak(text: str) -> bytes` — full pipeline, returns WAV.
- `_capi.dump_pipeline(text: str, stages: list[str]) -> dict[str,
  bytes]` — render with `DECTALK_DUMP_STAGES` set, return each
  stage's serialised output. Used by per-module parity tests as the
  oracle.

Unit-test the wrapper: assert `_capi.speak("hello world") ==
binary_say("hello world")` byte-for-byte.

### Phase B — Route public API through `_capi` (≈1 day)

**Plan revision (implementation notes):** the original Phase B
proposed deleting all approximate Python front-end modules in one
step and routing every public API entry point through `_capi`.
While exploring the C library we discovered that
`TextToSpeechConvertToPhonemes` — although exported by `libtts.so`
(the multi-language dispatcher) on Linux — is unusable there. The
implementation lives in `src/dapi/src/api/ttsapi.c` inside an
`#ifdef WIN32` block, so `libtts_us.so` does not export the symbol
on Linux. The dispatcher resolves the impl via `dlsym` /
`GetProcAddress` at startup, gets NULL, and its null-checks only
verify the library handle, not the function pointer. Calling the
public symbol on Linux therefore segfaults at the indirect call —
not because the API isn't exported, but because the implementation
is Windows-only. The Python `text_to_phonemes(text)` entry point
therefore cannot be ported to `_capi` without first patching the C
source (which is Phase A.4 work). To avoid blocking on that patch,
Phase B now does the minimum needed for bit-identical audio and
defers the module tear-down to the per-module translation phases:

B.1 (deferred) **Module tear-down — done per-module in Phases C-E.**

Each approximate Python module (`kernel/`, `cmd/`, `lts/`, `dic/`,
`ph/`, `vtm/`) is deleted only when its faithful translation lands
and the corresponding parity test passes. This means the approximate
code keeps the secondary `text_to_phonemes()` entry point and the
`synthesize_phonemes()` path alive during the translation period;
they will be one-by-one replaced with translations.

B.2 **`api/speak.py` routes audio through `_capi`.**

The two entry points that produce audio — `speak(text, ...)` and
`to_wav(text, path, ...)` — get rewritten to call `dectalk._capi.
CAPI.speak`. Voice/rate kwargs become DECtalk inline commands
(`[:np]` for Perfect Paul, `[:rate <wpm>]` for rate) prepended to
the text. The returned WAV bytes are decoded into `np.int16` PCM
for the public API.

The legacy `lts_fallback` kwarg is kept but ignored (with a
docstring deprecation note) since the C library has no equivalent
toggle.

B.3 **End-to-end binary-WAV parity test.**

A new pytest module `tests/parity/test_binary_wav_parity.py`
renders the corpus through `dectalk.to_wav` and asserts the output
file is byte-identical to the shipped binary's WAV. This is the
goalpost test that must remain green throughout Phases C-F.

B.4 **Other entry points retained.**

`text_to_phonemes()` and `synthesize_phonemes()` keep their
approximate Python implementations. Tests that exercised them
(`tests/unit/test_speak.py::test_text_to_phonemes_*`,
`tests/unit/test_prosody.py`, etc.) continue passing. The
`docs/c_audit/prosody.md` notes the divergence; per-module
translations supersede the approximate code one boundary at a time.

### Phase C — Translate INCLUDE/, KERNEL/, CMD/ (≈3–5 weeks)

Top of the dependency graph. Translation rules from the original
plan (struct → dataclass, enum → IntEnum, `#define` → constant,
goto → refactor) apply.

C.1 **INCLUDE/ headers (≈1–2 days)**

Walk every `.h` in `/tmp/dectalk-src/src/dapi/src/include/`:

- `dectalk.h`, `kernel.h`, `cmd.h`, `pipe.h`, `phdefs.h`, …
- For each, extract structs, enums, constants, and feature-bit
  flags into a Python sibling in `src/dectalk/include/`.
- These are pure data definitions — no runtime behaviour. Parity
  is trivially verified (structs round-trip).

C.2 **KERNEL/ (≈1–2 weeks)**

`/tmp/dectalk-src/src/dapi/src/kernel/` — ~10 files. The KERNEL is
text normalisation: number expansion ("123" → "one hundred twenty
three"), abbreviation lookup, sentence/clause segmentation,
character-to-phoneme rough mapping.

Per file:

1. Read the C file, write a Python translation following the
   translation rules.
2. Write `tests/parity/test_kernel_<file>_parity.py` using
   `_capi.dump_pipeline(text, ["kernel"])` as the oracle. Iterate
   on a corpus of texts (numbers, dates, abbreviations, edge cases
   from the C source's own test inputs if findable).
3. Acceptance: 100% of corpus produces byte-identical tokens.

C.3 **CMD/ (≈2–3 weeks)**

`/tmp/dectalk-src/src/dapi/src/cmd/` — ~45 files implementing the
`[:cmd value]` inline command parser. Each command (`[:rate 200]`,
`[:dv ap 110]`, `[:phoneme on]`, `[:lang us]`, `[:hs <handle>]`,
`[:sm <s>]`, `[:emph <e>]`, etc.) is its own subroutine.

Parallelise: command handlers are mostly independent, dispatch them
to translator agents in batches of 5–10 files. Orchestrator merges
serially with parity-test runs between merges.

C.4 **Wire C, B.2's `api/speak.py` to use the Python KERNEL and
CMD instead of `_capi` for those stages.**

End-to-end binary-WAV parity (test from B.3) must still pass after
this rewire. The hybrid path: `api/speak.py` calls Python KERNEL
and CMD, then passes the intermediate state to `_capi` for LTS, PH,
VTM, and synth.

This requires `_capi` to expose pipeline-stage entry points:
`_capi.kernel(text) -> tokens`, `_capi.cmd(tokens) -> command_stream`,
`_capi.lts(command_stream) -> phonemes`, etc. Adding these is part
of A.4's dump-hook work — both share the same boundary-instrumentation
infrastructure.

### Phase D — Translate LTS/ and dic/ (≈4–5 weeks)

D.1 **dic/ (≈1 week)**

The dictionary loader and the US text file `dtalk_us.dic`. The data
file is already vendored in the Python project at
`src/dectalk/data/dic/`. The loader translation is small (~500
lines of C). Parity test: `_capi.lookup("hello")` == `dictionary.
lookup("hello")` for every word in the dic.

D.2 **LTS/ engine + tables (≈3–4 weeks)**

119 files. ~60 of them are language-specific (US) rule tables;
the rest is the rule engine.

Order:

1. The rule **engine** (`/tmp/dectalk-src/src/dapi/src/lts/lts_main.c`
   and friends) — ~10 files.
2. The **rule tables** for US English — ~50 files, each is
   essentially a giant C struct array. These are embarrassingly
   parallel: dispatch one batch of agents, each handling 10 files.

Parity gate per file: `_capi.lts(token_stream) == python.lts.
apply(token_stream)` byte-for-byte over a corpus.

D.3 **Wire LTS+dic into `api/speak.py` end-to-end via Python.**

Now the pipeline is: Python KERNEL → Python CMD → Python LTS+dic →
`_capi.ph(...)` → `_capi.vtm(...)` → `hlsyn.synthesize(...)`.

End-to-end binary-WAV parity test from B.3 must still pass.

### Phase E — Translate PH/ and VTM/ (≈4–6 weeks)

The hard one. PH controls prosody (durations, F0 contours, stress),
VTM converts phonemes + prosody into Klatt frames.

E.1 **PH/ (≈3–4 weeks)**

104 files. The hot files:

- `ph_inton2.c` (~2080 lines) — F0 contour and intonation gestures
- `p_us_tim.c` (~1300 lines) — duration rules
- `p_us_st1.c` (~1500 lines) — stress assignment
- `p_us_sy1.c` (~170 lines) — syllabification
- `p_us_vdf*.c` (~7K lines combined) — US voice-definition tables
- ~40 more files implementing the impulse/step/glide F0 command
  system, allophone substitution, foot/syllable structure.

The audit at `docs/c_audit/prosody.md` is a Phase-3 reading guide
for `ph_inton2.c` and the timing files; reuse it.

E.2 **VTM/ (≈2 weeks)**

35 files. Converts phoneme + prosody plan into Klatt frame
trajectories. Currently a 4-line stub in Python — full translation
needed.

E.3 **Wire PH+VTM through Python end-to-end.**

Pipeline becomes fully Python from text through Klatt frames; only
`hlsyn/` (already faithful) remains untouched.

End-to-end binary-WAV parity test: now we're testing a fully
Python pipeline against the binary. If anything is misaligned this
is where it surfaces.

### Phase F — Remove ctypes scaffold + final API (≈1 week)

F.1 **Translate API/ (≈3–5 days).**

The `api/` C files (`TTSAPI.H`, `ttsapi.c`, `init.c`, `crypt2.c`,
`decstd97.c`) provide the public entry points and lifecycle. Most
of this is already shimmed in Python; rewrite to match C's
behaviour for command-line flags, error codes, voice presets, and
the speak-while-streaming interface.

F.2 **Delete `src/dectalk/_capi/`.**

`libtts_us.so` is no longer needed at runtime. The package becomes
pure Python. The Phase A dump hooks and parity infrastructure are
kept for regression-testing.

F.3 **End-to-end parity gate against an expanded corpus.**

Beyond the 7 sample prompts:

- All 9 voice presets (Perfect Paul, Beautiful Betty, …).
- Harvard sentences (50–100 phrases).
- Edge cases: numbers, dates, abbreviations, URLs, mixed
  punctuation, command syntax (`[:rate 250][:dv ap 110] text`).

Every input must produce a byte-identical WAV to the binary. Any
divergence is a bug to chase.

## Critical files

C source (read-only references on develop branch):

- `/tmp/dectalk-src/src/dapi/src/include/*.h`
- `/tmp/dectalk-src/src/dapi/src/kernel/*.c`
- `/tmp/dectalk-src/src/dapi/src/cmd/*.c`
- `/tmp/dectalk-src/src/dapi/src/lts/*.c` (+ rule tables)
- `/tmp/dectalk-src/src/dapi/src/dic/*` (+ `dtalk_us.dic`)
- `/tmp/dectalk-src/src/dapi/src/ph/*.c` (specifically the US-tagged
  files plus the engine: `ph_inton2.c`, `p_us_*`)
- `/tmp/dectalk-src/src/dapi/src/vtm/*.c`
- `/tmp/dectalk-src/src/dapi/src/api/*.{c,h}`
- The shipped binary: `/tmp/dectalk-binary-stable/say` — ground
  truth for the WAV parity gate.

Python — new during this port:

- `src/dectalk/_capi/` — ctypes wrapper around `libtts_us.so`
  (deleted in Phase F)
- `src/dectalk/include/` (rewritten in Phase C.1)
- `src/dectalk/kernel/` (Phase C.2)
- `src/dectalk/cmd/` (Phase C.3)
- `src/dectalk/lts/` (Phase D)
- `src/dectalk/dic/` (Phase D)
- `src/dectalk/ph/` (Phase E.1)
- `src/dectalk/vtm/` (Phase E.2)
- `src/dectalk/api/` (rewritten in Phase F.1)
- `tests/parity/c_harness/dump_hooks.patch` — C-source patch
  series adding per-module dump output
- `tests/parity/test_<module>_parity.py` (per module)
- `tests/parity/test_binary_wav_parity.py` — end-to-end goalpost
- `scripts/verify_source_matches_binary.py` (Phase A.3)

Python — preserved as-is:

- `src/dectalk/hlsyn/` — already bit-accurate
- `src/dectalk/nt/` — audio I/O
- `tests/parity/test_synth_parity.py`

Python — deleted in Phase B:

- `src/dectalk/{kernel,lts,dic,ph,cmd,vtm}/` (the approximations)
- `tests/unit/test_{prosody,lts*,dic*,kernel*,cmd*}.py`

## Verification

The plan's success metric is binary: `dectalk.speak(text)` produces
a WAV byte-identical to `say -a text -fo out.wav` from the binary
for every input in the test corpus, on every phase that touches
end-to-end audio.

Per-phase verification:

- **Phase A**: `libtts_us.so` builds; `_capi.speak("hello world")
  == binary("hello world")` byte-for-byte. Dump hooks emit
  parseable intermediate state.
- **Phase B**: After tear-down, `dectalk.speak(text)` still
  byte-matches the binary because it routes through `_capi`.
- **Phase C/D/E/F**: After each module is translated, the per-module
  parity test passes on the documented corpus AND the end-to-end
  binary-WAV parity test passes.
- **Final**: end-to-end parity holds across an expanded corpus
  (9 voices × ~100 prompts × edge cases). The `_capi` directory is
  gone; `pip install dectalk-python` produces a package with no
  native dependency.

## Risks and open questions

1. **Source-vs-binary commit drift**. Develop HEAD may not be the
   exact commit the shipped binary was built from. If `_capi.speak`
   != `binary.say` in Phase A.3, we need to bisect develop. The
   binary's `strings` output mentions `6.2.0-1015-azure`; that
   string may correlate to a release tag or a CI run number we can
   locate in the repo.

2. **Floating-point determinism**. C compiled with `-O2` and Python
   with NumPy float64 may differ in tiny ways (FPU rounding mode,
   order of operations). If WAV bit parity fails by 1 LSB on
   isolated samples, we need to investigate whether the C build is
   even deterministic across compilers (gcc vs clang).

3. **Pointer arithmetic / signed-int wraparound in C**. The C source
   uses platform-dependent C idioms in places. Faithful translation
   may require explicit modular arithmetic in Python (e.g. `np.int16`
   wraparound rather than Python's unbounded int). Each such case
   gets a comment.

4. **Build dependencies**. autoconf-based build on the local Linux
   host may need packages we don't have. Docker fallback is
   available but adds friction.

5. **Effort estimate**. 3–5 months is realistic for US-English-only.
   If LTS rule-table translation is fully parallelisable across
   translator agents (it likely is), this could compress; if PH's
   impulse-driven F0 system has hidden dependencies on undocumented
   feature bits, this could expand. Phase E is the schedule-critical
   path.

6. **Proprietary FONIX licensing stubs**. `api/crypt2.c` and
   `api/decstd97.c` may implement license checks. The user has
   acknowledged the proprietary status of the source; we may need
   to stub or skip these for a usable end state.

---

# (Superseded) Align Python port prosody with DECtalk C source

## Context

The Python output sounds unnatural compared to the binary, even after
recent prosody widening (declination 1.20 → 0.78, ±18 % stress accent).
A side-by-side listen on `docs/audio_samples/*.python.wav` vs
`*.binary.wav` shows the binary has more lifelike rhythm and pitch
movement: F0 std on "hello world" measures 13.5 Hz in Python vs 56 Hz
in the binary, and the binary's contour shape is clearly piecewise (sharp
initial rise → declination → sharp terminal dip), not the linear
ramp Python uses.

Earlier scoping assumed the FONIX C source was inaccessible — only the
Klatt synthesizer's inner loop (under `tests/parity/c_harness/`) and
the public headers under `/tmp/dectalk-binary-stable/` were readable.
The user pointed at three additional source archives:

- `https://github.com/dectalk/dectalk/tree/master/src/dapi/srcold/`
- `https://datajake.braillescreen.net/TTS/DECtalk/SourceCodeArchive/`
- `https://github.com/RetroBunn/dt51`

Verified via WebFetch: github.com/dectalk/dectalk has the **full
original C tree** at `src/dapi/srcold/` with the modules `API/ CMD/
INCLUDE/ KERNEL/ LTS/ NT/ PH/ PROTOS/ VTM/ dic/ hlsyn/`. The PH/
directory contains 143 files including `Ph_inton2.c` (intonation),
`p_us_vdf_tune.c` + `_tunehl.c` + `_tuneint.c` (US prosody tuning
constants), `p_us_tim.c` (duration tables), `P_us_ST1.C` (stress
assignment), `P_us_SY1.C` (syllabification). This is the data we need
to align Python with C.

The user also asked for a comma to be added to the 3-sentence test
prompt so the harness exercises clause-internal short-pause prosody
in addition to sentence-final long-pause prosody.

## Scope

Document all observable C-vs-Python differences; land code changes
only for prosody, where the audible gap lives. The synthesizer
back-end (`hlsyn/`) is already bit-accurate to the C harness via
`tests/parity/test_synth_parity.py`, so the audit payload is the
front end (text → tokens → phonemes → prosody → frames). Allophonic
expansion of `phoneme_frames.py` is held as an optional follow-up.

## Approach

### Phase 0 — Trivial fix bundled in (≈1 minute)

Add a comma inside the multi-sentence prompt in
`scripts/diagnose_audio.py:DEFAULT_PROMPTS`:

```
- "good morning. how are you today? have a great day!"
+ "good morning, my friend. how are you today? have a great day!"
```

The slug, README table, and `docs/audio_samples/` filenames update
on the next harness run.

### Phase 1 — C source acquisition (≈10 minutes)

Clone `github.com/dectalk/dectalk` shallowly to `/tmp/dectalk-src/`.
Verify presence of `src/dapi/srcold/{PH,KERNEL,LTS,dic,INCLUDE}/`.
If the official repo is incomplete or has a missing branch, fall
back to `github.com/RetroBunn/dt51` (DECtalk 5.1) or the datajake
archive. The clone is not committed; it lives in `/tmp` and the
audit references it by absolute path.

### Phase 2 — Spectrogram comparison harness (≈2-3 hours)

Build the quantitative tool that lets us measure "how close is Python
to the binary" so the rest of the plan has a numeric gate to land
against. Goal stated by the user: spectrogram output from ~500 ms
chunks should be nearly identical.

**Algorithm**

1. Render Python and binary audio for the same prompt (already done
   by `scripts/diagnose_audio.py`; reuse those .wav files when
   present).
2. Both outputs are mono 11025 Hz int16. Convert to float32 in
   [-1, 1].
3. STFT both: 512-sample Hann window (≈46 ms), 128-sample hop
   (≈12 ms). Compute magnitude.
4. Apply a 64-band mel filterbank (80–5500 Hz, perceptually weighted
   for the speech band), then take log → log-mel spectrogram with
   shape `(frames, 64)`.
5. **Time-align** with DTW on log-mel frames. The two recordings have
   different durations (different prosody, different phoneme
   timings), so a raw chunk-by-chunk comparison is dominated by drift
   rather than acoustic difference. Use a Sakoe-Chiba band of ±20 %
   to forbid pathological warps. The DTW total cost / path length
   gives a single global similarity number for free.
6. **Chunk** the warped pair into 500 ms chunks (configurable via
   `--chunk-ms`). For each chunk compute:
   - **MCD (mel-cepstral distortion)** in dB — the standard TTS
     comparison metric. ~6.5 dB is the literature threshold for
     human-perceptible difference; <4 dB is "very close".
   - **Log-spectral distance (LSD)** in dB — alternative cross-check.
   - **Spectral correlation** in [0, 1] — direction-invariant
     similarity.
   Report mean / p50 / p95 across chunks plus the per-chunk
   distribution.

**Why 500 ms by default**

Roughly two-syllable scale, so it's sensitive to local prosody and
phoneme timing without being so short that a single phoneme boundary
disagreement dominates the metric. We expose `--chunk-ms` so the user
can re-bucket without re-rendering. 250 ms is more phoneme-scale,
1000 ms is more phrase-scale; 500 ms is the right default for the
"rhythm and accent" question.

**Implementation layout**

- `tests/parity/_spectrogram_compare.py` — pure functions: STFT,
  mel filterbank, log-mel, DTW (Sakoe-Chiba band-constrained),
  MCD/LSD/correlation, chunk metrics. Self-contained on numpy +
  scipy (already deps). No librosa.
- `scripts/diagnose_audio.py` — gains `--binary <path>` flag. When
  set, after rendering Python audio it shells out to the binary,
  runs the comparison, and adds a **Comparison** section per prompt
  to `docs/audio_samples/report.md`:
  - global DTW cost
  - mean MCD, per-chunk MCD distribution
  - per-chunk PASS/FAIL against the threshold
  - link to the spectrogram PNG
- Per prompt, write `docs/audio_samples/comparisons/{slug}.spec.png`
  — three stacked panels (Python log-mel, binary log-mel, |diff|),
  shared x-axis on warped time. Uses matplotlib (add to dev-deps in
  `pyproject.toml [project.optional-dependencies] dev` if not
  present).
- Per prompt, write `docs/audio_samples/comparisons/{slug}.json` —
  machine-readable metrics for regression-tracking and future CI
  thresholds.

**Calibration**

Run the harness once before any prosody alignment to capture the
**baseline** (current state) numbers. Self-test by feeding identical
audio in (binary vs itself) — MCD must be ≈ 0 dB. Then on the real
prompts, set the initial gate threshold from baseline + headroom:

- Initial pass: mean MCD < (baseline mean + 1 dB) — i.e. don't
  regress.
- Target after Phase 4 (prosody alignment): mean MCD < 5 dB,
  per-chunk p95 MCD < 8 dB across all 7 prompts.

The thresholds are placeholders; the real numbers come out of the
baseline run. We may discover the binary itself isn't deterministic
or has dithering noise that floors MCD around some non-zero value —
in which case the threshold floats up.

**Limits**

- DTW alignment can mask gross duration errors; report the warp-path
  ratio so any duration that drifts by >25 % is visible.
- The harness cares about acoustic similarity, not naturalness. A
  perfectly-cloned binary output is naturally identical, but two
  syntheses can be subjectively similar with high MCD if formant
  positions disagree systematically. The PNG visualisation is the
  human cross-check.

### Phase 3 — Module audit (≈2-3 hours of orchestrator time)

Write side-by-side C-vs-Python audit reports under `docs/c_audit/`,
one per Python module. Each report has three sections: **what the C
does**, **what the Python does**, **deltas ranked by audibility**.

- `docs/c_audit/prosody.md` — compares `src/dectalk/ph/prosody.py`
  against `PH/Ph_inton2.c`, `PH/p_us_vdf_tune*.c`, `PH/p_us_tim.c`,
  `PH/P_us_ST1.C`, `PH/P_us_SY1.C`. Calls out:
  - Declination magnitudes and contour shape (linear vs piecewise)
  - Stress accent multipliers (primary / secondary / unstressed)
  - Per-phoneme-class duration multipliers
  - Question vs statement terminal contour (last-syllable rise vs
    last-foot rise)
  - Phrase / clause-comma pause behaviour
  - Foot-based vs phoneme-based contour structure
- `docs/c_audit/phoneme_frames.md` — compares
  `src/dectalk/ph/phoneme_frames.py` (41 codes) against the C
  voice-definition tables in `PH/p_us_vdf*.c` (US_TOT_ALLOPHONES =
  71 per `l_us_ph.h`). Identifies allophonic variants we're missing
  (DX, EL, EN, IX, RX, LX, AR, OR, UR, IR, Q, etc.).
- `docs/c_audit/kernel.md` — compares `src/dectalk/kernel/text.py`
  and `kernel/normalize.py` against `KERNEL/usa.c`. Sentence
  segmentation, abbreviation tables, number-to-words.
- `docs/c_audit/lts.md` — compares `src/dectalk/lts/rules_us.py`
  against the C `LTS/` rule tables.
- `docs/c_audit/dic.md` — confirms lexicon parity (stress-digit
  conventions, coverage of common words).
- `docs/c_audit/synthesizer.md` — short summary referencing the
  existing `tests/parity/test_synth_parity.py` results; notes any
  outstanding drift (LF source, etc.) without action items.

Audit only — no code changes in this phase.

### Phase 4 — Prosody alignment (≈2-3 hours)

Pull the C declination, stress, and duration constants into
`src/dectalk/ph/prosody.py`:

1. Replace the linear declination shape with the C's piecewise
   contour from `Ph_inton2.c`. Likely structure: a brief initial
   rise to a peak, then linear / log-linear fall, then a final-foot
   dip. Implement as a piecewise-defined function of utterance
   position rather than a straight lerp.
2. Replace the per-stress F0 multipliers with the C's tuned values
   from `p_us_vdf_tuneint.c`. The current ±18 % / ±6 % / ±8 %
   numbers are pragmatic guesses; the C side has calibrated values.
3. Replace the per-stress duration multipliers with the C's values
   from `p_us_tim.c`, applied per phoneme class (vowel / stop /
   fricative / nasal / liquid) rather than uniformly per stress.
4. If `Ph_inton2.c` operates over feet or syllables (likely),
   refactor `f0_contour()` to walk syllables rather than raw
   phonemes. The current implementation puts the same multiplier on
   every phoneme of a vowel-bearing syllable, which is fine, but a
   foot-level contour shape needs foot boundaries.

Keep the public API of `prosody.py` unchanged so the rest of the
pipeline (sequencer, speak) stays intact.

### Phase 5 — Allophonic alignment (optional, ≈2-3 hours)

Only if Phase 4 doesn't close the audible gap measured by Phase 2's
MCD harness. Add the most-audible 2-3 missing allophones to
`phoneme_frames.py` (likely DX flap, EL/EN syllabic, IX/AX reduced)
and add LTS rules to map common contexts to them. Bigger surface
area, more risk; gated on Phase 4 outcome.

### Phase 6 — Tests + verification

- `tests/unit/test_prosody.py` — relax / update value-specific
  assertions to match the new contour shape. Direction-only
  assertions (`test_statement_contour_falls`,
  `test_question_contour_rises`) stay. The dynamic-range test
  bumps to whatever the new shape produces (target ≥ 0.40 if Phase
  4 lands).
- Add a regression test asserting F0 std on "hello world" exceeds
  a threshold (e.g. > 25 Hz) so future changes can't accidentally
  re-flatten the contour.
- Add `tests/parity/test_spectrogram_compare.py` covering the new
  comparison module: identical-input MCD ≈ 0; DTW alignment cost
  monotonic in injected delay; chunk-metric shape matches expected
  `(n_chunks, n_metrics)`.
- Run `scripts/dev_check.sh` (lint + format + pyright + pytest).
- Regenerate `docs/audio_samples/` with the comparison harness on
  and confirm `docs/audio_samples/report.md` says PASS for all 7
  prompts on the **baseline** gate (don't regress); mean MCD
  improves from baseline after Phase 4 lands.
- Side-by-side listen of the audio samples (user-driven, since
  "natural sound" can't be unit-tested).

## Critical files

C source (read-only refs after `git clone` to /tmp):
- `/tmp/dectalk-src/src/dapi/srcold/PH/Ph_inton2.c`
- `/tmp/dectalk-src/src/dapi/srcold/PH/p_us_vdf_tune.c`,
  `_tunehl.c`, `_tuneint.c`
- `/tmp/dectalk-src/src/dapi/srcold/PH/p_us_tim.c`
- `/tmp/dectalk-src/src/dapi/srcold/PH/P_us_ST1.C`,
  `P_us_SY1.C`
- `/tmp/dectalk-src/src/dapi/srcold/INCLUDE/p_us_ph.h`
- `/tmp/dectalk-src/src/dapi/srcold/KERNEL/usa.c`
- `/tmp/dectalk-src/src/dapi/srcold/LTS/lts_us*.c`

Python files added:
- `tests/parity/_spectrogram_compare.py` — STFT, mel filterbank,
  DTW alignment, MCD/LSD/correlation, chunked metrics
- `tests/parity/test_spectrogram_compare.py` — unit coverage of
  the comparison module
- `docs/c_audit/*.md` — audit reports (one per module)

Python files modified:
- `src/dectalk/ph/prosody.py` — primary alignment target
- `scripts/diagnose_audio.py` — comma in the 3-sentence prompt;
  new `--binary <path>` flag wiring up the comparison harness
- `tests/unit/test_prosody.py` — assertions updated for new shape
- `docs/audio_samples/README.md` — slug table updated for the
  comma-prompt rename + comparison columns
- `pyproject.toml` — add matplotlib to `[project.optional-dependencies] dev` if not already present

Python files read-only:
- `src/dectalk/ph/phoneme_frames.py`, `ph/sequencer.py`
- `src/dectalk/kernel/*.py`, `lts/*.py`, `dic/*.py`,
  `api/speak.py`

Output artefacts:
- `docs/audio_samples/comparisons/{slug}.spec.png` — three-panel
  spectrogram comparison per prompt
- `docs/audio_samples/comparisons/{slug}.json` — machine-readable
  per-prompt metrics
- `docs/audio_samples/comparisons/baseline.json` — captured before
  Phase 4 so the delta is visible

## Verification

1. `scripts/dev_check.sh` passes (ruff lint + format + pyright +
   261-test suite still green).
2. `scripts/diagnose_audio.py --out-dir docs/audio_samples` reports
   overall PASS for all seven prompts (including the comma'd
   3-sentence one).
3. Quantitative — local prosody: F0 std on "hello world" climbs
   from 13.5 Hz to > 25 Hz; on "the quick brown fox" the contour
   dynamic range exceeds 0.40 (currently 0.31).
4. Quantitative — acoustic similarity to binary: mean MCD across
   all 7 prompts < 5 dB after Phase 4; per-chunk p95 MCD < 8 dB;
   no prompt regresses against its Phase 2 baseline. Per-prompt
   spectrogram PNGs under `docs/audio_samples/comparisons/` show
   visibly closer formant tracks and pitch contours after Phase 4
   than at baseline.
5. Audit reports under `docs/c_audit/` document every reviewed
   module — including ones we don't change — so a follow-up
   engineer has the full inventory.
6. Subjective: a human-driven listen of
   `docs/audio_samples/*.python.wav` vs `*.binary.wav` confirms
   the rhythm and accent gap has narrowed. Final acceptance is the
   user's ear; numeric tests can prevent regression but not certify
   "natural sound."

If Phase 4 doesn't close the gap measured by the Phase 2 harness,
Phase 5 (allophonic expansion) is the escape hatch. If neither
does, the audit documents what's left and we treat it as known
scope for a future phase rather than blocking on it.

---

# (Completed) Diagnose and fix static-y artefacts in `dectalk "hello world"`

## Context

The Python port produces audible static-y noise during voiced segments of
"hello world" after the prosody-smoothing fix. The previous diagnostic
(`scripts/dev_check.sh` + the parity tests) didn't catch this because:

- LLSynthesize parity tests check single hand-crafted *static* frames, never
  cross-phoneme transitions.
- The tokenizer/lexicon/prosody tests check structural properties, not
  audio quality.
- The binary-parity tests only assert "non-empty audio of comparable
  duration" — they don't compare waveform shape.

A spot diagnostic showed:

- Voiced-segment spectral peaks land where expected (~624 Hz close to F1).
- Noise floor at 4–5.5 kHz is essentially zero (no high-band hiss).
- **But** within-pulse residual (after fitting a smooth polynomial) gives
  ≈0.9 dB SNR — i.e. the per-pulse waveform shape doesn't match a clean
  glottal pulse. Either there's mid-band noise being injected, or the
  shape is being polluted by something the polynomial fit can't model.

The most likely root cause is frame-field interpolation. The sequencer
linearly interpolates **every** `LLFrame` field across the first 50 % of
each phoneme segment. For formant frequencies and AV that's musically
correct, but the *noise-source amplitudes* (`Af`, `Ah`, `A2f`..`A6f`,
`Ab`) are *sources*, not filters — interpolating them between a fricative
(e.g. HH with `Af=60`) and a vowel (`Af=0`) produces partial frication
during the voiced onset, which is broadband noise audible as static.

We need a thorough audio-diagnostic harness before changing any
synthesis code so we can:

1. confirm/reject the interpolation hypothesis with measurements,
2. surface other latent issues we haven't noticed yet,
3. compare quantitatively to the user-supplied DECtalk 4.61 Linux binary
   (the "right answer") and treat large divergences as bugs to fix.

The original full-port plan below is preserved (the scope and stack
choices remain in effect). The new work is a polish phase that runs
inside the existing project.

## Approach

### Step 1 — Build a comprehensive audio-diagnostic harness

Create `scripts/diagnose_audio.py` that runs a battery of tests on a set
of fixed prompts and writes a single human-readable report to stdout
plus per-prompt artefacts under `/tmp/dectalk-diag/`. Tests:

1. **Binary reference**. Run `/tmp/dectalk-binary-stable/say -a "<text>" -fo …`
   for each prompt to produce reference WAVs at 11025 Hz mono int16. Skip
   gracefully when the binary isn't present (env var
   `DECTALK_BIN_DIR` overridable).

2. **Python rendering**. Run `dectalk.speak(text)` for the same prompts
   and write WAVs to the same directory.

3. **Quantitative comparison metrics** (Python vs binary), per prompt:
   - Length ratio (binary samples / python samples).
   - Per-window RMS curve correlation (200-ms hanning windows).
   - Spectrogram cosine similarity (per time bin, 512-sample FFT,
     log-power).
   - Pitch-track correlation via `librosa.yin` if available, else a
     simple autocorrelation-based estimator.

4. **Intrinsic signal quality** on the Python output:
   - **Within-pulse residual**. Detect glottal-pulse onsets via
     state.pulse-style autocorrelation; for each cycle, fit the Klatt
     polynomial `2t − 3t²/T` (or KLGLOT88 source) plus a low-order
     correction term; report median residual / signal RMS in dB. A
     clean Klatt vowel should be > 20 dB.
   - **Frame-boundary discontinuity scan**. Walk the prosody plan,
     evaluate the frame at each phoneme-boundary sample, and compute
     the L1 distance between consecutive evaluated frames. Surface
     boundaries where any single field changes by > X (configurable).
   - **Per-field interpolation audit**. For each field of `LLFrame`,
     synthesise a two-phoneme test (HH→AH, S→AH, T→AH, P→AH) with all
     other fields held constant; measure the in-band noise during the
     supposedly-voiced second half. Reports which fields cause
     audible noise when interpolated.
   - **Soft-limiter activation log**. The sequencer's
     `_soft_normalize` path scales the whole utterance when the peak
     exceeds `_TARGET_PEAK_INT16`. Whether it triggered, and the
     applied gain, are reported.

5. **Acceptance summary**: a single block per prompt with PASS/FAIL
   tags for each metric and a short diagnosis line ("F0 contour 6 %
   higher than binary throughout", "frication noise leaks into AH for
   first 80 samples", etc.).

   Output also written to `docs/diagnostic_report.md` so reviewers can
   eyeball it in the repo.

The harness lives in `scripts/`, not `tests/`, because it's a
researcher's tool that runs slowly and produces a report rather than
asserting facts. The existing `tests/parity/` suite stays as the
machine-checkable contract.

### Step 2 — Fix root causes the harness identifies

Hypothesis-driven fixes; only land if the harness numbers improve.

**Most likely fix — partition `_interpolate_frame` by field semantics**

In `src/dectalk/ph/sequencer.py`, classify each LLFrame field:

- *Smooth-interpolate* (current behaviour): `F1`–`F6`, `B1`–`B6`,
  `DF1`/`DB1`, `FNP`/`BNP`/`FNZ`/`BNZ`/`FTP`/`BTP`/`FTZ`/`BTZ`,
  `F0`, `OQ`, `SQ`, `TL`, `FL`.
- *Snap-to-target*: noise sources whose presence is qualitative —
  `Af`, `Ah`, `A2f`–`A6f`, `Ab`. Mid-transition values for these
  amplitudes mean "half-frication", which doesn't correspond to any
  natural-speech state.
- *Snap on entry, smooth on exit*: `AV` and the parallel-voicing amps
  `ANV`/`A1V`–`A4V`/`ATV`. Going into voicing, voicing should ramp up
  smoothly so the first cycle isn't a click; going out of voicing,
  hard-snap to zero so the cycle doesn't keep ringing.

Possible *second* fix — split the transition window so noise sources
snap at the boundary (alpha < 1.0) while filters interpolate. Same
mechanism, different parameter.

**Other plausible fixes** (only land if the harness implicates them):

- Reset parallel-formant resonator state when transitioning from a
  fricative to a vowel (otherwise the parallel-F4–F6 resonators carry
  HH excitation into AH).
- Reset the LCG noise seed at voiceless→voiced boundaries to avoid the
  aspiration first-difference producing a step at the boundary.
- Re-compute the prosody contour to taper voicing amplitude (not just
  F0) over the start/end of the utterance.

### Step 3 — Add regression tests covering whatever shipped

The diagnostic harness produces numbers; one or two of them should
become assertions in `tests/unit/`:

- A new `tests/unit/test_no_static.py` asserting that within-pulse
  residual SNR for a fixed-vowel-after-fricative phrase is above some
  threshold (e.g. ≥ 20 dB).
- A new entry in `tests/parity/test_binary_parity.py` asserting
  spectrogram cosine similarity ≥ a threshold against the binary for
  "hello world" specifically.

Choose thresholds based on what the diagnostic reports for the *fixed*
implementation, not aspirational numbers; we want a tight regression
backstop, not a flake source.

## Critical files

Read-only references:

- `src/dectalk/ph/sequencer.py` — frame interpolation lives in
  `_interpolate_frame()` and `_render_segment()`.
- `src/dectalk/ph/phoneme_frames.py` — phoneme→frame target table; the
  per-phoneme `Af`/`Ah`/`A_F` values originate here.
- `src/dectalk/ph/prosody.py` — F0 contour (just changed, may need
  re-tuning if the harness suggests it).
- `src/dectalk/hlsyn/sample.py` and `synthesize.py` — synth core; the
  parity tests already validate this matches C, so unlikely to need
  changes.
- `tests/parity/test_binary_parity.py` — existing binary-comparison
  scaffolding to extend.
- `/tmp/dectalk-binary-stable/say` — the user-uploaded DECtalk 4.61
  Linux binary.

Files this plan adds:

- `scripts/diagnose_audio.py` — the new harness.
- `docs/diagnostic_report.md` — the harness's output, committed for
  the reviewer's convenience.
- `tests/unit/test_no_static.py` — regression test.

Files this plan likely modifies:

- `src/dectalk/ph/sequencer.py` — split `_interpolate_frame` into
  smooth vs. snap fields.
- `src/dectalk/ph/phoneme_frames.py` — small amplitude tweaks if
  needed.

## Verification

The diagnostic harness *is* the verification. Concrete pass criteria:

1. `uv run python scripts/diagnose_audio.py` writes a report where
   every prompt is tagged PASS for: within-pulse residual ≥ 20 dB,
   spectrogram cosine similarity ≥ 0.5 against the binary, no soft
   limiter triggers.
2. `scripts/dev_check.sh` stays green (≥ 253 unit/integration tests
   plus the new regression).
3. `uv run python -m dectalk "hello world" -o /tmp/x.wav` plus a
   manual listen — no audible static, no choppiness.
4. CI is green on Linux/macOS/Windows × Py 3.11/3.12/3.13, and the
   workflow uploads the diagnostic-harness WAVs (Python output + the
   binary's reference output where available) as a downloadable
   artifact for human listening.

Fixes are *not* shipped if the harness regresses on any prompt; if a
fix improves "hello world" but regresses "she sells sea shells",
investigate before merging.

## Test artifacts

The diagnostic harness writes WAVs to `/tmp/dectalk-diag/` by default
but accepts `--out-dir` so CI can route them to a stable directory.

`scripts/diagnose_audio.py --out-dir artifacts/audio --report
artifacts/audio/report.md` is invoked from a new CI step. The CI
workflow then uses `actions/upload-artifact@v4` to publish:

- `artifacts/audio/<prompt-slug>.python.wav` — Python `speak()` output.
- `artifacts/audio/<prompt-slug>.binary.wav` — DECtalk-binary output
  (only on Linux runners where the binary is available; the binary
  file isn't bundled in the repo).
- `artifacts/audio/report.md` — the human-readable report.

The DECtalk binary release lives outside the repo; CI fetches it on
the Linux runner only via a small step that downloads the release
zip the user uploaded earlier (or skips with a notice if unreachable).

## CI failure fixes

The user reports CI is currently failing. Plausible root causes
identified by reading the workflow and tree:

1. **Stale Linux ELF in `tests/parity/c_harness/llsyn_dump`**
   committed to git. The parity conftest checks
   `HARNESS_BINARY.exists()` *before* trying to compile, so on
   macOS/Windows runners it will try to `subprocess.run()` a Linux
   ELF binary and fail.

   Fix: add `tests/parity/c_harness/llsyn_dump` to `.gitignore`,
   `git rm --cached` it, and update `conftest.py` to invalidate the
   cached binary if it isn't executable for the current platform
   (e.g. by adding `os.access(p, os.X_OK)` and a platform check).

2. **C harness build fails on Windows runners** (no `gcc`/`cc` in
   PATH; `cl.exe` from MSVC isn't tried). Fix: extend `_which_cc()`
   to also find `cl.exe` and switch the build command accordingly,
   or skip cleanly with a clear message and tag the test
   `pytest.mark.skipif(sys.platform == "win32")`.

3. **Bundled large lexicon files might trip pre-commit's**
   `check-added-large-files` (limit 500 kB). The full DECtalk
   dictionaries are ~600 kB. Fix: bump the limit in
   `.pre-commit-config.yaml` to 2 MB, or split the lexicons into
   smaller compressed assets.

4. **`sounddevice` import on headless CI runners**. Our `nt/audio.py`
   imports it lazily inside `play()` so module import alone doesn't
   trigger it; CI never calls `play()` because we use `--write-test`
   for the smoke test. This should already be fine, but worth
   confirming once the other fixes land.

5. **Python 3.13 + numpy/scipy wheels** — both have prebuilt 3.13
   wheels at versions we depend on, so this should be a non-issue.
   Confirm by reading the failed run logs after the other fixes
   land.

6. **The just-pushed prosody change** added `from itertools import
   pairwise` inside a test, which requires Python 3.10+ — within
   our 3.11 floor, so fine. But the test does `import dectalk`
   inside the test function which works but is unusual; if pyright
   strict flags `reportImportCycles` we move it to module scope.

The plan is to land these fixes in the same PR as the diagnostic
harness, in the order: gitignore + cached-binary fix → CI artifact
upload → harness wiring → audio fixes.

---

## Original full-port plan (preserved — superseded for status; see `docs/STATUS.md`)

## Original Context

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
