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
| 3 | **Z→S** | 11 | plural/possessive `-s` after a voiced segment (*plays, doctors, matters*) | phoneme is `S` on **both** sides (`convert_to_phonemes` agrees); C's allophone stage **voices** final `-s`→Z after a voiced phone. Python's phalloph doesn't apply the voicing-assimilation rule | `src/dectalk/ph/us_phalloph2.py` (allophonic voicing) |
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
2. **Z→S voicing assimilation** (#3, 11×). Port the C allophone-stage rule
   that voices a final `-s` to the Z allophone after a voiced phone.
   Self-contained, testable against `[:debug 2200]`.
3. **Function-word vowel reduction** (#2/#4/#5). *can/than/had*→EH,
   article *a*→AX, AH/AX schwa selection. Likely a reduced-pronunciation
   table in the dictionary/cmd layer.

All three are outside the PH-target / LTS-rules lanes; they live in the
`ph/us_phalloph2.py` allophone chain and the dictionary/reduction tables.

## Status of the F2/targets lane (this worker)

Closed at parity. Shipped: `dev` ← #252 (word-final monosyllabic `a` → AA,
fixing the pa/ta/ka "stop→vowel F2 stuck high" symptom). The remaining
in-lane LTS rules (silent-`l` `-alm/-alk`, polysyllabic final-`a`→AX schwa)
are confirmed **low-value**: the common words are dictionary-resolved and
never reach the LTS fallback.
