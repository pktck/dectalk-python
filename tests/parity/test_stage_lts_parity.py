"""Per-stage parity (issue #150): LTS + dic — ARPABET phoneme stream.

LTS (letter-to-sound) + dic together produce DECtalk's ARPABET-style
phoneme stream. The C library exposes this via
``TextToSpeechConvertToPhonemes`` (added by
``tests/parity/c_patches/0001-expose-convert-to-phonemes-on-linux.patch``);
the Python port produces the same stream via
:func:`dectalk.text_to_dectalk_phonemes` and the byte-equality is
already enforced across the full bit-parity corpus by
``test_python_phonemes_vs_c_parity.py``.

This per-stage file is the narrow, fast version of that gate: a
handful of representative prompts run through both sides, byte-equal
asserted. The full-corpus test stays the authoritative regression
guard; this one slots into the per-stage parity dashboard so the LTS
stage shows green alongside its KERNEL / CMD / PH / VTM siblings.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

import pytest

import dectalk
from dectalk._capi import CAPI

from ._stage_helpers import STAGE_CORPUS, skipif_no_oracle

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))


def _convert_to_phonemes_exported() -> bool:
    """True iff libtts_us.so exports ``TextToSpeechConvertToPhonemes``.

    Mirrors the helper in ``test_python_phonemes_vs_c_parity.py`` so
    this test skips identically when the convert-to-phonemes patch is
    absent from the C build.
    """
    candidates = sorted(_SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    if not candidates:
        return False
    try:
        lib = ctypes.CDLL(str(candidates[-1]))
        getattr(lib, "TextToSpeechConvertToPhonemes")  # noqa: B009
    except (OSError, AttributeError):
        return False
    return True


pytestmark = [
    pytest.mark.c_oracle,
    skipif_no_oracle,
    pytest.mark.skipif(
        not _convert_to_phonemes_exported(),
        reason="libtts_us.so missing TextToSpeechConvertToPhonemes — apply C patches",
    ),
]


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI handle."""
    return CAPI()


