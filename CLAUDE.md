# Claude Code workflow guidance for dectalk-python

Project-specific operating instructions for Claude Code sessions on this
repository. Read this at the start of every session.

**See also**:
- `docs/PLAN.md` — strategic plan for the C→Python port (phases A-F).
- `docs/PLAN-CI-STRATEGY.md` — workflow infrastructure rationale.
- `docs/PORTING.md` — per-task playbook for translator agents.
- `docs/PARITY-METHOD.md` — Phase E byte-parity diagnosis playbook
  (capture rules, wrong-variant checklist, verification gates,
  misdiagnosis case studies). **Read before any parity work.**
- `docs/TASKS.md` — current open port targets (auto-generated from
  `NotImplementedError` shims).

## Autonomy protocol (anti-stall)

Sessions on this repo have historically stalled — ending the turn
after finishing a single task instead of continuing autonomously.
The protocol:

1. **End-of-turn checklist.** Before ending any turn, at least one of
   these must hold: (a) a PR green-poll or webhook subscription is in
   flight, (b) a background agent is running, (c) you are genuinely
   blocked on the user (send an ntfy first). If none hold and
   unclaimed `area/parity` issues exist, dispatch the next one
   instead of stopping.
2. **The sweep.** On every wake (webhook, poll completion, heartbeat):
   merge green PRs per `docs/PARITY-METHOD.md` §6 → check agents,
   salvage/re-dispatch dead ones → refill the dispatch pipeline →
   only then consider stopping.
3. **Heartbeat trigger.** A scheduled trigger
   (`orchestrator-heartbeat-parity-sweep`, every 2 h) fires the sweep
   prompt into the orchestrator session as a dead-man's switch, so a
   stalled session self-recovers within 2 h. Manage it with
   `list_triggers` / `update_trigger` (set `enabled:false` to pause).
4. **Status recaps are a stop-tell.** If you're drafting a summary
   and nothing is in flight, that is the signal to dispatch the next
   issue, not to stop.

## Orchestrator role (top-level session)

**The top-level session is an orchestrator, not a coder.** Its job
is to plan work, create GitHub issues for each port milestone,
spawn coding agents pointed at those issues, review the resulting
PRs, manage CI, and merge into `dev`. Do not write code directly
from this session; delegate every coding task to a sub-agent via
`Agent(...)`.

This rule keeps the orchestrator's context clean and lets parallel
agents work without the orchestrator stomping on hot files.

## Issue-driven agent dispatch

**Every coding agent task must be scoped by a GitHub issue.**
Before spawning a coding agent:

1. Create a GitHub issue via `mcp__github__issue_write` with:
   - A clear, scoped title (e.g. "Port `us_phtiming` from p_us_tim.c").
   - A description of what to port, which C file/lines, the
     acceptance criteria (gates / smoke tests), and a pointer
     to `docs/PORTING.md` for the per-task playbook.
   - Labels indicating subsystem (`area/ph`, `area/hlsyn`, etc.)
     and rough size (`size/small`, `size/medium`, `size/large`).
2. Spawn the agent with a prompt that **references the issue
   number** (e.g. "Working on #42: port `us_phtiming` from
   `p_us_tim.c` ..."). The agent's PR description should also
   reference the issue with a `Closes #42` line so the merge
   auto-closes the issue.
3. Every commit the agent makes should reference the issue in
   the commit body's trailer: `Refs: #42` (or `Closes: #42` on
   the final commit).

This requirement does **not** apply retroactively to in-progress
agent tasks spawned before this rule was added; let those finish
without forcing them through the issue gate.

The orchestrator's coding-agent prompts should be short -- the
issue body carries the detail. A prompt like:

```
Issue: pktck/dectalk-python#42
Branch: claude/port-us-phtiming-issue-42
Read the issue body for full scope. Push the branch when done;
do not open a PR (orchestrator handles that).
```

is the right shape.

## Agent attribution

This repo is co-authored by humans and AI agents, all surfacing on
GitHub under the user's PAT. Make authorship explicit on every
agent-authored artifact via a trailer line at the bottom of the body:

`Authored-by: AGENT_NAME:MODEL_VERSION[ TOOL1 TOOL2 ...]`

Examples:
- `Authored-by: Claude:claude-opus-4-7`
- `Authored-by: Claude:claude-opus-4-7 ruff pyright`
- `Authored-by: Codex:gpt-5.4`

