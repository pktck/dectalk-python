# Prosody — C vs. Python audit

Reference C tree: `/tmp/dectalk-src/src/dapi/srcold/PH/`. Most-cited
files: `Ph_inton2.c` (intonation/F0), `p_us_tim.c` (durations),
`p_us_vdf_tuneint.c` + `_tunehl.c` (tuning offsets per voice).

Reference Python: `src/dectalk/ph/prosody.py`.

This audit captures the structural and numeric deltas between the
two implementations. Each section has three subsections — **C
source**, **Python current**, **Delta** — with the deltas ranked by
audibility.

## Declination contour

**C source** (`Ph_inton2.c`):

The C implementation does **not** use a simple linear declination
model. Instead it issues IMPULSE / STEP / GLIDE commands throughout
the utterance.

- No single `F0_BASE` constant. F0 is managed through a
  command-based system that dispatches IMPULSE, STEP and GLIDE
  commands across the utterance (lines 1068–1330).
- **Stress-level impulses dominate** (lines 1084–1104): stress level
  (primary / secondary / emphatic / unstressed) determines the F0
  rise via tables `f0_mstress_level[]` and `f0_fstress_level[]`. For
  US English males (lines 324–334):
  `us_f0_mstress_level[] = {1, 81, 61, 161}` (Hz × 10 units for
  unstressed / primary / secondary / emphatic).
- **Phrase-position decay** (lines 314, 329–330):
  `us_f0_mphrase_position[] = {160, 80, 60, 40, 30, 20, 20, 5}` —
  successive stressed syllables decay by *position*, not linearly
  by time.
- **Final syllable fall** (lines 1351–1497): a dedicated GLIDE (Rule
  3) drops F0 below baseline. US: `F0_FINAL_FALL = 550` (line 690),
  scaled by `Reduce_last = 10` for phrase-final stress (line 695).
  Discrete gesture, not gradual declination.
- **Non-final comma fall** (line 692): `F0_COMMA_FALL = 120`,
  applied separately.
- **Contour shape**: piecewise impulse-based, **not** linear or
  spline. Each stressed syllable gets a separate command;
  unstressed syllables inherit baseline.

**Python current** (`src/dectalk/ph/prosody.py`):

- Lines 32–43: declarative statement uses
  `_DECLINATION_START = 1.20` (start at +20 % F0) and
  `_DECLINATION_END_STATEMENT = 0.78` (end at −22 % F0).
- Linear interpolation (lines 92–94):
  `alpha = i / max(1, n - 1)`, then
  `decl = 1.20 * (1 - alpha) + 0.78 * alpha`.
- Final dip (lines 100–104): multiplicative
  `_FINAL_DIP_FRACTION = 0.90` applied only to the last non-SIL
  phoneme.
- Question contour (line 40):
  `_DECLINATION_END_QUESTION = 1.30` (end at +30 % for rising).
- Contour shape: **linear multiplicative decay**, not piecewise
  impulses.

**Delta (ranked by audibility)**:

1. **Structural mismatch (highest impact)**. C uses IMPULSE-driven
   pitch accents on each stressed syllable, scheduled separately;
   Python applies a monotonic multiplier across all phonemes.
   Result: C's output has more granular pitch control and avoids
   the "smooth robotic" feel.
2. **Declination range**. C's stress impulses (`{1, 81, 61, 161}`
   Hz × 10 = 0.1…16.1 Hz absolute) interact multiplicatively with
   phrase-position (`{160, 80, 60, …}` Hz × 10). Python's linear
   model (+20 % to −22 % = 1.42:1 ratio) is shallower than C's
   final fall (550 Hz × 10 ≈ 55 Hz, a much steeper absolute drop).
3. **Baseline assumption**. C tables imply 100 Hz baseline (Hz × 10
   units); Python's multipliers are unit-free. On a 120 Hz voice,
   Python's declination is ±24 Hz, vs. C's −55 Hz at sentence end —
   roughly 3× the perceived "droop" in C.
