# Claude Code workflow guidance for dectalk-python

Project-specific operating instructions for Claude Code sessions on this
repository. Read this at the start of every session.

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

The matrix is 10 jobs per push (lint × 3 OSes × 3 Pythons + shellcheck +
c-oracle + report). Pushing dozens of commits in succession queues
hundreds of jobs and overwhelms GitHub Actions.

- `tests/parity/_corpus.py` and `docs/STATUS.md` are in
  `.github/workflows/ci.yml` `paths-ignore` — corpus-only and
  STATUS-only commits do **not** trigger CI. **Keep them there.**
- The workflow has `concurrency: cancel-in-progress: true`, so any new
  push to the same branch cancels still-queued runs on the prior commit
  — but only for runs that already had the concurrency rule applied.
- Even with both gates, do not push 50+ commits in a turn. Batch corpus
  growth into one commit per turn, not one per category.

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

Three lanes are useful:

1. **Background `Agent` subagents** for self-contained, long-running
   tasks (corpus generation rounds, multi-file inventory passes).
   Launch with `run_in_background: true`. Each agent has its own
   context, so isolate them by giving precise file paths and the
   exact append/commit code in the prompt — never just "expand the
   corpus". Cap concurrency at ~2 to avoid resource thrash on the
   single C oracle.
2. **Inline `Bash` batches** in the main thread for short
   (~30 s) generators run between agent launches. The main thread's
   context is the only place that sees latest disk state, so do all
   file edits, commits, and pushes here — not inside agents.
3. **Read/Grep/Edit operations** in parallel within a single tool-use
   block when independent. Sequencing them wastes round-trips.

Anti-pattern: pushing a commit per inline batch. Accumulate several
batches' worth of corpus into one commit and push once per turn.

## Build and test gates

Always run `scripts/dev_check.sh` (ruff + pyright + pytest + shellcheck)
before pushing. CI re-runs the same checks plus the C-oracle build
(`scripts/setup_c_oracle.sh`) which clones dectalk source, applies our
patches, builds `libtts_us.so`, and runs the full test suite with
`DECTALK_SRC` / `DECTALK_BIN` set.

## C-to-Python port context

See `/root/.claude/plans/create-a-python-port-smooth-hoare.md` for the
authoritative plan. Key invariants:

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