**For Claude.** `MODEL_VERSION` is the model actually running the
session (e.g. `claude-fable-5`, `claude-opus-4-8`), without any
`[1m]`-style harness suffix — those are chat-only details. Do not
copy a stale value from older artifacts; state the model you are.

**Tools listed.** Significant non-basic tools whose output materially
influenced the artifact: ruff, ruff-format, pyright, pytest,
shellcheck, pre-commit, the scaffolders under `scripts/`. Excluded:
git, gcc, make, editors, shells, basic curl/jq plumbing. Omit the
tool list entirely when nothing of substance was used (e.g. a plain
issue describing a future task is fine without it).

**Applies to.** PR bodies, issue bodies, and every agent-authored
PR / issue / review comment. Append the line at the bottom of the
body, after any existing footer (e.g. the `_Generated by Claude
Code_` link).

**Does NOT apply to.** Git commit messages (already attributed via
commit metadata) and `github-actions[bot]` comments (workflow output;
the workflow is agent-authored, the comment text is not).

## User notifications (ntfy)

The user is not always watching the session. Send a push notification
via [ntfy.sh](https://ntfy.sh) to topic **`cladue-code-jafoofado`** when
either condition holds:

1. You are about to end the turn waiting for user input
   (`AskUserQuestion`, an open clarification question, or just nothing
   left to do without a decision).
2. You have not produced user-facing output for ~10 minutes
   (long-running agents, CI polling that's overdue, etc.).

One-liner:

```bash
curl -sS -d "<short status — what you're waiting on>" \
  https://ntfy.sh/cladue-code-jafoofado
```

Keep the message to one line ("CI green on PR #9, ready to merge",
"asked you about X", "agent finished, awaiting review"). The topic
name is intentional — don't autocorrect the spelling.

Do **not** spam — send once per blocking event, not on every
intermediate progress update.

## PR cadence (target: 1 PR per 1-4h wall-clock, 1000+ LOC)

PRs trigger the full `ci.yml` matrix (9-way test, 16-shard c-oracle,
~10-15 min of compute total). Don't open one for every commit.

**Hard rule:** a PR should contain **multiple commits** totalling
**1000+ lines of changes** (insertions + deletions). A single-commit
PR with a 5-line fix is almost always wrong — stack the fix on a
working branch with related ports until the diff reaches milestone
size, then open one PR.

**Open a PR only for a milestone**, not for incremental progress.
A milestone is something like:
- a whole subsystem ported (e.g. the gettar/us_gettar/getbegtar/
  getendtar chain landed together),
- a measurable parity improvement (more c-oracle prompts pass),
- infrastructure that other work depends on (CI policy, foundation
  dataclasses, etc.).

Stacking individual ports into a single branch and opening one PR
after several hours of work is the right shape; don't open a fresh
PR every 20-30 minutes. If a branch grows past ~4h of accumulated
work without a clear stopping point, prefer to ship what's done and
start fresh.

**Anti-pattern**: opening separate PRs for (a) a 50-line bug fix,
(b) a 100-line LUT port, (c) a 30-line wiring tweak in the same
turn. Each triggers the full matrix; the user pays for 3x the CI
compute and reviews 3x the merge events. Stack them on one branch
and open one PR with three commits.

The CI throttling section below describes the per-tier cost so you
can pick the right cadence.

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

### Closing the merge loop (don't sit idle waiting for "all green")

The PR subscription delivers individual events (per-comment, per-check,
per-review) — there is **no guaranteed "all CI green" webhook**.
The bot's CI-status sticky comment fires for the first workflow run on
a SHA, so when concurrency cancels and replaces a run, you can get a
single FAIL comment from the cancelled run and then silence as the
replacement goes green. "Subscribed and waiting" is the right state
only when you're babysitting a PR for *new* failures — not when the
goal is to merge once green.

When the goal is autonomous merge:

1. After pushing, kick off a `run_in_background: true` Bash poll
   that exits when `get_status` returns `success` (an `until` loop
   with `sleep 30`s). The Bash tool's docs name this as the canonical
   "one notification when X is ready" pattern — you'll be woken by
   the completion notification when the loop exits.
2. **Don't end the turn while the poll is in flight.** The
   remote-execution container can suspend during long quiet windows,
   and webhook delivery to a suspended container is best-effort.
   Stay engaged: review the diff, draft the next port, or just
   call `get_check_runs` once before ending. The background poll's
   completion is the most reliable wake — but the more activity in
   the foreground, the lower the chance of a stale-container race.
3. Once the poll wakes you, call `merge_pull_request`
   (rebase — linear history is required on `dev` and `main`) and
   `unsubscribe_pr_activity`. The merge is the loop's terminal state.

If a polling loop runs longer than its cap (10 min default) without
turning green, ntfy the user and end the turn — the rerun-via-API
trick (`POST /actions/runs/$id/rerun`) clears cancelled-by-flake
workflow runs without needing a push.

If `enable_pr_auto_merge` is unavailable at the repo level (it is at
present), do the manual merge yourself — don't tell the user "auto-merge
unavailable" and then stop.

**Anti-pattern**: pushing + subscribing + ending the turn while
expecting webhooks to wake you. They might; they might not, if the
container suspended between turn-end and webhook delivery. The
background-poll completion notification is more reliable because
it's a direct wake on your session, not a queued external event.

### Mandatory pattern after every PR push

After pushing **any** PR (draft or open), do all three of these in
the same turn before ending it:

1. `subscribe_pr_activity` for the PR.
2. Kick off a foreground `run_in_background: true` Bash `until`
   poll that exits on green CI (see "Closing the merge loop"
   above for the exact pattern).
3. **Immediately start the next port target** — branch, edit,
   run tests. Do not end a turn whose only outstanding work is
   a webhook subscription; webhook delivery to a suspended
   remote container is best-effort, and a "Status:" recap
   message is a stop tell.

If you find yourself drafting an end-of-turn status summary, that
itself is the trigger to start the next port instead.

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
(`CLAUDE.md`, `docs/PLAN.md`, `docs/STATUS.md`,
`docs/PLAN-CI-STRATEGY.md`, `docs/PORTING.md`, `docs/TASKS.md`,
`README.md`, `tests/parity/_corpus.py`). **Keep them there.**

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
  changed vs `origin/dev`, plus `pytest -n auto tests/unit/ -m "not
  c_oracle and not slow"`. ~40 s on the current unit tree (~21 K
  tests); ruff+pyright on a small diff adds a few seconds.
- **`--smoke`** — tight inner loop: `ruff` + `pytest --lf` on
  `tests/unit/` (last-failed only, falls back to the unit tree when
  the cache is empty). <5 s when green.

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

## Phase E (audio bit-parity from pure Python) — REACHED

`DECTALK_DISABLE_CAPI=0 dectalk.to_wav(...)` is byte-identical to the
binary via `_capi`. As of issue #311, **plain `DECTALK_DISABLE_CAPI=1`
is byte-identical too**: the translated PH orchestration layer +
`vtm1.c`-ported synthesiser (FULL+VTM1) is the no-`_capi` default,
verified across the full 133,641-prompt corpus WAV census
(`scripts/corpus_wav_sweep.py`; `DECTALK_FULL_PIPELINE=0` opts out to
the legacy approximate pipeline). Keep the census green: any PH/VTM
change must hold the 500-sample gate
(`scripts/measure_full_vtm1_sample.py`) and the pinned byte-exact
prompt suites; re-run the full sweep for changes with corpus-wide
blast radius. See `docs/STATUS.md` §"Project goalpost" for the
current numbers.

## Corpus phoneme gate + corpus expansion

The ~135K-prompt corpus phoneme gate
(`tests/parity/test_python_phonemes_vs_c_parity.py`) runs in the
16-shard c-oracle lane on a deterministic 2000-prompt strided
subsample (`DECTALK_CORPUS_GATE_SAMPLE`). Measured 2026-07-10 (issue
#310, on top of the #280 census): **134,990 / 134,990 prompts
byte-identical (100%)**; the known-divergent allowlist
(`tests/parity/data/corpus_phoneme_known_divergent.txt`) is empty
after the #295 homograph, #280 stress, and #310 -ed suffix-family
close-outs. Full-corpus
sweeps go through `scripts/corpus_phoneme_sweep.py` — bulk in-process
oracle use segfaults, so the sweep slices across fresh subprocesses.
Do not call the corpus "strict-pass" without re-measuring; the gate
rotted unenforced for weeks before #281 wired it into CI.

Corpus expansion has diminishing returns beyond this scale: adding
50-prompt micro-batches isn't valuable signal — it's mostly variations
on patterns already covered. Prefer either:
- one big rounded batch (~1000+ prompts) covering a genuinely new
  syntactic pattern, **committed once**; or
- shift to Phase E (audio parity) where there's real work left.
