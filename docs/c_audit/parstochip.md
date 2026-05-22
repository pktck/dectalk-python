# `parstochip` — HL→Klatt frame translator audit

Reference C tree: `${DECTALK_SRC}/src/dapi/src/`. Most-cited files:

- `ph/ph_claus.c` — `send_pars()` (lines 681–859) is the canonical
  parstochip-to-`delaypars` translator that emits one SPC voice
  frame per call.
- `ph/ph_drwt02.c` — writes `parstochip[OUT_T0]` (the F0 cell) in
  HLSYN vs. non-HLSYN builds with different units.
- `ph/ph_draw.c` — writes the NEW_VTM area cells (`OUT_AG`,
  `OUT_AL`, `OUT_AN`, `OUT_PS`, etc.) in raw "x100" / "x10" scaled
  integers.
- `vtm/vtmiont.c` — the canonical SPC-frame → `HLFrame` reader
  (lines 720–750), which applies the unit-conversion scales that
  the Python `_build_hl_frame_from_parstochip` path must mirror.

Reference Python:
`src/dectalk/ph/parstochip_to_frames.py` and the per-frame
driver loop in `src/dectalk/api/speak.py` (lines 575–609).

Scope: this is **doc-only research** — no Python code or tests are
modified. The audit identifies parity divergences in the
`parstochip` → `LLFrame` translator that may bias the
`DECTALK_DISABLE_CAPI=1` audio output relative to the C binary.
Findings are ranked by audibility.

## 1. Source-of-truth: what `send_pars()` actually does

`send_pars()` (ph_claus.c:694–859) implements a **one-frame delay
buffer**. Per call:

1. On the first call (`initpardelay == 0`), allocate `delaypars[]`,
   seed `OUT_TLT/OUT_T0/OUT_AV` to 0, and **return without
   `spcwrite`** — the seed frame is discarded.
2. On every subsequent call:
   - Set `delaypars[OUT_AV] = parstochip[OUT_AV]` (line 720).
   - Set `delaypars[OUT_TLT] = lineartilt[parstochip[OUT_TLT]]`
     (line 731, under `#ifndef NEW_TILT`).
   - Set `delaypars[OUT_T0] = parstochip[OUT_T0]` (line 741).
   - **`spcwrite(delaypars)`** (line 776) — emits the frame whose
     formant/bandwidth/parallel slots are still holding values from
     the *previous* call's parstochip.
   - **After** `spcwrite`, overwrite every other slot
     (`OUT_F1..OUT_B3`, `OUT_FZ`, `OUT_A2..OUT_A6`, `OUT_AB`,
     `OUT_AP`, `OUT_PH`, `OUT_DU`, `OUT_PH2`, plus NEW_VTM
     `OUT_ABLADE`/`OUT_AL`/`OUT_AN`/`OUT_BRST`/`OUT_FNP`/`OUT_GF`/
     `OUT_F4`/`OUT_DP`/`OUT_AG`/`OUT_PS`/`OUT_CNK`/`OUT_UE`/
     `OUT_DC`/`OUT_OQ`/`OUT_ATB`/`OUT_PLACE`) from the *current*
     parstochip, so they will be emitted on the **next** call.

Net effect: `AV`, `TILT` (linearised), and `T0` are real-time;
**every other slot lags by one frame**.

There is also a **dead-code mini-divergence** at line 810–813:

```c
if (pDph_t->parstochip[OUT_AP] >= 10)
    pDph_t->delaypars[OUT_AP] = pDph_t->parstochip[OUT_AP] - 3;
#endif
pDph_t->delaypars[OUT_AP] = pDph_t->parstochip[OUT_AP];
```

The `-3` correction is unconditionally clobbered on the next line.
Python correctly does NOT replicate this dead path.

## 2. Python current — direct path (`parstochip_to_llframe`)

`parstochip_to_frames.py:103`. Used by `parstochip_to_llframe`
(unit-test only entry point; **not** wired into `speak.py`).

- Maps every `OUT_*` slot to its `LLFrame` field with a saturating
  clamp.
- F0 fallback: when `parstochip[OUT_T0] == 0`, substitute
  `_DEFAULT_F0_DECIHZ = 1220` (122 Hz adult-male). C never produces
  zero T0 after `pht0draw` runs — this is an init guard.
