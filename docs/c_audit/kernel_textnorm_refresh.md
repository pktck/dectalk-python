# Kernel text-normalization — refresh audit vs C oracle

Companion to `docs/c_audit/kernel_textnorm.md` (issue #90). That
doc captured the architectural map (rule engine, domain
dictionaries, LTS dispatch) and a 51-prompt edge-case table. This
refresh re-runs the comparison against the **current** dev head
(`e0db2bc`, "refresh parstochip audit speak.py line refs"), pins the comparison to
**byte-exact `CAPI.convert_to_phonemes()` outputs** rather than
prior-doc "C expected" prose, and extends coverage on the
sentence-splitting axis that the prior table undertested.

Doc-only research (issue #90). No production code touched. No
`_DEFERRED` allow-list changes.

## What changed since the original audit

- `src/dectalk/kernel/text.py`, `kernel/normalize.py`, and
  `kernel/numbers.py` are unchanged at byte level between
  commit `6962206` (when the original audit landed) and the
  current dev tip `e0db2bc`.
- The two open ports cited by the original audit are still open:
  `src/dapi/src/cmd/par_pars1.c → src/dectalk/cmd/par_match_rule.py`
  and `→ src/dectalk/cmd/par_process_input.py` (both still raise
  `NotImplementedError`; confirmed via grep on the Python
  modules).
- The corpus the prior audit characterised has not visibly grown
  in `tests/parity/_corpus.py` between then and now. The
  divergences below are therefore the same divergences that
  the original doc identified — but expressed against the
  C oracle's exact byte output rather than a reconstructed
  word stream.

## Ground-truth methodology

For each probe input, the C side is **`CAPI.convert_to_phonemes(s)`**
from the locally-built `libtts_us.so` (the same library the
`tests/parity/test_convert_to_phonemes_parity.py` tests pin
against; outputs are byte-deterministic across the test corpus).
The Python side is the upper-case `WORD`-kind tokens emitted by
`dectalk.kernel.text.tokenize`. Pause tokens are omitted because
the C output uses phoneme-stream metacharacters (`,`, `.`, `?`)
rather than typed pauses; the asymmetry is documented separately
below.

## Phoneme-stream alphabet (for reading the C column)

DECtalk's phoneme stream encodes:

- lowercase letters = phonemes (`f` = /f/, `aellz` = /æɫz/, etc.),
- `'` = primary stress on the next vowel,
- `` ` `` = secondary stress,
- `^` `(` `)` `*` `#` = boundary / juncture / stress markers,
- spaces and `,` = pause / silence markers (the same character
  the input had — comma stays comma, period stays period),
- `.` / `?` / `!` at end of clause = clause-terminal pause class.

So `b"hxaxll' ow. w ' rrlld . "` reads "hello [pause] world
[pause]" with the inputs' period preserved.

## Refreshed divergence table — numbers

| Input | C oracle phoneme stream | Python tokens (WORD) | Match? | Why divergent |
|---|---|---|---|---|
| `5` | `f ' ayv` | `FIVE` | yes | trivial |
| `42` | `f ' ort iy  t ' uw` | `FORTY TWO` | yes | `number_to_words` covers 2 digits |
| `100` | `w ' ahn   hx' ahn d r axd` | `ONE HUNDRED` | yes | hundreds branch fine |
| `999` | `n ' ayn   hx' ahn d r axd   ) ehn d   n ' ayn t iy  n ' ayn` | `NINE HUNDRED NINETY NINE` | partial | C emits `) ehn d` (an "and" juncture) between hundreds and tens; Python emits raw words without `AND` |
| `1024` | `t ' ehn   t w ' ehn t iy  f ' or` (= "ten twenty four") | `ONE THOUSAND TWENTY FOUR` | no | C 4-digit year-form heuristic fires (`ls_util_is_year` → `ls_proc_do_4_digits`); Python treats every 4-digit number as cardinal |
| `2024` | `t w ' ehn t iy  t w ' ehn t iy  f ' or` | `TWO THOUSAND TWENTY FOUR` | no | same — C reads as year form "twenty twenty four"; Python cardinal "two thousand twenty four" |
| `1000` | `w ' ahn   th' awz axn d` | `ONE THOUSAND` | yes | 4-digit-year heuristic skips clean thousands |
| `1001` | `w ' ahn   th' awz axn d   ) ehn d   w ' ahn` | `ONE THOUSAND ONE` | partial | C emits "and" juncture; Python omits |
| `12345` | `t w ' ehllv   th' awz axn d , thr ' iy  hx' ahn d r axd   ) ehn d   f ' ort iy  f ' ayv` | `TWELVE THOUSAND THREE HUNDRED FORTY FIVE` | partial | C emits comma between magnitudes; Python no separator |
| `1,000` | `w ' ahn   th' awz axn d` | `ONE THOUSAND` | yes | commas stripped on both sides |
| `1,234,567` | `w ' ahn   m ' ihllyxaxn , t ' uw  hx' ahn d r axd ...` | `ONE MILLION TWO HUNDRED THIRTY FOUR THOUSAND FIVE HUNDRED SIXTY SEVEN` | partial | C inserts comma between magnitudes; Python doesn't |
| `5085551212` | `f ' ayv   z ' iyr ow  ' eyt , f ' ayv   f ' ayv   f ' ayv , w ' ahn   t ' uw  w ' ahn   t ' uw` | `FIVE BILLION EIGHTY FIVE MILLION FIVE HUNDRED FIFTY ONE THOUSAND TWO HUNDRED TWELVE` | **no** | **Original-audit correction.** R207 fires in US mode: 10-digit bare runs read as a phone number with comma pauses between area-code / exchange / line. Prior audit assumed C read this as integer; it does not. |
| `1234567890` | `w ' ahn   b ' ihllyxaxn , t ' uw  hx' ahn d r axd ...` | `ONE BILLION TWO HUNDRED THIRTY FOUR MILLION FIVE HUNDRED SIXTY SEVEN THOUSAND EIGHT HUNDRED NINETY` | partial | 10-digit non-phone reads as integer in both (no phone pattern match); divergence is the comma-between-magnitudes pause |
| `01` | `z ' iyr ow  w ' ahn` | `ONE` | no | C preserves leading zero ("zero one"); Python int-parses, dropping the `0` |
| `007` | `z ' iyr ow  z ' iyr ow  s ' ehv axn` | `SEVEN` | no | same; agents-of-007 / version-007 case |
| `00` | `z ' iyr ow  z ' iyr ow` | `ZERO` | no | same |
| `0.5` | `z ' iyr ow  p ' oyn t   f ' ayv` | `0.5` | no | decimal not parsed; emitted as raw word |
| `.5` | `p ' oyn t   f ' ayv` | `FIVE` | no | leading `.` stripped by Python; sign-flag analogue missing |
| `1.5 hours` | `w ' ahn   p ' oyn t   f ' ayv   ' awr z` | `1.5 HOURS` | no | decimal not parsed |
| `1.` (digit + period) | `w ' ahn .` | `ONE` | partial | C preserves the `.` as clause-terminal; Python drops period & pause |
| `3.14` | `thr ' iy  p ' oyn t   w ' ahn   f ' or` | `3.14` | no | decimal not parsed |
| `-3.14` | `m ' ayn axs   thr ' iy  p ' oyn t   w ' ahn   f ' or` | `3.14` | no | leading `-` stripped (`text.py:99-101` bug from prior audit, still present); decimal not parsed |
| `+5` | `p ll' ahs   f ' ayv` | `FIVE` | no | sign stripped |
| `-5` | `m ' ayn axs   f ' ayv` | `FIVE` | no | sign stripped |
| `1/2` | `w ' ahn   hx' aef` | `1/2` | no | `ls_task_frac_processing` not ported |
| `3/4` | `thr ' iy  f ' orths` | `3/4` | no | same |
| `12/25` | `t w ' ehllv   t w ' ehn t iy  f ' ihf ths` | `12/25` | no | **Surprise:** in C, `12/25` with no year reads as the fraction "twelve twenty-fifths" (frac_processing), not a date. The Python tokenizer does not match it as either date or fraction. Re-verified for issue #145 (2026-05-23): C oracle does NOT do date detection on bare `M/D` or `MM/DD` forms. |
| `01/01` | `z ' iyr ow  w ' ahn   s ll' aesh  z ' iyr ow  w ' ahn` | `01/01` | no | Issue #145 verification: leading-zero numerator/denominator suppresses C's frac_processing entirely — emits "zero one slash zero one" literal. Python emits raw `01/01`. |
| `7/8` | `s ' ehv axn   ' eyths` | `7/8` | no | C frac_processing → "seven eighths"; Python raw. Confirms `M/D` form is always fraction in C, never date. |
| `13/45` | `th' rr* t ' iyn   f ' ort iy  f ' ihf ths` | `13/45` | no | Same — even with month=13 (out of range), C reads as fraction "thirteen forty-fifths", not as anything date-shaped. |
| `60s` | `s ' ihk s t iyz` | `60S` | no | plural-decade rule (`sflag`) not ported |
| `'60s` | `s ' ihk s t iyz` | `60S` | no | same; the apostrophe variant also normalises in C |
| `the 1990s` | `dhax  w ' ahn   th' awz axn d , n ' ayn   hx' ahn d r axd   ) ehn d   n ' ayn t iyz` | `THE 1990S` | no | 4-digit + `s` → "nineteen-ninety-s" via combined year-form + plural-decade |
| `1st place` | `f ' rrs t   p ll' eys` | `1ST PLACE` | no | ordinal-suffix rule (R389 / LTS) missing |
| `21st` | `t w ' ehn t iy  f ' rrs t` | `21ST` | no | same |
| `2nd` | `s ' ehk axn d` | `2ND` | no | same |
| `3rd` | `th' rrd` | `3RD` | no | same |
| `22nd` | `t w ' ehn t iy  s ' ehk axn d` | `22ND` | no | same |
| `21st century` | `t w ' ehn t iy  f ' rrs t   s ' ehn chrriy` | `21ST CENTURY` | no | same |

## Refreshed divergence table — currency

| Input | C oracle phoneme stream | Python tokens (WORD) | Match? | Why |
|---|---|---|---|---|
| `$5` | `f ' ayv   d ' aallrrz` | `FIVE DOLLARS` | yes | Python special-cases `$<integer>` |
| `$5.50` | `f ' ayv   d ' aallrrz   ) ehn d   f ' ihf t iy  s ' ehn t s` | `5.50` | no | `$<int>.<int>` currency regex (`text.py:95`) too narrow — `.5` fails `isdigit()`. Same bug as in original audit. |
| `$0.50` | `z ' iyr ow  d ' aallrrz   ) ehn d   f ' ihf t iy  s ' ehn t s` | `0.50` | no | same |
| `$.50` | `f ' ihf t iy  s ' ehn t s` | `FIFTY` | no | leading-`$` then `.` strips both; emits naked `50` |
| `$5,000` | `f ' ayv   th' awz axn d   d ' aallrrz` | `FIVE THOUSAND DOLLARS` | yes | Python `$<comma-int>` path covers this; matches modulo the inter-magnitude pause juncture |
| `$1,234.56` | `w ' ahn   th' awz axn d , t ' uw  hx' ahn d r axd ...  d ' aallrrz   ) ehn d   f ' ihf t iy  s ' ihk s   s ' ehn t s` | `1,234.56` | no | same `.` bug; currency branch never fires |
| `$1 million` | `w ' ahn   m ' ihllyxaxn   d ' aallrrz` | `ONE MILLION` | no | "DOLLARS" suffix missing (the C path realises the currency word applies to a multi-token amount) |
| `5 cents` | `f ' ayv   s ' ehn t s` | `FIVE CENTS` | yes | both bare-word |
| `5%` | `f ' ayv   p rrs ' ehn t   ` | `FIVE` | no | `%` not recognized as percent-suffix; Python drops it as trailing punct |
| `20%` | `t w ' ehn t iy  p rrs ' ehn t   ` | `TWENTY` | no | same |
| `5cm` | `f ' ayv   s ' iy  ' ehm` | `5CM` | no | C `nabtab[]` matches `cm` and spells it letter-by-letter ("c m"); Python emits the token raw |
| `5km` | `f ' ayv   k ' ey  ' ehm` | `5KM` | no | same |
| `5lb` | `f ' ayv   ' ehll  b ' iy` | `5LB` | no | same |
| `60mph` | `s ' ihk s t iy  m ' ayllz   p rr  ' awr` | `60MPH` | no | **`nabtab[]` expands `mph` → "miles per hour"**; Python misses entirely |
| `10kg` | `t ' ehn   k ' ey  jh' iy` | `10KG` | no | same |

## Refreshed divergence table — abbreviations

| Input | C oracle phoneme stream | Python tokens (WORD) | Match? | Why |
|---|---|---|---|---|
| `Dr.` (alone) | `b''` (empty — clause is a single abbreviation; oracle emits nothing) | `DR` | no | abbreviation lookup happens before phoneme emission; standalone abbr produces empty stream in our test harness |
| `Dr. Smith` | `d aak t rr  s m ' ihth` | `DR SMITH` | no | `ls_task_Dr_St_process` matches "Dr." → "doctor"; Python emits letters |
| `Mr. Jones` | `m ihs t rr  jh' own z` | `MR JONES` | no | abbr lookup → "mister"; Python emits letters |
| `Mrs. Smith` | `m ihs ixz   s m ' ihth` | `MRS SMITH` | no | → "missus" |
| `Ms. Brown` | `m ihz   b r ' awn` | `MS BROWN` | no | → "miz" |
| `St. Louis` | `s eyn t   ll' uwixs` | `ST LOUIS` | no | → "saint" |
| `Mt. Everest` | `m awn t   ' ehv rrixs t` | `MT EVEREST` | no | → "mount" |
| `Rt. 66` | `' aar   t ' iy. s ' ihk s t iy  s ' ihk s` | `RT 66` | no | "Rt." not in any abbr dict; C spells "R T", emits `.` pause |
| `Apt 5b` | `' aep t   f ' ayv   b ' iy` | `APT 5B` | partial | C emits "apt" as a single morpheme (not expanded); Python preserves raw token but loses the digit-letter split |
| `U.S.` | `yx' uw  ' ehs` | `U.S` | partial | R44 keeps period-laden caps as a run in C; Python emits `U.S` with trailing `.` stripped to comma pause |
| `U.S.A.` | `yx' uw  ' ehs   ' ey` | `U.S.A` | partial | same as `U.S.` — pattern preserved by R44 |
| `USA` | `` ` yuehs ' ey`` | `USA` | yes | matches at LTS layer for both |
| `FBI` | `' ehf   b iy  ' ay` | `FBI` | yes | LTS minidict / acronym pass; Python emits the raw upper-case token, which the LTS layer then spells out — net match |
| `NASA` | `n ' aes ax` | `NASA` | yes | acronym in dict, pronounced as word |
| `MIT` | `` ` ehm ayt ' iy`` | `MIT` | yes | acronym in dict |
| `a.m.` | `) aem ` (about 5 chars) | `A.M` | no | R45 (`a.m.` → spelled) fires in C; Python keeps the dotted form |
| `p.m.` | `b''` (empty in isolation) | `P.M` | no | same |
| `i.e.` / `e.g.` / `etc.` / `vs.` (each alone) | `b''` (empty) | `I.E` / `E.G` / `ETC` / `VS` | no | `abbrp_words` (and the contraction lexicon) handles these in C; in isolation the oracle returns an empty phoneme stream because the abbreviation becomes a clause-empty token |
| `Mr. Smith vs. Jones.` | `m ihs t rr  s m ' ihth  v rrs ixs   jh' own z .` | `MR SMITH VS JONES` | no | C emits "mister … versus … jones"; Python emits raw |
| `AT&T` | `' ey  t ' iy  ' aen d   t ' iy.` | `AT&T` | no | `abbrp_words` rewrites `AT&T` → `A.T. & T.`; Python emits the raw token (the `&` is preserved because it's alnum-ish under `isalnum`) |
| `AC/DC` | `' aek   d ' iy  s ' iy` | `AC/DC` | no | LTS treats `/` as a separator and reads the letters; Python emits the raw token (slashes not split) |
| `P.O. Box` | `p ' iy  ' ow  b ' aak s` | `P.O BOX` | partial | both reach "P O Box" but Python loses the second `.` as a clause-terminal |
| `ZIP 90210` | `z ' ihp   n ' ayn t iy  th' awz axn d , t ' uw  hx' ahn d r axd   ) ehn d   t ' ehn` | `ZIP 90210` | no | 5-digit ZIP read as integer in C; Python emits the raw digit run |
| `route 66` | `r ' uwt   s ' ihk s t iy  s ' ihk s` | `ROUTE 66` | partial | Python passes `66` raw |
| `apartment 5B` | `axp ' aar t m axn t   f ' ayv   b ' iy` | `APARTMENT 5B` | partial | C splits `5B` into "five b"; Python keeps as one |
| `item #1` | `' ayt axm   n ' ahm b rr  s ayn   w ' ahn` | `ITEM 1` | no | C reads `#` as "number sign"; Python drops it |
| `#hashtag` | `n ' ahm b rr  s ayn   hx' aesht axg` | `HASHTAG` | no | same |
| `@user` | `' aet   ' yuz rr` | `USER` | no | `@` read as "at" in C; Python drops it |
| `and/or` | `' aen d * ' owr` | `AND/OR` | no | `/` → space in C; Python keeps the slash |

## Refreshed divergence table — sentence splitting

This axis was undercovered by the original audit. Findings:

| Input | C oracle phoneme stream | Python tokens (WORD) | Notes |
|---|---|---|---|
| `Hello. World.` | `hxaxll' ow. w ' rrlld .` | `HELLO WORLD` (+ 2× `pause_long:.`) | C preserves both periods in the phoneme stream as clause-terminal markers; Python's `tokenize` strips them off into PAUSE_LONG tokens whose `.text` field does carry the literal `.` character (so the information is preserved, just on a different token kind). For audio bit-parity both emit a long pause; for textual round-trip the divergence is the literal stream content. |
| `Hello! World!` | `hxaxll' ow! w ' rrlld !` | `HELLO WORLD` | same — `!` preserved by C |
| `Hello? World?` | `hxaxll' ow? w ' rrlld ?` | `HELLO WORLD` | same — `?` preserved by C |
| `one two; three four; five six` | `w ' ahn   t ' uw, thr ' iy  f ' owr , f ' ayv   s ' ihk s` | `ONE TWO THREE FOUR FIVE SIX` | C maps `;` to comma pause; Python emits a PAUSE_SHORT but the word stream loses the marker |
| `foo: bar` | `f ' uw, b ' aar` | `FOO BAR` | C maps `:` to comma; Python `:` becomes PAUSE_SHORT |
| `hello — world` (em-dash) | `hxaxll' ow  ' ey  s ' rrk axm f llehk s   yx' uwr ow  w ' rrlld` | `HELLO — WORLD` | **C spells out the em-dash as "a-circumflex euro" because UTF-8 bytes 0xE2 0x80 0x94 are interpreted as three separate Latin-1 characters in the C parser** — the C library has no Unicode support |
| `hello -- world` | `hxaxll' ow  d ' aesh  w ' rrlld` | `HELLO WORLD` | C reads `--` as the word "dash"; Python emits as a hyphen split that drops both halves |
| `wait... what` | `w ' eyt . w ` aht ` (wait period; what) | `WAIT WHAT` | R57 / R51 collapses long punct runs in C; Python drops the `...` into PAUSE_LONG but loses the literal ellipsis |
| `wait----what` | `w ' eyt   w ` aht ` | `WAIT WHAT` | C strips `----`; Python splits on `-` and emits `WAIT WHAT` (accidentally matches) |
| `(test)` | `t ' ehs t` | `TEST` | both strip parens correctly |
| `[test]` | `t ' ehs t` | `TEST` | same |
| `"hello"` | `hxaxll' ow` | `HELLO` | quotes stripped |
| `It ended.\nThen it began.` | `iht   ' ehn d ixd . dh` ehn   iht   ) b axg ' aen .` | `IT ENDED THEN IT BEGAN` | C treats newline as a clause boundary identical to `.`; Python's `.split()` does the same |
| `It ended.  Then it began.` (double space) | identical to above | identical | both fine |
| `(Note: this matters.)` | `n ' owt , dh` ihs   m ' aet rrz .` | `NOTE THIS MATTERS` | C strips parens, maps `:` to comma; Python emits NOTE THIS MATTERS (the `:` becomes a PAUSE_SHORT, the period a PAUSE_LONG) |
| `See note(1).` | `) s ' iy  n ' owt   w ' ahn .` | `SEE NOTE(1` | C splits `note(1)` into "note one"; Python keeps `(` mid-token because `_strip_trailing_punct` only walks from the right (it strips `.` then `)`), so the inner body becomes `note(1` which fails `isdigit()` and emits as `NOTE(1` raw. The C side instead inserts a space before the `(` via R5 / R230 (mid-word punctuation rule), then expands the digit. |

