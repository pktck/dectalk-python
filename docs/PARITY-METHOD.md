# Parity diagnosis method — the Phase E playbook

Written 2026-07-06 during the Fable 5 window, as the operating manual
for closing the remaining pure-Python byte-parity gap. It encodes the
method that produced every parity win to date and the traps that
produced two near-miss misdiagnoses. **Read this before touching any
parity work, and before trusting any parity claim.**

## 1. Goal and ladder state

Goal: `DECTALK_DISABLE_CAPI=1` + the full pure-Python pipeline renders
**byte-identical** WAVs vs the C `say` binary. The parity path is
**FULL+VTM1** (`DECTALK_FULL_PIPELINE=1`; vtm1 is the only FULL-path
render since #279 retired the legacy hlsyn render, which over-ran
uniformly and caused the #254 misdiagnosis).

Ladder for `hello world` (13845 samples), as of dev `22a8c16`:

- [x] Phoneme stream byte-exact (#256 front-end unification)
- [x] Sample count exact — 189/500 corpus prompts (0/500 byte-exact)
- [x] F0 contour frame-exact — mean |Δ| = 0.0 Hz, a **hard** parity
      test (#257 dynamics re-port, #260 mean, #262 range)
- [x] Leading silence byte-exact — first-audio sample 213 (#267)
- [ ] Per-frame formants/amplitudes from frame 3 on (#268 #269 #271)
- [ ] Timing for the other 311 prompts (#270)

## 2. The core loop (per barrier)

1. Render both sides (capture rules in §4; C reference:
   `$DECTALK_BIN/say -a "TEXT" -fo out.wav`).
2. Find the first diverging **sample**; divide by 71 (samples/frame at
   11025 Hz) to get the **frame**.
3. Dump the oracle's per-frame voice packets: `DECTALK_DUMP_DIR=… `+
   patch-0006 `vtm_frames.dump` (full packet, every `OUT_*` cell; see
   `tests/parity/test_per_frame_f0.py` for the invocation pattern).
4. Capture the Python per-frame `parstochip[]` stream (§4).
5. Compare at the post-`send_pars` `delaypars` level: formant-side
   indices are delayed one frame; `OUT_TLT` maps through the
   `lineartilt[]` LUT; `OUT_AV`/`OUT_T0` are current-frame.
   F0 in Hz = `40000 / OUT_T0`.
6. The first diverging **param** names the generation site
   (`phdraw`/`phsettar`/`gettar`/`getbegtar`/`make_dip`/voice seeding).
7. **Check the wrong-variant table (§3) before anything else.**
8. Fix → verify (§5) → draft PR to `dev` → orchestrator merges.

Every barrier so far has been **diagnosis-hard, fix-easy**: the fix is
usually one line once the divergence is named.

## 3. The wrong-variant checklist (root cause #1)

The shipped/oracle build compiles with **no** `HLSYN` / `NEW_VTM` /
`CHANGES_AFTER_V43` / `FAKE_HLSYN`; **with** `OLD_INTONATION_AND_TIMING`,
`VOICE_ROM_DECTALK_1996M_43F`, `VDF_DECTALK_43`. US English is the
**second** function definition in multi-variant C files. Voice rows:
the non-`_8` variants are active at ≥ 8763 Hz (`ph_vset.c:449-459`).

Precedents — all were one-line fixes after deep diagnosis:

| PR | symptom | root cause | C ref |
|---|---|---|---|
| #257 | flat F0 dynamics | whole F0 subsystem ported from `ph_inton2.c`/`ph_drwt02.c` (HLSYN) instead of `ph_inton0.c`/`ph_drwt01.c` | those files |
| #260 | mean F0 ~20 Hz low | `f0minimum` used the HLSYN `(AP-12)*10`; active is `AP*10` | `ph_vset.c:615` vs `:617` |
| #262 | F0 range ~70% of C | `size_hat_rise` missing `*10`; `f0basefall` never seeded | `ph_vset.c:611`, `:620` |
| #267 | first byte div @ 142 | leading-silence latch held 2 frames; the binary holds 3 | `vtm1.c:383-398` |

Note on #267: when the C **source** and the shipped **binary**
disagree, the binary wins — the byte-exact binary is the spec, and the
16-shard c-oracle corpus is the arbiter.

## 4. Capture rules (the #265 trap)

- Set `DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1` **before**
  `import dectalk` — or render in a subprocess. Setting them after
  import silently measures the wrong pipeline.
- **Sanity-check every capture**: `OUT_T0` must show ~120 Hz ramping
  on `hello world`. Flat ~110 Hz ⇒ wrong pipeline ⇒ discard the
  capture and every conclusion drawn from it.
- Python per-frame capture: monkeypatch
  `dectalk.ph.parstochip_to_frames.send_pars_delaypars` — the
  per-frame packet builder the driver calls with the raw
  current/previous parstochip pair (the #279 capture seam; pattern
  in `tests/parity/test_per_frame_f0.py`).
- Oracle: the **shared** per-container build at
  `/tmp/dectalk-oracle-src` + `/tmp/dectalk-oracle-bin`. Never rebuild
  per-agent; `scripts/setup_c_oracle.sh` fetches a prebuilt tarball if
  a container lacks it.

## 5. Verification gates

Per fix (local, fast):
- `hello world` first-audio sample == 213 and the byte-identical
  prefix did not shrink.
- Sample counts unchanged and == C on `hello world` / `BBC` /
  `one two three`.
- `tests/parity/test_per_frame_f0.py` — `hello world` stays a **hard
  pass**.
- `scripts/dev_check.sh --changed` green.

Per PR (CI, authoritative — required for anything with blast radius):
- All 16 `c-oracle` shards + `Tests with C library` green — the corpus
  gate (133K byte-exact phoneme prompts + CAPI WAV parity 1065/1065).
- `get_check_runs` is the truth; the legacy `get_status` API reports
  "pending" forever.

Metrics that matter: **per-frame param deltas** and **byte-identical
prefix length**. Raw waveform RMS is *not* a progress metric (phase
drift dominates once F0 differs anywhere), and sample count alone is
necessary but nowhere near sufficient.

## 6. Orchestration mechanics (merge-owner)

- Workers: issue-scoped `claude/<lane>-*` branch → **draft** PR to
  `dev`, `Closes #N` / `Refs #N`, `Authored-by:` trailer. Workers never
  merge.
- Orchestrator: **independently re-verify any claim that contradicts a
  CI-locked result** (see §7), mark ready, **rebase**-merge (linear
  history required), unsubscribe. Branch deletion: try the REST
  `DELETE /git/refs/heads/…` or `git push origin --delete`; some
  containers' proxies block BOTH (REST 403 + sideband disconnect) —
  if so, skip it: stale merged branches are cosmetic.
- Orchestrator commits: `git -c commit.gpgsign=false commit …`.
- After every push: `subscribe_pr_activity`. Where raw `GH_TOKEN`
  REST works, also arm a `run_in_background` until-loop polling
  check-runs (its completion is a reliable wake). In containers whose
  proxy blocks raw REST (curl returns "GitHub access is not enabled"),
  background curl polls CANNOT work — wakes come from the CI-status
  sticky-comment webhook, scheduled self check-ins, and the heartbeat
  trigger; read CI state via mcp `get_check_runs` in the foreground.
- Stale webhooks: verify a CI event's commit SHA before acting on it;
  concurrency cancels superseded runs.

## 7. Misdiagnosis case studies — verify before propagating

- **#254**: measured the FULL path **without** VTM1 → phantom "+7600
  regression", blamed #229, demanded a revert. Reality: wrong path +
  misread `docs/STATUS.md` direction. Caught by a direct pre/post
  repro; #229 was untouched.
- **#265**: env-set-after-import capture → false "F0 is flat" claim
  (contradicting the CI-hard #262 result) and unreliable F2/F3
  findings — wrapped around a **correct** VTM-latch discovery. Caught
  by re-running the hard test; the good finding was salvaged into
  #266/#267 and the rest discarded.

Rule: agent conclusions are inputs, not facts. Anything that
contradicts a hard CI assertion gets re-verified from scratch before
any action (especially reverts).

## 8. The queue

Work through open `area/parity` issues; as of writing: #268 (frame-3
first divergence), #269 (phdraw vs `ph_drwt01.c` audit), #270 (timing
vs `p_us_tim0.c` audit), #271 (divergence map — spawns further
issues), #272 (VTM1 default). After each merge wave, re-run
`scripts/measure_full_vtm1_sample.py` and track byte-exact /
count-exact against the 0/500 and 189/500 baselines. The loop in §2
repeats until byte-exact prompts appear, then the corpus closes in.
