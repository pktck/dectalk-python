# Pure-Python synth-path phone divergences — prioritized catalog (2026-05-29)

Diagnostic hand-off for the pure-Python parity effort
(`DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1` → `dectalk.to_wav`).
Companion to `docs/parity-f2-stop-vowel-rootcause-2026-05-29.md`.

## Method

For a deterministic 200-prompt corpus sample, render each prompt through
the C oracle (`say -a "[:debug 2200]…"`, per-frame allophone dump) and the
pure-Python full pipeline (`parstochip[OUT_PH]` per frame), collapse to
phone-code run sequences, and — on **length-aligned** prompts — tally the
single-phone substitutions `C_phone → Py_phone`. Reproducers:
`/tmp/{subscan,trace_subs,find_ihix}.py` (worker scratch).

## Headline

- **~89 % of prompts have a different phone sequence** C-vs-Python. This —
  not any per-frame formant error — is the dominant byte-parity blocker.
- Where sequences **match**, the PH target / `make_dip` / locus chain is at
  parity: per-frame |ΔF2| ≈ 5–22 Hz, steady-vowel median ΔF2 ≈ 0 (see the
  F2 root-cause companion doc). **The PH target lane is not the problem.**
- The sequence mismatches are overwhelmingly **vowel-identity / reduction**
  and **allophonic-voicing** differences originating in the
  ARPABET→allophone (`us_phalloph2`) and dictionary/reduction layers.

## Top substitution patterns (C → Py), by frequency

| # | C→Py | ~count | Trigger (examples) | Root cause | Lane / file |
|---|---|---:|---|---|---|
| 1 | **IH→IX** | 60 | function words *it, is, if, in, him* (unstressed) | `_ARPABET_UNSTRESSED_ALIAS_OFFSET` maps **all** `IH0→IX`; C keeps IH for monosyllabic function words and only reduces in polysyllabic `-es/-ed` endings (*roses*) | `src/dectalk/ph/us_phalloph2.py` |
| 2 | **EH→AE** | 13 | reduced auxiliaries *can, than, had* | C reduces the stressed-form AE → EH when the function word is unstressed; Python keeps AE | dict / reduction (cmd/dic or phalloph) |
| 3 | **Z→S** | 11 | plural/3sg `-s` after a voiced stem (*plays, doctors, runs*) | **morphological**, not allophonic — see the validated deep-dive below. `phalloph2` already renders ARPABET `Z`→Z correctly; the synth path `_render_clause_full` emits ARPABET `S` because it skips the `-s` voicing that `text_to_dectalk_phonemes` applies | `src/dectalk/api/speak.py` (synth-path resolution) |
| 4 | **AX→EY** | 10 | the article/letter *a* (unstressed) | Python emits EY (or AE) for bare `a`; C reduces the unstressed article to AX | dict / function-word reduction |
| 5 | **AH↔AX** | 12 | schwa class (*but, under, others* → AH; *us* → AX) | Python swaps the two schwa variants (full AH vs reduced AX) by context | reduction logic (phalloph/dic) |

Smaller tail (≤3 each): `UH→UW`, `EL→LL`, `EN→N`, `NX→N`, `AA→AO`,
`D→JH`, `T→DF`, `AY→IH` — mostly reduction/flapping and nasal-syllabic
realisation, same phalloph/dic neighbourhood.

## Why this is *not* the PH target lane (gettar/make_dip/locus)

`text_to_dectalk_phonemes(word)` already byte-matches C's
`convert_to_phonemes(word)` for the common words above (walk, talk, half,
data, comma, doctors, plays…) — the **phoneme string is correct**. The
divergence appears one stage later, when ARPABET phonemes are turned into
DECtalk **allophones** (`phsort`/`us_phalloph`): unstressed-vowel reduction
(`IH0→IX`, AE→EH, AH/AX) and consonant voicing-assimilation (`S→Z`). The PH
target/locus chain downstream consumes whatever allophone it is handed and
renders it correctly (verified per-frame).

## Recommended dispatch order (impact × tractability)