@pytest.mark.parametrize("text", STAGE_CORPUS, ids=list(STAGE_CORPUS))
def test_python_arpabet_matches_c(text: str, capi: CAPI) -> None:
    """``dectalk.text_to_dectalk_phonemes`` matches ``CAPI.convert_to_phonemes``.

    Per-stage version of the LTS gate: small corpus, fast runtime,
    shows up in the per-stage parity dashboard. The full-corpus
    enforcement lives in ``test_python_phonemes_vs_c_parity.py`` and
    must also stay green; this test is the per-stage facet of the
    same invariant.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"LTS+dic phoneme stream mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


# Issue #310 representatives: the -ed / -ing / -er / -s suffix family
# on doubled-final-consonant (and related runtime-dictionary-rooted)
# stems. Each row names a distinct mechanism in the fix:
#   - "stopped" / "stopping" / "stopper": the l_us_suf.c un-doubling
#     variants re-deriving the runtime-dictionary root (AO vowel from
#     the dictionary row; the -ed rule devoices to T after P).
#   - "grabbed" / "planned": LTS-tier stems (outside both
#     dictionaries) with the voiced -ed -> D tail.
#   - "stirred": the -ed rule's ``rr`` un-doubling variant.
#   - "fitted": the T/D-final stem's epenthetic IX + D tail.
#   - "swapped": curated override for the compiled ``wa`` -> AO
#     letter rule the Python heuristic LTS lacks.
#   - "committed": curated override for C's second-syllable LTS
#     stress the Python heuristic LTS lacks.
#   - "admitted" / "begins" / "married": pure-verb runtime roots
#     emitting the ``)`` VPSTART marker from the root entry's mask.
#   - "visited" / "referring": lexicon rows re-aligned from the 2002
#     source rows to the runtime Dic_us.txt rows (IX vs AX vowels).
#   - the in-context rows: the family embedded in running text.
_ED_SUFFIX_FAMILY: tuple[str, ...] = (
    "stopped",
    "stopping",
    "stopper",
    "grabbed",
    "planned",
    "stirred",
    "fitted",
    "swapped",
    "committed",
    "admitted",
    "begins",
    "married",
    "visited",
    "referring",
    "the rain stopped.",
    "it stopped raining",
    "she grabbed it",
    "we planned a trip",
    "he admitted it",
)


# Issue #244 representatives: symbol -> runtime-dictionary expansion.
# Each row names a distinct mechanism in the fix:
#   - "you & me" / "a = b" / "email me @ work" / "one + two": the
#     standalone-symbol word forms whose phonemes come from the
#     Dic_us.txt symbol rows, NOT the spelled word ("&" reads a
#     stressed ``' aen d`` without the ``^ (`` function-word markers;
#     "@" reads stressed ``' aet``; "=" carries the syllabic EL;
#     "+" keeps the voiceless final S).
#   - "hello / world" / "fifty % done": the two symbol forms that were
#     already byte-exact before the fix (regression guard).
#   - "one+ two" / "one# two" / "one/ two" / "one^ two": word-attached
#     symbols split out of the chunk (the census-confirmed set).
#   - "a+b" / "A&B": mid-word splits (the article rule still applies
#     to the split-out "a"/"A").
#   - "x / y" / "vitamin C": standalone letters read as their
#     primary-stressed letter names in every position.
#   - "and/or": whole-token dictionary entries beat the splitter.
_SYMBOL_EXPANSION_FAMILY: tuple[str, ...] = (
    "you & me",
    "one + two",
    "a = b",
    "email me @ work",
    "hello / world",
    "fifty % done",
    "two * three",
    "one # two",
    "one ^ two",
    "one+ two",
    "one# two",
    "one/ two",
    "one^ two",
    "a+b",
    "A&B",
    "x / y",
    "vitamin C",
    "and/or",
)


@pytest.mark.parametrize("text", _SYMBOL_EXPANSION_FAMILY, ids=list(_SYMBOL_EXPANSION_FAMILY))
def test_symbol_expansion_family_matches_c(text: str, capi: CAPI) -> None:
    """Symbol word-forms and letter names are byte-identical (issue #244).

    Pins the symbol -> runtime-dictionary expansion chain: standalone
    and word-attached symbol tokens speak via their Dic_us.txt rows
    (``&`` -> ``' aen d``, ``^`` -> ``k ' ehr axt``, ...), single
    letters read as primary-stressed letter names, and whole-token
    dictionary entries (``and/or``) keep beating the splitter.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"symbol-expansion mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


# Issue #246 representatives: title-abbreviation expansion.
# Each row names a distinct mechanism in the fix:
#   - "Mr. Smith" / "Mrs. Brown called today." / "Ms. Jones" /
#     "Bond vs. Smith" / "Prof. White teaches here.": the period-keyed
#     runtime-dictionary rows (destressed ``m ihs t rr`` etc.), firing
#     case-insensitively in any context.
#   - "St. Paul is a city." / "Dr. Smith said hello.": the
#     ls_task_Dr_St_process capitalised-next branch (saint/doctor).
#   - "Main St. is long." / "The Dr. smith": the lowercase-next,
#     not-clause-initial branch (street/drive).
#   - "Hello, St. paul": comma resets the clause -> first-word rule
#     picks saint.
#   - "mister Smith" / "Saint Paul is a city." / "No. 5": spelled-out
#     controls that must stay untouched.
#   - "today": the runtime-dictionary IX first vowel (``t|d'e``).
_ABBREVIATION_FAMILY: tuple[str, ...] = (
    "Mr. Smith",
    "Mrs. Brown called today.",
    "Ms. Jones",
    "Bond vs. Smith",
    "Prof. White teaches here.",
    "St. Paul is a city.",
    "Dr. Smith said hello.",
    "Main St. is long.",
    "The Dr. smith",
    "Hello, St. paul",
    "mister Smith",
    "Saint Paul is a city.",
    "No. 5",
    "today",
)


@pytest.mark.parametrize("text", _ABBREVIATION_FAMILY, ids=list(_ABBREVIATION_FAMILY))
def test_abbreviation_family_matches_c(text: str, capi: CAPI) -> None:
    """Title abbreviations are byte-identical (issue #246).

    Pins both C mechanisms: the period-keyed runtime-dictionary rows
    (mr./mrs./ms./prof./vs. — destressed, context-free) and the
    ``ls_task_Dr_St_process`` context rule for dr./st.
    (doctor/saint vs drive/street by next-word case, clause position,
    and the back-to-back guard).
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"abbreviation mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


@pytest.mark.parametrize("text", _ED_SUFFIX_FAMILY, ids=list(_ED_SUFFIX_FAMILY))
def test_ed_suffix_family_matches_c(text: str, capi: CAPI) -> None:
    """Doubled-consonant -ed/-ing family is byte-identical (issue #310).

    Pins the suffix-strip chain fixed in #310: the ACTIVE
    ``l_us_suf.c`` strip rules (un-doubling variants, runtime-
    dictionary membership, the ``)`` VPSTART marker from the stripped
    root's entry) plus the C LTS engine's -ed tail behaviour
    (devoiced T / voiced D / epenthetic IX D) for stems outside the
    dictionaries.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"-ed suffix family mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


# Issue #320 representatives: silent-e / doubled-stem massaging for the
# vowel-initial suffixes -ing / -es / -er / -est (the #316 census
# residual after #310 handled -ed). Each row names a distinct mechanism:
#   - "poking" / "hiking" / "gliding" / "moping" / "roving": magic-e
#     lengthening on the -ing stem (POKE -> ...OW K, not the short
#     whole-word LTS vowel) via _lts_inflection_stem's silent-e attach.
#   - "pokes" / "hikes" / "glides": the same magic-e stem through the
#     -es path (keep the orthographic E rather than stripping it).
#   - "braver" / "paler": magic-e on the -er stem (BRAVE -> ...EY V).
#   - "bravest" / "palest" / "cutest" / "finest" / "ripest" / "latest" /
#     "widest": magic-e on the -est stem, preferring the silent-e base
#     (CUTE not CUT), with the C-faithful IX S T suffix.
#   - "fittest" / "dimmest" / "slimmest" / "maddest": doubled-stem
#     un-doubling on -est (FITT -> FIT) plus the IX S T suffix vowel.
#   - "stressing" / "stressed" / "blessing" / "pressing": root -SS is a
#     cluster the C engine keeps voiceless -- it is NOT un-doubled (that
#     would voice the S to Z).
#   - "roses" / "foxes" / "masses" / "classes" / "bushes": epenthetic
#     IX Z on sibilant-final -es stems (regression guards for the
#     keep-the-E change).
_INFLECTION_SILENT_E_FAMILY: tuple[str, ...] = (
    "poking",
    "hiking",
    "gliding",
    "moping",
    "roving",
    "pokes",
    "hikes",
    "glides",
    "braver",
    "paler",
    "bravest",
    "palest",
    "cutest",
    "finest",
    "ripest",
    "latest",
    "widest",
    "fittest",
    "dimmest",
    "slimmest",
    "maddest",
    "stressing",
    "stressed",
    "blessing",
    "pressing",
    "roses",
    "foxes",
    "masses",
    "classes",
    "bushes",
    "she was poking around",
    "the bravest knight",
    "it kept stressing me",
)


@pytest.mark.parametrize("text", _INFLECTION_SILENT_E_FAMILY, ids=list(_INFLECTION_SILENT_E_FAMILY))
def test_inflection_silent_e_family_matches_c(text: str, capi: CAPI) -> None:
    """Silent-e / doubled-stem -ing/-es/-er/-est family is byte-identical (issue #320).

    Pins the generalisation of the #310 -ed stem massaging to the other
    vowel-initial suffixes: magic-e lengthening on out-of-lexicon stems
    (``poking`` -> POKE), the -est superlative's silent-e-preferring
    lookup + ``IX S T`` suffix, doubled un-doubling (``fittest`` -> FIT),
    and the root-``SS`` voiceless-keep guard (``stressing`` stays
    ``ehs``, not ``ehz``).
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"silent-e/doubled inflection mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


# Issue #321 representatives: consonant + y stems inflected -ier / -iest
# / -ies / -ied. The orthographic y -> i mutation (happy -> happier)
# reads in C as the base's final /iy/, not the whole-word LTS /ay/. Each
# row recovers the -Y base and appends the inflection:
#   - "happier" / "easier" / "busier" / "funnier" / "heavier" /
#     "uglier" / "angrier" / "lazier": -ier -> base + ER0 (HAPPY + ER).
#     "heavier" also pins the lexicon-EA stem (HEAV -> ...EH V, not the
#     whole-word LTS /iy/); "angrier" pins the retained G (ANGR + IY).
#   - "happiest" / "easiest" / "busiest" / "funniest": -iest -> base +
#     IX S T (the ``iy ix s t`` tail).
#   - "envies" / "pities": -ies -> base + Z on an out-of-lexicon -Y root.
#   - "pitied" / "envied": -ied -> base + D on an out-of-lexicon -Y root.
#   - "babies" / "carries" / "cities" / "cries" / "flies" / "carried" /
#     "married" / "tried" / "soldier": regression guards -- the LTS
#     y-rule keeps single-syllable bases /ay/ (FLY) and lexicon bases
#     correct, and "soldier" (a lexicon root, not happy->happier) is
#     untouched.
_INFLECTION_Y_MUTATION_FAMILY: tuple[str, ...] = (
    "happier",
    "easier",
    "busier",
    "funnier",
    "heavier",
    "uglier",
    "angrier",
    "lazier",
    "happiest",
    "easiest",
    "busiest",
    "funniest",
    "envies",
    "pities",
    "pitied",
    "envied",
    "babies",
    "carries",
    "cities",
    "cries",
    "flies",
    "carried",
    "married",
    "tried",
    "soldier",
    "the happiest day",
    "she felt busier now",
)


@pytest.mark.parametrize(
    "text", _INFLECTION_Y_MUTATION_FAMILY, ids=list(_INFLECTION_Y_MUTATION_FAMILY)
)
def test_inflection_y_mutation_family_matches_c(text: str, capi: CAPI) -> None:
    """-ier/-iest/-ies/-ied y-mutation family is byte-identical (issue #321).

    Pins the y -> i mutation reading: the mutated ``i`` is rendered as
    the -Y base word's final /iy/ (``happier`` -> ``hx aep iyrr``), not
    the whole-word LTS /ay/ ("happ-eye-er"). Single-syllable bases
    (``flies`` -> FLY) stay /ay/ via the LTS y-rule, and lexicon roots
    like ``soldier`` are left alone.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"y-mutation inflection mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


# Issue #322 representatives: the re-rendered stem's weak vowel (IX vs
# AX) on the suffix-strip path. The encoder's word-final AH0 -> IX/AX
# reductions gate on the vowel being word-final, so an appended suffix
# shifts the reduction context; C freezes the stem's *bare* weak vowel.
# Each row names a direction / guard:
#   - "edits" / "edited" / "limits" / "limiting": IX direction -- the
#     bare stem's word-final -it IX is kept under the suffix (``ehd ixt``
#     not ``ehd axt``).
#   - "finishing" / "finishes" / "finished" / "polished" / "punished" /
#     "vanished": the -ish IX kept under -ing/-es/-ed.
#   - "focused": AX direction -- FOCUS's bare AX is kept, not the
#     spurious IX the appended ``S T`` (-est-like) pattern would add.
#   - "satisfies": the -sfy IX kept under -ies.
#   - "promised" / "practiced" / "noticed": the silent-e sibilant class
#     (PROMISE / PRACTICE / NOTICE) where the bare Python reduction is
#     unreliable -- the freeze is skipped so the assembled IX stands.
_INFLECTION_WEAK_VOWEL_FAMILY: tuple[str, ...] = (
    "edits",
    "edited",
    "limits",
    "limiting",
    "finishing",
    "finishes",
    "finished",
    "polished",
    "punished",
    "vanished",
    "focused",
    "focuses",
    "satisfies",
    "promised",
    "practiced",
    "noticed",
    "he edited it",
    "she was finishing up",
    "we focused on it",
)


@pytest.mark.parametrize(
    "text", _INFLECTION_WEAK_VOWEL_FAMILY, ids=list(_INFLECTION_WEAK_VOWEL_FAMILY)
)
def test_inflection_weak_vowel_family_matches_c(text: str, capi: CAPI) -> None:
    """Weak-vowel (IX vs AX) freeze on the inflection-stem path (issue #322).

    Pins both directions of the stem weak-vowel selection: the stem
    keeps its *bare* reduction under an appended suffix (``edits`` keeps
    ``edit``'s IX; ``focused`` keeps ``focus``'s AX rather than gaining a
    spurious IX from the -est-like ``S T``), while the silent-e sibilant
    class (``promised`` / ``practiced`` / ``noticed``) defers to the
    assembled context so it is not demoted to AX.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"weak-vowel inflection mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


# Issue #225 representatives: the C front end's numeric-format
# expansion, routed through ``lts.numeric_formats``. Each row names a
# distinct mechanism:
#   - ordinals: pordin units ("1st"/"42nd"), teens + TH ("11th"),
#     tens + IX + TH ("20th"), hundred + pand + ordinal ("103rd"),
#     magnitude-bail + TH ("1000th") — ls_task.c:3953 + the
#     do_digit_group oflag arms (l_us_pr1.c:429).
#   - currency: dollars plural Z, "$N.NN" cents with the leading-zero
#     skip and singular/plural pflag forms, ".00" suppression, the
#     non-2-digit decimal fallback, and the nwdtab "$5 million"
#     scale-word lookahead (ls_task_currency_processing).
#   - clock times: 1/2-digit hour, VPSTART joins, "00"-minute skip,
#     leading-zero minute spell, :SS tails, and the spelled am/pm
#     lookahead (ls_proc_is_time / do_time, ls_task.c:3616).
#   - fractions: half/halves, ordinal denominators with the Z/S
#     plural allomorph, the "12/25" M/D-looking form that C reads as
#     a fraction (ls_proc_is_frac / do_frac).
#   - dd-mon dates: month word + ordinal day + year forms
#     (ls_proc_is_date / do_date).
#   - part-number ranges: digit runs via do_2/3/4_digits with the
#     spelled "dash" separator (ls_task_part_number).
#   - signed integers / decimals: ls_proc_do_sign + do_number.
#   - digit plurals: do_number + ls_util_pluralize ("60s" / "60's").
_NUMERIC_FORMATS: tuple[str, ...] = (
    "1st",
    "2nd",
    "3rd",
    "11th",
    "20th",
    "42nd",
    "103rd",
    "1000th",
    "$5",
    "$1.50",
    "$0.01",
    "$3.00",
    "$3.240",
    "$12,345.67",
    "$5 million",
    "3:30",
    "12:45",
    "3:05",
    "7:00",
    "12:34:56",
    "3:30 pm",
    "1/2",
    "3/4",
    "12/25",
    "99/100",
    "10-20",
    "5-3",
    "2022-2023",
    "B-52",
    "23-aug-1984",
    "23-Aug",
    "-5",
    "+5",
    "-1/2",
    "60s",
    "60's",
    "the 3rd time",
    "pay $1.50 now",
    "range 10-20 only",
    "meet on 12/25 sharp",
    "it costs $5 million",
)


@pytest.mark.parametrize("text", _NUMERIC_FORMATS, ids=list(_NUMERIC_FORMATS))
def test_numeric_formats_match_c(text: str, capi: CAPI) -> None:
    """Numeric-format expansion is byte-identical (issue #225).

    Pins the ``lts.numeric_formats`` dispatch: ordinal suffixes,
    currency (incl. the nwdtab scale-word lookahead), clock times
    (incl. the spelled am/pm lookahead), fractions, dd-mon dates,
    digit-dash part-number ranges, signed numbers, and digit plurals
    — each byte-compared against ``TextToSpeechConvertToPhonemes``.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"numeric-format mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


# Issue #323 representatives: mixed alphanumeric clusters. The C NWS
# pre-processor (par_rule.par rules R390/R391) inserts a space at every
# digit/letter boundary and reads each run independently; guard rule R389
# keeps the ordinal/plural suffixes whole. Each row names a mechanism:
#   - letter+digit and digit+letter runs: single letters wordize (``A``
#     -> article schwa, ``M`` -> "em", ``x`` -> "ex"), digit runs read as
#     numbers ("forty two", "ten").
#   - unpronounceable all-caps clusters spell (``kg`` -> "kay gee") via the
#     say-it predicate.
#   - the ``e``/``E`` in ``1E10`` / ``6.02e23`` is split off as its own
#     letter run (no MODE_MATH exponent), and the decimal in ``6.02``
#     survives the split.
#   - the R389 guard leaves decade plurals (``1990s`` / ``70s`` / ``'90s``)
#     to the numeric plural path.
_MIXED_ALNUM_FAMILY: tuple[str, ...] = (
    "A1",
    "3M",
    "B2B",
    "42kg",
    "2x",
    "3D",
    "1E10",
    "6.02e23",
    "2e-5",
    "M1",
    "1kg",
    "the '90s",
    "1990s",
    "70s",
    "Buy 42kg now.",
    "model 3D printing",
)


@pytest.mark.parametrize("text", _MIXED_ALNUM_FAMILY, ids=list(_MIXED_ALNUM_FAMILY))
def test_mixed_alnum_split_matches_c(text: str, capi: CAPI) -> None:
    """Mixed alphanumeric clusters are byte-identical (issue #323).

    Pins the ``token_shapes`` letter/digit split + reinject: each run
    reads as its own word (numbers, letter names / article schwa, or
    spelled all-caps clusters), byte-compared against
    ``TextToSpeechConvertToPhonemes``.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"mixed-alnum mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )


# Issue #324 representatives: contextual roman numerals. The C NWS rule
# R387 (par_rule.par:417) rewrites a roman numeral to its ordinal value
# ("the Nth") only when it directly follows a capitalised word; the
# ``roman_num`` table is exact strings for 2..20. Every row here is a
# *triggered* case (capitalised prefix + table hit); the non-triggered
# and false-positive-guard cases live in the oracle-free unit test
# ``tests/unit/test_token_shapes.py`` (bare ``IV`` / lowercase ``iv`` /
# ``Chapter, IV`` stay ordinary words). Rows span the table range and a
# variety of capitalised prefixes (proper nouns, common nouns, all-caps,
# two-letter, sentence-initial verb).
_ROMAN_NUMERAL_FAMILY: tuple[str, ...] = (
    "Chapter IV",
    "Henry VIII",
    "Book XIV",
    "World War II",
    "Louis XVI",
    "Chapter III",
    "Chapter VII",
    "Chapter XI",
    "Chapter XVIII",
    "Chapter XX",
    "Pope VI",
    "Hi IV",
    "Cat IV dog",
    "RED IV",
    "Mix IV things",
    "Apple II",
    "Say XIV again.",
)


@pytest.mark.parametrize("text", _ROMAN_NUMERAL_FAMILY, ids=list(_ROMAN_NUMERAL_FAMILY))
def test_roman_numeral_ordinal_matches_c(text: str, capi: CAPI) -> None:
    """Capitalised-prefix roman numerals read as ordinals (issue #324).

    Pins the ``token_shapes`` R387 recognizer: a capitalised word
    followed by a table roman (2..20) rewrites to "the Nth", byte-compared
    against ``TextToSpeechConvertToPhonemes``.
    """
    expected = capi.convert_to_phonemes(text)
    actual = dectalk.text_to_dectalk_phonemes(text)
    assert actual == expected, (
        f"roman-numeral mismatch for {text!r}:\n"
        f"  expected (C): {expected!r}\n"
        f"  actual (Py):  {actual!r}"
    )
