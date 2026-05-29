# Wave-A parity diagnostics — synthesis (2026-05-29)

Output of the first Wave-A fan-out: 10 read-only diagnostic agents,
each comparing the pure-Python pipeline to the C oracle at one stage /
corpus-category / Klatt-parameter slice (see
`docs/PARITY-DIAGNOSTIC-MATRIX.md`). This reframes the remaining
pure-Python audio-parity gap and indexes the fix backlog (#217–#229).

## TL;DR

Nearly the entire remaining gap reduces to **three root-cause classes**,
all far more tractable than new ports:

- **A. Wrong build configuration** — the Python port followed C branches
  that the shipped `libtts_us.so` does *not* compile.
- **B. Unwired integrations** — C-faithful logic is ported and tested but
  never called on the active synth path.
- **C. Specific logic gaps** — a handful of localized rule/value bugs.

Already done (contrary to the stale `STATUS.md`): the `us_phtiming`
**duration over-run is solved** (`hello world`/`one two three` now
*exact* sample count; #199 closed); **#121/#122** (us_phalloph wired,
assertiveness) and **#159** (F4/B4/F5/B5 reach the LLFrame) verified
correct; **decimals** fixed (#216).

## The active build configuration (measured)

`libtts_us.so` compiles with `-DENGLISH -DENGLISH_US -DACNA -DACCESS32
-DTYPING_MODE` and, critically, **none** of `HLSYN`, `NEW_VTM`,
`CHANGES_AFTER_V43`, `FAKE_HLSYN`; plus `OLD_INTONATION_AND_TIMING` and
`VOICE_ROM_DECTALK_1996M_43F` (`src/dectalkf_klsyn.h:248,296`);
`VOICE_PARS=20`. Several Python modules assumed the opposite.

## Class A — wrong build configuration (largest waveform impact)

| Finding | Where | Issue |
|---|---|---|
| **`OUT_T0` emitted as frequency, not period** (`muldv(400,1000,f0prime)`). **Dominant per-sample residual** — T0 mean \|Δ\| 559→104 when corrected. | `ph/pht0draw.py:589,1021` ↔ `ph_drwt02.c:1403-1409` | **#227** |
| phdraw runs HLSYN-only blocks: spurious `A2=4000` jams (max \|Δ\|=4000 on sonorants), FVOWEL place-jams, `OUT_TLT=0`, parallel-amp path, formant scaling | `ph/phdraw.py:1681,1694,1530-1644,2370,474` ↔ `ph_draw.c` | **#226** |
| Ports cite inactive source variants (`ph_inton.c`/`ph_inton2.c`, `ph_aloph2.c`, `p_us_tim.c`); active are `ph_inton0.c`, `ph_aloph1.c`, `p_us_tim0.c` | PH docstrings + matrix | **#222** |
| Voice ROM transcribed from BETA5 `p_us_rom.c`; active is `p_us_rom_dectalk_1996m_43f.c` (phone-subset B/F target divergence) | `ph/rom_tables.py:164,217,270,539` | **#229** |

## Class B — unwired integrations (logic ported, never called)

| Finding | Where | Issue |
|---|---|---|
| Spell-out (`say_it`/`ls_spel`) wired into the phoneme stream but **not** the synth path → acronyms −7.5k samples | `api/speak.py:2474` (synth) vs `:1925` (phoneme) | **#217** |
| Ordinal/currency/date/time/fraction/range emitters exist but the number entry point hand-rolls only int/decimal | `api/speak.py:1893-1953`; `lts/{number,date,time,frac}_emit.py` | **#225** |
| Default `to_wav` uses the SenSyn 110-sample frame, not the VTM **71**-sample frame (C: `13845 = 195×71`) | `data/voices.py:54` vs `vtm/pump_frames.py` | **#219** |

## Class C — specific logic gaps

| Finding | Where | Issue |
|---|---|---|
| Internal punctuation pauses collapse to 1 frame + whole text is one declination clause (**dominant for punctuated text**, −2.6k…−10.7k) | `api/speak.py:779-781`, `_render_clause_full` | **#218** |
| F0 baseline low: Paul `average_pitch` 100 vs C **122**; + under-rendered dynamic range / Q-gesture | `ph/voice_definitions.py:55`; `ph/phinton.py:637` | **#220** |
| Content monosyllables marked S2 (CMUdict) vs C's S1 (`dtalk_us.dic`+`ph_sort`) → flattens F0 | `ph/us_phalloph2.py:88` | **#224** |
| `us_phtiming` Rule-1 mask codes bitmask-`any` as `both`; `dpause` 1/0 vs 14/15 (couple with #157 leading-silence) | `ph/us_phtiming.py:281,284,286` | **#228** |
| ~70 Hz steady-state F2 offset on long vowels — smoothing/coarticulation | `ph/phsettar.py:208-275`; `ph_setar.c` smooth | (after #229) |

## Test-infrastructure gaps (no real gate today)

`test_stage_ph_allofeats` is proxy-only (`_STRICT_FEATURES=False`, the
`0006` C-dump patch was never written); `test_python_parstochip_matches_c`
is xfail; `test_per_frame_f0` broke on the `spd_chip` arg. → **#223**
(audit gates) and **#221** (harness fix). Without these, fixes can't be
regression-gated — do these alongside the first fixes.

## Recommended fix order (by leverage) and Wave-B partitioning

Sequence the dominant levers; parallelize across disjoint files.

1. **#227** `OUT_T0` period — `pht0draw.py` *(dominant per-sample)*
2. **#226** phdraw HLSYN gating — `phdraw.py`
3. **#218** punctuation pauses/clauses — `api/speak.py` *(dominant for punctuated text)*
4. **#220 + #224** F0 baseline + stress — `voice_definitions.py`, `us_phalloph2.py` *(the residual f0prime magnitude after #227)*
5. **#229** voice-ROM re-port — `rom_tables.py`
6. **#225 / #217** number + spell-out wiring — `api/speak.py` *(serialize with #218)*
7. **#219** VTM frame, **#228** us_phtiming mask, **#221/#223** gates, **#222** variant audit

**Parallelism map (disjoint hot files → concurrent Wave-B agents):**
`pht0draw.py` · `phdraw.py` · `rom_tables.py` · `us_phtiming.py` ·
`us_phalloph2.py` · `voice_definitions.py` are independent. **`api/speak.py`
is the serialization hotspot** (#218/#217/#225 all touch it) — one agent
at a time there.