## Verified Python-side bugs (carried over from original audit)

All five bugs from §"Specific bugs in the current Python kernel"
of `kernel_textnorm.md` still apply to the current dev head:

1. **Over-aggressive leading-punct strip** (`text.py:99-101`) —
   `-5`, `+5`, `-3.14` all lose their sign before the body
   matcher sees them.
2. **Currency regex too narrow** (`text.py:95`) — `$5.50` and
   `$1,234.56` fail because `.` makes the `isdigit()` check
   return False.
3. **Matcher ordering inside body** (`text.py:140-144`) — phone
   matchers run on the **stripped** token, so paren-style
   phones `(508)555-1212` only match a pattern that lacks
   the leading `(`.
4. **Ad-hoc `number_to_words` vs LTS port** (`numbers.py:42-90`)
   — Python concatenates magnitude words; C emits `COMMA` /
   `pand` ("and") junctures between them.
5. **No clause-boundary detection beyond per-token punctuation**
   — Python's `tokenize` is a `str.split()` plus per-token
   trailing-punct walk; the C side runs `cm_text_getclause`
   which has a stream-level state machine.

## New findings (not in original audit)

These divergences were not tabulated in the prior doc:

1. **Leading-zero numbers** (`01`, `007`, `00`) — C preserves
   each `0` as a spoken "zero" digit ahead of the integer
   value; Python's `int("01") == 1` loses the leading zero.
   This matters for ZIP-prefix, badge-number, version-string
   prompts.
