You're a worker session in a multi-session push to reach pure-Python byte parity (DECTALK_DISABLE_CAPI=1) for pktck/dectalk-python. Read CLAUDE.md and docs/PARITY-FINDINGS-2026-05-29.md first.

RULES:
1. Build the C oracle ONCE (`eval "$(scripts/agent_oracle_env.sh)"; scripts/setup_c_oracle.sh`) and share it read-only across all your sub-agents (export the same DECTALK_SRC/DECTALK_BIN; skip per-agent builds). 4-vCPU container → ≤~12 concurrent sub-agents.
2. Edit ONLY your lane's files. Other sessions own the rest.
3. Push `claude/voice-*` branches + open DRAFT PRs to `dev`; do NOT merge — the orchestrator merges.

LANE — voice tables + speaker amplitude:
Files: `src/dectalk/ph/voice_definitions.py`, `src/dectalk/vtm/spd_chip.py`.
(NOTE: #235 amplitude ROM tables in `rom_tables.py` are ALREADY DONE/merged — do not touch `rom_tables.py`.)

1. **#230 — re-source all 10 US voices** in `voice_definitions.py` from the ACTIVE `p_us_vdf_dectalk43.c`. CRITICAL: the active build uses the **non-`_8` `paul`** row (selected at sample rate ≥ 8763 Hz per `ph_vset.c:449-459`), NOT `paul_8` (which is the <8763 Hz / 8 kHz path). The active Paul gains are GF=70 GH=70 GV=65 GN=74 G1=68 G3=48 G4=64 LO=86 OS=0. Re-source every voice's full row from the active table, set `voice_chris = voice_paul`, repoint the parity test at `p_us_vdf_dectalk43.c`, and remove the `_C_SOURCE_OVERRIDES` shim in `tests/unit/test_ph_voice_definitions.py`.
2. **spd_chip fix** — `src/dectalk/vtm/spd_chip.py::default_us_paul_spd()` hardcodes Paul's gains from `p_us_vdf1.c::paul_8` (the HLSYN file, stale — HLSYN is not in the active build). This is the path that actually feeds synth amplitude, so it's the real gain lever. Correct it to the active non-`_8` `paul` gains. Verify per-frame A1-A6/AV amplitude vs the C oracle on "hello world" / "she sells sea shells".

Run `scripts/dev_check.sh --changed`; ruff + pyright clean; no regression. Reference issues with `Closes #N` / `Refs #230`.