- TILT goes through `lineartilt[]` (32-entry table, `ph_romi.c:96`)
  unconditionally; the C build uses `lineartilt` only when
  `NEW_TILT` is undefined (production Linux US-English build).
- Higher formants (`F4..F6`, `B4..B6`) take Python-side fixed
  defaults (3500/4500/5500 Hz, 250/300/500 Hz B) because the
  parstochip array doesn't carry them in classic Klatt mode.

## 3. Python current — delayed path (`parstochip_to_llframe_delayed`)

`parstochip_to_frames.py:167`. **This is the path wired into the
pure-Python pipeline** (`speak.py:608`).

Real-time slots from current parstochip: `F0` (`OUT_T0`), `AV`
(`OUT_AV`), `TL` (`lineartilt[OUT_TLT]`).

Delayed slots from `previous_parstochip`: `Ah` (`OUT_AP`), `F1/B1`,
`F2/B2`, `F3/B3`, `FNZ` (`OUT_FZ`), `A2f..A6f`, `Ab`.

First-call fallback: when `previous_parstochip is None`, the
"delayed" feed is taken from the current frame — collapsing the
seed-frame-discarded behaviour of C's `initpardelay == 0` branch
to a single emitted frame.

`F4..F6 / B4..B6 / OQ / SQ / DI / FL / Af / FNP / BNP / FTP / BTP
/ FTZ / BTZ / A1V..A4V / ANV / ATV` all keep their `LLFrame`
defaults (synth-neutral resting values).

## 4. Python current — `via_hl` path

`parstochip_to_frames.py:325` (`parstochip_to_llframe_via_hl`).
Builds an `HLFrame` + approximated `HLState` from parstochip and
runs the full `hl_synthesize_ll_frame` (HL→LL) mapper. Currently
**not wired into `speak.py`** — exists for opt-in experimentation.

## 5. Deltas ranked by audibility

### 5a. (Critical) `via_hl` path applies no parstochip → HLFrame unit conversion

C source (vtmiont.c:720–750) shows the canonical SPC-frame →
HLFrame reader, which applies these scaling factors:

| HLFrame field | C scale          | Python (`_build_hl_frame_from_parstochip`) | Off-by                      |
|---------------|------------------|-------------------------------------------|------------------------------|
| `ag`          | `* 0.01f`        | direct copy                               | **100×** too large           |
| `al`          | `* 0.1f`         | direct copy                               | **10×** too large            |
| `ab`          | `* 0.1f` from `OUT_ABLADE` | not populated (defaults 0.0)    | missing entirely             |
| `ap`          | `* 0.01f` from `OUT_CNK`   | direct from `OUT_AP` (wrong cell + no scale) | wrong source + 100× wrong |
| `an`          | `* 0.1f`         | direct copy                               | **10×** too large            |
| `ue`          | `(short)…` cast  | direct copy                               | OK in magnitude, but no signed cast |
| `atb`         | `* 0.1f` (signed)| direct copy                               | **10×** too large            |
| `ps`          | `* 0.01f`        | `/ 10.0`                                  | factor of 10 wrong (also docstring incorrectly says "deciHz") |
| `dc`          | `(short)…` cast  | direct copy                               | OK in magnitude, but no signed cast |
| `f0`          | direct           | direct                                    | OK                           |
| `f1/f2/f3`    | direct           | direct                                    | OK                           |
| `f4`          | direct           | direct                                    | OK                           |
| `place`       | `(short)…` cast  | `int(_safe(...))`                         | OK                           |

The C code reads from `parambuff[OUT_X + 1]` because the VTM
input pipe has a 1-cell frame-header prefix; Python reads from
the raw parstochip with no offset, which is correct (the +1 is a
pipe convention, not a parstochip convention).

**Consequence:** when the `via_hl` path is enabled,
`hl_synthesize_ll_frame` sees `state.agf` 100× larger than
`speaker.agm` for any voiced frame, which forces every `AV`
gating branch into the "agx > speaker.agm + agAVModalOffsetMax"
zero-out path (hlframe.c lines 411–414). Audio is silent.

This is the primary reason `parstochip_to_llframe_via_hl` is not
yet wired into `speak.py`.