4. **Question rise**. C's `F0_QGesture1 = 351, F0_QGesture2 = 451`
   (Hz × 10) are absolute deltas on unstressed-final syllables
   (lines 684–685); Python's `_DECLINATION_END_QUESTION = 1.30` is
   a multiplier. C creates a "pop" rise via gestures; Python's rise
   is proportional to existing F0 (weaker for low-F0 voices).

## Per-stress F0 multipliers

**C source** (`p_us_vdf_tuneint.c`, `p_us_vdf_tunehl.c`,
`Ph_inton2.c`):

The tuning files contain speaker-specific offsets, not base
multipliers. The base stress levels are in `Ph_inton2.c`:

- Lines 324–325 (US male): `us_f0_mstress_level[] = {1, 81, 61, 161}`
  (Hz × 10 for unstressed / primary / secondary / emphatic).
- Line 334 (US female): `us_f0_fstress_level[] = {1, 100, 80, 161}`
  (Hz × 10).
- Added to phrase-position deltas (lines 1084–1112) and scaled by
  speaker `scale_str_rise` (line 1188).
- No "multiplier" concept; F0 is driven by absolute Hz × 10 targets
  modulated by IMPULSE commands.

**Python current** (`prosody.py`, lines 50–54):

```python
_STRESS_F0 = {"1": 1.18, "2": 1.06, "0": 0.92}
```

Symmetric around 1.0: primary +18 %, secondary +6 %, unstressed
−8 %.

**Delta (ranked by audibility)**:

1. **Unit mismatch**. C uses absolute Hz deltas (80–160 Hz × 10 ≈
   8–16 Hz added to base); Python uses proportional multipliers
   (±18 %, ±6 %, −8 %). For 120 Hz, Python's ±21.6 Hz (primary) is
   in C's ballpark, but C's tables **add**, they don't multiply.
   C's primary-vs-secondary contrast is constant (20 Hz) regardless
   of base F0; Python's is proportional (2.4 × vs 1.06 × base).
2. **Secondary stress**. C splits secondary from primary
   (`61` vs. `81` Hz × 10); Python lumps them (`2` gets `1.06×`).
   Audible: secondary stress sounds weaker in Python relative to C.
3. **Emphatic stress**. C has `161` Hz × 10 (~16 Hz); Python leaves
   `FEMPHASIS` at 1.0. Emphasized syllables get only duration
   stretch, no F0 bump.
4. **Phrase-position decay**. C's per-accent falloff
   (`160, 80, 60, 40, 30, 20, 20, 5` Hz × 10) means the 2nd and 3rd
   stresses are already 50 % and 37 % of the 1st. Python applies the
   same `_STRESS_F0` to all accents regardless of position.
   Python sounds "too peppy" mid-utterance; C sounds more
   "gravitational."

## Per-stress duration multipliers

**C source** (`p_us_tim.c`, lines 107–1317):

- **No simple per-stress multipliers.** Complex rule-based
  adjustments on `prcnt` (where 128 = 100 %) within a large
  switch / if tree.
- Rule 4 (lines 419–443): monosyllabic vowels shortened to 85 %
  (primary), 75 % (secondary), 70 % (unstressed); base multiplied by
  `N70PRCNT`, `N75PRCNT`, `N85PRCNT`.
- Rule 5 (lines 467–476): polysyllabic vowels shortened by 0.8.
- Rule 6 (lines 479–497): non-word-initial consonants shortened to
  0.85.
- Rule 7 (lines 499–562): unstressed segments more compressible;
  `durmin` halved for sonorants (line 507), reduced by 25 % for
  obstruents (line 512).
- **No flat multiplier per stress digit.** Duration depends on
  syllable type, phoneme class, and position.

**Python current** (`prosody.py`, lines 56–60):

```python
_STRESS_DURATION = {"1": 1.20, "2": 1.05, "0": 0.85}
```

