# Kernel text-normalization — C vs. Python audit

Reference C tree:
- `src/dapi/src/cmd/par_rule.par`, `par_rule1.par`, `par_rule2.par`
  (rule-based clause preprocessor — punctuation, dates, phone
  numbers, URLs, abbreviations).
- `src/dapi/src/cmd/par_pars.c`, `par_pars1.c`
  (rule interpreter; `par_convert_number`, `par_match_*`,
  `par_match_rule`, `par_process_input`).
- `src/dapi/src/cmd/cm_text.c`
  (clause buffer / `cm_text_getclause` / `cm_text_get_word`
  splitter — feeds the parser).
- `src/dapi/src/cmd/par_nws.par`
  (NWS-mode rule set + the domain dictionaries `states`,
  `english_months`, `month_words`, `month_abbr`, `day_words`,
  `time_words`, `direct_words`, `abbr_words`, `abbrp_words`).
- `src/dapi/src/lts/ls_task.c`
  (per-token dispatcher; `ls_task_parse_number`,
  `ls_task_plain_number_processing`, `ls_task_Dr_St_process`,
  `ls_task_currency_processing`, `ls_task_date_processing`,
  `ls_task_frac_processing`, `ls_task_part_number`).
- `src/dapi/src/lts/l_us_pr1.c`
  (`ls_proc_do_number` — phoneme-level number expansion up to 18
  digits with comma/grouping handling).
- `src/dapi/src/lts/l_us_con.c`
  (`nabtab[]` — unit-abbreviation table consulted after numbers:
  `cm`/`mm`/`km`/`in`/`ft`/`yd`/`mi`/`ha`/`ml`/`tsp`/`tbsp`/`qt`/
  `gm`/`mg`/`kg`/`lb`/`oz`/`nsec`/...).

Reference Python (current state):
- `src/dectalk/kernel/text.py` (`tokenize`, `_normalize_token`,
  `_strip_trailing_punct`, `_body_words`).
- `src/dectalk/kernel/normalize.py` (`try_date`, `try_phone`,
  `try_url`).
- `src/dectalk/kernel/numbers.py` (`number_to_words`).
- `src/dectalk/lts/number_emit.py` (`ls_proc_do_number` — bit-parity
  port of the LTS-side number-to-phoneme function; already covered
  by `tests/unit/test_lts_number_emit.py`).
- `src/dectalk/lts/number_words.py`, `src/dectalk/lts/number_tables.py`
  (digit-group helpers used by `ls_proc_do_number`).

