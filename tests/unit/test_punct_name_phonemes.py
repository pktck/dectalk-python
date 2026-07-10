"""Spoken-punctuation-name phoneme streams (issue #315).

Punctuation-only input does NOT collapse to a bare clause marker: the
C cmd stage (``cm_pars_proc_char`` / ``cm_text_getclause``) forwards an
isolated mark as its own one-char word, and ``ls_spel`` spells it via
the language typing table (``usa_type.tab``) -- the binary SPEAKS the
mark's name. Bare ``...`` therefore renders the 182-frame "period"
clause, where the old Python front end emitted a lone ``PERIOD`` marker
and the PH chain rendered ~1 frame.

Every literal below is pinned byte-for-byte against the C library's
``convert_to_phonemes`` on the 8-space-flushed stream (the speak path's
flush -- ``say`` and ``CAPI._speak_locked`` both append it -- which
resolves the C parser's pending-dot state). The WAV-level counterpart
lives in ``tests/parity/test_vtm1_pcm_parity.py``
(``_PUNCT_NAME_BYTE_EXACT_PROMPTS``); this file keeps the front-end
rules covered in the oracle-free fast lane.
"""

from __future__ import annotations

import pytest

from dectalk.api.speak import text_to_dectalk_phonemes

# Typing-table renderings (``usa_type.tab``):
#   '.' "p'irixd"          -> b"p ' iyr iyaxd "
#   ',' "k'amx"            -> b"k ' aam ax"
#   ':' "k'olxn"           -> b"k ' owllaxn "
#   ';' "s'Emi#kolxn"      -> b"s ' ehm iy# k owllaxn "
#   '!' "Eksklxm'eSxn pOnt"-> b"ehk s k llaxm ' eyshaxn   p oyn t "
#   '?' "kw'EsCxn mark"    -> b"k w ' ehs chaxn   m aar k "
_PERIOD = b"p ' iyr iyaxd "
_COMMA = b"k ' aam ax"
_COLON = b"k ' owllaxn "
_SEMI_COLON = b"s ' ehm iy# k owllaxn "
_EXCLAMATION_POINT = b"ehk s k llaxm ' eyshaxn   p oyn t "
_QUESTION_MARK = b"k w ' ehs chaxn   m aar k "


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Punctuation-only input speaks the name. No terminator marker:
        # the utterance-final PERIOD comes from the PH task's flush
        # (ph_task.c line 738), exactly as for unpunctuated text.
        ("...", _PERIOD),
        (".", _PERIOD),
        ("....", _PERIOD),
        (",", _COMMA),
        (":", _COLON),
        (";", _SEMI_COLON),
        ("!", _EXCLAMATION_POINT),
        ("?", _QUESTION_MARK),
        # ``..`` is the LTS word ``.`` plus its ``.`` right-punct:
        # "period" + attached terminator.
        ("..", _PERIOD + b". "),
        # Repeated dot runs: one name word per run.
        ("... ...", _PERIOD + b"  " + _PERIOD),
        # Name words at clause start, real words following.
        (", hello", _COMMA + b"  hxaxll' ow"),
        ("... hello", _PERIOD + b"  hxaxll' ow"),
        # A name closes the clause: marks after a name are spoken by
        # name too, never attached.
        ("... !", _PERIOD + b"  " + _EXCLAMATION_POINT),
        ("... ?", _PERIOD + b"  " + _QUESTION_MARK),
        ("... , hello", _PERIOD + b"  " + _COMMA + b"  hxaxll' ow"),
        # Isolated multi-dot runs after a word speak the name (never
        # attach) -- the #315 headline shape.
        ("hello ...", b"hxaxll' ow  " + _PERIOD),
        ("hello ..", b"hxaxll' ow  " + _PERIOD + b". "),
        (
            "text with trailing ...",
            b"t ' ehk s t   w ihth  t r ' eyllixnx  " + _PERIOD,
        ),
        # A SINGLE isolated mark directly after a word attaches as the
        # ordinary clause/sentence marker (cm_text.c rev 074 removes
        # the space before clause punctuation).
        ("hello .", b"hxaxll' ow. "),
        ("hello !", b"hxaxll' ow! "),
        ("hello ?", b"hxaxll' ow? "),
        ("hello ,", b"hxaxll' ow, "),
        ("hello ;", b"hxaxll' ow, "),
        ("hello :", b"hxaxll' ow, "),
        ("one . two", b"w ' ahn . t ' uw"),
        # After a closed clause (word + terminator) the next isolated
        # mark has no word to attach to -- spoken by name again.
        ("one, .", b"w ' ahn , " + _PERIOD),
    ],
)
def test_punct_name_stream(text: str, expected: bytes) -> None:
    """``text_to_dectalk_phonemes`` matches the C stream byte-for-byte."""
    assert text_to_dectalk_phonemes(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        # Attached multi-dot runs collapse to a single attached PERIOD
        # -- the pre-#315 behaviour, and the corpus's six ``word...``
        # prompts depend on it staying put.
        "well...",
        "wait...",
        "the end...",
    ],
)
def test_attached_dot_runs_unchanged(text: str) -> None:
    """Attached ``word...`` runs still collapse to one attached PERIOD."""
    stream = text_to_dectalk_phonemes(text)
    assert stream.endswith(b". ")
    assert b"iyr iyaxd" not in stream  # no spurious "period" word


@pytest.mark.parametrize(
    "text",
    [
        # 5+ dot runs hit a C-side cm_pars buffer bug (the run
        # degenerates to a lone ``t`` word); they deliberately stay on
        # the legacy pause path here rather than modelling the bug.
        ".....",
        "......",
    ],
)
def test_long_dot_runs_stay_on_legacy_path(text: str) -> None:
    """5+ dot runs keep the legacy bare-marker stream (C hits a parser bug)."""
    assert text_to_dectalk_phonemes(text) == b". "
