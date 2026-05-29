# Pure-Python parity — Wave-A diagnostic matrix & fan-out plan

The path from "functionally correct but 0/500 byte-exact" to bit-parity,
decomposed for wide parallel execution. This file is the **dispatch
source** for the orchestrator: each row is an independent, read-only
diagnostic task that localises one divergence and files one scoped
fix-issue. Fixes (Wave B) are dispatched from the resulting issue
backlog, not from here.

## Current state (read first)

- **Goal:** `dectalk.to_wav(text)` byte-identical to the C `say` binary
  with `DECTALK_DISABLE_CAPI=1`.
- **Done:** phoneme stream byte-exact (130K+ prompts); `hlsyn` Klatt
  back-end bit-exact (≤1 LSB).
- **Blocker:** Phase E (PH/VTM). Latest sample (PR #215): **0/500
  byte-exact**, median |Δ|≈426 samples. The gap is now in *waveform /
  formant values*, not only duration.
- **Closed-as-done:** #121 (`us_phalloph` wired), #122 (assertiveness).
- **Open engineering issues:** **#199** `us_phtiming` re-port from
  `p_us_tim0.c` (*74.6% of the remaining gap*), #200 leading silence,
  #201 front-end under-run.

## The one hard ordering constraint

**Sample-count parity must land before most byte-level work is
meaningful** — when Python and C disagree on length, a per-sample diff
is dominated by misalignment, not by formant error. Therefore:

1. **Critical path:** land **#199** (timing) first; re-baseline the
   500-prompt sample. This is a single large port, *not* a fan-out task.
2. **Parallel-safe now (not timing-blocked):** everything that compares
   *intermediate* state at a stage boundary (phoneme stream, allofeats,
   targets, F0 commands, SpdChip/VtmT fields) rather than final audio,
   **plus** the handful of prompts that already match sample count
   (e.g. questions — "count matches, bytes differ", PR #215 pattern #5).
3. **Floodgates (post-#199):** once lengths align, the full per-sample /
   per-Klatt-parameter fan-out across the whole corpus becomes
   meaningful → ramp Wave A to its full width.

## Execution model

Per `CLAUDE.md`: orchestrator dispatches issue-scoped, **worktree-isolated**
agents; merges to protected `dev` are serial rebase-merges.

- **Wave A — diagnostics (this file, 100+ cells, fully parallel).**
  Read-only. Output = one GitHub issue per cell, with: the measured Δ,
  the *first* diverging stage/line, the C source location, and an
  acceptance target. **No branches, no PRs, no CI** → zero merge
  conflict, zero CI load. This is where "100+ agents" genuinely applies.
- **Wave B — fixes (bounded width).** Drains the Wave-A backlog.
  Worktree per agent, **partitioned by subsystem/hot-file** so no two
  agents edit `ph/timing.py` / `api/speak.py` / `ph/phdraw.py` at once.
  Fixes stacked into milestone PRs (per the 1000+-LOC cadence) to avoid
  flooding the 16-shard c-oracle matrix. Throughput is gated by
  orchestrator review + serial merge — widen it by subsystem
  partitioning, not by raw agent count.

### Per-agent recipe (validated: oracle builds in ~18 s here)

```bash
export AGENT_SLUG=<unique>            # orchestrator sets this
eval "$(scripts/agent_oracle_env.sh)" # isolated DECTALK_SRC / DECTALK_BIN
scripts/setup_c_oracle.sh             # ~5–20 s (prebuilt tarball)
# ... run the cell's diff (below) ...
```

Diagnostics build on the **existing** harnesses — do not reinvent:
`tests/parity/_stage_helpers.py`, `test_stage_{kernel,cmd,lts}_parity.py`,
`test_stage_ph_allofeats_parity.py`, `test_stage_ph_targets_parity.py`,
`test_stage_vtm_parity.py`, `test_per_frame_f0.py`, and the
`DECTALK_DUMP_DIR` stage dumps (`CAPI.dump_pipeline`).

---

## Axis 1 — Stage-boundary parity (per function) — ~50 cells

Compare Python intermediate state vs the C oracle at each function
boundary; report the **first** divergence. `B?` = blocked by #199 timing.

| # | Stage / cell | Python target | C source | Harness | B? |
|--:|---|---|---|---|:--:|
| A1 | kernel: integer expansion | `kernel/numbers.py` | `dapi/.../kernel` | stage_kernel | no |
| A2 | kernel: decimal expansion (verify #216) | `kernel/text.py` | kernel | stage_kernel | no |
| A3 | kernel: acronym/spell-out (2/3/4-letter) | `kernel/text.py` | kernel | stage_kernel | no |
| A4 | kernel: abbreviation overrides (Dr/Mr/St) | `kernel/text.py` | kernel | stage_kernel | no |
| A5 | kernel: clause/pause classification | `kernel/text.py` | kernel | stage_kernel | no |
| A6 | cmd: `par_match_rule` | `cmd/par_match_rule.py` | `cmd/*` | stage_cmd | no |
| A7 | cmd: `par_process_input` | `cmd/par_process_input.py` | `cmd/*` | stage_cmd | no |
| A8 | cmd: `[:rate N]` WPM semantics | `cmd/commands.py` | cmd | stage_cmd | no |
| A9 | lts: suffix stripping families | `lts/rules_us.py` | `lts/*` | stage_lts | no |
| A10 | lts: stress-digit assignment | `lts/rules_us.py` | lts | stage_lts | no |
| A11 | lts: syllabic-L/N, AH0/IH0 reduction | `lts/rules_us.py` | lts | stage_lts | no |
| A12 | ph: `all_phsort` US path | `ph/all_phsort.py` | `ph/ph_sort.c` | stage_ph_targets | no |
| A13 | ph: `gettar` / `us_gettar` dispatch | `ph/gettar.py` | `ph/ph_setar.c` | stage_ph_targets | no |
| A14 | ph: `getbegtar` / `getendtar` | `ph/get*tar.py` | ph_setar.c | stage_ph_targets | no |
| A15 | ph: `make_dip` | `ph/make_dip.py` | ph_setar.c | stage_ph_targets | no |
| A16 | ph: `setloc` | `ph/setloc.py` | ph_setar.c | stage_ph_targets | no |
| A17 | ph: `phsettar` orchestration | `ph/dph_settar_st.py` | ph_setar.c | stage_ph_targets | no |
| A18 | ph: `us_forw/back_smooth_rules` | `ph/*smooth*` | ph_setar.c | stage_ph_targets | no |
| A19 | ph: `us_special_rules` / `*_coartic` | `ph/*coartic*` | ph_setar.c | stage_ph_targets | no |
| A20 | ph: `tarnex` coarticulation | `ph/*` | ph_setar.c | stage_ph_targets | no |
| A21 | ph: non-US locus tables (uk/fr/gr/la/sp) | `ph/*_locus_tables.py` | ph_setar.c | stage_ph_targets | no |
| A22 | ph: `phinton` Rules 1–9 (each a cell) | `ph/f0_intonation.py` | `ph/ph_inton.c` | per_frame_f0 | no |
| A23 | ph: `ph_setallofeats` | `ph/make_out_phonol.py` | ph_inton.c | stage_ph_allofeats | no |
| A24 | ph: `make_f0_command` | `ph/make_f0_command.py` | ph_inton.c | per_frame_f0 | no |
| A25 | ph: `interp_user_f0` | `ph/interp_user_f0.py` | ph_inton.c | per_frame_f0 | partial |
| A26 | **ph: `us_phtiming` (=#199)** | `ph/timing.py` | `ph/p_us_tim0.c` | stage_ph_targets | **IS the gap** |
| A27 | ph: `init_timing` wiring | `ph/init_timing.py` | p_us_tim0.c | stage_ph_targets | yes |
| A28 | ph: `durlookup` / `frame_counts` | `ph/durlookup.py` | ph_timng.c | stage_ph_targets | yes |
| A29 | ph: `phdraw` per-frame Klatt emission | `ph/phdraw.py` | `ph/ph_draw.c` | per_frame | yes |
| A30 | ph: `pht0draw` MALE F0 contour | `ph/*pht0draw*` | `ph/ph_drwt02.c` | per_frame_f0 | partial |
| A31 | ph: `pht0draw` FEMALE branch | `ph/*pht0draw*` | ph_drwt02.c | per_frame_f0 | partial |
| A32 | ph: `dcstep` tracker / GEN_SIL ends | `ph/phdraw.py` | ph_draw.c | per_frame | yes |
| A33 | ph: FVOWEL A2-jamming, F3/F2 floor | `ph/phdraw.py` | ph_draw.c | per_frame | yes |
| A34 | ph→chip: `parstochip` | `ph/parstochip*` | `ph/*` | stage_vtm | yes |
| A35 | ph→chip: `parstochip_to_llframe_delayed` (F4/B4/F5/B5 — #159) | `ph/*llframe*` | ph/* | stage_vtm | yes |
| A36 | ph→chip: `lineartilt` LUT + send_pars delay | `ph/*` | ph/* | stage_vtm | yes |
| A37 | vtm: `seed_speaker_state` (verify #103) | `vtm/seed_speaker_state.py` | `vtm/*` | seed_speaker_state | no |
| A38 | vtm: `spd_chip` US-Paul defaults (#85) | `vtm/spd_chip.py` | vtm | stage_vtm | no |
| A39 | vtm: `set_sample_rate` / UI 110 vs 71 (#152) | `vtm/set_sample_rate.py` | vtm | stage_vtm | yes |
| A40 | vtm: `pump_frames` / `vtm_main` | `vtm/vtm_main.py` | vtm | vtm1_pcm | yes |
| A41 | vtm: `resonator` / `setzeroabc` | `vtm/resonator.py` | vtm | synth | no |
| A42 | vtm: `speech_waveform_generator` | `vtm/speech_waveform_generator.py` | vtm | vtm1_pcm | yes |
| A43 | hlsyn: `circuit` aerodynamic solver (regress) | `hlsyn/*circuit*` | `hlsyn/circuit.c` | synth | no |
| A44 | hlsyn: `hlframe` HL→LL mapper (regress) | `hlsyn/hlframe.py` | hlframe.c | synth | no |
| A45 | hlsyn: `nasalf1x` (regress, #91) | `hlsyn/*nasal*` | nasalf1x.c | synth | no |
| A46 | api: `_render_clause_full` clause start (#200) | `api/speak.py` | — | binary_wav | yes |
| A47 | api: leading/trailing silence pads (#200/#201) | `api/speak.py` | — | binary_wav | yes |
| A48 | KsdT defaults vs C (#84) | `ph/dph_t.py` | ph | stage_ph_targets | no |
| A49 | init_phclause defaults vs C (#74) | `ph/init_phclause.py` | ph | stage_ph_targets | no |
| A50 | frame-level Klatt parity sweep (#86) | (all) | ph/vtm | per_frame | yes |

## Axis 2 — Corpus-category root-cause — ~45 cells

Stratify the 133K-prompt corpus; one agent per category measures the
gap distribution and root-causes it to an Axis-1 cell. Seeded by the
PR #215 ranked failure patterns (★ = named there).

`numbers:` integers · decimals★(#216) · ordinals · currency `$`/`¢` ·
version strings★ (`6.2.0`) · dates `12/25` · times · phone numbers ·
ranges · fractions.
`acronyms:` 2-letter · 3-letter★ · 4-letter · mixed-case · ALLCAPS ·
dotted (`U.S.A`).
`morphology:` plural/-s · -ed · -ing · -tion/-sion · -ment/-ness ·
-ful/-less · -er/-est/-ly · -ive/-ify · possessive `'s` · `n't`.
`prosody:` questions★ (count-matches/bytes-differ) · exclamations `!` ·
multi-clause comma★ (inter-clause pause) · ellipsis · quotes · parens ·
em-dash · long paragraph (declination).
`reduction:` function-word destress (a/and/to/for) · sentence-initial
stress · syllabic-L/N · AH0/IH0 context-gates.
`phone probes:` one cell per vowel · per stop · per fricative · per
nasal · per liquid/glide (single-word minimal prompts).
`directives:` `[:rate N]` · voice switch · `[:phoneme on]` · `[:nb]`.

## Axis 3 — Per-Klatt-parameter frame divergence — ~24 cells

For each reference prompt (`hello world`, a `?`-question, a long vowel,
a fricative-heavy word, a nasal word), diff each parameter frame-by-frame
and attribute drift to its source function. Params: `OUT_T0` (F0),
`F1–F5`, `B1–B5`, `AV`, `AVS`, `AH`, `AF`, `OQ`, `TL` (tilt), `AspV`,
plus the parallel branch amplitudes. (~20 params × 5 prompts, deduped to
~24 high-signal cells; most are #199-blocked except F0/source on
count-matched prompts.)

---

## Dispatch protocol

Orchestrator, per cell:
1. Open a GitHub issue: title `parity-diag: <cell>`, body = the cell's
   target + harness + C location + acceptance metric; labels
   `area/<subsystem>`, `size/small`, `diagnostic`.
2. Spawn a background, worktree-isolated agent with `AGENT_SLUG` set and
   a 2-line prompt citing the issue. The agent runs the recipe, writes a
   findings comment on the issue (measured Δ, first-divergence
   stage+line, C ref, proposed minimal fix + expected sample recovery),
   and **does not** push code.
3. Triage incoming findings into the **Wave-B fix backlog**, grouped by
   hot-file so fix agents don't collide.

Ramp Wave A in batches (~20–25 concurrent) to respect API rate limits
and container CPU; the cells are independent, so order is free — front-
load the `B? = no` rows so progress isn't wasted behind #199.

## Guardrails

- Wave-A agents never branch/PR → no CI load, no merge conflicts.
- Wave-B PRs throttled to milestones (1000+ LOC, multiple commits);
  the 16-shard c-oracle matrix is the expensive resource.
- Per-agent oracle isolation (`agent_oracle_env.sh`) prevents source-tree
  trampling; worktrees isolate write paths.
- Protected `dev`: linear history, rebase-merge, serial.
- **`main` is 907 commits behind `dev`** and effectively retired; decide
  whether to fast-forward it from `dev` at the next parity milestone.
