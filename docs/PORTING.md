# Porting playbook (C → Python)

This document is the self-contained brief for a translator agent
working on the DECtalk port. The strategic plan is in `docs/PLAN.md`;
this file is the per-task recipe. The dev-workflow plumbing
(branching, CI, agent isolation) lives in `docs/PLAN-CI-STRATEGY.md`.

Open tasks are listed in `docs/TASKS.md`. Pick one whose dependencies
are already ported, claim it by setting the `Owner` column to your
agent slug, and follow the steps below.

## 1. Set up isolated environment

```bash
# Per-agent /tmp dirs so concurrent agents don't trample each other.
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh   # ~5 s if the prebuilt release tarball is current
```

After this, `$DECTALK_SRC` points to the patched C source tree and
`$DECTALK_BIN` to the assembled `say` binary + libraries.

## 2. Read both sides

1. Open the C source file from `docs/TASKS.md` under
   `${DECTALK_SRC}/<C path>`. Read the function you're porting and at
   least one caller / callee to understand the data-flow context.
2. Open the existing Python target (a shim that raises
   `NotImplementedError`). It documents the C location and signature
   in the module docstring — this is the contract you must preserve.
3. Cross-check headers under `${DECTALK_SRC}/include/` for any
   `struct`/`enum`/`#define` the function uses; their Python mirrors
   live under `src/dectalk/include/`.

## 3. Translate following the rules table

(Lifted from `docs/PLAN.md` so an agent doesn't need both files open.)

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
| `goto` | refactor to early returns / loops |
| `void *` opaque handles | typed wrapper class (never `Any`) |
| Function pointers | `Callable[..., T]` with full parameter typing |
| Fixed-size C arrays | `NDArray[np.intN]` or `tuple[int, ...]` |

### Common pitfalls

- **Signed wraparound.** C `short` wraps at ±32768; Python ints don't.
  When the C relies on wraparound (e.g. accumulators in
  `hlsyn/voice.c`), add an explicit modular reduction with a comment
  citing the C behaviour.
- **Pointer arithmetic patterns.** `for (p = &PF1; p <= &PTILT; p++)`
  iterates a fixed array — translate as `for p in (PF1, F2, F3, ...)`
  enumerating each parameter symbol, **not** as a magic index loop.
- **`static` storage in C.** A `static` local persists across calls;
  in Python this is a module-level variable, not a default arg.
  Wrap it in a small dataclass when state shouldn't leak between
  worktrees / agent instances.
- **Brace-depth parsing.** The parity-test scaffolder uses brace-depth
  tracking to extract a C function body; if a function has macro-based
  control flow (`IS_PLUS`, `IS_MINUS` etc.), the macros expand to
  comparison operators and don't break depth.

## 4. Scaffold the parity test

```bash
uv run python scripts/scaffold_parity_test.py \
    --c-file <C path from docs/TASKS.md> \
    --c-function <C function name> \
    --python-module <dotted Python module path> \
    --python-symbol <Python symbol name>
```

This writes `tests/unit/test_<module>_<function>_parity.py` with:
- The brace-depth body/signature extractor.
- A "signature exists" smoke check.
- A `NotImplementedError` assertion for the current shim contract.

Fill in the `# TODO(translator)` block with assertions specific to the
function body — formant-frequency rules, table lookups, helper calls,
etc. Mirror the style of `tests/unit/test_ph_make_dip_parity.py`.

## 5. Self-verify before reporting done

```bash
scripts/dev_check.sh --changed
DECTALK_SRC="$DECTALK_SRC" DECTALK_BIN="$DECTALK_BIN" \
    uv run pytest -n auto tests/unit/test_<your-test>.py -v
```

### Acceptance checklist

- [ ] `uv run ruff check .` passes (no new warnings)
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run pyright` passes (strict mode, no new `# type: ignore`)
- [ ] `uv run pytest -n auto` passes (with and without
      `DECTALK_SRC`/`DECTALK_BIN` set)
- [ ] Parity test exists and asserts at least 3 substantive properties
      of the C body (signature, branches, table references)
- [ ] Python shim's `NotImplementedError` is removed and the function
      now executes
- [ ] If the module had an entry in any `_DEFERRED` allow-list under
      `tests/unit/test_*_module_inventory.py`, that entry is removed
- [ ] `docs/TASKS.md` row for this port is removed by running
      `scripts/refresh_tasks.py` (the script removes rows for modules
      that no longer raise `NotImplementedError`)
- [ ] Commit message follows the project's style: short imperative
      subject, body explaining *why* if non-obvious

## 6. Push and watch CI

```bash
git push -u origin <branch>
```

The fast workflow (`ci-fast`) runs in ~2-3 min on ubuntu+Py3.11. If
green, open a PR to `dev`; the full workflow (`ci`) then runs the 3 OS
× 3 Python matrix and the c-oracle parity tests.

When CI is green and the PR is reviewed, the orchestrator merges.

## Further reading

- `docs/PLAN.md` — strategic phase plan and Python coding standards.
- `docs/PLAN-CI-STRATEGY.md` — workflow infrastructure rationale.
- `docs/TASKS.md` — current open ports.
- `tests/unit/test_ph_make_dip_parity.py` — canonical example of a
  parity test with substantive body assertions.
- `src/dectalk/ph/make_dip.py` (the shim) and the corresponding C
  function in `${DECTALK_SRC}/src/dapi/src/ph/ph_setar.c` for a
  worked example of the C-to-Python diff structure.
