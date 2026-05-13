#!/usr/bin/env bash
# Stop-hook: only allow stop when the project goal is verifiably met.
#
# Fires when the assistant signals end-of-turn. Replaces the old
# "N-cycles guard" with a verification-based gate: stop is allowed
# ONLY when one of these is true:
#
#   1. DECTALK_ALLOW_STOP=1 in the env — explicit user override
#      (used when a human wants to suspend the loop for inspection).
#   2. Every module-inventory test's ``_DEFERRED`` dict is empty AND
#      the end-to-end parity test ``tests/parity/test_binary_wav_parity.py``
#      passes. That's the project goalpost from
#      ``/root/.claude/plans/create-a-python-port-smooth-hoare.md``.
#
# Otherwise, the hook re-injects the standing instruction and forces
# the assistant to continue. The verifier doubles as project status:
# every stop attempt prints a one-line snapshot of what's still
# deferred.
#
# Hot-path optimisation: the cheap inventory check (parses files via
# ast, ~tens of ms) runs FIRST. The slow parity test only runs when
# inventories are clear — avoiding a 30s gate on every stop event
# while the deferred lists are still populated.
#
# The hook reads its JSON payload on stdin per Claude Code's hook
# protocol; emits diagnostics on stderr; exit 0 = allow stop, exit 2
# = force continuation.
set -euo pipefail

payload="$(cat)"
hook_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# -------------------------------------------------------------------
# Override 1: explicit user opt-out.
# -------------------------------------------------------------------
if [[ "${DECTALK_ALLOW_STOP:-0}" == "1" ]]; then
  printf 'stop-hook: DECTALK_ALLOW_STOP=1 set — allowing stop\n' >&2
  exit 0
fi

# -------------------------------------------------------------------
# Verifier 1: every inventory's _DEFERRED dict empty?
# Cheap — ast-parses 8 files, no test runner.
# -------------------------------------------------------------------
inventory_ok=0
if "${hook_dir}/check_inventory_empty.py" 2>&1; then
  inventory_ok=1
fi

# -------------------------------------------------------------------
# Verifier 2: end-to-end parity test passes?
# Only run if inventories are clear — saves ~30s of pytest on every
# stop event while ports are still landing.
# -------------------------------------------------------------------
parity_ok=0
if [[ "$inventory_ok" -eq 1 ]]; then
  parity_test="tests/parity/test_binary_wav_parity.py"
  if [[ -f "${hook_dir}/../../${parity_test}" ]]; then
    if (cd "${hook_dir}/../.." && \
        DECTALK_SRC=/tmp/dectalk-src \
        DECTALK_BIN=/tmp/dectalk-binary-stable \
        uv run pytest "${parity_test}" -q >/dev/null 2>&1); then
      parity_ok=1
      printf 'stop-hook: %s passes\n' "${parity_test}" >&2
    else
      printf 'stop-hook: %s does NOT pass — forcing continuation\n' \
        "${parity_test}" >&2
    fi
  else
    printf 'stop-hook: %s not found — treating as not-yet-passing\n' \
      "${parity_test}" >&2
  fi
fi

if [[ "$inventory_ok" -eq 1 && "$parity_ok" -eq 1 ]]; then
  printf 'stop-hook: project goal verified — allowing stop\n' >&2
  exit 0
fi

# -------------------------------------------------------------------
# Force continuation.
# -------------------------------------------------------------------
cat <<'EOF' >&2
Standing instruction reminder: continue working toward byte-identical
bit parity between dectalk.speak() output and the DECtalk binary.

Stop is only allowed when the verifier passes — i.e. every module-
inventory test's _DEFERRED dict is empty AND
tests/parity/test_binary_wav_parity.py is green. Until then, every
stop event triggers a force-resume.

If you genuinely cannot proceed (architectural decision, missing
permission, fundamental disagreement with the plan), ask the user
via AskUserQuestion instead of stopping silently.

If a human reviewer needs to suspend the loop, they can set
DECTALK_ALLOW_STOP=1 in the environment.

Do NOT stop merely because:
- CI just passed (that's a green checkpoint, not a finish line)
- A "natural break point" feels reached
- The current sub-task wrapped up cleanly
- Atomic ports feel like diminishing returns
- A bare "continue" prompt arrived with no fresh content
- You just wrote a "session summary" / "final status snapshot" /
  similar recap. Recaps are a stop tell. If you find yourself
  drafting one, pick the next port target instead.

Resume the in-progress work. If nothing is in-progress, pick the
next port target from /root/.claude/plans/create-a-python-port-smooth-hoare.md
or shrink the largest _DEFERRED dict (printed above) by porting one
of its entries.
EOF

exit 2  # non-zero: force continuation per Claude Code hook protocol.
