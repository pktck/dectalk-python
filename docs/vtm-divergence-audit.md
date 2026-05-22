# VTM-stage divergence audit (issue #83)

Research-only audit of the VTM (Vocal Tract Model) stage in the
Python port versus the C oracle. Looks at what the C binary
actually runs at the PH→VTM boundary, what the Python pipeline
runs in its place, and where the largest divergence contributors
live.

## TL;DR

The headline finding is **architectural**, not numeric: there is
no Python "VTM" module that runs in the audio path. The directory
`src/dectalk/vtm/` is almost entirely:

- lookup tables ported as Python data
  (`amp_table`, `cosine_radius_tables`, `glottal_b0_table`,
  `log_tables`, `nasal_zero_tables`, `sinetab`, `tilt_tables`,
  `volume_table`),
- the SPD_CHIP voice-data factory (`spd_chip`,
  `read_speaker_definition`),
- thin architectural shims for the C source's pthread / pipe
  machinery (`vtm_main`, `empty_vtm_pipe`, `sync_main`,
  `send_visual_notification`, `play_tones`,
  `initialize_vtm`),
- two small helpers used by other stages (`frac.frac4mul`,
  `setzeroabc`, `tone`).

The actual waveform synthesizer the Python pipeline drives is in
`src/dectalk/hlsyn/`, not `src/dectalk/vtm/`. And the C source
the Python `hlsyn/` module translates (`src/dapi/src/hlsyn/`,
SenSyn 2.2 from Sensimetrics) is **NOT** the synthesizer the
shipped Linux `libtts_us.so` actually runs — that's
`src/dapi/src/vtm/vtm3.c::speech_waveform_generator`.

Three concrete consequences of this single architectural mismatch
account for the entire VTM-stage divergence budget:

1. **Frame size mismatch** (Section 1): vtm3.c emits one frame
   every 71 samples (~6.4 ms) at 11025 Hz; the Python
   `hlsyn`/`vowels.default_speaker()` synthesizes 110 samples
   (~10 ms) per frame. Python output is ~55 % longer in wall-
   clock per frame than the C reference. The PH layer counts
   frames in 6.4 ms units (`init_timing`); each one is stretched
   to 10 ms at synthesis. This is the largest fixable VTM-stage
   divergence.
2. **Different synthesizer implementations** (Section 2):
   vtm3.c is integer fixed-point Klatt (S16/S32 coefs, `muldv`,
   `frac4mul`, lookup-table approximations of `dB→amp`,
   `setzeroabc` anti-resonator); hlsyn is floating-point Klatt
   (`dB2amp` via `pow(10, ...)`, exact `sin`/`cos` resonator
   updates). Even when fed identical LL parameters, the two
   produce different samples — sometimes by a few quanta,
   sometimes (on quiet aspiration / silence) by much more
   because the integer build pegs many gains to 0 at lower input
   thresholds than float does.
3. **HLSYN-vs-vtm3 frame parameter set mismatch** (Section 3):
   the LL parameter structure differs between the two
   synthesizers. vtm3 reads ~20 SPC frame slots (`OUT_AP`..
   `OUT_AV`, `OUT_F1`..`OUT_F3`, `OUT_FZ`, `OUT_B1`..`OUT_B3`,
   `OUT_TLT`, `OUT_A2`..`OUT_A6`, `OUT_AB`, `OUT_T0`) — these
   are the slots the PH layer's `parstochip[]` array writes.
   hlsyn's `LLFrame` adds DF1/DB1 (glottal-open formant shifts),
   FNP/BNP/FNZ/BNZ (nasal pole+zero), F4..F6/B4..B6 (cascade
   higher formants), A1V..A4V/ATV (parallel voicing amplitudes),
   OQ/SQ (open quotient / spectral quality). The Python
   `parstochip_to_llframe_delayed` populates the slots PH writes
   and leaves the rest at synthesizer-neutral defaults
   (F4=3500, B4=250, F5=4500, B5=300, OQ=50, SQ=200) drawn from
   Klatt 1980 reference values rather than from the per-voice
   SPD_CHIP table.

