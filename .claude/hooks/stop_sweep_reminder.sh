#!/usr/bin/env bash
# Stop-hook: bounded anti-stall + work-safety gate.
#
# Replaces the old stop_continue.sh (removed in #264), redesigned from
# the failure analysis of the multi-day autonomous run:
#
#   * The old hook force-resumed until FULL byte-parity passed — an
#     unbounded terminal condition that burned quota and needed a
#     human off-switch. This hook allows every stop after at most
#     MAX_CONSECUTIVE_REMINDERS bounded nudges.
#   * The single most valuable intervention across that run was not
#     "keep going" — it was "PUSH YOUR WORK": every session-limit /
#     credit kill was survivable only because work was committed and
#     pushed early. That check is this hook's hard gate.
#   * The sweep reminder points at the standing protocol docs instead
#     of restating strategy that will go stale.
#
# Behaviour (exit 0 = allow stop, exit 2 = force continuation with the
# stderr text injected as guidance):
#
#   1. DECTALK_ALLOW_STOP=1        -> allow (human off-switch).
#   2. Uncommitted changes          -> block: commit them.
#   3. Unpushed commits             -> block: push them.
#   4. Otherwise                    -> remind about the sweep, at most
#      MAX_CONSECUTIVE_REMINDERS times in a row, then allow. The
#      counter resets whenever a stop is allowed or the marker goes
#      stale, so each fresh work burst gets fresh nudges.
#
# Any unexpected git failure allows the stop: the hook must never
# brick a session. Cheap by design: pure git status checks, no test
# runs, no network.
set -u

# Consume the hook-protocol JSON payload on stdin (unused).
cat >/dev/null 2>&1 || true

MAX_CONSECUTIVE_REMINDERS=2
STALE_SECONDS=21600 # 6 h: a marker older than this is a dead session's

# ------------------------------------------------------------------
# 1. Human off-switch.
# ------------------------------------------------------------------
if [[ "${DECTALK_ALLOW_STOP:-0}" == "1" ]]; then
  printf 'stop-hook: DECTALK_ALLOW_STOP=1 — allowing stop\n' >&2
  exit 0
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
cd "$repo_root" || exit 0

marker="/tmp/dectalk-stop-reminders-$(printf '%s' "$repo_root" | cksum | cut -d' ' -f1)"

allow_and_reset() {
  rm -f "$marker" 2>/dev/null
  exit 0
}

# ------------------------------------------------------------------
# 2. Uncommitted work — the salvage-discipline gate.
# ------------------------------------------------------------------
dirty="$(git status --porcelain 2>/dev/null)" || allow_and_reset
if [[ -n "$dirty" ]]; then
  cat >&2 <<'EOF'
Stop blocked: the working tree has uncommitted changes. The recurring
lesson of this project's autonomous runs is that sessions die without
warning (session limits, credit exhaustion, container reclaim) and
only committed-and-pushed work survives. Commit now (WIP commits are
fine — trailer `Refs: #<issue>`), push the branch, then stop. If these
files are genuinely scratch, clean them up instead. Off-switch:
DECTALK_ALLOW_STOP=1.
EOF
  exit 2
fi

# ------------------------------------------------------------------
# 3. Unpushed commits.
# ------------------------------------------------------------------
branch="$(git branch --show-current 2>/dev/null)"
if [[ -n "$branch" ]]; then
  if git rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1; then
    ahead="$(git rev-list --count '@{upstream}..HEAD' 2>/dev/null || echo 0)"
    if [[ "$ahead" -gt 0 ]]; then
      cat >&2 <<EOF
Stop blocked: branch '$branch' is $ahead commit(s) ahead of its
upstream. Push before stopping (git push) so the work survives a
session death. Off-switch: DECTALK_ALLOW_STOP=1.
EOF
      exit 2
    fi
  elif [[ "$branch" == claude/* ]]; then
    cat >&2 <<EOF
Stop blocked: working branch '$branch' has no upstream — it has never
been pushed. Push it (git push -u origin $branch) so the work survives
a session death. Off-switch: DECTALK_ALLOW_STOP=1.
EOF
    exit 2
  fi
fi

# ------------------------------------------------------------------
# 4. Bounded sweep reminder.
# ------------------------------------------------------------------
count=0
if [[ -f "$marker" ]]; then
  now="$(date +%s)"
  mtime="$(stat -c %Y "$marker" 2>/dev/null || stat -f %m "$marker" 2>/dev/null || echo 0)"
  if (( now - mtime < STALE_SECONDS )); then
    count="$(cat "$marker" 2>/dev/null || echo 0)"
    [[ "$count" =~ ^[0-9]+$ ]] || count=0
  fi
fi

if (( count >= MAX_CONSECUTIVE_REMINDERS )); then
  # Nudged enough this burst — allow the stop and reset. The 2-hourly
  # heartbeat trigger remains the cross-turn dead-man's switch.
  allow_and_reset
fi

printf '%d\n' "$((count + 1))" >"$marker" 2>/dev/null || true
cat >&2 <<'EOF'
Before stopping, run the end-of-turn checklist (CLAUDE.md "Autonomy
protocol"): is a PR webhook subscription or background agent in
flight, or are you genuinely blocked on the user? If none hold and
open `area/parity` issues remain, do the sweep instead of stopping —
merge green PRs per docs/PARITY-METHOD.md §6, salvage/re-dispatch dead
agents, then dispatch the next unclaimed issue (§8 has the queue). If
you ARE blocked on the user, the correct exit is: one ntfy to the
topic in CLAUDE.md, then stop — that stop will be allowed. This
reminder is bounded (it will not loop); DECTALK_ALLOW_STOP=1 skips it
entirely.
EOF
exit 2