1. **IH→IX gating** (#1, 60×, ~40 % of prompts). In
   `us_phalloph2._ARPABET_UNSTRESSED_ALIAS_OFFSET` / its caller, stop
   reducing `IH0→IX` for monosyllabic function words; keep the reduction
   for polysyllabic final `-es/-ed/-et` syllables. **Architecturally
   significant** (needs word-context, risks the `roses`/`wanted` words that
   *correctly* use IX) — wants its own issue + careful corpus validation.
2. **Z→S plural-`s` voicing** (#3, 11×). **In `speak.py`, not phalloph2**
   — see the validated deep-dive below. Wire the synth path through the
   same morphological `-s` voicing that `text_to_dectalk_phonemes` already
   applies.
3. **Function-word vowel reduction** (#2/#4/#5). *can/than/had*→EH,
   article *a*→AX, AH/AX schwa selection. Likely a reduced-pronunciation
   table in the dictionary/cmd layer.

These are outside the PH-target / LTS-rules lanes; they live in the
`ph/us_phalloph2.py` allophone chain, the `api/speak.py` synth-path
front-end, and the dictionary/reduction tables.

## Validated deep-dive — Z→S is morphological, in `speak.py` (hand-off)

Investigated under orchestrator authorization; the fix turned out to be in
`api/speak.py`, **not** `us_phalloph2.py`, so it is handed off here for
the synth-path / api owner rather than implemented by the F2 worker.

**What is *not* wrong:**
- `phalloph2` already renders ARPABET `Z`→Z allophone correctly. Verified:
  `loves` (lts `… V EH0 Z`) → synth allophones `LL AA V EH **Z** SIL`;
  `buzzes` likewise. No phalloph change is needed.
- `text_to_dectalk_phonemes("dogs")` → `d aog **z**` (correct); it voices
  the inflectional `-s` via the nested helper `_voice_final_s_after_consonant`
  (speak.py ~L1828) plus stem-stripping.

**What is wrong:** the full-pipeline synth path
`_render_clause_full → _tokens_to_phoneme_words` resolves words via `lts()`
without that morphology, so it emits ARPABET `S`:
`dogs → ['D','AA1','G','S']`, `doctors → [… 'R','S']`, `runs → [… 'N','S']`.
`phalloph2` then faithfully renders `S`. Hence per-frame **C=Z, Py=S**.

**Why it's not a blanket rule (don't "voice S after any voiced phone"):**
the voicing is morphological. C keeps root `-s` voiceless
(`bus, this, yes, gas, us, plus, class` → **S**) but voices the suffix
(`dogs, runs, plays, goes, sees, beds` → **Z**). `plays`→Z and `yes`→S are
**both** vowel+`s`; distinguishing them needs stem detection
(`plays`=`play`+s), which is exactly what `text_to_dectalk_phonemes`'
stem-strip + `_voice_final_s_after_consonant(..., from_stem_strip=True)`
provides and a phonetic-context rule cannot.

**Fix sketch (for the speak.py owner):**
1. Promote `_voice_final_s_after_consonant` (and its `voiced_cons_for_z` /
   `vowel_arpabet` sets) from a `text_to_dectalk_phonemes` local to module
   scope, behaviour-preserving (guard with the existing 133 K
   `test_python_phonemes_vs_c_parity` corpus → byte-identical).
2. In `_render_clause_full`, after `_tokens_to_phoneme_words`, run each
   word's phones through the same stem-strip + `_voice_final_s_after_consonant`
   pass `text_to_dectalk_phonemes` uses, so the synth path's ARPABET gains
   the `S→Z` voicing before `phalloph2`.
3. Accept criteria: `[:debug 2200]` per-frame allophones — `dogs/doctors/
   runs/plays/goes/sees` final `-s` → **Z**; `bus/this/yes/gas/class` → **S**;
   full corpus WAV/phoneme tests unregressed.

Reproducers: `/tmp/{trace_synth_phon,subscan,trace_subs}.py` (worker scratch).

## Status of the F2/targets lane (this worker)

Closed at parity. Shipped: `dev` ← #252 (word-final monosyllabic `a` → AA,
fixing the pa/ta/ka "stop→vowel F2 stuck high" symptom). The remaining
in-lane LTS rules (silent-`l` `-alm/-alk`, polysyllabic final-`a`→AX schwa)
are confirmed **low-value**: the common words are dictionary-resolved and
never reach the LTS fallback.
