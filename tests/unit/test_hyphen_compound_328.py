"""Hyphen tokens no longer leak the compound ``#`` marker (issue #328).

The C phoneme alphabet's ``HYPHEN`` code (``l_com_ph.h:55``, printed as a
literal ``#``) is the *noun-compound* boundary. The Python front end used
to insert it for **every** hyphen, so hyphen-joined tokens leaked a ``#``
into the stream where C strips it, realizes it as a dictionary ``*``
MBOUND, verbalizes the ``-`` as the spoken word "dash", or uses a plain
word break. :func:`dectalk.text_to_dectalk_phonemes` now mirrors C:

- a whole-token dictionary compound (``x-ray`` -> ``'Eksre``, ``t-shirt``
  -> ``t'i*S`Rt``, ``so-called`` -> ``s'o*k`cld``) is looked up intact
  and carries its own boundary from the runtime ``Dic_us.txt`` row;
- two multi-letter alphabetic words take the genuine ``#`` compound
  boundary (``well-known``, ``twenty-one``);
- a digit run on either side, or a leading single letter, verbalizes the
  ``-`` as "dash" (``par_rule.par`` R223/R224) instead of ``#``;
- ``e-mail`` is the lexical one-off C renders as two words ("e mail").

The expected phoneme streams below are the byte-exact
``TextToSpeechConvertToPhonemes`` output (captured from the shared C
oracle); this unit test pins them without needing the oracle at run time.
The live-oracle facet lives in
``tests/parity/test_stage_lts_parity.py::test_hyphen_compound_marker_matches_c``.
"""

from __future__ import annotations

import dectalk

# Byte-exact C ``convert_to_phonemes`` output for each representative.
_EXPECTED: dict[str, bytes] = {
    # Whole-token dictionary compounds (the core fix): the hyphenated
    # form is a single Dic_us.txt entry, so no per-hyphen ``#`` leaks.
    "x-ray": b"' ehk s r ey",
    "t-shirt": b"t ' iy* sh` rrt ",
    "so-called": b"s ' ow* k ` aolld ",
    # Two multi-letter words -> the genuine compound ``#`` boundary.
    "well-known": b"w ' ehll# n ' own ",
    "twenty-one": b"t w ' ehn t iy# w ' ahn ",
    "self-taught": b"s ' ehllf # t ' aot ",
    "high-end": b"hx' ay# ' ehn d ",
    # Word then a bare single letter still takes ``#`` (the asymmetry
    # that distinguishes it from a *leading* single letter).
    "cat-a": b"k ' aet # ' ey",
    # A digit run on either side verbalizes the ``-`` as "dash".
    "Catch-22": b"k ' aech  d ' aesh  t w ' ehn t iy  t ' uw",
    "1-cat": b"w ' ahn   d ' aesh  k ' aet ",
    "cat-1": b"k ' aet   d ' aesh  w ' ahn ",
    # A leading single letter verbalizes "dash".
    "x-cat": b"' ehk s   d ' aesh  k ' aet ",
    "u-turn": b"yx' uw  d ' aesh  t ' rrn ",
    # Lexical one-off: rendered as the two words "e mail" (word break).
    "e-mail": b"' iy  m ' eyll",
    # Pure digit/dash ranges owned by the numeric part-number dispatch
    # (issue #225) -- regression guard that the hyphen change left them.
    "3-2": b"thr ' iy  d ' aesh  t ' uw",
    "1-10": b"w ' ahn   d ' aesh  t ' ehn ",
}


def test_hyphen_representatives_byte_exact() -> None:
    """Each #328 representative matches the pinned C phoneme stream."""
    for text, expected in _EXPECTED.items():
        actual = dectalk.text_to_dectalk_phonemes(text)
        assert actual == expected, (
            f"phoneme mismatch for {text!r}:\n"
            f"  expected (C): {expected!r}\n"
            f"  actual (Py):  {actual!r}"
        )


def test_compound_hash_present_only_for_word_compounds() -> None:
    """The ``#`` marker appears for word compounds, never for dash cases."""
    for word in ("well-known", "twenty-one", "self-taught", "high-end", "cat-a"):
        assert b"#" in dectalk.text_to_dectalk_phonemes(word), (
            f"compound # marker missing for {word!r}"
        )


def test_no_stray_hash_in_dash_and_dict_cases() -> None:
    """No literal ``#`` leaks where C verbalizes "dash" or hits the dict.

    Covers the #328 leak class directly: a digit run on either side, a
    leading single letter, the dictionary compounds, and the ``e-mail``
    one-off must all be free of the ``#`` (HYPHEN) marker.
    """
    dash_or_dict = [
        "x-ray",
        "t-shirt",
        "so-called",
        "e-mail",
        "Catch-22",
        "3-2",
        "1-10",
        "1-cat",
        "cat-1",
        "22-dog",
        "x-cat",
        "u-turn",
        "a-b",
        "b-x",
        "one-2",
    ]
    for text in dash_or_dict:
        out = dectalk.text_to_dectalk_phonemes(text)
        assert b"#" not in out, f"stray # marker leaked for {text!r}: {out!r}"