Multiplicative, applied uniformly to all phonemes with the matching
stress digit.

**Delta (ranked by audibility)**:

1. **Granularity (highest)**. C adjusts per phoneme class (sonorant
   gets a different rule than obstruent); Python applies a flat
   multiplier. Python over-lengthens final unstressed consonants in
   words like "BAT-uh" (both AH and schwa get 0.85×); C uses
   feature bits to shorten only vowels and some consonants.
2. **Vowel shortening in polysyllables**. C applies 20 % reduction
   (line 474) to stressed vowels in polysyllabic words; Python's
   primary-stressed vowel gets +20 % — opposite sign. Audible as
   over-lengthening of word-medial stressed vowels.
3. **Monosyllable handling**. C aggressively reduces monosyllabic
   vowels (70–85 %, lines 426–442); Python treats them like any
   stressed vowel (+20 %).
4. **Phrase-final lengthening**. C Rule 2 (lines 352–387) adds 40 ms
   to clause-final vowels; Python has no phrase-aware rule.
   Statement-final syllables sound shorter in Python.

## Question / statement terminal contour

**C source** (`Ph_inton2.c`):

- **Question detection** (lines 1505–1518): boundary flag
  `(struccur & FBOUNDARY) == FQUENEXT`.
- **Question gesture for stressed final syllable** (lines
  1525–1559): `make_f0_command(IMPULSE, 41, F0_QGesture1, delayf0,
  24, &cumdur, nphon)` plus a second impulse with `F0_QGesture2`
  (lines 1543–1549). US: `F0_QGesture1 = 351, F0_QGesture2 = 451`
  (Hz × 10, lines 684–685). Two separate pulses near the final
  stressed vowel.
- **Question gesture for unstressed final syllable** (lines
  1823–1840): different values and timing — `F0_QGesture1, delayf0,
  24` then `F0_QGesture2, pDph_t->allodurs[nphon], 20`.
- **Statement gesture** (lines 1351–1497): final fall (Rule 3) uses
  `F0_FINAL_FALL = 550` Hz × 10 (line 690) as a GLIDE, scheduled at
  `delayf0` for `length` frames.
- **Mechanism**: last-stressed-syllable (or last-final in UK,
  line 941) is the trigger. Contour shape changes via gesture
  scheduling and timing, not via a global multiplier change.

**Python current** (`prosody.py`, lines 63–106):

- Question detection: parameter `question: bool = False` to
  `f0_contour()`.
- Question contour: if `question`, set
  `end_factor = _DECLINATION_END_QUESTION (1.30)` instead of
  `_DECLINATION_END_STATEMENT (0.78)`. Applied uniformly via linear
  interpolation; final dip is skipped for questions.
- **Mechanism**: sentence-final multiplier flip. Entire utterance
  contour changes, not just the final syllable.

**Delta (ranked by audibility)**:

1. **Scope (highest)**. C modulates only the last stressed syllable
   (or last syllable in UK); Python changes the contour across the
   entire utterance. Python's question rise starts at the
   beginning of the sentence and is gentle; C's is a sharp rise
   confined to the final syllable(s). "English-like" (C) vs.
   "monotone rising" (Python).
2. **Gesture strength**. C's question impulses (`351, 451` Hz × 10
   ≈ 35–45 Hz rise) are absolute additions; Python's `1.30×` is
   proportional (120 Hz → 156 Hz = 36 Hz, similar by accident, but
   C's timing is critical — the gesture is a brief impulse near
   vowel end).
3. **Stressed vs. unstressed final syllables**. C has separate code
   paths (lines 1525–1559 for stressed, 1823–1840 for unstressed);
   Python treats all final syllables identically.
