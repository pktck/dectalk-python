You're a worker session in a multi-session push to reach pure-Python byte parity (DECTALK_DISABLE_CAPI=1) for pktck/dectalk-python. Read CLAUDE.md and docs/PARITY-FINDINGS-2026-05-29.md first.

RULES:
1. Build the C oracle ONCE (`eval "$(scripts/agent_oracle_env.sh)"; scripts/setup_c_oracle.sh`) at a fixed path, then have every sub-agent you spawn SHARE it read-only (export the same DECTALK_SRC/DECTALK_BIN; skip per-agent builds). This is a 4-vCPU container, so keep to ≤~12 concurrent sub-agents.
2. Edit ONLY your lane's files (below). Other sessions own the rest.
3. Push `claude/frontend-*` branches and open DRAFT PRs to `dev`; do NOT merge — the orchestrator session merges.

LANE — the pure-Python synth FRONT-END:
Files: `src/dectalk/api/speak.py`, `src/dectalk/ph/us_phalloph2.py`, `src/dectalk/lts/*`.

The audio/synth path (`_render_clause_full` → `_tokens_to_phoneme_words` → `lts()`, speak.py:539,2662) runs its OWN, less-faithful expansion, while `text_to_dectalk_phonemes` (speak.py:1153) is byte-exact vs C across 130K prompts. **Unify the synth path onto `text_to_dectalk_phonemes`** so audio inherits the faithful phoneme stream. This single change closes:
- #217 (spell-out / acronyms not wired into synth path),
- #225 + #238 (ordinals/currency/dates + spoken-number "and"/commas/destress),
- #237 (spurious word-final `-s/-z` → `Z S` allophone),
- the `IH→IX` / `AH→AX` vowel over-reduction and dropped syllabic `EL`/`EN`/long-`IR` (us_phalloph2.py:149-161).

Then make **comma / semicolon / colon a clause delimiter** (mirroring C `ph_task.c:972` `speak_now`-per-delimiter): split the clause body on `,;:` and render each segment as its own `_render_clause_full`/phclause (so the pre-comma word becomes clause-final and gets Rule-2 lengthening), with a COMMACLAUSE trailing pause — gate the period pause/72-frame trailing SIL on actual sentence-terminal punctuation. This SUPERSEDES #218 (whose single-clause GEN_SIL mechanism is structurally wrong; its pause magnitude can be retained per-segment).

Verify allophone stream + sample count vs the C oracle on: BBC/GDP, 999/1234567890, gives/loves/tells, "hello, world.", "we saw big, small, tall, and short". Run `scripts/dev_check.sh --changed`; ruff + pyright clean; no regression on the 130K phoneme corpus. Reference issues with `Closes #N`.
