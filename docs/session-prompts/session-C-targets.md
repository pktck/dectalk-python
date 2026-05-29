You're a worker session in a multi-session push to reach pure-Python byte parity (DECTALK_DISABLE_CAPI=1) for pktck/dectalk-python. Read CLAUDE.md and docs/PARITY-FINDINGS-2026-05-29.md first.

RULES:
1. Build the C oracle ONCE (`eval "$(scripts/agent_oracle_env.sh)"; scripts/setup_c_oracle.sh`) and share it read-only across all your sub-agents (export the same DECTALK_SRC/DECTALK_BIN; skip per-agent builds). 4-vCPU container → ≤~12 concurrent sub-agents.
2. Edit ONLY your lane's files. Other sessions own the rest.
3. Push `claude/targets-*` branches + open DRAFT PRs to `dev`; do NOT merge — the orchestrator merges.

LANE — PH formant targets / coarticulation:
Files: `src/dectalk/ph/{gettar,getbegtar,getendtar,make_dip,setloc,dph_settar_st}.py`, `src/dectalk/ph/*_locus_tables.py`.
Do NOT touch `rom_tables.py` target tables (#229 done) or `phinton`/`pht0draw`/`make_f0_command` (the orchestrator's F0 lane).

Two known divergences (verified vs the C oracle):
1. **Stop→vowel F2 stuck ~440 Hz high**: on `pa`/`ta`/`ka`/`pea`/`tea`/`key`, Python F2 holds ~1697 Hz through the vowel vs C ~1190. The vowel formant *targets* themselves match C (#229), so this is a stop locus / stop→vowel coarticulation / `make_dip` interpolation bug — find whether it's the stop locus value or the begin-target transition (`getbegtar`/locus tables / `ph_setar.c`).
2. **~70 Hz steady-state F2 offset** on long vowels (e.g. ER/RR in "her"/"world": Py F2 1220 vs C 1313 — wait, that specific case was the ROM #229, already fixed; re-verify): any *residual* steady-state F-offset after #229/#236 is in the smoothing layer (`us_forw_smooth_rules`/`us_back_smooth_rules`/vv-coarticulation/`tarnex`). Pin it to the active C (`ph_setar.c`).

Verify per-frame F1/F2/F3 vs the C oracle on the stop words above + a few vowels. Run `scripts/dev_check.sh --changed`; ruff + pyright clean; no regression.
