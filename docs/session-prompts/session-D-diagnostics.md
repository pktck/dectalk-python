You're a READ-ONLY diagnostic worker session in a multi-session push to reach pure-Python byte parity (DECTALK_DISABLE_CAPI=1) for pktck/dectalk-python. Read CLAUDE.md, docs/PARITY-FINDINGS-2026-05-29.md, and docs/PARITY-DIAGNOSTIC-MATRIX.md first.

RULES:
1. Build the C oracle ONCE (`eval "$(scripts/agent_oracle_env.sh)"; scripts/setup_c_oracle.sh`) and share it read-only across all your sub-agents (export the same DECTALK_SRC/DECTALK_BIN; skip per-agent builds). 4-vCPU container → ≤~12 concurrent sub-agents.
2. **Do NOT edit code or push branches.** Your output is GitHub issues.

LANE — read-only diagnostic fan-out to widen the fix backlog:
Drain uncovered cells from `docs/PARITY-DIAGNOSTIC-MATRIX.md` — corpus categories not yet diagnosed (morphology suffixes beyond -s/-z, dates/times/currency audio, questions/exclamations, mixed-case, hyphenates, per-language), per-phoneme audio audits, and per-Klatt-parameter sweeps on count-matched prompts.

For each prompt cluster: measure Δ vs the C oracle (`scripts/measure_full_vtm1_sample.py` for the 500-prompt sample; remember all sample deltas are integer multiples of 71 = one VTM frame), localize the divergence (allophone count? which allophone duration? which Klatt parameter if same-length?), and pin it with file:line on both the Python and active-C sides.

When you find a genuinely-new, concrete, file:line root cause NOT already covered by open issues (#217–#238 + the front-end/F0/targets work), **file a scoped GitHub issue** (title, evidence table, fix location, acceptance) — but SEARCH open issues first and add a comment to an existing one rather than filing a duplicate. Return a summary of issues filed/commented.

Active-build caveats (so you cite the right C): no HLSYN/NEW_VTM/CHANGES_AFTER_V43; OLD_INTONATION_AND_TIMING; VOICE_ROM_DECTALK_1996M_43F. Active files: ph_inton0.c, ph_drwt01.c, ph_aloph1.c, p_us_tim0.c, p_us_rom_dectalk_1996m_43f.c, p_us_vdf_dectalk43.c.