2. **`5085551212` reads as a phone, not an integer.** The
   prior audit asserted C would read this as a billion-plus
   integer; testing shows R207 actually fires and the digits
   read with comma pauses between area-code / exchange / line.
   Update the prior table accordingly.
3. **`12/25` with no year reads as a fraction in C, not a
   date.** C `ls_task_frac_processing` emits "twelve
   twenty-fifths". The Python `try_date` matcher in
   `kernel/normalize.py` doesn't accept the 2-part form (it
   requires year), so `12/25` falls through to raw — but the
   "correct" C interpretation isn't `MAY 12 25` either; it's
   the fraction.

   **Issue #145 verification (2026-05-23, NO-OP):** Probed the
   C oracle via `CAPI.convert_to_phonemes()` on `12/25`, `01/01`,
   `7/8`, `13/45`. Confirmed: no date detection at all in the C
   `M/D` or `MM/DD` form. `12/25` → fraction, `7/8` → fraction,
   `13/45` → fraction, `01/01` → literal "zero one slash zero
   one" (leading zeros suppress frac_processing). Adding
   Python-side date detection for these patterns would
   **diverge** Python from C and regress the bit-parity goalpost
   in `docs/PLAN.md` Phase E. Issue #145 closed as
   no-op-by-design; the gap (raw `12/25` in Python vs.
   "twelve twenty-fifths" in C) is the unported
   `ls_task_frac_processing` listed in
   `docs/c_audit/kernel_textnorm.md` recommended-ports table.