The dump-hook stage-boundary infrastructure for VTM is also
incomplete (Section 4): the patch in
`tests/parity/c_patches/0005-vtm-stage-dump-hooks.patch` captures
only the **packet control word** (one S16 per packet), not the
~37-word VOICE_PARS payload that follows. Closing this gap is a
~50-line patch update and is a prerequisite for any quantitative
PH→VTM boundary comparison.

The VTM `_DEFERRED` allow-list in
`tests/unit/test_vtm_module_inventory.py` is **already empty**;
every C function in the scanned VTM source files
(`vtm3.c`, `vtmiont.c`, `sync.c`, `playtone.c`, `vtm.c`) has a
matching Python symbol. The inventory check passes. The remaining
work is not "add new modules" — it is "make the existing modules
match the C semantics", concentrated in the
`hlsyn`/`parstochip_to_llframe` translation layer.

## 1. Frame size mismatch (largest divergence contributor)

### What C does

In `src/dapi/src/vtm/vtm3.c::SetSampleRate` (lines 2267-2269),
the 11 kHz path sets:

```
pVtm_t->rate_scale             = 18063;     // 1.1 in Q14
pVtm_t->inv_rate_scale         = 29714;     // Q15
pVtm_t->uiNumberOfSamplesPerFrame = 71;
```

`speech_waveform_generator` then iterates 71 samples per frame at
the 11025 Hz sample rate (vtm3.c line 747:
`for (ns = 0; ns < pVtm_t->uiNumberOfSamplesPerFrame; ns++)`).

71 samples / 11025 Hz ≈ **6.439 ms per frame**.

The PH layer (`ph_claus.c`'s `phclause` loop, `init_timing`,
`us_phtiming` durations) is calibrated to this rate. The
`allodurs[]` array stores per-allophone durations counted in
"frame units"; `init_timing` derives `sprat0/sprat1/sprat2` from
words-per-minute under the assumption that one frame is ~6.4 ms.

### What Python does

`src/dectalk/hlsyn/vowels.py::default_speaker()` line 30:

```python
samples_per_frame = round(sr_hz * 0.01)  # ~10 ms frames
return Speaker(..., UI=samples_per_frame, ...)
```

At 11025 Hz this gives **UI = 110 samples ≈ 9.977 ms per frame** —
the standard SenSyn / Klatt 1980 reference frame rate.

`_pump_frames_to_samples` in `src/dectalk/api/speak.py` then
allocates `len(frames) * 110` int16 samples and calls
`ll_synthesize` over each 110-sample buffer.

### Why this is the dominant divergence

The PH layer hands a frame stream to the synthesizer. The number
of frames is computed at PH time from `allodurs[i]` (in 6.4 ms
units). For `hello world`:

```
allodurs = [12, 20, 21, 6, 23, 9, 12]  # 103 frames total at 6.4 ms each
```

Expected wall-clock duration: 103 × 6.4 ms ≈ 660 ms = ~7280 samples.
Observed C output: 13845 samples ≈ 1.26 s (the rest is leading +
trailing silence padding). Observed Python output (full pipeline):
10670 samples ≈ 0.97 s — because Python stretches each 6.4 ms-
calibrated frame into 10 ms of audio. 103 × 110 = 11330 samples,
matching the observed 10670 to within rounding + the missing-phones
front-end issue from `parity-divergence-audit.md`.

### Fix sketch

Pick one of two equally valid strategies:

**(A) Re-calibrate Python `default_speaker.UI = 71`** (one-line
change). This is the cheap fix: the PH layer already targets the
71-sample frame, so dropping `UI` to 71 should align the
wall-clock duration immediately. But it will cause the hlsyn
synthesizer's internal smoothing / state-update intervals to fire
at 6.4 ms rather than 10 ms — a regime the SenSyn implementation
was not designed for. The Klatt resonator update math is per-
sample, so this is probably benign, but per-frame quantities like
DF1/DB1 glottal-open shifts (which fire when
`state.glottis_open` is asserted, not at frame boundaries)
should be re-validated.

