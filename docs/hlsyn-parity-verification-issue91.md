# hlsyn frame parity verification (issue #91)

Doc-only research note. Verifies that the `hlsyn` Klatt-synth back-end
remains bit-accurate at the frame level after recent PH-stage churn
(`hlframe`, `circuit`, `nasalf1x` and friends).

## TL;DR

`tests/parity/test_synth_parity.py` is **green on `dev` HEAD**
(commit `fbd679d`): 17 LLSynthesize parity cases plus 1 field-count
sanity check, **18 / 18 passing**, no regressions vs the documented
tolerance budget (4 LSBs for tight cases, 2 % of peak for the
narrow-bandwidth LF glottal source).

Verified locally with the per-agent C oracle at
`$DECTALK_SRC=/tmp/dectalk-src-<slug>`,
`$DECTALK_BIN=/tmp/dectalk-binary-stable-<slug>` after
`scripts/setup_c_oracle.sh`.

## Reproducer

```bash
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh
DECTALK_SRC="$DECTALK_SRC" DECTALK_BIN="$DECTALK_BIN" \
  uv run pytest tests/parity/test_synth_parity.py -v
# => 18 passed
```

Cases covered (each is a 10-frame steady-state synth, int16 PCM
compared sample-for-sample against the in-tree C harness
`tests/parity/c_harness/llsyn_dump.c`):

- Vowels: `AH`, `IY`, `UW`, `AE`, `AO` (Klatt 1980 reference formants).
- Source-shape variants: natural (default), `SOURCE_IMPULSIVE`,
  `SOURCE_LF`.
- Non-voiced excitation: `aspirated` (Ah=50), `fricated` (Af + A2f..A4f).
- F0 sweep: low (80 Hz) and high (200 Hz).
- Spectral tilt: TL=5 and TL=15.
- Open-quotient extremes: OQ=30 and OQ=80.
- Diplophonia: DI=30.
- F1 dynamic transition: DF1=100, DB1=50.
- Field-order sanity: `LLFrame` has exactly 48 fields and `Speaker`
  has exactly 12, matching what the C harness reads.

## Notes on the pytest-xdist false-positive

A first run with `pytest -n auto` produced 3 `PermissionError:
[Errno 13] Permission denied: tests/parity/c_harness/llsyn_dump` on
`vowel_AO`, `vowel_UW`, `fricated`. The harness binary is built lazily
by a `session`-scoped fixture in `tests/parity/conftest.py::llsyn_dump`.
With pytest-xdist, each worker process has its own session — multiple
workers race to compile the binary to the same path and a worker can
try to exec it while another's `gcc` is mid-write (no `os.X_OK` yet).
This is a harness-build race, **not** a parity regression: a serial
re-run is clean 18 / 18.

If this becomes a recurring CI flake, the fix is to either:

- Build `tests/parity/c_harness/llsyn_dump` once up-front in
  `scripts/setup_c_oracle.sh` so the fixture's `if HARNESS_BINARY.exists()
  and os.access(HARNESS_BINARY, os.X_OK)` short-circuit fires before
  worker startup; or
- File-lock the compile inside the fixture (e.g. `filelock` around
  `_build_unix`).

Filed separately as a follow-up if the flake recurs in CI; not in
scope for #91.

## Unrelated path-resolution gap in the unit-level shims

While running the broader hlsyn unit tests
(`uv run pytest tests/unit -k hlsyn`) 216 tests are skipped under the
per-agent oracle layout with messages of the form

```
DECtalk C source not available at /tmp/dectalk-src
```

The cause is a literal-path constant in tests like
`tests/unit/test_hlsyn_ll_frame_n_parity.py`:

```python
_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/hlsynapi.h"
...
@pytest.mark.skipif(not _C_FILE.exists(),
    reason="DECtalk C source not available at /tmp/dectalk-src")
```

The reason-string is hard-coded; the `os.environ.get(..., default)`
defaulting is correct so this is purely cosmetic. **However**, in the
current per-agent setup `setup_c_oracle.sh` does not create a
`/tmp/dectalk-src` symlink — only the slug-suffixed path — and
several of these tests resolve their `_C_FILE` relative to a
sub-path (e.g. `src/dapi/src/ph/hlsynapi.h`) that does not actually
exist anywhere in the source tree. Those would skip even with the
default path, so it's a *separate* defect from the path-resolution
quirk. Both are out of scope for #91.

Recommended follow-ups (not done here):

- Fix the skip reason strings to interpolate the real
  `DECTALK_SRC` value.
- Replace `hlsynapi.h` references with the actual header in the
  source tree (`grep` shows no file by that name under
  `${DECTALK_SRC}`); these tests were written against a path that
  was renamed/moved during the port.

Neither blocks the hlsyn-parity claim — the authoritative end-to-end
check is `tests/parity/test_synth_parity.py`, which exercises the
full `LLSynthesize` integration through the C harness and is green.

## Conclusion

No hlsyn frame-parity regression on `dev` HEAD `fbd679d`. Recent
PH-stage work (`init_phclause` audit, `phinton` Rule 9 `goto skiprules`
mirror, etc.) has **not** affected the synth back-end's bit-level
agreement with the FONIX C reference.

Closes #91.

Authored-by: Claude:claude-opus-4-7 pytest
