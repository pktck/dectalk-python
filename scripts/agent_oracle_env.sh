#!/usr/bin/env bash
#
# Emit unique DECTALK_SRC / DECTALK_BIN env vars for a parallel agent.
# Usage:
#     eval "$(scripts/agent_oracle_env.sh)"
#     scripts/setup_c_oracle.sh
#
# Each agent gets its own /tmp dirs so concurrent setup_c_oracle.sh runs
# don't trample each other's tree. With the prebuilt-tarball fast path
# in setup_c_oracle.sh, the per-agent setup cost is ~5 s.
#
# The slug derives from $AGENT_SLUG when set (orchestrator may set this
# per agent), otherwise from $$-$RANDOM so two ad-hoc invocations don't
# collide.

set -euo pipefail

slug="${AGENT_SLUG:-$$-${RANDOM}}"
printf 'export DECTALK_SRC=/tmp/dectalk-src-%s\n' "${slug}"
printf 'export DECTALK_BIN=/tmp/dectalk-binary-stable-%s\n' "${slug}"