4. **Final dip on statements**. C's 550 Hz × 10 fall can dip below
   baseline (line 1369 comment). Python's `_FINAL_DIP_FRACTION =
   0.90` is multiplicative reduction, cannot go below the
   declination baseline. C sounds more "finished"; Python sounds
   "flat."

## Foot / syllable structure

**C source** (`Ph_inton2.c`):

- **Syllable-based iteration**. Main loop (lines 744–2017) walks
  `allophons[]` (phonemes) and `allofeats[]` (feature flags).
- **Syllable detection** via feature bits (lines 939, 1740): tests
  `(feacur & FSYLL) IS_PLUS` for syllabic nuclei (vowels and
  sonorant consonants).
- **Syllable boundaries via boundary flags** (lines 849–878): looks
  ahead from the current phoneme, skipping word-initial consonants
  (line 845: `while ((pDph_t->allofeats[nphonx] & FWINITC) IS_PLUS)`),
  then checks `FBOUNDARY` for syllable (`nextsylbou`), word
  (`nextwrdbou`), and phrase (`nextphrbou`) boundaries.
- **Foot concept**: no explicit foot data structure. Multi-syllable
  feet are inferred by walking ahead until boundary flags change.
- **Stress marking**: each phoneme in `allofeats[]` carries stress
  bits (`FSTRESS_1`, `FSTRESS_2`, `FNOSTRESS`, `FEMPHASIS`).

**Python current** (`prosody.py`, lines 63–132):

- Phoneme-based, stress-digit based: processes a flat ARPABET
  phoneme stream without syllable or foot structure. Each phoneme
  is a string like `"AH1"`, `"N"`, `"AE2"`.
- Stress extraction: trailing digit (`code[-1]`) if present;
  empty string maps to 1.0× (unstressed).
- No syllable structure: cannot detect boundaries; multipliers are
  applied per-phoneme.
- Position in utterance: only via global `alpha = i / max(1, n - 1)`
  for declination. No syllable count or foot count.

**Delta (ranked by audibility)**:

1. **Structural mismatch (highest)**. C distinguishes phrase-final,
   word-medial, monosyllabic etc. via boundary lookups. Python has
   no boundary information, so cannot apply differential rules
   (e.g., monosyllable shortening) to syllables in the same word.
2. **Stress digit scope**. C applies stress rules to the entire
   syllable (onset + nucleus + coda); Python applies per-phoneme,
   so onset consonants of a stressed syllable don't inherit stress
   benefits. Stressed syllables sound less "prominent."
3. **Multi-accent tracking**. C tracks `nrises_sofar`
   (lines 1110–1336) to count accents and decay phrase-position F0
   by accent position. Python has no counter; every `"1"` gets the
   same `1.18×` regardless of position. Python sounds "too peppy"
   mid-utterance.

## Pause / comma behaviour

**C source** (`p_us_tim.c` lines 276–350 for silence;
`Ph_inton2.c` lines 1382–1395 for comma gesture):

- **Pause duration**. Silence phoneme (`GEN_SIL`) triggers special
  rules:
  - Clause-initial: `dpause = 14` frames (~7 ms, line 280).
  - Comma: `dpause = pDph_t->nfcomma + pDph_t->compause +
    pDph_t->asperation` (lines 289–305; user-settable via `:dv cp
    __`). Default `nfcomma` is speaker-dependent, ~80–150 frames.
  - Period: `dpause = pDph_t->nfperiod + pDph_t->perpause +
    pDph_t->asperation` (lines 308–321; longer, ~150–300 frames).
  - Speaking-rate scaling (lines 334–336): `dpause =
    mlsh1(dpause, pDphsettar->sprat1)`.
- **Contour reset** (`Ph_inton2.c` lines 1930–1937): after a comma
  boundary, optional `F0_RESET` (line 1935). No automatic reset
  after periods in the visible excerpt.
- **Comma gesture on final stressed syllable** (lines 1560–1588):
  before silence following a comma, IMPULSE gestures are scheduled
  with `F0_CGesture1 = 171, F0_CGesture2 = 250` Hz × 10
  (lines 686–687) — a "continuing" rise, not a fall.

**Python current** (`prosody.py`, lines 135–171):

- **No pause handling**. `f0_contour()` does not process pauses;
  pauses are assumed to be handled at a higher level.
- `split_sentences()` identifies sentence boundaries by `.?!`
  but does not adjust F0 or pause durations. Returns
  `(sentence_text, is_question)` tuples for downstream processing.
- No explicit reset: F0 is recomputed per-sentence via fresh calls,
  so each sentence starts at `_DECLINATION_START = 1.20`.

**Delta (ranked by audibility)**:

1. **Pause duration control (highest)**. C scales pauses by speaker
   parameters and speaking rate; Python has no pause model. Python
   will not pause between clauses unless silence phonemes are
   inserted upstream.
2. **Comma gesture**. C applies a specific `F0_CGesture1/2` rise
   before commas (a continuation rise to signal more speech
   coming). Python has no mechanism for this; comma-final F0
   follows linear declination, missing the continuing intonational
   signal.
3. **Baseline reset scope**. C issues `F0_RESET` at phrase
   boundaries (line 1935), so multi-clause utterances can reset
   partway. Python recomputes per-sentence; multi-sentence
   utterances each start at +20 %.
4. **Aspiration modulation**. C deducts aspiration time from pause
   duration (lines 284–301). Python has no aspiration model;
   pauses are fixed-duration.

## Summary table

| Aspect | C (`Ph_inton2.c`, `p_us_tim.c`) | Python (`prosody.py`) | Impact |
|---|---|---|---|
| Declination | Impulse-driven, piecewise; 550 Hz×10 final fall | Linear multiplicative; 1.20→0.78 ratio | C "snappier"; Python "smooth monotone" |
| Per-stress F0 | Absolute Hz deltas (1, 81, 61, 161 Hz×10); position-dependent decay | Multiplicative (±18 %, ±6 %, −8 %); uniform | C more granular; Python lacks emphatic-stress bump and phrase-position decay |
| Per-stress duration | Rule-based per phoneme class and position | Flat multiplier per stress digit | C respects phoneme class; Python over-lengthens unstressed consonants |
| Question intonation | Final-syllable-only gesture; stressed vs unstressed code paths | Global sentence-wide rise; disables final dip | C's question rise is local and sharp; Python's is broad and gentle |
| Foot/syllable structure | Feature-bit boundaries; per-syllable rules | Phoneme stream with stress digits; no boundaries | C applies syllable/word rules; Python cannot discriminate |
| Pause/comma | Speaker-def durations, rate scaling, comma gesture, F0 reset | No pause model; per-sentence F0 recompute | C signals clause structure via pauses and rises; Python silent on both |

All deltas are immediately audible (perceptible in side-by-side
A/B). The Python port is simplified and more linear throughout; it
lacks the position- and class-aware rules of the C original.

## Phase-4 priorities (highest audible impact)

These are the changes most likely to close the audible gap, in
priority order:

1. **Stronger, localised final fall**. Replace `_FINAL_DIP_FRACTION
   = 0.90` with a stronger drop on the last 1–2 syllables that can
   go below the declination baseline (target: ~0.65–0.70 of base
   F0 at the last vowel for declarative endings).
2. **Phrase-position F0 decay across stress accents**. Add per-
   accent decay so the 3rd, 4th, 5th stressed syllable gets a
   smaller F0 rise than the 1st. Track accent count from the
   utterance start; halve the stress-F0 contribution after the 3rd
   accent.
3. **Localised question rise**. Constrain the question contour to
   the last 1–2 syllables instead of the whole utterance. Keep the
   sentence-wide declination, then add a sharp rise on the final
   stressed (or last) syllable.
4. **Comma gesture (small rise)**. When a sentence ends with a
   comma rather than `.?!`, apply a small final-syllable rise
   (continuation gesture) instead of the declination's natural
   fall.
5. **Phrase-final lengthening**. Add ~40 ms of extra duration to
   the last vowel of declarative sentences (Rule 2 from
   `p_us_tim.c`).
