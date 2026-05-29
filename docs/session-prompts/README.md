# Multi-session parallelization — how to scale to 100+ agents

To run 100+ agents you need more cloud containers, and **each Claude Code web session is its
own fresh 4-vCPU VM**. One session productively runs ~12–15 concurrent sub-agents (CPU-bound);
beyond that they just time-share 4 cores. So scaling = **more sessions**, which **only you can
start** (there is no tool for an agent to create a session) — at https://claude.ai/code.

## How many

- **Start 4 worker sessions** (5 total with the orchestrator session that's already running).
- If no rate-limit errors appear, add **1–2 more diagnostic sessions** → ~7 total ≈ 90–100
  concurrent agents.
- Don't exceed ~7: your **account rate limits are shared across all sessions** and bind before
  compute does.

## How to start each

For each session: go to claude.ai/code → repo `pktck/dectalk-python`, branch `dev`
(same environment is fine — each gets its own container) → paste the contents of one file below
as the task prompt.

| File | Lane | Don't touch |
|---|---|---|
| `session-A-frontend.md` | synth front-end unification + comma-as-clause | F0, voice, targets |
| `session-B-voice.md` | voice tables + speaker amplitude (`spd_chip`) | front-end, F0, targets |
| `session-C-targets.md` | PH formant targets / coarticulation | F0, front-end, voice |
| `session-D-diagnostics.md` | read-only diagnostics → file issues | (edits nothing) |

The **orchestrator session** (already running) keeps the **F0 subsystem re-port (#220)** — the
dominant lever — and is the **only** session that merges into `dev`.

## Coordination rules (baked into each prompt)

1. Each session builds the C oracle **once** and shares it read-only across its sub-agents
   (≤~12 concurrent, 4 vCPU).
2. Each session edits **only its lane's files** (lanes touch disjoint files → no collisions).
3. Worker sessions push `claude/<lane>-*` branches and open **draft** PRs to `dev`, but **never
   merge** — the orchestrator reviews and rebase-merges them serially.
4. Sync happens through GitHub (branches + issues), since sessions are filesystem-isolated.

See `docs/PARITY-FINDINGS-2026-05-29.md` for the full root-cause map and
`/root/.claude/plans/generic-launching-globe.md` for the plan.
