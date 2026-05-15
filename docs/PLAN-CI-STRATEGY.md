# Dev-workflow overhaul for parallel-agent porting

## Context

The dectalk-python project is in the middle of a long-running C→Python
port driven primarily by Claude Code agents. The Phase E PH-stage port
(`phsettar.py`) is the active blocker, but the user has chosen to ship
a **workflow-first** overhaul before resuming any port work. The goal
is to make the codebase capable of sustaining **as many concurrent
porting agents as is practical** — limited by orchestrator review
bandwidth and API quota, not by shared filesystem state, CI minutes,
or manual dispatch overhead.

**Relationship to `docs/PLAN.md`**: this is a *tactical addendum*.
`docs/PLAN.md` is the strategic roadmap for the C→Python port (Phases
0-6, repository layout, translation rules, parallelization model);
this plan implements the workflow plumbing those phases assume.
Where the two might conflict, PLAN.md wins; this plan calls out the
divergences explicitly (e.g. PLAN.md's "≤ 5 concurrent agents" → this
plan removes the cap, per user feedback).

**Friction points being removed**:

1. *Lint runs 9× redundantly* — pure static analysis re-executed on
   every OS × Python combo.
2. *Every CI run rebuilds the C oracle from source* — ~30 s of
   redundant work per push, magnified across 10+ jobs.
3. *Upstream `dectalk/dectalk` is pinned to the moving `develop` branch*
   — CI is non-deterministic and the C oracle can't be safely cached.
4. *Single `/tmp/dectalk-src`* — CLAUDE.md caps concurrent agents at
   ~2 to avoid the shared-mutable resource.
5. *Tests run serially* — `pytest -v` ignores cores.
6. *No machine-readable task queue* — orchestrator picks each agent's
   work by hand, doesn't scale past a handful of simultaneous fan-outs.
7. *No standardized parity-test scaffolding* — each translator agent
   writes the C-source re-parsing boilerplate from scratch.
8. *No perf gate* — PLAN.md asks for "1 s of speech in ≤ 0.3 s" but
   nothing measures regressions.
9. *No auto-review on PRs* — orchestrator manually reviews every diff.
10. *Branch protection not configured* — `main`/`dev` accept any push.

## Section I — CI restructure (per-commit speed)

### 1. Two-tier CI

**Create `.github/workflows/ci-fast.yml`** — runs on every push to
working branches; targets ~2-3 min:

```yaml
name: CI (fast)
on:
  push:
    branches: ["claude/**", dev]
    paths-ignore:
      - "tests/parity/_corpus.py"
      - "docs/STATUS.md"
      - "docs/PLAN.md"
      - "docs/PLAN-CI-STRATEGY.md"
      - "docs/PORTING.md"
concurrency:
  group: ci-fast-${{ github.ref }}
  cancel-in-progress: true
jobs:
  fast:
    name: Fast checks (Ubuntu, Py 3.11)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with: { enable-cache: true, python-version: "3.11" }
      - run: uv sync --only-group dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pyright
      - run: uv run pytest -n auto -m "not c_oracle and not slow"
      - run: shellcheck scripts/*.sh
```

**Modify `.github/workflows/ci.yml`** (the "full" workflow):
- Trigger: `push: [main, dev]` + `pull_request: [main, dev]` only —
  `claude/**` is handled by `ci-fast`.
- Split `lint-and-type` into:
  - `lint` job — ubuntu + Py 3.11, single job, runs ruff + pyright +
    audio diagnostic + artifact upload (one upload, not nine).
  - `test-matrix` job — 3 OSes × 3 Pythons, runs only
    `pytest -n auto -m "not c_oracle"`. `needs: lint`.
- `shellcheck` — unchanged.
- `c-oracle-tests` — adds cache step + release-fetch step (§2).
  `needs: lint`. Runs `pytest -n auto` (everything including c_oracle).
- `perf-bench` — **new**, ubuntu + Py 3.11, runs benchmark suite
  against checked-in baseline (§9). `needs: lint`.
