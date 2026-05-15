# Claude Code workflow guidance for dectalk-python

Project-specific operating instructions for Claude Code sessions on this
repository. Read this at the start of every session.

**See also**:
- `docs/PLAN.md` — strategic plan for the C→Python port (phases 0-6).
- `docs/PLAN-CI-STRATEGY.md` — workflow infrastructure rationale.
- `docs/PORTING.md` — per-task playbook for translator agents.
- `docs/TASKS.md` — current open port targets (auto-generated from
  `NotImplementedError` shims).

## CI watch (mandatory after every push)

**After every `git push`, subscribe to the branch's PR via
`mcp__github__subscribe_pr_activity` and continue working — do not block on
CI.** The subscription is idempotent; re-subscribing on subsequent pushes
is a no-op. CI events arrive as `<github-webhook-activity>` messages that
wake the session asynchronously.

When a CI failure event arrives:
1. Read the failure context delivered in the webhook message.
2. Reproduce the failure locally if possible (typically via
   `scripts/dev_check.sh`, `uv run pytest`, or
   `scripts/setup_c_oracle.sh && uv run pytest`).
3. Push a fix on the same branch. The existing subscription will catch
   the next CI run automatically.
4. Only report back to the user once CI is green or you're truly blocked.

When you're working on a branch that does not yet have a PR, create a
draft PR before subscribing. A draft PR signals "infrastructure for CI
watching, not ready for merge" and is the only practical way the GitHub
MCP server surfaces workflow events for a push.

Do **not** poll CI status with `sleep` loops in the foreground. The
subscription mechanism is the right tool — use it.

**CI run IDs in old `<github-webhook-activity>` messages are stale**
once you've pushed a fix. If every webhook references a run from before
your latest commit, ignore them — concurrency cancels the older runs
and `paths-ignore` (below) keeps quiet pushes silent. Verify by checking
the run's commit SHA, not by acting on the webhook.

## CI throttling — do not saturate Actions

CI is two-tier (see `docs/PLAN-CI-STRATEGY.md` §1):

- **Pushes to `claude/**` branches** trigger `ci-fast.yml` only — one
  ubuntu+Py3.11 job running ruff + ruff-format + pyright + pytest
  (excluding `c_oracle`/`slow`) + shellcheck. ~2-3 min total.
- **Pushes to `main`/`dev` and pull requests** trigger `ci.yml`: split
  into `lint`, 9-way `test-matrix` (3 OSes × 3 Py), `shellcheck`,
  `c-oracle-tests` (with prebuilt-tarball fetch), and
  `report-ci-status` (PR-only sticky comment).
- **`build-c-oracle.yml`** runs only when
  `scripts/setup_c_oracle.sh`, `scripts/apply_c_patches.py`, or
  `tests/parity/c_patches/**` change. It publishes a prebuilt oracle
  tarball as a GitHub Release so subsequent CI runs (and local agents)
  download instead of rebuilding.

Path-ignore lists in both workflows already cover doc-only changes
(`docs/PLAN.md`, `docs/STATUS.md`, `docs/PLAN-CI-STRATEGY.md`,
`docs/PORTING.md`, `docs/TASKS.md`, `README.md`,
`tests/parity/_corpus.py`). **Keep them there.**

Both workflows have `concurrency: cancel-in-progress: true`. Even with
that, don't push 50+ commits in a turn — batch related changes into
one commit per push.

If the queue still ends up flooded (e.g. a logic bug triggered the full
matrix per push), cancel via the REST API — `GH_TOKEN` is set in the
session env:

```bash
REPO=pktck/dectalk-python BRANCH=claude/python-dectalk-port-Nq5Oe
API=https://api.github.com/repos/$REPO/actions/runs
ids=$(for st in queued in_progress; do
  curl -s -H "Authorization: Bearer $GH_TOKEN" \
    "$API?branch=$BRANCH&status=$st&per_page=100" \
    | python3 -c "import json,sys;print('\n'.join(str(r['id']) for r in json.load(sys.stdin)['workflow_runs']))"
done | sort -u)
for id in $ids; do
  curl -s -o /dev/null -X POST -H "Authorization: Bearer $GH_TOKEN" \
    "$API/$id/cancel"
done
```

## Parallelization

Fan out **as wide as is practical**. The bottlenecks are orchestrator
review bandwidth and Claude API quota — not shared filesystem state.
The infrastructure that makes this safe:

- **Per-agent C-oracle isolation.** Each agent should `eval
  "$(scripts/agent_oracle_env.sh)"` before invoking
  `scripts/setup_c_oracle.sh`. This emits unique
  `DECTALK_SRC=/tmp/dectalk-src-<slug>` and
  `DECTALK_BIN=/tmp/dectalk-binary-stable-<slug>` paths so concurrent
  agents don't trample each other's source tree or build artefacts.
  With the prebuilt-tarball fast path, per-agent setup is ~5 s.
- **Worktree isolation for write paths.** Spawn translator agents
  with `Agent(..., isolation: "worktree")` so each gets an isolated
  checkout. The orchestrator merges completed worktrees serially.
