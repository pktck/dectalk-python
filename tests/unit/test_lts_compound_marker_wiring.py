"""Verify the compound-``*`` MBOUND and ``)`` VPSTART sidecar wiring.

The compound-marker sidecar (``src/dectalk/data/lexicon_us_markers.txt``)
and the VPSTART sidecar (``src/dectalk/data/vpstart_us.txt``) are
consumed by :func:`dectalk.text_to_dectalk_phonemes` via
:mod:`dectalk.dic.markers`. This test asserts both flow through the
phoneme path correctly without needing the C oracle to be available.
"""

from __future__ import annotations

import dectalk
from dectalk.dic.markers import load_marker_lexicon, load_vpstart_words


def test_marker_sidecar_loads_with_entries() -> None:
    """Sidecar lexicon parses and contains representative compounds."""
    lex = load_marker_lexicon(lang="us")
    # Roughly 1100 closed compounds in the bundled sidecar.
    assert len(lex) > 500
    # Well-known closed compounds with ``*`` MBOUND markers.
    for word in ("BREAKFAST", "PIPELINE", "DATABASE", "AIRPLANE", "BIRTHDAY"):
        assert word in lex, f"{word!r} missing from marker lexicon"
        assert "__PUNCT__*" in lex[word], f"{word!r} marker entry missing __PUNCT__*: {lex[word]}"


def test_vpstart_sidecar_loads_with_entries() -> None:
    """Sidecar VPSTART set parses and contains representative verbs."""
    words = load_vpstart_words(lang="us")
    # Roughly 1400 verb infinitives in the bundled sidecar.
    assert len(words) > 500
    # Spot-check classic dictionary verbs (form-class FC_VERB).
    for verb in ("SEE", "GO", "EAT", "SELL", "SPEAK"):
        assert verb in words, f"{verb!r} missing from VPSTART set"


def test_compound_marker_emitted_for_sidecar_word() -> None:
    """Compound words from the sidecar emit ``*`` in the phoneme stream.

    The C source's main dictionary marks BREAKFAST as
    ``B R EH1 K * F AH0 S T`` (``__PUNCT__*`` between the two
    components). The Python phoneme path encodes that ``*`` as a literal
    ``*`` in the DECtalk ASCII output.
    """
    out = dectalk.text_to_dectalk_phonemes("breakfast")
    assert b"*" in out, f"compound * marker missing for breakfast: {out!r}"


def test_compound_marker_emitted_for_multiple_compounds() -> None:
    """All representative sidecar compounds emit the ``*`` marker."""
    for word in ("breakfast", "pipeline", "database", "airplane", "birthday"):
        out = dectalk.text_to_dectalk_phonemes(word)
        assert b"*" in out, f"compound * marker missing for {word!r}: {out!r}"


def test_vpstart_marker_emitted_for_sidecar_verb() -> None:
    """A sidecar-only verb (not in the hand-curated set) emits ``)``.

    ``DENY`` is a verb that is in ``Dic_us.txt``'s form-class set but
    absent from the hand-curated ``vpstart_words`` block in
    :func:`dectalk.text_to_dectalk_phonemes`. With the sidecar wired in,
    it now emits the ``)`` VPSTART marker.
    """
    # Verify our assumption: DENY is in the sidecar.
    assert "DENY" in load_vpstart_words(lang="us")
    out = dectalk.text_to_dectalk_phonemes("deny")
    assert b")" in out, f"VPSTART ) marker missing for deny: {out!r}"


def test_vpstart_not_emitted_for_non_verb() -> None:
    """A common noun does NOT trigger the VPSTART marker."""
    # ``DOG`` is a noun, not a verb -- should not emit ``)``.
    assert "DOG" not in load_vpstart_words(lang="us")
    out = dectalk.text_to_dectalk_phonemes("dog")
    assert b")" not in out, f"VPSTART ) erroneously emitted for dog: {out!r}"