- `report-ci-status` — update `needs:` list and `results` keys.

### 2. C-oracle build cache + GitHub Release artifact

**Pin upstream SHA** in `scripts/setup_c_oracle.sh`:
```bash
DECTALK_REF="${DECTALK_REF:-32efa30ef2e216b3ad091c41abf5b502498a19aa}"
```

Replace the `--depth 1 --branch` clone with SHA-aware shallow init:
```bash
if [[ ! -d "${DECTALK_SRC}/.git" ]]; then
  mkdir -p "${DECTALK_SRC}"
  git -C "${DECTALK_SRC}" init -q
  git -C "${DECTALK_SRC}" remote add origin "${DECTALK_REPO}"
  git -C "${DECTALK_SRC}" fetch --depth 1 origin "${DECTALK_REF}"
  git -C "${DECTALK_SRC}" checkout "${DECTALK_REF}"
fi
```

**Deterministic oracle hash** (release tag + cache key):
```bash
oracle_hash() {
  { echo "${DECTALK_REF}"
    find "${REPO_ROOT}/tests/parity/c_patches" -name '*.patch' \
      -exec sha256sum {} \; | sort
    sha256sum "${REPO_ROOT}/scripts/setup_c_oracle.sh" \
              "${REPO_ROOT}/scripts/apply_c_patches.py"
  } | sha256sum | cut -c1-16
}
```

**Fetch-from-release fast path** before the build:
```bash
ORACLE_TAG="c-oracle-$(oracle_hash)"
ORACLE_URL="https://github.com/pktck/dectalk-python/releases/download/${ORACLE_TAG}/c-oracle.tar.zst"
if [[ ! -d "${DECTALK_BIN}" ]] && \
   curl -fsSL "${ORACLE_URL}" -o /tmp/c-oracle.tar.zst; then
  tar --use-compress-program=unzstd -xf /tmp/c-oracle.tar.zst -C /
  log "Restored prebuilt C oracle from ${ORACLE_TAG}"
  exit 0
fi
```

**New workflow `.github/workflows/build-c-oracle.yml`** — triggers on
changes to `scripts/setup_c_oracle.sh`, `scripts/apply_c_patches.py`,
or `tests/parity/c_patches/**`, plus `workflow_dispatch`. Builds the
oracle, tars `/tmp/dectalk-src` + `/tmp/dectalk-binary-stable`, creates
release `c-oracle-<hash>` with the tarball attached.
`permissions: contents: write`.

**Actions cache fallback** in `c-oracle-tests` for feature branches
that haven't yet triggered a release build.

### 3. pytest infrastructure

`pyproject.toml`:
```toml
[dependency-groups]
dev = [..., "pytest-xdist>=3.0", "pytest-benchmark>=4.0"]

[tool.pytest.ini_options]
markers = [
  "slow: long-running tests (>5s)",
  "c_oracle: requires DECTALK_SRC/DECTALK_BIN built oracle",
  "parity: parity test against C source (auto-skips when source absent)",
  "perf: performance benchmark (run via pytest --benchmark-only)",
]
addopts = "--strict-markers"
```

Annotate existing tests:
- `@pytest.mark.c_oracle` on `test_capi_parity.py`,
  `test_binary_wav_parity.py`, `test_convert_to_phonemes_parity.py`.
- `@pytest.mark.slow` on any test currently >5 s wall-clock (audit via
  `pytest --durations=20`).

## Section II — Local dev experience

### 4. `dev_check.sh --changed` and `--smoke`

```bash
case "${1:-}" in
  --changed)
    base="$(git merge-base HEAD origin/dev 2>/dev/null || echo HEAD~1)"
    changed_py="$(git diff --name-only "$base"...HEAD -- '*.py' || true)"
    [[ -n "$changed_py" ]] && {
      run_step "ruff lint (changed)" uv run ruff check $changed_py
      run_step "pyright (changed)" uv run pyright $changed_py
    }
    run_step "pytest" uv run pytest -n auto -m "not c_oracle and not slow"
    ;;
  --smoke)  # <5 s; for tight inner loops
    run_step "ruff" uv run ruff check .
    run_step "pytest fast" uv run pytest -n auto -m "not c_oracle and not slow" --lf
    ;;
  *) ... ;;  # full check, existing behavior
esac
```