### 5b. (Moderate) `Ah` aspiration path — semantic confusion

In `send_pars()` (line 813), `OUT_AP` is treated as an aspiration
**amplitude in dB**, copied directly to `delaypars[OUT_AP]`. The
synthesiser's `LLFrame.Ah` field is also in dB. Python's
`parstochip_to_llframe_delayed` correctly maps
`feed[OUT_AP] → frame.Ah` (clamp 0..80 dB).

But `_build_hl_frame_from_parstochip` re-interprets the same
`OUT_AP` cell as `HLFrame.ap`, which `hlframe.c` treats as a
*posterior glottal area* (mm²) and uses in the TL posterior-glottal
correction (`_source_specifics`, hlframe.py:454). vtmiont.c
intentionally reads `frame.ap` from `OUT_CNK` (chink area), **not**
`OUT_AP`. Python is reading the wrong cell, and even if it read
`OUT_CNK` it would still need a `*0.01` scale.

Acknowledged in the docstring as "ShimmedSpeechCircuit path uses
it only for posterior-glottal TL corrections where the
order-of-magnitude matters more than exact units" — but the
order-of-magnitude **is** off by 100×, so TL is materially wrong.

### 5c. (Moderate) F0 clamp ceiling 5000 vs. C ceiling 5121

`parstochip_to_frames.py:136`: `F0=_clamp(f0, 500, 5000)`
(deciHz). The C source `ph_drwt02.c:242` defines
`#define HIGHEST_F0 5121` (Hz×10). The C clamp is applied
*upstream* (line 1383) before `f0prime` is stored into
`parstochip[OUT_T0]`. Python re-clamps at the adapter to a
*tighter* ceiling, which silently dampens the top ~12 Hz of voiced
F0 range. The `LOWEST_F0 = 500` floor matches.

### 5d. (Moderate) `OUT_T0` units differ by build flag

`ph_drwt02.c:1406–1410`:

```c
#if (defined FAKE_HLSYN || !(defined HLSYN))
    pDph_t->parstochip[OUT_T0] = temp;          /* period = 400000/f0prime */
#else
    pDph_t->parstochip[OUT_T0] = pDph_t->f0prime;  /* Hz × 10 */
#endif
```

In the HLSYN-enabled production build (which the C oracle ships),
`OUT_T0` carries `f0prime` directly in deciHz, matching
`LLFrame.F0`. Python assumes this convention, which is correct for
the oracle but would be wrong if a non-HLSYN binary were ever
introspected.

Documented in the `parstochip_to_frames.py:23–28` docstring;
flagged here for completeness — no action needed.

### 5e. (Minor) Bandwidth lower clamps tighter than C

`parstochip_to_frames.py:143–147`: B1/B2/B3 are clamped to a
minimum of 40 Hz. C `send_pars()` does no bandwidth clamping at
all. With the LLFrame default of B1=60 there is no observable
effect, but a downstream caller passing an explicit B1<40 would
diverge silently. Low-risk.

### 5f. (Minor) Amplitude (AV/AP/A2..A6/AB) clamp ceiling 80 dB

Python clamps every dB amplitude to `[0, 80]`
(`parstochip_to_frames.py:137–141, 158–163, 208, 211, 219–224`).
C `send_pars()` does no clamping; the SPC packet format is a
`short`, so the implicit ceiling is 32767. The 80 dB ceiling is a
"safety net during port-in-progress" per the module docstring at
lines 86–100. In practice phdraw produces values ≤ 80, so this is
a no-op for steady-state utterances. Low-risk.

### 5g. (Minor) F0 fallback magic number 122 Hz

When `parstochip[OUT_T0] == 0` the Python path substitutes
`_DEFAULT_F0_DECIHZ = 1220` (122 Hz). C never emits `OUT_T0 == 0`
post-`pht0draw`; the only place this kicks in is at the very
start of the per-frame loop before `pht0draw` has run, which (in
the current `speak.py` driver) **never happens** because `pht0draw`
is called inside the loop before `parstochip_to_llframe_delayed`.
Effectively dead code; harmless.

### 5h. (Trivial) Higher-formant defaults differ slightly from `LLFrame` defaults