This audit is **doc-only research** (issue #90). No code changes;
nothing in `_DEFERRED` allow-lists is touched. The goal is to
quantify the gap so the next ported milestone (a faithful
`par_match_rule` / `par_process_input` port) has a concrete target
list of failing edge cases.

## Architectural mismatch

**C side** runs a two-stage text-normalization pipeline:

1. **`cm_text_getclause`** chops the input stream into "clauses"
   (sentence-ish chunks bounded by `.`, `?`, `!`, certain control
   codes, and the email-header heuristic in rules R601-R608).
2. **`par_match_rule` / `par_process_input`** apply the compiled
   rule table from `par_rule*.par` (~3300 lines of grammar) to each
   clause. The grammar performs:
   - punctuation insertion (R0, R5),
   - URL/e-mail scheme rewriting (R46, R130, R376-R383),
   - date pattern → month-day-year reordering (R308-R312, R401,
     R500, R551 — language-specific),
   - phone-number grouping with comma pauses (R204-R210),
   - currency / signed-number pass-through (R40-R43),
   - time-of-day pass-through (R39, R41),
   - state-postal-code → state-name lookup (R327, R329),
   - compound-noun and hyphen splitting (R345-R353, R390-R393),
   - abbreviation rewriting from the `abbr_words` / `abbrp_words`
     / `univ_words` / `month_abbr` / `day_words` / `time_words` /
     `direct_words` / `states` domain dictionaries.
3. **`ls_task_*` (LTS)** then walks the rewritten clause token by
   token. Per-token dispatch includes `ls_task_Dr_St_process`,
   `ls_task_currency_processing`, `ls_task_date_processing`,
   `ls_task_frac_processing`, `ls_task_plain_number_processing`,
   `ls_task_part_number`, and the per-language
   `ls_proc_do_number`.

**Python side** is a thin two-pass tokenizer:

1. `tokenize()` splits on whitespace only (no clause boundary
   detection beyond per-token trailing punctuation; sentence
   strength is captured but used only to emit `PAUSE_LONG`).
2. Per-token: try `try_url` (full-token URL); strip trailing
   punctuation; recognise leading `$` currency; route inner body
   through `try_date` / `try_phone`; otherwise split on `-` and
   expand purely-digit chunks through `number_to_words`.

Concrete consequences:

- **No rule-engine** — the C parser is rewriting and re-scanning;
  the Python tokenizer makes one left-to-right pass with
  hand-written regex matchers. Many C rules cannot be expressed
  one-shot (e.g. R310's "month + ordinal day, comma" pattern
  spans three tokens; the Python tokenizer cannot look across
  whitespace).
- **No domain dictionaries** — none of the eight C dicts in
  `par_nws.par` have a Python equivalent. `Mt.` → `mount`,
  `mph` → `miles an hour`, `AT&T` → `A.T. & T.`, `MA` → state
  name `Massachusetts`, etc. are all missing.
- **No language-mode gating** — every C rule is keyed on a
  language bit (`0x00000021` = US, `0x00000004` = German,
  `0x00000020` = UK, etc.). Python ignores language entirely;
  there is no equivalent of US-only or UK-only behaviour.
- **Number-to-words is duplicated** —
  `dectalk.kernel.numbers.number_to_words` is an ad-hoc Python
  re-implementation; `dectalk.lts.number_emit.ls_proc_do_number`
  is the bit-accurate port of `ls_proc_do_number()`. The kernel
  tokenizer calls the **ad-hoc** one, not the bit-accurate one,
  so even simple integer expansions can diverge in pause
  placement (the C path emits `COMMA`/`VPSTART`/`pand` between
  magnitudes per `ls_proc_non_zero` rules; the Python ad-hoc
  path just concatenates words).

## Per-prompt divergence

Running `dectalk.kernel.text.tokenize` over a representative
edge-case set (US-mode expectations; words are the upper-case
strings the tokenizer emits, `[pause_*]` are pause markers):

| Input | C expected (US mode) | Python tokenize output | Divergence |
|---|---|---|---|
| `Dr. Smith` | "DOCTOR SMITH" (R47-like / `ls_task_Dr_St_process`) | `DR . SMITH` | abbr dict missing; `.` emitted as long-pause |
| `St. John` | "SAINT JOHN" (LTS lookahead) | `ST . JOHN` | same — no Dr/St lookahead in Py |
| `Mr. Jones` | "MISTER JONES" (lexicon abbreviation) | `MR . JONES` | dictionary expansion missing |
| `U.S.A.` | "U S A" pass through (R44 keeps single-upper-`.` runs) | `U.S.A .` | R44 not modelled; period leaks |
| `a.m.` | "A M" (R45: `a.m.` → `eyh m`) | `A.M .` | R45 missing |
| `p.m.` | "P M" (R45) | `P.M .` | R45 missing |
| `i.e.` | "I E" (`abbrp_words` lookup, R49) | `I.E .` | abbrp dict missing |
| `e.g.` | "for example" (`abbrp_words`) | `E.G .` | abbrp dict missing |
| `Inc.` | "INC" (LTS abbreviation table) | `INC .` | no abbr lookup, period leaks |
| `etc.` | "et cetera" (lexicon) | `ETC .` | OK at LTS layer; tokenizer leak isn't fatal |
| `10,000` | "TEN THOUSAND" (LTS) | `TEN THOUSAND` | match — comma-stripped + `number_to_words` covers it |
| `$1,000,000` | "ONE MILLION DOLLARS" (LTS currency) | `ONE MILLION DOLLARS` | match (Python special-cases `$` prefix) |
| `3.14` | "THREE POINT ONE FOUR" (LTS, `ppoint`) | `3.14` (raw) | Python doesn't recognise decimal fractions |
| `-3.14` | "MINUS THREE POINT ONE FOUR" (LTS sign) | `3.14` (raw, sign dropped) | Python strips `-` leading punct then fails to expand |
| `+42` | "PLUS FORTY TWO" (LTS sign) | `FORTY TWO` (sign dropped) | Python ignores sign |
| `1/2` | "ONE HALF" (LTS fraction / `ls_task_frac_processing`) | `1/2` (raw) | fractions not implemented |
| `60s` | "SIXTIES" (LTS plural-number rules in `ls_task_plain_number_processing`) | `60S` (raw) | not implemented |
| `60's` | "SIXTIES" (LTS plural-number rules) | `60'S` (raw) | not implemented |
| `21st` | "TWENTY FIRST" (R389 keeps ordinal suffix; LTS ordinal) | `21ST` (raw) | not implemented |
| `2nd` | "SECOND" (R389; LTS) | `2ND` (raw) | not implemented |
| `chapter 5` | "CHAPTER FIVE" | `CHAPTER FIVE` | match |
| `chapter.....2` | "CHAPTER 2" (R51 collapses >=5 punct → pause; R50 strips trailing `.`) | `CHAPTER.....2` | rule R50/R51 missing |
| `http://example.com` | "H T T P COLON SLASH SLASH EXAMPLE DOT COM" (R46 → ` http:// `; R130/R5130 → "dot"/"slash") | `H T T P COLON SLASH SLASH EXAMPLE DOT COM` | match |
| `foo@example.com` | "F O O at sign EXAMPLE dot COM" (R377: e-mail) | `FOO@EXAMPLE.COM` (raw) | R377 missing |
| `4:32pm` | "FOUR THIRTY TWO P M" (R39 time pass-through; R45 a.m./p.m.) | `4:32PM` (raw) | R39 / R45 missing |
| `4.40.38` | "FOUR DOT FORTY DOT THIRTY EIGHT" (R13425 v-version rule eats it) | `4.40.38` (raw) | R13425 missing |
| `1-508-555-1212` | "ONE COMMA FIVE ZERO EIGHT COMMA FIVE FIVE FIVE COMMA ONE TWO ONE TWO" (R204) | `ONE FIVE ZERO EIGHT FIVE FIVE FIVE ONE TWO ONE TWO` | recognised; commas/pauses missing |
| `(508)555-1212` | full phone (R206) with commas | `FIVE ZERO EIGHT FIVE FIVE FIVE ONE TWO ONE TWO` | recognised; commas missing |
| `5085551212` | "FIVE BILLION EIGHTY FIVE MILLION..." (R207 is opt-in; default treats as integer via `ls_proc_do_number`) | `FIVE BILLION ... TWELVE` | match (C also reads as integer when phone-rule mode bit off) |
| `1996/05/15` | "MAY FIFTEENTH NINETEEN NINETY SIX" (R312 → `15-may-1996` → LTS year-pattern) | `MAY FIFTEEN ONE THOUSAND NINE HUNDRED NINETY SIX` | year-pattern (`ls_util_is_year` → `ls_proc_do_4_digits`) not modelled |
| `15-March-1996` | "FIFTEENTH MARCH NINETEEN NINETY SIX" (R309) | `FIFTEEN MARCH ONE THOUSAND NINE HUNDRED NINETY SIX` | year-pattern missing; ordinal day missing |
| `May 3, 1996` | "MAY THIRD NINETEEN NINETY SIX" (R311) | `MAY THREE , ONE THOUSAND NINE HUNDRED NINETY SIX` | ordinal-day, year-form missing |
| `V4.41` | "V FOUR POINT FOUR ONE" (R328: alpha + decimal → spell + " point ") | `V4.41` (raw) | R328 missing |
| `c:\access32` | "C COLON BACKSLASH ACCESS THIRTY TWO" (R2433/R2444 path-mode) | `C:\ACCESS32` (raw) | path-mode missing |
| `$5` | "FIVE DOLLARS" | `FIVE DOLLARS` | match |
| `$5.50` | "FIVE DOLLARS AND FIFTY CENTS" (LTS currency) | `5.50` (raw — fails `isdigit()` after `$.replace(',','')`) | bug: decimal trips currency path |
| `$1,234,567` | "ONE MILLION TWO HUNDRED THIRTY FOUR THOUSAND FIVE HUNDRED SIXTY SEVEN DOLLARS" | matches | OK |
| `AT&T` | "A T AND T" (`abbrp_words`: `AT&T~A.T. & T.`) | `AT&T` (raw) | dict missing |
| `C++` | "C PLUS PLUS" (R52: literal protected then spelled) | `C` (`+` stripped, `++` dropped silently) | R52 missing |
| `twenty-four` | "TWENTY FOUR" | `TWENTY FOUR` | match (hyphen split) |
| `self-driving` | "SELF DRIVING" | `SELF DRIVING` | match |
| `don't` | "DO NOT" (lexicon / LTS contraction) | `DON'T` (raw) | apostrophe handling absent |
| `I've` | "I HAVE" (lexicon) | `I'VE` (raw) | apostrophe handling absent |
| `15 W.` | "FIFTEEN WEST" (R384 → `direct_words`) | `FIFTEEN W .` | direct_words dict missing |
| `King Charles III` | "KING CHARLES THE THIRD" (R387 → `roman_num`) | `KING CHARLES III` (raw) | roman_num dict missing |
| `60 percent` | "SIXTY PERCENT" | `SIXTY PERCENT` | match |
| `90 degrees` | "NINETY DEGREES" | `NINETY DEGREES` | match |

Summary: 9 of 51 cases match. 42 of 51 (~82%) diverge, of which:

- **22** trace to missing domain dictionaries (`abbr_words`,
  `abbrp_words`, `month_words` post-tokenization, `direct_words`,
  `roman_num`, `day_words`, `time_words`, `states`, the LTS
  `nabtab[]`, the contraction lexicon).
- **9** trace to missing LTS dispatch logic
  (`ls_task_Dr_St_process`, `ls_task_frac_processing`,
  `ls_task_currency_processing` 4-digit year branch,
  `ls_proc_do_4_digits`, `ls_proc_is_am_pm`, plural-number "60s").
- **8** trace to missing rule-engine rules (R40 sign handling,
  R44 single-upper-`.`, R45 a.m./p.m., R46 e-mail, R50/R51
  punctuation collapse, R52 c++, R204-R208 phone-number comma
  pauses, R328 alpha+decimal, R339 file-name dot replacement,
  R384 `15 W.`).
- **3** trace to year-pattern detection
  (`ls_util_is_year` + `ls_proc_do_4_digits` are not ported;
  every 4-digit number reads as cardinal "two thousand twenty
  four", never "twenty twenty four").

## Tracked divergences (C-faithful — do NOT "fix")

These are behaviors the Python side already mirrors faithfully from
C source, even though they may look intuitively wrong. Issues to "fix"
these get closed as no-ops; documenting here so future audits don't
re-open them.

1. **`MM/DD` two-component slash dates are fractions, not dates** (issue #145).

   `12/25` reads as "twelve twenty-fifths", `1/2` as "one half", etc.
   The C `ls_proc_is_date` (`l_us_pr1.c` lines 826+) only matches
   `D-MMM[-YY[YY]]` patterns — alphabetic month abbreviation with
   dash separator. There is no `MM/DD` date pattern anywhere in
   `l_us_pr1.c`. Slash-separated two-component tokens fall through
   to `ls_proc_is_frac` (`l_us_pr1.c` lines 991+), which accepts
   1-2 digit numerator over 1-3 digit denominator (capped at 100
   for the 3-digit case) and emits the ordinal-denominator form.
   `01/01` is rejected by the fraction check (leading-zero numerator)
   and falls through to plain digit-by-digit reading with the slash
   spoken as "slash".

   Python's `dectalk.lts.date_recognizer.ls_proc_is_date` and
   `ls_proc_is_frac` mirror this exactly (see
   `tests/unit/test_lts_date_recognizer.py`). The kernel-side
   `dectalk.kernel.normalize.try_date` also requires three
   components (month/day/year) before treating a slash token as a
   date — adding `MM/DD` detection would *introduce* a divergence,
   not remove one.

   The original audit row above (`12/25` in the per-prompt table)
   isn't listed because Python's tokenizer and C agree: both say
   "twelve twenty-fifths".

## Specific bugs in the current Python kernel

1. **`text.py:99-101` over-aggressive leading-punct strip**

   ```python
   while word and not word[0].isalnum():
       word = word[1:]
   ```

   silently drops leading `-` / `+` / `(` / quote without
   preserving the sign for the number that follows. C handles
   sign via `ls_task_set_sign_flag` → `ls_proc_do_sign`. The
   Python tokenizer can never produce "MINUS THREE POINT ONE
   FOUR" because the `-` is stripped before the body is
   examined.

2. **`text.py:95` currency regex too narrow**

   ```python
   if word.startswith("$") and word[1:].replace(",", "").isdigit():
   ```

   only recognises `$<integer>` and `$<comma-separated-integer>`.
   `$5.50` fails the `isdigit()` check because `.` is non-digit,
   so it falls through to the body path and is emitted raw.
   `ls_task_currency_processing` (l_us_pr1.c lines 3181+) handles
   `$<int>.<int>` and emits "DOLLARS AND <n> CENTS".

3. **`text.py:140-144` matcher ordering inside body**

   The body tries `try_date` then `try_phone`. After `_strip_trailing_punct`
   has run, `(508)555-1212` has lost the leading `(`. C order in
   `par_rule.par` is the inverse: phone matchers (R204-R210) are
   evaluated before date matchers (R308-R312) inside the rule
   pass. The Python tokenizer pattern-matches against the
   *stripped* word, not the raw one, so paren-style phones only
   match a regex that has no `(`.

4. **`numbers.py:42-90` ad-hoc `number_to_words` vs LTS port**

   The kernel tokenizer calls `number_to_words` (a Python-only
   helper) while LTS already has the bit-accurate
   `ls_proc_do_number`. These two have non-identical join
   behaviour: the LTS port emits `COMMA` / `VPSTART` / `pand`
   between magnitudes via `_emit_separator`; the kernel helper
   just concatenates words with no separator markers. For
   audio-bit parity this matters because the COMMA marker
   triggers a Klatt frame pause.

5. **No clause-boundary detection beyond per-token punctuation**

   `cm_text_getclause` (cm_text.c lines 276-1303) actively walks
   the input stream, treats `0x0fff`, control-XON, certain
   email-header lines, etc. as clause-internal vs
   clause-terminating. Python's `tokenize` splits on whitespace
   only — a long paragraph with embedded `0x82` markers will
   yield a single mega-clause to the synthesizer.

6. **Hyphen-split is too eager**

   `twenty-four` correctly splits, but C does this via
   compound-word dictionary lookups (`2_c_words` through
   `6_c_words`) plus R350 (suffix compounds). Python's eager
   `.split('-')` breaks `self-driving` (correct accident) but
   also breaks `e-mail` (C explicitly rewrites it to `e mail`
   via R221, but only after R49 / R50 have had a chance to fire).

## Recommended ports (no work done in this PR)

These should be filed as follow-up issues; rough size estimates
based on lines of C plus the per-rule tabulation above.

| Port target | C source | Est. size | Why |
|---|---|---|---|
| `par_match_rule` / `par_process_input` | `par_pars1.c` lines 581-708, 709-900 | large (1000+ LOC) | The actual rule interpreter; already listed in `docs/TASKS.md` |
| Domain-dictionary loader for `par_nws.par` | new module + ~500 lines of dict data | medium | unlocks ~22 of the 42 diverging cases |
| `ls_task_Dr_St_process` | `ls_task.c` lines 2989-3060 | small (~100 LOC) | Dr. / St. / Mt. routing |
| `ls_task_currency_processing` | `l_us_pr1.c` lines 3181+ | medium | dollars-and-cents form |
| `ls_task_frac_processing` | `l_us_pr1.c` lines 3679+ | small | `1/2`, `1/4`, `^2`, `^3` |
| `ls_proc_do_4_digits` | `l_us_pr1.c` | small | year form ("nineteen ninety-six") |
| Plural-number "60s" / "60's" / ordinal "21st" | `l_us_pr1.c` lines 3936+ | small | `pflag`/`sflag` extension |
| `nabtab[]` (unit abbrev table) | `l_us_con.c` lines 364+ | data-only, medium | mph / cm / kg etc. after numbers |
| Contraction lexicon (don't, I've, won't, can't…) | lives in the binary dictionary, not C source | data-only | matches LTS dictionary lookup |

Until these land, the Python `dectalk.kernel.text` pipeline is
useful only for the simplest prompts — well-formed words,
plain integers, currency without cents, hyphenated compounds.
Anything date-ish, phone-ish, abbreviation-ish, ordinal,
fractional, or signed will mispronounce. This is consistent
with `docs/parity-divergence-audit.md` § "Front-end" — 0/15
corpus prompts achieve bit-parity with the C oracle, and the
diagnostic dump shows the divergence starts at the first
non-silence sample, i.e. at the very first phoneme produced
by a mismatched front-end token stream.

## Cross-references

- `docs/PLAN.md` Phase E (the active milestone) — bit-accurate
  audio out of the pure-Python path requires this front-end
  layer to land first.
- `docs/parity-divergence-audit.md` — the audio-level snapshot
  whose root cause is documented in this file.
- `docs/TASKS.md` rows
  `src/dapi/src/cmd/par_pars1.c → src/dectalk/cmd/par_match_rule.py`
  and
  `src/dapi/src/cmd/par_pars1.c → src/dectalk/cmd/par_process_input.py`
  are the two open ports that, when complete, will enable the
  rest of the rule-engine work above.

_Generated by Claude Code_

Authored-by: Claude:claude-opus-4-7