### 5. Pre-commit hook (opt-in)

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks: [{id: ruff}, {id: ruff-format}]
  - repo: https://github.com/RobertCraigie/pyright-python
    rev: v1.1.380
    hooks: [{id: pyright, additional_dependencies: [".[dev]"]}]
```

Install instructions in CLAUDE.md; not enforced (fast CI catches the
same issues).

## Section III — Scaling agent fan-out

### 6. Per-agent C-oracle isolation, no concurrency cap

`scripts/agent_oracle_env.sh` — sourced by agents:
```bash
#!/usr/bin/env bash
# Usage: eval "$(scripts/agent_oracle_env.sh)"
slug="${AGENT_SLUG:-$$-$RANDOM}"
echo "export DECTALK_SRC=/tmp/dectalk-src-${slug}"
echo "export DECTALK_BIN=/tmp/dectalk-binary-stable-${slug}"
```

With the prebuilt tarball (§2), each agent's setup is ~5 s of curl +
untar into its own /tmp dir. No shared mutable state. CLAUDE.md
documents that translator agents should `eval` this before
`scripts/setup_c_oracle.sh`. Hard concurrent-agent cap removed.

### 7. Task queue (`docs/TASKS.md`)

A machine-readable registry of remaining C→Python ports.
**Auto-generated** from the existing `_DEFERRED` allow-lists + module
inventory tests + `NotImplementedError` grep. Format:

```markdown
## Open porting tasks

| C source | Target Python | Stage | Status | Owner | Deps |
|---|---|---|---|---|---|
| src/dapi/src/ph/ph_setar.c::phsettar | src/dectalk/ph/phsettar.py | E-PH | open | — | init_variables, gettar, make_dip (done) |
| src/dapi/src/ph/ph_inton2.c::phinton | src/dectalk/ph/phinton.py | E-PH | open | — | f0_intonation (done) |
| ... | ... | ... | ... | ... | ... |
```

`scripts/refresh_tasks.py` regenerates this from the codebase on
demand (and via `build-c-oracle.yml` workflow on a schedule). Agents
claim a task by editing the table (PR-scoped change) to set `Owner =
@agent-slug`; orchestrator sees claims live, never double-dispatches.

### 8. Porting playbook (`docs/PORTING.md`)

A self-contained recipe so translator agent prompts stay short.
Includes:
- Translation rules table (lifted from `docs/PLAN.md` for hot reference).
- A *worked example*: walk through one completed port end-to-end
  (e.g., `make_dip` in `ph_setar.c` → `make_dip.py` + parity test),
  showing the exact diff structure.
- Common pitfalls: C signed wraparound, pointer arithmetic patterns,
  `static` storage semantics, brace-depth parsing for C-source tests.
- Acceptance checklist the agent must self-verify before reporting
  done: `ruff check`, `pyright`, `pytest -n auto`, parity test exists
  and passes when `DECTALK_SRC` is set, `_DEFERRED` entry removed if
  any.
- Pointer to `docs/PLAN.md` and `docs/PLAN-CI-STRATEGY.md`.

Agent prompts then become: *"Port the function at <C path> to
<Python path> per docs/PORTING.md. Dependencies: <list>. Acceptance:
docs/PORTING.md §Checklist."*

### 9. Parity-test scaffolding

`scripts/scaffold_parity_test.py <c_file> <function> <python_module>`
generates a stub test file mirroring the structure of
`tests/unit/test_ph_make_dip_parity.py` (brace-depth extraction,
signature assertion, body-content assertions, Python-shim assertion).
Reduces per-agent test boilerplate from ~150 lines hand-written to
~10 lines of customization.

### 10. Performance baseline + CI gate

Add `tests/perf/test_synth_perf.py` with `pytest-benchmark`. Measures
synthesizing a fixed 1 s phrase (e.g. "the quick brown fox") end-to-end
and asserts wall-clock ≤ baseline + 20%. Baseline stored in
`tests/perf/baseline.json` (committed). Update via `pytest --benchmark-save`
during a deliberate perf push, gated by orchestrator review. CI job
`perf-bench` runs this on ubuntu + Py 3.11 only (single-version
baseline; the test matrix on the full workflow still validates
3.11/3.12/3.13 for correctness, just not perf).

PLAN.md target: "synthesizing 1 s of speech in ≤ 0.3 s on a modern
laptop". Encoded as the perf gate's absolute ceiling.

### 11. Auto-review on PRs

Currently /ultrareview is user-triggered and billed. Cheaper option:
a `pr-review.yml` workflow that runs on `pull_request: opened, synchronize`
and posts a sticky comment with:
- Diff summary (files changed by stage).
- Auto-detected concerns (TODO/FIXME left in code, `# type: ignore`
  added, `_DEFERRED` allow-list changed, parity test missing for a
  newly-ported function — grep-level checks, not Claude-level).
