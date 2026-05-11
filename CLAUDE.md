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
