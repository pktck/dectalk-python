# Parity divergence map: per-frame VTM params, pure-Python vs C oracle

Issue #271 deliverable. Diagnosis-only — no `src/` changes accompany this
document. Captured against `dev` @ `22a8c16` with the shared oracle
(`/tmp/dectalk-oracle-{src,bin}`, upstream pin `32efa30e`, parity patches
0001-0006 applied).

Maps **every** per-frame VTM parameter divergence (`OUT_F1/F2/F3`,
`OUT_B1/B2/B3`, `OUT_AV/AP/A2-A6`, `OUT_TLT`, `OUT_FZ`, plus `OUT_T0` and
the `OUT_PH/DU/PH2` metadata cells) between the pure-Python full pipeline
and the C oracle on four prompts, classifies each cluster, and proposes a
fix order. Cross-links: #263 (parent frontier), #268 (frame-3 first
divergence), #269 (phdraw audit), #270 (timing audit), #220 (question
F0), #226 (TLT re-port, fault 1 landed), #230 (voice-table gains), #266
(leading-silence latch, landed at `49d54d7`). New issues filed from this
map: **#275** (vtm1 pump-path delaypars omission), **#276** (OUT_TLT
residual +3), **#277** (OUT_PH/OUT_DU metadata overwrite).

## Method

**C oracle side.** `CAPI._speak_locked(text, speaker=0, rate=None,
encoding=1)` with `DECTALK_DUMP_DIR` set (the `test_per_frame_f0.py`
pattern); patch 0006 writes one `vtm_frame 21 <p0> … <p20>` line per
`SPC_type_voice` packet the VTM reads (`vtmiont.c`, `case
SPC_type_voice`). `VOICE_PARS == 21` on this build; index 20 is unused
(never written by the non-`NEW_VTM` `send_pars`) and is excluded.