- Encouragement to run `/review` if substantial.

Doesn't replace human/orchestrator review; reduces what they have to
catch manually.

## Section IV — Branch protection, docs, hygiene

### 12. Branch protection (do it as part of this work)

Use `GH_TOKEN` + REST API to configure protection on `main` and
`dev` once the new workflows have run once and registered their job
names. Concrete calls (Bash, after merging the workflow changes):

```bash
for branch in main dev; do
  curl -sS -X PUT \
    -H "Authorization: Bearer $GH_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/pktck/dectalk-python/branches/${branch}/protection" \
    -d '{
      "required_status_checks": {
        "strict": true,
        "contexts": ["lint", "test-matrix (ubuntu-latest, Py 3.11)",
                     "shellcheck", "c-oracle-tests", "perf-bench"]
      },
      "enforce_admins": false,
      "required_pull_request_reviews": null,
      "restrictions": null,
      "allow_force_pushes": false,
      "allow_deletions": false,
      "required_linear_history": true
    }'
done
```

Exact `contexts` names come from the first successful workflow run on
each renamed job (GitHub stores them as "<workflow name> / <job
name>" — verify and adjust). `claude/**` branches are unaffected.

### 13. CLAUDE.md updates

- Fix the "10 jobs per push" claim → reflect new structure (~3 jobs on
  `claude/**` pushes; ~6 on `main`/`dev`/PRs).
- Document `DECTALK_REF`, per-agent `DECTALK_SRC`/`DECTALK_BIN` envs,
  and the `agent_oracle_env.sh` helper.
- Document the c-oracle release-rebuild trigger.
- Remove the "~2 concurrent agents" cap; replace with "fan out as wide
  as is practical".
- Add a "see also: `docs/PLAN.md`, `docs/PORTING.md`,
  `docs/PLAN-CI-STRATEGY.md`, `docs/TASKS.md`" pointer near the top.
- Note that `main`/`dev` are branch-protected; PRs needed for merge.

### 14. Documentation set

- `docs/PLAN-CI-STRATEGY.md` — checked-in copy of this plan. Saved
  *immediately* (user already requested this) so other sessions see it.
- `docs/PORTING.md` — the playbook (§8).
- `docs/TASKS.md` — the task queue (§7).
- All three are in `paths-ignore` of both CI workflows.

## Critical files

**New**:
- `.github/workflows/ci-fast.yml`
- `.github/workflows/build-c-oracle.yml`
- `.github/workflows/pr-review.yml`
- `.pre-commit-config.yaml`
- `scripts/agent_oracle_env.sh`
- `scripts/scaffold_parity_test.py`
- `scripts/refresh_tasks.py`
- `tests/perf/test_synth_perf.py`
- `tests/perf/baseline.json`
- `docs/PLAN-CI-STRATEGY.md` (saved first, mirror of this plan)
- `docs/PORTING.md`
- `docs/TASKS.md` (auto-generated initial version)

**Modified**:
- `.github/workflows/ci.yml` — split jobs, add cache, drop `claude/**`
  trigger, add `perf-bench`.
- `scripts/setup_c_oracle.sh` — pin SHA, add release fetch path,
  add `oracle_hash` helper.
- `scripts/dev_check.sh` — add `--changed` and `--smoke` modes.
- `pyproject.toml` — add `pytest-xdist`, `pytest-benchmark`; declare
  pytest markers.
- `tests/unit/test_capi_parity.py`, `test_binary_wav_parity.py`,
  `test_convert_to_phonemes_parity.py` — `@pytest.mark.c_oracle`.
- `CLAUDE.md` — updates per §13.

**Branch-protection** (no file changes — REST API calls): `main`, `dev`.

## Reuse — existing utilities

- `scripts/apply_c_patches.py` — invoked unchanged.
- Brace-depth C-body extraction from
  `tests/unit/test_ph_make_dip_parity.py` — becomes the template for
  `scripts/scaffold_parity_test.py`.
- `paths-ignore` / `concurrency` patterns from current `ci.yml`.
- `tests/parity/conftest.py` platform detection — untouched.
- `report-ci-status` sticky-comment mechanism — extended with `lint`
  and `perf-bench` keys.

## Implementation order

1. **Save this plan to `docs/PLAN-CI-STRATEGY.md` immediately** (user
   request) so collaborating sessions see it.
2. CI restructure + oracle release artifact (§1, §2): ship as one PR;
   the `build-c-oracle.yml` workflow runs and creates the first
   release; the `c-oracle-tests` job then uses it.
3. Pytest markers, xdist, dev_check.sh changes (§3, §4): one PR.
4. Per-agent oracle isolation + CLAUDE.md updates (§6, §13).
5. Task queue + porting playbook + parity scaffolder (§7, §8, §9):
   one PR; large doc + scripts.
6. Perf baseline + CI gate (§10).
7. PR auto-review workflow (§11).
8. Branch protection via REST API (§12) — last, once all check names
   are known and stable.
9. Resume `phsettar.py` port (deferred original task).

## Verification

1. `scripts/dev_check.sh --changed` returns in <10 s.
2. `uv run pytest -n auto -m "not c_oracle"` succeeds locally with
   measurable speedup vs serial.
3. Fresh container: `scripts/setup_c_oracle.sh` completes in <10 s
   (release-tarball path) and full pytest passes with
   `DECTALK_SRC`/`DECTALK_BIN` set.
4. Modify a `.patch` file → push → `build-c-oracle.yml` publishes a
   new release tag → next `c-oracle-tests` run fetches it.
5. Push to `claude/test-fast` → only `ci-fast` triggers, completes in
   ~2-3 min.
6. Open PR to `dev` → `ci-full` runs full matrix, `c-oracle-tests`
   uses prebuilt tarball, `perf-bench` reports within baseline,
   `pr-review.yml` posts review comment, `report-ci-status` updates.
7. `gh api repos/pktck/dectalk-python/branches/main/protection` shows
   `required_status_checks` listing the new job names.
8. Try a force-push to `dev` — denied.
9. Run `scripts/refresh_tasks.py` → `docs/TASKS.md` regenerates with
   the current open ports.
10. Spawn 5 parallel translator agents on disjoint tasks from
    `docs/TASKS.md` with `Agent(isolation: "worktree")` — each
    completes without /tmp collisions, each PR auto-reviews, no
    manual orchestrator dispatch.

## Out of scope (deferred)

- `phsettar.py` port — resume after this workflow ships and bakes for
  1-2 days of green CI.
- Adding Python 3.14 to the test matrix.
- Creating `tests/audio/` per `docs/PLAN.md` repo layout.
- Property-based testing, mutation testing.
- Docker dev image / devcontainer.
- Stacked PRs / dependency tracking automation (manual ordering via
  `docs/TASKS.md` "Deps" column suffices for now).
- Cost observability dashboard.
