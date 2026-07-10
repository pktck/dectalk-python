# Orchestrator bootstrap — standing up a merge-owner session

How to (re)create the autonomy machinery for an orchestrator session
on this repo. Written for the post-Fable era (Opus 4.8 or any model):
the anti-stall design is model-agnostic, but it lives in three layers
and only one of them travels with a git checkout.

## The three layers

| layer | lives in | catches |
|---|---|---|
| Stop hook (`.claude/hooks/stop_sweep_reminder.sh`) | **the repo** — active automatically in any session on a checkout | in-turn stalls ("stopped after finishing a task") + unpushed work |
| Heartbeat trigger (`orchestrator-heartbeat-parity-sweep`) | **the session** — server-side scheduled prompt, survives container restarts | cross-turn stalls, suspended containers, dead sessions (fires every 2 h) |
| Protocol + queue (CLAUDE.md "Autonomy protocol", `docs/PARITY-METHOD.md`, `area/parity` issues) | the repo | direction: what to do on each wake |

A session with only the repo layers self-recovers *within a turn*; the
heartbeat is what revives a session that already stopped. **A new
orchestrator session must create its own heartbeat trigger** — the
existing one is bound to the session that created it and keeps firing
there.

## Creating the heartbeat trigger

In the new orchestrator session, with the Claude Code Remote trigger
tools available (`create_trigger`), create:

- **name**: `orchestrator-heartbeat-parity-sweep`
- **cron**: `0 */2 * * *` (hourly is the platform minimum; 2 h balances
  wake latency against token spend)
- **prompt** (verbatim; adjust the two environment-facts sentences if
  your container's proxy differs — test with one raw
  `curl api.github.com` call and one `git push origin --delete` of a
  scratch branch):

```
[Scheduled heartbeat — anti-stall sweep] You are the merge-owner/orchestrator
for pktck/dectalk-python. Environment facts for this container: raw GH_TOKEN
REST curl and git branch-deletes are BLOCKED by the proxy — use ONLY the
mcp__github__* tools for GitHub state (get_check_runs is truth; get_status
lies "pending"); background curl CI-polls do NOT work, so wakes come from PR
webhook subscriptions and this heartbeat; skip branch deletion (stale merged
branches are cosmetic). Sweep now, per docs/PARITY-METHOD.md:
1. List open PRs to dev (mcp). For each: verify via get_check_runs; if fully
   green, review per the playbook gates, mark ready (update_pull_request
   draft=false), REBASE-merge, unsubscribe.
2. Check in-flight background agents/tasks; read completed outputs; salvage +
   re-dispatch anything that died.
3. If the merge queue is empty and no agents are in flight, dispatch the next
   unclaimed open issue labeled area/parity as an issue-scoped worktree agent
   per CLAUDE.md (shared oracle: DECTALK_SRC=/tmp/dectalk-oracle-src
   DECTALK_BIN=/tmp/dectalk-oracle-bin; draft PR to dev;
   push-early-on-timeout instructions).
4. After each merge wave, re-run scripts/measure_full_vtm1_sample.py with the
   shared-oracle env and report byte-exact / count-exact vs the current
   baselines (see docs/STATUS.md).
5. Only if truly blocked on the user: send one ntfy to the topic in
   CLAUDE.md, then stop.
Never end the turn with zero in-flight work while unclaimed area/parity
issues remain.
```

Manage it with `list_triggers` / `update_trigger` (`enabled:false`
pauses it); a session being paused *for the user's review* should keep
the trigger enabled and simply hold dispatch — the sweep is one cheap
call when idle.

## Operating lessons the hook/trigger design encodes

1. **Push early, push always.** Every session death in the Fable run
   (two session-limit kills, one credit exhaustion) was survivable
   only because work was committed and pushed, or salvageable from a
   worktree by the orchestrator. The Stop hook hard-gates on this.
2. **Bounded nudges, unbounded schedule.** The removed 2026-05 stop
   hook force-resumed until full byte-parity — unbounded, quota-hungry,
   needed a human off-switch. The replacement nudges at most twice per
   burst and lets the *heartbeat* provide persistence instead.
3. **External wakes beat in-session loops.** Webhook subscriptions +
   the scheduled trigger survived everything; in-session polling loops
   did not (and raw-REST polls are impossible in proxy-blocked
   containers anyway).
4. **Verify before propagating.** See `docs/PARITY-METHOD.md` §7 —
   agent conclusions are inputs, not facts.

## Off-switches

- Stop hook: `DECTALK_ALLOW_STOP=1` in the environment (or delete
  `.claude/settings.json` locally).
- Heartbeat: `update_trigger enabled:false`, or delete the trigger.
