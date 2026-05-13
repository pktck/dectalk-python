#!/usr/bin/env bash
# Stop-hook: evaluate whether the session should continue.
#
# Fires when the assistant signals end-of-turn. If the standing
# instruction (continue toward bit-parity with the DECtalk binary,
# don't stop unless hitting a blocker that would shift project
# trajectory) is still in effect, re-inject it as context and force
# the assistant to keep working.
#
# Loop guard: if the hook payload's stop_hook_active flag is true,
# the assistant has already been force-resumed once this turn — exit
# 0 to let it stop cleanly. This prevents infinite Stop/resume loops
# when there's genuinely nothing left to do.
#
# The hook reads its JSON payload on stdin per Claude Code's hook
# protocol. It emits a JSON object on stdout with the reason for
# continuation; non-zero exit forces continuation.
set -euo pipefail

payload="$(cat)"

# Loop guard — if we've already been force-resumed, allow stop.
stop_hook_active=$(printf '%s' "$payload" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print("true" if data.get("stop_hook_active") else "false")
except Exception:
    print("false")
')

if [[ "$stop_hook_active" == "true" ]]; then
  exit 0
fi

# Re-inject the standing instruction.
cat <<'EOF' >&2
Standing instruction reminder: continue working toward byte-identical
bit parity between dectalk.speak() output and the DECtalk binary.

Don't stop unless you hit a blocker that would require shifting the
project trajectory (e.g. ambiguous architectural decision, missing
permission, fundamental disagreement with the plan). In those cases
ask the user via AskUserQuestion rather than stopping silently.

Do NOT stop merely because:
- CI just passed (that's a green checkpoint, not a finish line)
- A "natural break point" feels reached
- The current sub-task wrapped up cleanly
- Atomic ports feel like diminishing returns
- A bare "continue" prompt arrived with no fresh content

Resume the in-progress work. If nothing is in-progress, pick the
next port target from /root/.claude/plans/create-a-python-port-smooth-hoare.md
or the C source.
EOF

exit 2  # non-zero: force continuation per Claude Code hook protocol.