4. **Unit-abbreviation table (`nabtab[]`) is wide-ranging.**
   `5cm`, `5km`, `5lb`, `10kg`, `60mph` all expand in C
   (mph → "miles per hour", cm → "C M", lb → "L B", etc.).
   Python's hyphen-and-currency-and-date-only matcher misses
   every one. This is on top of the 9 cases the prior audit
   tabulated.
5. **`%` and `#` and `@` and `&` symbols.** C maps these to
   spoken words ("percent", "number sign", "at", "and").
   Python's tokenizer treats them as non-alnum trailing punct
   and silently drops them.
6. **`!` and `?` survive into the C phoneme stream** as
   literal markers. Python's tokenizer maps them to a
   `PAUSE_LONG` token whose `.text` field does carry the
   literal `!`/`?` character (the strongest-trailing-punct
   path in `_strip_trailing_punct` captures it) — so the
   data is on the wire, just on a different token kind than
   on the WORD stream. Audio synthesis behaviour matches;
   only a literal-string round-trip parity check would
   fail.
7. **Em-dash and other Unicode punctuation cause C to garble
   the input** (the C library is ISO-8859 only). Python
   handles em-dash and en-dash correctly as `PAUSE_SHORT`.
   This is the one case where **Python does the right thing
   and C doesn't** — but parity tests should mark such
   prompts as expected-divergent rather than failing on them.