- **Task queue.** `docs/TASKS.md` lists every Python module that
  still raises `NotImplementedError`. Agents claim a row by setting
  the `Owner` column; orchestrator never double-dispatches.
  Regenerate with `uv run python scripts/refresh_tasks.py`.
- **Porting playbook.** `docs/PORTING.md` is the self-contained
  per-task brief. Translator agent prompts cite it instead of
  redescribing the recipe inline.
- **Parity-test scaffolder.** `scripts/scaffold_parity_test.py`
  generates the C-source re-parsing boilerplate so agents focus on
  body assertions rather than extractor plumbing.

The three execution lanes inside the orchestrator session are
unchanged:

1. **Background `Agent` subagents** (`run_in_background: true`) for
   self-contained translation tasks. Give precise file paths and the
   exact acceptance criteria from `docs/PORTING.md`.
2. **Inline `Bash` batches** in the main thread for short generators
   between agent launches. The main thread sees latest disk state, so
   do all file edits, commits, and pushes here — not inside agents.
3. **Read/Grep/Edit operations** in parallel within a single tool-use
   block when independent. Sequencing them wastes round-trips.

Anti-pattern: pushing a commit per inline batch. Accumulate several
batches' worth of changes into one commit and push once per turn.

## Branch protection

`main` and `dev` are protected. Direct push is allowed (admin can
override) but the GitHub REST API enforces:

- Required status checks (strict mode — head must be up to date with
  base before merge): `Lint + type-check + audio diagnostic (Ubuntu,
  Py 3.11)`, `Pytest (ubuntu-latest, Py 3.11)`, `Shellcheck`,
  `Tests with C library (Ubuntu, Py 3.11)`.
- Force-push disabled.
- Branch deletion disabled.
- Linear history required (no merge commits).

Working branches (`claude/**`) are unaffected and can be force-pushed,
rebased, etc. PR merges into `main`/`dev` go through the
ci-full pipeline. To adjust the protection use the REST API with
`GH_TOKEN` (see `docs/PLAN-CI-STRATEGY.md` §12 for the curl call).

## Build and test gates

`scripts/dev_check.sh` has three modes:

- **No args** — full local quality gate: `ruff check`, `ruff format`,
  `pyright`, `pytest -n auto`, `shellcheck`. Pre-push verification.
- **`--changed`** — fast pre-push: `ruff` + `pyright` on `.py` files
  changed vs `origin/dev`, plus `pytest -n auto -m "not c_oracle and
  not slow"`. Runs in <10 s for small diffs.
- **`--smoke`** — tight inner loop: `ruff` + `pytest --lf` (last
  failed only). <5 s when green.

CI runs the same checks plus `c-oracle-tests`. The C-oracle build
fetches a prebuilt tarball from GitHub Releases (built by
`build-c-oracle.yml`) and only re-builds from source when the
patches/script change. `setup_c_oracle.sh` does the fetch
automatically, so local runs and CI use the same fast path.

## C-to-Python port context

See `docs/PLAN.md` for the authoritative strategic plan and
`docs/PORTING.md` for the per-task recipe. Key invariants:

- The synthesizer back-end (`src/dectalk/hlsyn/`) is bit-accurate already.
- `dectalk.speak()` and `dectalk.to_wav()` route through
  `dectalk._capi.CAPI` for byte-identical WAVs vs the binary, with a
  fallback to the approximate Python pipeline when `_capi` can't load.
- Parity tests (`tests/parity/`, plus `tests/unit/test_lts_*` and
  `tests/unit/test_phoneme_codes.py`) re-parse the C source at test time
  and assert byte-identical translations — they skip cleanly when
  `/tmp/dectalk-src` is absent.
- Translations follow a per-file pattern: extract C data → embed as
  Python literal → write parity test that re-parses the C source.
- The module-inventory tests (`test_*_module_inventory.py`) carry
  `_DEFERRED` allow-lists; **all 8 are currently empty**, which means
  every C function in `api/cmd/dic/hlsyn/kernel/lts/ph/vtm` has at
  least a Python symbol (often a `NotImplementedError` shim routing
  through `_capi`). Do not regress this — when you add a new Python
  module, also delete its `_DEFERRED` entry if any.

## Phase E (audio bit-parity from pure Python) — the active blocker

`DECTALK_DISABLE_CAPI=0 dectalk.to_wav(...)` is byte-identical to the
binary. `DECTALK_DISABLE_CAPI=1` is functionally correct but produces
audio of the wrong sample count (timing diverges). Closing this gap
is multi-week work: port the PH orchestration layer from
`/tmp/dectalk-src/src/dapi/src/ph/` (`ph_sort*.c`, `ph_setar.c`,
`ph_inton*.c`, `ph_timng.c`) into the existing Python shims in
`src/dectalk/ph/`. The hlsyn back-end is already bit-accurate; the
gap is purely in PH.

## Corpus expansion — diminishing returns

The phoneme parity corpus is at ~133K strict-pass prompts. Beyond this
scale, adding 50-prompt micro-batches isn't valuable signal — it's
mostly variations on patterns already covered. Prefer either:
- one big rounded batch (~1000+ prompts) covering a genuinely new
  syntactic pattern, **committed once**; or
- shift to Phase E (audio parity) where there's real work left.