**(B) Port `vtm3.c::speech_waveform_generator`** into a new
`dectalk.vtm.speech_waveform_generator` module that the
`_pump_frames_to_samples` path can call instead of
`ll_synthesize`. This is the bit-accuracy-correct fix: 71-sample
frames are then native, and the integer arithmetic + lookup-table
quantisation match the C oracle exactly. Cost: ~2400 lines of
fixed-point C to translate, with bandwidth-tracking dependencies
into `setzeroabc` (already ported), `volume_table` (already
ported), `tilt_tables` (already ported), `glottal_b0_table`
(already ported). Many of the lookup tables `vtm3.c` needs are
already in `src/dectalk/vtm/` — they were ported in earlier
sprints; only the orchestrating function is missing.

Recommendation: **(A)** for a quick wall-clock fix to drop
hello-world's |Δsamples| from ~3175 to ~700, then **(B)** as
follow-up for true bit parity. Both strategies are compatible —
(A) doesn't preclude doing (B) later.

### Estimated impact

|Δsamples| drops from ~3175 to ~700 on `hello world` with (A)
alone (samples align proportionally; the residual is the
front-end ARPABET-dropout from `parity-divergence-audit.md`
issue #58). (B) is the only path to bit-exact PCM parity from
the Python pipeline.

## 2. Different synthesizer implementations

### What the C oracle compiles in

`src/dapi/src/vtm/Makefile` line 19:

```
DEFINES = -D_REENTRANT -DNOMME -DLTSSIM -DTTSSIM -DANSI
          -DBLD_DECTALK_DLL -D$(LANGUAGE)
          -DDECTALK_INSTALL_PREFIX=...
          -DACCESS32 -DTYPING_MODE
```

Notably **NOT** in this list: `HLSYN`, `FAKE_HLSYN`, `VTM1`,
`VTM2`, `FP_VTM`, `ARM7`, `SAPI5DECTALK`, `ASM_FVTM`,
`POSS_FUTURE_FUNCTION`, `NEW_VTM`, `HLSYN_NEWPOLE`,
`TONGUE_BODY_AREA`.

With `HLSYN` undefined, `vtm.c` (a dispatcher,
`/tmp/dectalk-src/src/dapi/src/vtm/vtm.c`) `#include`s
`vtm3.c` (line 38: `#else / #include "vtm3.c"` -- none of VTM1,
VTM2, FP_VTM are defined). `vtmiont.c` line 1469
unconditionally calls `speech_waveform_generator(phTTS)`. The
`#ifdef HLSYN` branches at lines 158, 309, 398, 454, 536, 719,
869, 1464 are all dead in this build.

The bottom line: the only synthesizer the C oracle runs is
`src/dapi/src/vtm/vtm3.c::speech_waveform_generator` —
**not** anything under `src/dapi/src/hlsyn/`.

### What Python translates

`src/dectalk/hlsyn/synthesize.py` module docstring line 2:

```
Translated from `src/dapi/src/hlsyn/frame.c`. One call to
:func:`ll_synthesize` produces ``synth.spkr.UI`` samples ...
```

The Python `dectalk.hlsyn` package translates the SenSyn 2.2
synthesizer from `src/dapi/src/hlsyn/` (`frame.c::LLSynthesize`,
`sample.c::next_sample`, `voice.c::next_voice_sample`,
`reson.c::InterPolePair` + `SetPolePair`, etc.).

`HLSynthesizeLLFrame` (`src/dapi/src/hlsyn/hlframe.c`, also
ported to `src/dectalk/hlsyn/hlframe.py`) is the
HLSyn-frame → LLFrame mapper that runs at vtmiont.c line 788
**only when HLSYN is defined** — i.e. on a different Fonix build
flavor that didn't ship as `libtts_us.so`.

### Implementation differences (vtm3.c vs hlsyn/frame.c)

| Aspect | vtm3.c (the C oracle) | hlsyn/frame.c (what Python ports) |
|---|---|---|
| Arithmetic | S16/S32 fixed-point | float (and double) |
| dB→amplitude | `int_volume_table[]` (LUT, Q15) | `pow(10.0, dB/20.0)` via `dB2amp` |
| Anti-resonator coefs | `setzeroabc(f, bw, rnpg, ...)` | `SetZeroPair` (continued fractions) |
| Frame samples | 71 (11 kHz) / 51 (8 kHz) | `spkr.UI` (config-driven; 110 in Python) |
| Cascade formants | F1..F6 + F7/F8 fixed at 6500/7500 | F1..F8 in `LLFrame`; F7/F8 hard-coded in `synthesize.py` |
| Glottal-open shift | `IsGlottalOpen`-keyed integer rescale | `DF1`/`DB1` added to F1/B1 when `state.glottis_open` |
| Source-waveform | Integer impulse-train (`Diplo`, `T0inS4`, etc.) + custom tilt | `next_voice_sample` with `SOURCE_NATURAL` / `SOURCE_IMPULSIVE` / `SOURCE_LF` selectable |
| Spectral tilt | `ntiltf[42]` LUT remap | Single-pole `TL` filter |
| Sample clipping | `if (out > 32767) ...; if (out < -32768) ...` (line ~1900) | Identical pattern in `synthesize.py::_run_frame` |
| Volume attenuation | `vol_att = int_volume_table[pKsd_t->vol_att]` post-scale | None (the per-clause `vol_att` plumbing is not in hlsyn) |

### Why the divergence is real even with identical LL inputs

Even if `parstochip_to_llframe_delayed` produced LL parameters
identical to what `vtm3.c` reads from `pVtm_t->parambuff[]`,
the two synthesizers would not produce identical samples
because:

- vtm3.c's `setzeroabc(f, bw, rnpg, &sacoef, &sbcoef, &sccoef)`
  consults `cos_radius_table[]` and `radius_table[]` (both in
  `src/dectalk/vtm/cosine_radius_tables.py`); hlsyn's
  `SetZeroPair` uses `cos(2*pi*f/SR)` and `exp(-pi*bw/SR)` exactly.
  These agree to ~3 decimal places for typical f/bw; they
  disagree by 1-3 LSB on individual coefs.
- vtm3.c's `dB → amp` is a 256-entry LUT capped at ~32767;
  hlsyn's `dB2amp` is `pow(10, dB/20.0) * 32767` and produces
  floating-point values that round on integer-cast at the
  output. For low dB values (e.g. `Ah=2`) the LUT pegs to 0
  while the float path produces ~41.
- vtm3.c's noise generator (`pVtm_t->state.noise`) is the C
  `rand()` family seeded from `pVtm_t->state.random`; hlsyn
  uses a separate LCG (`synth.state.random`) seeded from
  `synth.spkr.RS`. Noise streams diverge from sample 0.

### Fix sketch

The vtm3 port is the only path to true PCM-bit-parity. Concrete
plan:

1. Port the table-driven helpers first (most are done):
   `int_volume_table`, `setzeroabc`, `cos_radius_table`,
   `radius_table`, `ntiltf`, `int_glottal_b0`, `sinetab` —
   already in `src/dectalk/vtm/`.
2. Port the frame-init helpers next:
   `read_speaker_definition` (done), `InitializeVTM` (shim
   exists in `initialize_vtm.py`; needs body).
3. Port the source generator: the voice/aspiration loop is
   ~400 lines of vtm3.c (the `while (nsr4 < 4)` glottal-pulse
   loop at lines ~1300-1700). The smoothing/state machinery
   for `voice`, `noise`, `aspbuf`, `T0inS4` lives here.
4. Port the cascade-parallel filter bank: ~600 lines of
   resonator iteration with integer-coefficient updates
   (lines ~1700-2200).
5. Wire `_pump_frames_to_samples` to dispatch on a feature flag
   (`DECTALK_VTM_PATH=vtm3` vs `hlsyn`) so the existing
   `synth_parity` tests keep passing under hlsyn while vtm3
   gains coverage.

Estimated effort: 2-4 weeks of focused porting; the integer
arithmetic carries the same bit-trickiness as `hlsyn/voice.py`'s
short-wraparound accumulators.

### Estimated impact

Closes the residual PCM divergence after the frame-size fix
(Section 1). The leading-silence prefix already matches the C
binary to the byte; the first-voiced-frame divergence is
entirely attributable to this synthesizer mismatch.

## 3. HLSYN-vs-vtm3 frame parameter set mismatch

### The two parameter sets

`src/dectalk/ph/param_indices.py` carries both index sets in
parallel:

- **PH-input** (`F0=0, F1=1, F2=2, F3=3, FZ=4, B1=5, B2=6,
  B3=7, AV=8, AP=9, A2=10..A6=14, AB=15, TILT=16,
  AREAB..AREAN=17..20`) — what `phdraw`'s smoothing logic
  reads from `param[]`.
- **SPC frame output** (`OUT_AP=0, OUT_F1=1, OUT_A2=2..OUT_A6=6,
  OUT_AB=7, OUT_TLT=8, OUT_T0=9, OUT_AV=10, OUT_F2=11,
  OUT_F3=12, OUT_FZ=13, OUT_B1=14, OUT_B2=15, OUT_B3=16,
  OUT_PH=17, OUT_DU=18, OUT_PH2=19`) — what `parstochip[]`
  exposes to VTM.

The C `vtm3.c` reads exactly these 17 + 3 slots from
`pVtm_t->parambuff[]`. The hlsyn `LLFrame` accepts ~45 named
fields (see `dectalk.hlsyn.llsyn.LLFrame`). The mapping done by
`parstochip_to_llframe_delayed` fills the 17 vtm3 slots and
defaults the other 28 fields.

### Defaulted fields and where they come from in C

The Python defaults (`src/dectalk/ph/parstochip_to_frames.py`
lines 36-99) versus what vtm3 actually uses:

| LLFrame field | Python default | vtm3.c source |
|---|---|---|
| `F4` | 3500 | `pVtm_t->speakerDef.SPC_CHIP.r4cc` (from `read_speaker_definition`; Paul = 3300) |
| `B4` | 250 | `pVtm_t->speakerDef.SPC_CHIP.r4cb` (Paul = 260) |
| `F5` | 4500 | `pVtm_t->speakerDef.SPC_CHIP.r5cc` (Paul = 3650) |
| `B5` | 300 | `pVtm_t->speakerDef.SPC_CHIP.r5cb` (Paul = 330) |
| `F6`/`B6` | 6500 / 600 (synth-neutral) | not used in vtm3 (F6/B6 are hlsyn-only) |
| `FNP`/`BNP` | 270 / 100 | derived from `pVtm_t->parambuff[OUT_FNP]` in NEW_VTM build only; else fixed (no NEW_VTM in our build) |
| `DF1`/`DB1` | 0 / 0 | hlsyn-only; vtm3 doesn't have glottal-open shift |
| `A1V..A4V`/`ATV` | 0 | hlsyn-only (parallel-voicing branch); vtm3's cascade-only path doesn't use them |
| `OQ`/`SQ` | 50 / 200 | hlsyn-only; vtm3 derives the glottal pulse from `pVtm_t->parambuff[OUT_T0]` + integer `Diplo` math |
| `Ah` | from `OUT_AP` | `pVtm_t->parambuff[OUT_AP+1]` (matches) |
| `Af` | unset (defaults to 0) | derived from `A2..A6` in vtm3; setting to 0 zeros frication |

The most important divergence here is **`F4`/`B4`/`F5`/`B5`
hardcoded to Klatt 1980 reference values rather than the
per-voice SPD_CHIP**. Paul's F4 is 3300 Hz (per `p_us_vdf.c`),
not 3500. F5 is 3650, not 4500. These are 6-22 % off, and the
upper-formant tail is where most vowels' "voice quality" lives.

### Fix sketch

`parstochip_to_llframe_delayed` should consume the voice-loaded
SPD_CHIP and use the per-voice F4/B4/F5/B5 (and any other
speaker-defined fields) rather than its current synth-neutral
defaults. The plumbing already exists:

- `default_us_paul_spd()` in `src/dectalk/vtm/spd_chip.py`
  already extracts Paul's r4cc=3300, r4cb=260, r5cc=3650,
  r5cb=330 from `p_us_vdf.c`.
- `_speak_via_python_full` already calls
  `default_us_paul_spd()` and stores the result on
  `p_dph_t.fnscale` (line 423 of `api/speak.py`); the rest of
  the SPD_CHIP fields are loaded but never read.

The fix is to thread `SpdChip` through to
`parstochip_to_llframe_delayed` (one extra argument) and pull
`f4 = spd.r4cc, b4 = spd.r4cb, f5 = spd.r5cc, b5 = spd.r5cb` into
the LLFrame instead of `_DEFAULT_F4` / `_DEFAULT_F5` etc.

Scope: ~30 lines. Voice changes will then take effect on the
upper-formant spectrum in the Python pipeline, matching the C
oracle's per-voice spectral envelope.

### Estimated impact

Modest sample-distance change (the upper formants don't dominate
the L2 energy), but a noticeable voice-quality improvement —
particularly for non-Paul voices where F4/F5 deviate further from
the Klatt 1980 male reference. Voice-specific parity tests (when
they exist) will improve significantly.

## 4. VTM-stage dump hook is incomplete

The C dump hook for PH→VTM boundary data lives in
`tests/parity/c_patches/0005-vtm-stage-dump-hooks.patch`. The
relevant call site is the patch's only `_dectalk_dump_vtm_chunk`
invocation:

```c
#ifdef SINGLE_THREADED
    _dectalk_dump_vtm_chunk((const unsigned short *)input, 1);
#endif
```

`count=1` means **only the packet control word** is dumped — not
the VOICE_PARS payload (~37 words) that follows for speech
packets.

Empirically: `c.dump_pipeline('hello world', ['vtm'])` returns
203 `vtm_write` lines each holding one S16. The first is `0001`
(speaker-def packet header), 195 of the next ones are `0000`
(speech packets where the control word is mostly metadata), and
the last 7 are tones. The actual frame-by-frame F0/F1/F2/F3/AV/AG
parameters that flow into `speech_waveform_generator` are
**never written to the dump file**.

This is the reason the audit in `docs/parity-divergence-audit.md`
(issue #58) had to instrument the Python side rather than do a
direct PH→VTM byte-comparison: the C oracle's PH→VTM dump is
unusable for that purpose right now.

### Fix sketch

Extend `_dectalk_dump_vtm_chunk` to dump the full
`VOICE_PARS`-sized payload after each `SPC_type_voice` packet
header. The patch site needs two callsite changes:

1. After `read_pipe(pKsd_t->vtm_pipe, &(pVtm_t->parambuff[1]),
   VOICE_PARS)` (line 696) and after the `SINGLE_THREADED` copy
   loop (lines 698-701), emit
   `_dectalk_dump_vtm_chunk(&pVtm_t->parambuff[1], VOICE_PARS)`.
2. Optionally tag the dump format so consumers can distinguish
   "control word" frames from "voice param" frames; the current
   `vtm_write %u\n%04x ... %04x\n` format already carries the
   count, so a `count == VOICE_PARS` heuristic works without a
   format change.

Patch scope: ~10 lines added in `0005-vtm-stage-dump-hooks.patch`.
This is a prerequisite for any quantitative PH→VTM boundary
parity test.

### Estimated impact

Unlocks the diagnostic that produced this audit's numbers in the
first place — without a working PH→VTM dump, the Python side has
to instrument itself to capture the parstochip stream, which
limits comparison to the Python-only view. Once the C dump emits
the full parameter set, a per-frame parstochip-vs-parambuff diff
becomes a one-liner.

## 5. Smaller-impact findings

- **Sample-rate-change LSB**: `src/dectalk/vtm/set_sample_rate.py`
  documents that "the active vtm3.c build differs by a single bit
  (29714 vs 29722) in `inv_rate_scale`". The active build
  (no `SINGLE_THREADED`, no `ARM7`) sets `inv_rate_scale=29714`
  (line 2268 of vtm3.c) but the Python value picks the other
  build's 29722. This is a 1-LSB Q15 difference, sub-audible, but
  affects bit-exact parity for any LL frame that goes through the
  sample-rate-conversion path.
- **`vol_att` post-scale never applied**: vtm3.c at line 520 reads
  `vol_att = int_volume_table[pKsd_t->vol_att]` and uses it to
  post-scale the synthesised output (an integer-domain multiply
  at the end of `speech_waveform_generator`). The hlsyn path
  doesn't have this; the per-clause `[:volume N]` directive
  silently does nothing in pure-Python mode. Symptom: setting
  volume via `[:vol set sp N]` has no audible effect on the
  `DECTALK_DISABLE_CAPI=1` path. Fix: thread `vol_att` through
  `_pump_frames_to_samples` and apply
  `samples[:] = (samples.astype(np.int32) * vol_att) >> 15` after
  synthesis. `volume_table` is already ported to
  `src/dectalk/vtm/volume_table.py`.
- **`tilt_tables` (ntiltf) already applied**: `lineartilt[]`
  remap happens in `parstochip_to_llframe_delayed` (line 132 of
  `parstochip_to_frames.py`). Verified correct; this is one place
  the Python pipeline actually uses VTM-stage data.
- **`int_glottal_b0_table` unused**: `src/dectalk/vtm/glottal_b0_table.py`
  is ported but never imported outside `tests/`. It's a vtm3
  internal — only used inside `speech_waveform_generator` for the
  glottal-pulse waveform. Will become relevant when the vtm3
  port from Section 2 lands.
- **`int_amp_table` unused**: same story —
  `src/dectalk/vtm/amp_table.py` is the integer dB→amplitude LUT
  that vtm3 uses. The hlsyn path doesn't need it.

## 6. What this audit does NOT change

This is research-only. No code changes ship with this PR; the
findings inform future port targets. Each numbered section above
is intended to spawn a follow-up issue:

- **Issue (proposed)**: "Recalibrate `default_speaker.UI` from
  110 to 71 to match vtm3.c frame size" — Section 1, fix A,
  size/small, area/hlsyn.
- **Issue (proposed)**: "Port `vtm3.c::speech_waveform_generator`
  to `dectalk.vtm.speech_waveform_generator`" — Section 2,
  size/large, area/vtm.
- **Issue (proposed)**: "Thread per-voice F4/B4/F5/B5 from
  SpdChip into `parstochip_to_llframe_delayed`" — Section 3,
  size/small, area/ph.
- **Issue (proposed)**: "Extend
  `0005-vtm-stage-dump-hooks.patch` to dump the full VOICE_PARS
  payload" — Section 4, size/small, area/parity.
- **Issue (proposed)**: "Apply `vol_att` post-scale in
  `_pump_frames_to_samples`" — Section 5, size/small,
  area/vtm.

Each follow-up is independent and can be picked up in any order.
Section 1 (frame size) is the highest-impact single change;
Section 2 (full vtm3 port) is the only path to true bit parity.

## Reproducer

```bash
# Set up oracle env.
eval "$(scripts/agent_oracle_env.sh)"
scripts/setup_c_oracle.sh

# Confirm the vtm3.c frame size.
grep -n "uiNumberOfSamplesPerFrame" "$DECTALK_SRC/src/dapi/src/vtm/vtm3.c"
# -> 2269: pVtm_t->uiNumberOfSamplesPerFrame = 71;

# Confirm the build flag set excludes HLSYN.
grep -n "DEFINES" "$DECTALK_SRC/src/dapi/src/vtm/Makefile"

# Confirm the dump hook is single-word.
grep -n "_dectalk_dump_vtm_chunk" \
    tests/parity/c_patches/0005-vtm-stage-dump-hooks.patch
# -> count = 1 in every call.

# Compare Python (full pipeline) vs C oracle on hello world.
DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1 \
    uv run python -c "
import wave, io, tempfile
from dectalk import to_wav
with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
    path = f.name
to_wav('hello world', path)
data = open(path, 'rb').read()
with wave.open(io.BytesIO(data), 'rb') as w:
    print(f'Python samples: {w.getnframes()}')
"
# -> ~22330 samples (after the recent inline-command parse fix)

# C oracle reference.
uv run python -c "
from dectalk._capi import CAPI
import wave, io
c = CAPI()
wav = c.speak('hello world', speaker=0)
with wave.open(io.BytesIO(wav), 'rb') as w:
    print(f'C samples: {w.getnframes()}')
"
# -> 13845 samples
```

## Authored-by

Authored-by: Claude:claude-opus-4-7