8. **C abbreviation lookup returns an empty phoneme stream
   for isolated abbreviations** (`Dr.`, `i.e.`, `Inc.`,
   `etc.` alone). This is a C-side quirk: the abbreviation
   expansion runs after clause segmentation, and a
   single-token clause whose only content is a known abbrv
   collapses to nothing in the phoneme dump.

## Summary

Same conclusion as the original audit, with the corrections
above folded in:

- The pure-Python `dectalk.kernel.text` pipeline matches the
  C oracle on simple words, plain integers <10 digits (modulo
  the COMMA juncture), bare `$<int>` currency, and hyphenated
  compounds.
- It diverges on every date, every phone, every fraction,
  every ordinal, every decimal, every signed number, every
  4-digit year, every leading-zero number, every plural
  decade, every abbreviation that expects dictionary lookup,
  every unit suffix (`mph`/`cm`/`kg`/...), and every
  punctuation symbol other than `.`/`,`/`;`/`:`/`!`/`?`/`-`.
- The unblocker is still the two open ports in
  `docs/TASKS.md`: `par_match_rule` and `par_process_input`
  in `src/dectalk/cmd/`. Until those land plus the eight
  domain dictionaries in `par_nws.par`, every divergence in
  the tables above will persist.

## Cross-references

- `docs/c_audit/kernel_textnorm.md` — the original 51-prompt
  audit. This refresh adds byte-exact C phoneme output and
  extends sentence-splitting coverage.
- `docs/c_audit/lts.md` — companion audit for the LTS-side
  divergences (`ls_task_*` ports).
- `docs/PLAN.md` Phase E — the active milestone whose root
  cause is the front-end gap documented here.
- `docs/TASKS.md` rows for `par_match_rule.py` and
  `par_process_input.py` — the two open ports that unblock
  the rule engine and the eight domain dictionaries.

_Generated by Claude Code_

Authored-by: Claude:claude-opus-4-7