**Python side.** Subprocess with `DECTALK_DISABLE_CAPI=1
DECTALK_FULL_PIPELINE=1 DECTALK_USE_VTM1=1` in the environment **before**
`import dectalk` (the #265 trap); a wrapper on
`dectalk.ph.parstochip_to_frames.parstochip_to_llframe_delayed` records
copies of both arguments per driver frame — `cur` (current parstochip)
and `feed` (previous frame's parstochip). Sanity gate on every capture:
`40000 / OUT_T0` must ramp (span > 5 Hz) around ~120 Hz. All four
captures passed (means 120.5-133.4 Hz, spans 64.7-73.8 Hz).

**Comparison level: post-`send_pars` `delaypars`** (what each VTM
actually consumes on the C side), per `ph_claus.c:694-825`:

- packet *j* takes `OUT_AV`, `OUT_T0` from parstochip frame *j+1* and
  `OUT_TLT = lineartilt[parstochip_{j+1}[OUT_TLT]]` (the `ph_romi.c`
  0..31 → 0..40 LUT);
- all other slots (`AP F1 A2-A6 AB F2 F3 FZ B1 B2 B3 PH DU PH2`) come
  from frame *j* (one-frame delay);
- the first `send_pars` call seeds and does not write, so C emits N-1
  packets for N driver frames — matching the Python driver's first-frame
  discard.

The Python `cur`/`feed` pairs are folded into the same packet layout and
compared cell-by-cell. 71 samples/frame at 11025 Hz; "frame fN" below is
the 0-based packet index (sample offset = 71·N).

**Caveats discovered while building the map** (both matter when reading
any per-frame dump):

1. The C dump's `OUT_PH`/`OUT_DU` are **not** the driver's phone: the
   active `ph_drwt01.c:3022` re-writes them every frame from
   `np_drawt0`, pht0draw's own F0-segment pointer (→ #277; the
   1081/1942 sites are the `NWSNOAA`/`ENGLISH_UK` variant's branch
   tails, not compiled). Phoneme context below therefore uses the
   Python-side cells (driver-written, true `nphone`), delayed one
   frame like the rest of the formant side.
   *[Update, #290/#297]*: the Python port now applies the same
   per-frame `np_drawt0` overwrite (`pht0draw.py` step 13) **and**
   replays the `phonemes = &allophons[SAFETY]` alias
   (`ph_claus.c:597`) behind the `OUT_PH2` one-past-end read, so
   `OUT_PH`/`OUT_DU`/`OUT_PH2` are byte-equal to the dump on the
   pinned prompts (`tests/parity/test_packet_metadata_parity.py`).
   The overwrite is NOT audio-neutral as first classified: vtm1.c:1318
   gates its silence ramp-down on `OUT_PH & PVALUE == 0` (→ #297).
   Dump-based phoneme alignment can now use either side's cells.
2. `how are you` has a real 4-frame count drift (C 200 vs Py 196
   packets, all in one allophone — see the prompt section). Rows after
   the drift onset compare shifted positions; their spans/magnitudes
   overstate. The three other prompts are packet-count-exact.

Frame counts: `hello world` 195 == 195 · `one two three` 201 == 201 ·
`BBC` 206 == 206 · `how are you` C 200 vs Py 196.

Classification vocabulary (issue #271): wrong-variant suspect /
wrong-unit / wrong-value (target-level) / target-hold / smoothing /
transition-shape / metadata-only / downstream / unknown.

---

## Prompt: `hello world` (declarative; the byte-prefix frontier prompt)

195 packets both sides. Allophones (Python driver, du in frames):
GEN_SIL(1) HX(8) AX(8) LL(11) OW(28) W(10) RR(32) LX(12) D(10) IX(4)
GEN_SIL(72). `OUT_T0` exact on all packets (the #262 hard pass).
Exact columns: `T0 A2 A3 A5 AB FZ B1 B2 B3`.

| param | first div. frame | span (n frames) | magnitude max/mean | phoneme context | suspected generation site | classification |
|---|---|---|---|---|---|---|
| OUT_TLT | f0 | f0-f194 (127) | 30 / 7.1 | everywhere; onset GEN_SIL→HX, steady LL/OW… | base TILT target chain (phsettar/gettar/target ROM) + clause-onset init; NOT the #226 zeroing (fixed), NOT lineartilt/spdeftltoff/temptilt (verified equal) | wrong-value (steady raw +3, → #276) + init-state (onset, D2) |
| OUT_F2 | f0 | f0-f141 (46) | 74 / 13.2 | GEN_SIL/HX onset; transitions into LL, W·RR | init_pars/parini + getbegtar clause-onset seed; phdraw draws a transition during leading silence where C holds 1260 flat (f0-f10) | init-state + spurious onset transition (D2) |
| OUT_F3 | f0 | f0-f143 (53) | 151 / 24.1 | GEN_SIL/HX onset (C holds 2600, Py dips 2449→2589) | same as OUT_F2 | init-state + spurious onset transition (D2) |
| OUT_F1 | f13 | f13-f143 (32) | 12 / 5.2 | AX→LL boundary; later transitions | transition draw start-values inherited from D2 offsets; converges at steady targets (LL f17+ exact) | transition-shape, downstream of D2 |
| OUT_AP | f1 | f1-f13 (13) | 4 / 3.4 | HX aspiration (peak C 60 vs Py 56; curve scales ~56/60) | aspiration amplitude target for HX (gettar/phsettar amp chain; GH=70 verified equal both sides) | wrong-value (target-level, D4) |
| OUT_A4 | f107 | f107-f123 (9) | 15 / 7.4 | LX→D closure/release ("worl-D") | phdraw parallel-amp special events (tspesh steps, `ph_draw.c:512-576`) vs Python draw | transition-shape (D4) |
| OUT_A6 | f107 | f107-f123 (9) | 18 / 9.4 | LX→D closure/release; Py non-zero where C 0 | same | transition-shape (D4) |
| OUT_AV | f119 | f119-f122 (4) | 5 / 4.8 | D→IX | `OUT_AV += max(0,(OUT_TLT>>2)-4)` coupling (`ph_draw.c:4299` == `phdraw.py:2527`) | downstream of OUT_TLT (D3) |
| OUT_PH | f5 | f5-f123 (34) | — | metadata | missing `np_drawt0` overwrite (`ph_drwt01.c:1081`) | metadata-only (→ #277) |
| OUT_DU | f13 | f13-f123 (30) | — | metadata | same | metadata-only (→ #277) |
| OUT_PH2 | f124 | f124-f194 (71) | — | trailing GEN_SIL | C reads `allophons[nallotot]` one-past-end (stale 7707); Py zero-filled | metadata-only (→ #277) |

Detail, clause onset (the #268 frontier): during f0-f10 C holds
F2=1260/F3=2600 (first-phone context targets) completely flat through
silence + HX; Python starts offset (P0: F2 1284, F3 2570) and draws a
transition (F2 jumps to 1334 then decays ~-10/frame; F3 dips to 2449 then
recovers +20/frame), reconverging by f9-f10, exact from f17 (LL steady).
First audio is frame 3 (sample 213): what the first audible frames see is
exactly this cluster (plus wrong TLT scale via #275). Steady-state and
most transition frames from f17 on are **exact** for F1/F2/F3 — the
drawing core is healthy; the onset seed and a few transition
start-values are not.

---

## Prompt: `one two three` (number words)

201 packets both sides. Allophones (Python driver, du in frames):
GEN_SIL(1) W(10) AH(22) N(4) T(11) UW(29) TH(12) R(8) IY(33) GEN_SIL(72);
the number-word front-end produced identical allophone/duration
sequences both sides (`OUT_T0` exact; count exact). Exact columns:
`T0 AV A5 B3 PH2`.

| param | first div. frame | span (n) | magnitude max/mean | phoneme context | suspected generation site | classification |
|---|---|---|---|---|---|---|
| OUT_F2 | f0 | f0-f149 (62) | 114 / 41.0 | GEN_SIL/W onset (C 610 vs Py 590); W→AH, transitions | clause-onset seed + transition start-values (init_pars/getbegtar) | init-state + transition-shape (D2) |
| OUT_F1 | f0 | f0-f149 (44) | 99 / 25.4 | GEN_SIL/W onset (C 265 vs Py 262) | same | init-state + transition-shape (D2) |
| OUT_F3 | f0 | f0-f148 (27) | 42 / 9.9 | GEN_SIL/W onset (C 2150 vs Py 2125) | same | init-state (D2) |
| OUT_TLT | f1 | f1-f200 (125) | 20 / 5.2 | everywhere | as hello world | wrong-value +3 (→ #276) + D2 onset |
| OUT_B1 | f48 | f48-f53 (6) | 250 / 250 | T→UW release hold (C 325 vs Py 575, then both 86) | vowel-onset B1 widening after voiceless stop — begin-target/target-hold value (phsettar/getbegtar) | wrong-value (target-hold, D4) |
| OUT_B2 | f48 | f48-f53 (6) | 20 / 20 | T→UW release hold (C 140 vs Py 120) | same | wrong-value (target-hold, D4) |
| OUT_A6 | f34 | f34-f86 (20) | 30 / 19.9 | N-closure anticipatory leak (Py 6-18 where C 0), T-burst peak (C 49 vs Py 37), slower Py decay into UW; TH region | phdraw parallel-amp special events (tspesh) + burst amp targets | transition-shape + wrong-value (D4) |
| OUT_A4 | f34 | f34-f52 (10) | 22 / 12.2 | same window | same | transition-shape (D4) |
| OUT_A3 | f34 | f34-f52 (10) | 13 / 6.8 | same window | same | transition-shape (D4) |
| OUT_A2 | f34 | f34-f52 (10) | 12 / 6.0 | same window | same | transition-shape (D4) |
| OUT_AB | f74 | f74-f93 (20) | 19 / 9.8 | TH frication (bypass amp) | frication amp targets/draw for TH | wrong-value / transition-shape (D4) |
| OUT_AP | f48 | f48-f53 (6) | 6 / 6.0 | T-release aspiration into UW (C 61 vs Py 55) | aspiration amp target (as hello world HX Δ4) | wrong-value (D4) |
| OUT_FZ | f21 | f21-f47 (23) | 29 / 15.1 | AH→N nasal-zero rise (C from 373 step ~+9, Py from 351 step ~+6) and N→T fall | phdraw FZ nasal-zero path (NON_NASAL_ZERO 290 / BOUNDARY 370 / CONS 400 constants + slope) | transition-shape (D5) |
| OUT_PH / OUT_DU | f7 | (23 each) | — | metadata | np_drawt0 overwrite | metadata-only (→ #277) |

---

## Prompt: `BBC` (spell-out)

206 packets both sides. Allophones (Python driver, du in frames):
GEN_SIL(1) B(13) IY(26) B(13) IY(26) S(19) IY(37) GEN_SIL(72); the
spell-out front-end produced identical allophone/duration sequences
(`OUT_T0` exact; count exact). Exact columns:
`T0 AP A2 A3 A4 A5 FZ B1 B2 B3 PH2`.

| param | first div. frame | span (n) | magnitude max/mean | phoneme context | suspected generation site | classification |
|---|---|---|---|---|---|---|
| OUT_F2 | f0 | f0-f154 (34) | 70 / 32.7 | GEN_SIL/B onset (C 1100 vs Py 1065); B→IY transitions ×3 | clause-onset seed + stop→vowel transition start-values | init-state + transition-shape (D2) |
| OUT_F3 | f0 | f0-f153 (33) | 82 / 21.4 | GEN_SIL/B onset (C 2150 vs Py 2125) | same | init-state (D2) |
| OUT_F1 | f0 | f0-f154 (33) | 19 / 7.6 | GEN_SIL/B onset (C 210 vs Py 207) | same | init-state (D2) |
| OUT_TLT | f0 | f0-f205 (105) | 20 / 5.0 | everywhere | as hello world | wrong-value +3 (→ #276) + D2 onset |
| OUT_A6 | f13 | f13-f102 (42) | 17 / 6.3 | B→IY release (C 38 vs Py 25) ×3 B's | voiced-stop release parallel amps (burst events) | wrong-value / transition-shape (D4) |
| OUT_AB | f13 | f13-f57 (15) | 21 / 10.5 | B→IY release (C 54 vs Py 35) | same | wrong-value / transition-shape (D4) |
| OUT_AV | f13 | f13-f54 (7) | 3 / 1.7 | B→IY voicing onset (Py slightly high) | TLT-coupling and/or voiced-stop AV special | downstream / unknown (D3/D4) |
| OUT_PH / OUT_DU | f10 | (20 each) | — | metadata | np_drawt0 overwrite | metadata-only (→ #277) |

Notably: BBC's amplitude table is otherwise **clean** (AP and A2-A4
exact) — the aspiration-target delta only shows on aspirated segments
(HX, T-release), absent here; the A6/AB deltas isolate the voiced-stop
(B) release path.

---

## Prompt: `how are you` (question intonation)

**C 200 vs Py 196 packets — the only count drift in the set.**
Per-allophone durations (`OUT_DU` runs): identical everywhere
(GEN_SIL 1, HX 10, AR 26, Y 13, UW 45, GEN_SIL 72) **except AW: C 34 vs
Py 30** — one allophone accounts for the entire 4-frame drift. True
boundaries: aligned through AW's start (f11); Python runs 4 frames ahead
of C from f41 (Py AR onset) onward, so rows below with spans past ~f41
compare shifted phones and overstate (marked ⚠).

| param | first div. frame | span (n) | magnitude max/mean | phoneme context | suspected generation site | classification |
|---|---|---|---|---|---|---|
| OUT_T0 | f0 | f0-f195 (188) | 50 / 18.9 | entire clause; largest through HX+AW (grows +4→+50 period ≈ −1.5→−15 Hz), tail (final rise) re-converges to ±1 | phinton QUEST-clause gesture chain + pht0draw playback (#220 fault 2); alignment shift compounds after f41 | question-contour (D6, → #220) |
| OUT_DU | f7 | (36) | — | AW duration **30 vs 34** | us_phtiming rule producing AW's duration in a question clause (stressed clause-initial diphthong) | timing (D6b, → #270) |
| OUT_F2 | f0 | f0-f148 (144) ⚠ | 313 / 85.6 | GEN_SIL/HX onset (C 1200 vs Py 1237); AW diphthong; shifted tail | D2 onset + make_dip AW trajectory + shift artifact | init-state + transition-shape ⚠ |
| OUT_F3 | f0 | f0-f148 (143) ⚠ | 292 / 54.8 | as F2 (C 2650 vs Py 2613 at f0) | same | init-state ⚠ |
| OUT_F1 | f0 | f0-f148 (144) ⚠ | 138 / 23.7 | as F2 (C 710 vs Py 687 at f0) | same | init-state ⚠ |
| OUT_TLT | f0 | f0-f146 (109) | 26 / 5.6 | as other prompts | as hello world | wrong-value +3 (→ #276) |
| OUT_AP | f1 | f1-f141 (51) | 16 / 8.4 | HX aspiration (C 49 vs Py 45 — same Δ4 as hello world), later ⚠ | aspiration amp target (D4) | wrong-value (D4) |
| OUT_AV | f10 | f10-f127 (67) ⚠ | 60 / 6.2 | AW voicing; max at shifted boundaries | TLT coupling + T0-contour coupling + shift artifact | downstream ⚠ |
| OUT_B1 | f27 | f27-f195 (76) ⚠ | 50 / 20.2 | inside AW (aligned, Δ2) then shifted | diphthong (make_dip) bandwidth trajectory + shift artifact | transition-shape ⚠ |
| OUT_B2 | f36 | f36-f195 (67) ⚠ | 44 / 21.4 | as B1 | same | transition-shape ⚠ |
| OUT_B3 | f62 | f62-f89 (28) ⚠ | 54 / 42.4 | AR→Y (shifted region) | shift artifact dominates | ⚠ unknown |
| OUT_PH / OUT_PH2 | f7 | (6 / 12) | — | metadata | np_drawt0 overwrite | metadata-only (→ #277) |

The declarative prompts prove the F0 subsystem exact; this prompt
isolates the **question** path: the contour diverges from the very first
packet (before any timing drift exists — C period 328 vs Py 332 at f0)
with the gap growing through the hat/plateau region, while the terminal
rise itself lands within ±1. Combined with AW's 34-vs-30, both question
deltas sit in QUEST-gated code: the phinton gesture chain (#220 fault 2)
and a QUEST-sensitive duration rule (#270's audit scope).

---

## Cross-prompt divergence clusters, ranked by blocking impact

**D1 — vtm1 pump path skips the send_pars delaypars transformation
(→ #275, new).** Not visible in the tables above (the comparison
deliberately reconstructs delaypars on the Python side) but it gates
everything: with `DECTALK_USE_VTM1=1`, `pump_frames_via_vtm1` feeds the
synth **raw** parstochip — wrong tilt scale on every frame (raw 0..31
instead of `lineartilt[]` 0..40) and formant side one frame early at
every transition, on every prompt. Blocks: 4/4 prompts, 100% of frames
at the consumption level. The synth itself is proven byte-exact on
delaypars-level input (#263/#266). Cheap, mechanical fix.

**D2 — clause-onset init state + silence-window drawing (F1/F2/F3, TLT
onset).** 4/4 prompts, frames 0-~16 each plus transition start-values
that inherit the offset deeper into the clause (F2/F3/F1 rows). C holds
the first phone's context targets flat through leading silence; Python
starts offset (F2 ±20-37 Hz, F3 −25..−37 Hz, F1 −3..−23 Hz, TLT raw
−9..−10) and draws motion where C holds. This *is* the #268 frontier
(first audio = frame 3; the audible content of frames 3+ is exactly
these cells) and the target chain is #269's audit scope — covered, no
new issue. Sites: `init_pars`/`parini` seeding, `phsettar(GEN_SIL)` /
`getbegtar` begin targets, phdraw hold-vs-draw during silence.

**D3 — OUT_TLT steady +3 raw offset (→ #276, new) + OUT_AV coupling.**
4/4 prompts, 105-127 frames each (~55-65%): the single widest
audio-relevant param divergence by frame count. Verified not
`lineartilt`/`spdeftltoff`/`temptilt`/#226-zeroing; sits in the base
TILT target/draw. `OUT_AV += max(0,(TLT>>2)-4)` drags AV with it.
Bonus defect: `speak.py:723` seeds `f0_dep_tilt = 73` from the HLSYN vdf
file; active `p_us_vdf_dectalk43.c` `paul[]` has FT=75 (#222/#230
class).

**D4 — obstruent amplitude/bandwidth special events.** 3/4 prompts
(hello: D; one-two-three: N/T/TH; BBC: B×3): anticipatory parallel-amp
leaks before closures (Py ramps A2-A6 where C holds 0), burst peaks
low (C 49 vs Py 37; C 38 vs 25; C 54 vs 35 on AB), slower post-release
decay, the post-T B1/B2 release hold (C 325/140 vs Py 575/120), and the
aspiration peak Δ4-6 (AP: C 60/61/49 vs Py 56/55/45; GH=70 equal both
sides, so target-level not gain-row). Squarely inside #269's audit scope
(amplitude drawing + target chain + `tspesh` special events,
`ph_draw.c:512-576`) — covered, no new issue.

**D5 — FZ nasal-zero transition shape.** 1/4 prompts (the only one with
a nasal): rise/fall start-value and slope around N differ (≤29 Hz, 23
frames); steady values exact. Within #269's formant-drawing scope —
covered.

**D6 — question-clause prosody.** 1/4 prompts: (a) F0 contour diverges
everywhere except the terminal rise (→ #220 fault 2, open; fresh trace
added there); (b) AW duration 34 vs 30 = the only sample-count drift in
this set (→ #270's per-allophone-duration audit; data point added
there). Declaratives are exact on both axes.

**D7 — packet metadata cells (→ #277, new).** OUT_PH/OUT_DU per-frame
overwrite from `np_drawt0` un-ported; OUT_PH2 end-of-clause one-past-end
read. Audio-neutral; poisons alignment tooling and packet-level byte
comparisons. 4/4 prompts.

## Proposed fix order

1. **#275 (D1)** — mechanical; until it lands, no PH-side fix can
   translate into audio bytes on the vtm1 path. Also makes future maps
   directly comparable at the synth input.
2. **D2 via #268/#269** — the clause-onset seed + silence hold. Extends
   the `hello world` byte prefix past 213 directly (it is the first
   audible content divergence once #275 lands). Small scalar/branch
   surface: `init_pars`/`parini`, `getbegtar`, phdraw silence hold.
3. **#276 (D3)** — one target-chain scalar hunt; collapses the widest
   per-frame divergence (TLT on ~60% of frames) plus the AV coupling.
4. **D4 + D5 via #269** — the obstruent special-event audit (burst
   steps, release holds, amp targets, FZ slopes). Largest remaining
   magnitude items (B1 Δ250, A6 Δ30, AB Δ21).
5. **D6 via #220 + #270** — question-clause contour + AW duration;
   unblocks the question slice of the corpus (and is the only
   count-drift cause in this set).
6. **#277 (D7)** — any time; zero audio impact, but do it before
   building more per-frame tooling on OUT_PH.

## Reproduction

Capture (per prompt, separate subprocesses):

```bash
export DECTALK_SRC=/tmp/dectalk-oracle-src DECTALK_BIN=/tmp/dectalk-oracle-bin
# C side: CAPI._speak_locked with DECTALK_DUMP_DIR=<tmp>; parse
#   "vtm_frame 21 ..." lines from <tmp>/vtm_frames.dump.
# Python side: env DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
#   DECTALK_USE_VTM1=1 set before interpreter start; wrap
#   parstochip_to_llframe_delayed, record list(cur)/list(feed) per call;
#   assert 40000/OUT_T0 ramps (span > 5 Hz) or discard the capture.
```

Fold Python rows to delaypars level (`row[i] = feed[i]` for the 17
delayed slots; `TLT = lineartilt[clamp(cur[TLT],0,31)]`; `T0/AV = cur`),
int16-wrap, then compare cell-by-cell against the dump rows. Exclude
index 20 always and OUT_PH/OUT_DU/OUT_PH2 for audio purposes (#277).
*[Update, #290/#297]*: with the `np_drawt0` overwrite and the
`allophons[SAFETY]` alias replay ported, the metadata cells match the
dump byte-for-byte (pinned by
`tests/parity/test_packet_metadata_parity.py`); OUT_PH additionally
feeds the vtm1.c:1318 silence-ramp gate, so it is no longer safe to
exclude when chasing silence-boundary audio divergence — only index 20
remains always-excluded.

Authored-by: Claude:claude-fable-5 pytest