`parstochip_to_frames.py:_DEFAULT_F4 = 3500`, `_DEFAULT_B4 = 250`,
`_DEFAULT_F5 = 4500`, `_DEFAULT_B5 = 300`, `_DEFAULT_F6 = 5500`,
`_DEFAULT_B6 = 500`.

`LLFrame` (llsyn.py:111–116) defaults: `F4=3500, B4=200, F5=4500,
B5=250, F6=5500, B6=500`.

`B4` and `B5` differ (250 vs. 200, 300 vs. 250). Likely harmless
because the cascade resonators above F3 have negligible energy
unless excited by frication noise, but inconsistency between two
"neutral" defaults is a minor confusion-source. Pick one source
and document.

### 5i. (Trivial) `OUT_PH`, `OUT_DU`, `OUT_PH2` not copied

C `send_pars()` lines 818–820 copy these to `delaypars[]`. They
are phoneme-code and duration metadata used by SAPI / debug
hooks, not by the synthesiser itself. Python `LLFrame` has no
corresponding fields, so dropping them at this boundary is
correct. No action needed.

### 5j. (Trivial) `asp_bump` side-effect not modelled

C `send_pars()` lines 796–807 set `asp_bump = TRUE` if any
parallel-amplitude slot (`OUT_A2..OUT_A6`, `OUT_AB`, `OUT_AV`)
is non-zero, then on line 851 adds it into
`pDph_t->asperation`. Python's `parstochip_to_llframe_delayed`
is a pure function and has no access to `Dph_t`; the
`asperation` counter feeds back into `ph_inton*.c` decisions
about phrase-end aspiration. Since the per-frame driver doesn't
currently rewire phrase-end aspiration, this is a known gap
flagged for the broader Phase E work.

## 6. Action items (none required by this audit)

This issue is research-only; no Python code or tests should be
modified by this PR.

If the orchestrator wants to file follow-ups, suggested split:

- **#TBD (critical)** — Fix `_build_hl_frame_from_parstochip`
  unit conversions per §5a, scaffold a parity test that compares
  the resulting `HLFrame` against vtmiont.c line 720–750 reads.
  Required before `parstochip_to_llframe_via_hl` can be wired
  into `speak.py`.
- **#TBD (moderate)** — Adjust the direct/delayed F0 ceiling from
  5000 → 5121 deciHz to match `HIGHEST_F0` in `ph_drwt02.c`.
  Small audibility impact; useful for byte-parity on edge-case
  voices.
- **#TBD (moderate)** — Move `parstochip[OUT_AP]` interpretation
  to a single shared helper (current: `Ah` dB in the delayed
  path, `ap` mm² in the via_hl path) and decide whether the
  via_hl path should pull from `OUT_CNK` like vtmiont.c does.
- **#TBD (housekeeping)** — Reconcile the `_DEFAULT_F4..B6` Python
  constants in `parstochip_to_frames.py` against the `LLFrame`
  dataclass defaults (currently inconsistent on B4, B5).

## References

- C: `${DECTALK_SRC}/src/dapi/src/ph/ph_claus.c` — `send_pars()`
  lines 681–859.
- C: `${DECTALK_SRC}/src/dapi/src/ph/ph_drwt02.c:1406–1410` —
  `OUT_T0` units by build flag.
- C: `${DECTALK_SRC}/src/dapi/src/ph/ph_draw.c:4159, 4280, 4282` —
  raw integer area writes (mm² × 100, mm² × 10, pressure × 100).
- C: `${DECTALK_SRC}/src/dapi/src/vtm/vtmiont.c:720–750` —
  canonical SPC-frame → `HLFrame` reader with unit-conversion
  scales.
- C: `${DECTALK_SRC}/src/dapi/src/ph/ph_romi.c:96–105` —
  `lineartilt[32]` table.
- Python: `src/dectalk/ph/parstochip_to_frames.py` (entire file).
- Python: `src/dectalk/api/speak.py:540–613` — per-frame driver
  loop, sole live caller of `parstochip_to_llframe_delayed`.
- Python: `src/dectalk/hlsyn/hlframe.py:557–643` —
  `hl_synthesize_ll_frame` consumes the `HLFrame` constructed by
  the via_hl path.

Closes #87.
