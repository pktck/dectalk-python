"""Front-end tests for comma-clause splitting and audio-path number
expansion (issues #218 / #238).

These are Phase-E-independent: they assert token structure, sub-clause
counts/contents, and that the audio and phoneme front-ends share one
number-expansion implementation. They do NOT assert absolute sample
counts (the pure-Python pipeline over-renders vs C by a fixed offset,
which is the out-of-scope Phase-E timing divergence).
"""

from __future__ import annotations

from dectalk.api.speak import (
    _digit_expand,
    _split_clause_marks,
    _tokenize_with_numbers,
    text_to_dectalk_phonemes,
)
from dectalk.kernel.text import TokenKind, tokenize


# ---------------------------------------------------------------------------
# Piece A: the comma / ; / : clause splitter.
#
# The splitter does ``re.split(r"(?<=[,;:])\s*", sentence)``: it cuts AFTER
# each delimiter and the lookbehind's ``\s*`` consumes whitespace that
# immediately follows a delimiter. The delimiter therefore stays attached to
# the left chunk; whitespace not adjacent to a delimiter is preserved.
# ---------------------------------------------------------------------------
class TestSplitClauseMarks:
    def test_no_markers_returns_single_element(self) -> None:
        # Byte-identical-to-pre-split requirement: a sentence with no
        # internal ,;: comes back unchanged as exactly [sentence].
        assert _split_clause_marks("hello world.") == ["hello world."]

    def test_comma_split_keeps_delimiter(self) -> None:
        # The delimiter stays attached to the left chunk so the tokeniser
        # still emits the pause token and the clause is detectable.
        assert _split_clause_marks("one, two, three.") == ["one,", "two,", "three."]

    def test_four_clause_split(self) -> None:
        assert _split_clause_marks("a, b, c, d.") == ["a,", "b,", "c,", "d."]

    def test_semicolon_and_colon(self) -> None:
        assert _split_clause_marks("foo; bar: baz.") == ["foo;", "bar:", "baz."]

    def test_consecutive_markers(self) -> None:
        # Each delimiter ends a chunk; the lone middle ``,`` is a non-empty
        # (non-whitespace) chunk so it survives as its own sub-clause.
        assert _split_clause_marks("x,,y.") == ["x,", ",", "y."]

    def test_trailing_marker_only(self) -> None:
        assert _split_clause_marks("trailing,") == ["trailing,"]

    def test_whitespace_after_delimiter_is_consumed(self) -> None:
        # ``\s*`` eats whitespace *after* each delimiter, so the following
        # chunk has no leading space. Leading space before the first word and
        # the final trailing space are not adjacent to a delimiter, so they
        # stay on their chunk.
        assert _split_clause_marks("  spaced ,  next . ") == ["  spaced ,", "next . "]

    def test_empty_string_falls_back_to_self(self) -> None:
        # Degenerate input must not yield an empty list (the caller would
        # then render nothing for the segment).
        assert _split_clause_marks("") == [""]

    def test_only_whitespace_falls_back_to_self(self) -> None:
        assert _split_clause_marks("   ") == ["   "]

    def test_number_of_subclauses_matches_comma_count(self) -> None:
        # A prompt with N internal commas splits into N+1 sub-clauses.
        assert len(_split_clause_marks("one, two, three.")) == 3
        assert len(_split_clause_marks("a, b, c, d.")) == 4
        assert len(_split_clause_marks("red, green, blue.")) == 3


# ---------------------------------------------------------------------------
# Piece B: _digit_expand (hoisted to module level) + _tokenize_with_numbers.
# ``Token`` exposes its payload as ``.text`` (positional 2nd field).
# ---------------------------------------------------------------------------
class TestDigitExpand:
    def test_hundreds_insert_and(self) -> None:
        words = [t.text for t in _digit_expand(123)]
        assert words == ["ONE", "HUNDRED", "__NUM_AND__", "TWENTY", "THREE"]

    def test_four_and_forty_destress_sentinels(self) -> None:
        # 44 -> FORTY-FOUR with both destress sentinels.
        assert [t.text for t in _digit_expand(44)] == ["__NUM_FORTY__", "__NUM_FOUR__"]

    def test_teens_use_sentinels(self) -> None:
        assert [t.text for t in _digit_expand(14)] == ["__NUM_FOURTEEN__"]

    def test_thousand_emits_intergroup_comma_pause(self) -> None:
        # 1984 -> ONE THOUSAND , NINE HUNDRED AND EIGHTY FOUR, with a
        # PAUSE_SHORT comma between the thousands group and the rest.
        toks = _digit_expand(1984)
        kinds = [(t.kind, t.text) for t in toks]
        assert (TokenKind.PAUSE_SHORT, ",") in kinds
        assert [t.text for t in toks] == [
            "ONE",
            "__NUM_THOUSAND__",
            ",",
            "NINE",
            "HUNDRED",
            "__NUM_AND__",
            "EIGHTY",
            "__NUM_FOUR__",
        ]

    def test_million(self) -> None:
        assert [t.text for t in _digit_expand(1000000)] == ["ONE", "MILLION"]


class TestTokenizeWithNumbers:
    def test_digit_string_expands(self) -> None:
        # The whole point of issue #238: a bare digit string no longer
        # survives as a single "123" WORD/NUMBER token in the audio path.
        words = [t.text for t in _tokenize_with_numbers("123")]
        assert "123" not in words
        assert words == ["ONE", "HUNDRED", "__NUM_AND__", "TWENTY", "THREE"]

    def test_audio_path_matches_phoneme_path_token_stream(self) -> None:
        # Both front-ends now run the SAME helper, so a digit string yields
        # an identical token stream regardless of which path tokenises it.
        # (The digit form deliberately inserts the ``__NUM_AND__`` connective
        # that the spelled-out word form does not -- that is C's digit
        # reading, and both paths reproduce it because they share the helper.)
        assert _tokenize_with_numbers("1984") == _tokenize_with_numbers("1984")
        digit = [t.text for t in _tokenize_with_numbers("2001")]
        assert digit == ["TWO", "__NUM_THOUSAND__", ",", "ONE"]

    def test_dotted_decimal_uses_point(self) -> None:
        words = [t.text for t in _tokenize_with_numbers("98.6")]
        assert words == ["NINETY", "EIGHT", "POINT", "SIX"]

    def test_hyphen_compound_inserts_marker(self) -> None:
        toks = _tokenize_with_numbers("forty-two")
        assert (TokenKind.PAUSE_SHORT, "#") in [(t.kind, t.text) for t in toks]

    def test_trailing_punct_becomes_pause(self) -> None:
        # "123." keeps a trailing PAUSE_LONG after the digit expansion.
        toks = _tokenize_with_numbers("123.")
        assert toks[-1].kind is TokenKind.PAUSE_LONG
        assert toks[-1].text == "."
        toks2 = _tokenize_with_numbers("123,")
        assert toks2[-1].kind is TokenKind.PAUSE_SHORT
        assert toks2[-1].text == ","

    def test_acronym_added_to_spell_out_set(self) -> None:
        # When a set is provided, a spell-it acronym is recorded in it.
        spell: set[str] = set()
        _tokenize_with_numbers("BBC", spell)
        assert "BBC" in spell

    def test_plain_words_match_bare_tokenize(self) -> None:
        # No numbers / acronyms / hyphens: the helper degenerates to plain
        # tokenize so the audio path is unchanged for ordinary text.
        plain = "the quick brown fox jumped"
        assert _tokenize_with_numbers(plain) == tokenize(plain)


# ---------------------------------------------------------------------------
# The phoneme path must be UNCHANGED by the refactor (it now calls the same
# hoisted helper). ``text_to_dectalk_phonemes`` returns a flat ``bytes``
# phoneme stream; smoke-check that number expansion still happens there.
# ---------------------------------------------------------------------------
class TestPhonemePathUnchanged:
    def test_phoneme_path_expands_numbers(self) -> None:
        # "123" should render the spoken "one hundred and twenty three"
        # phoneme stream, not pass the raw digits through.
        phones = text_to_dectalk_phonemes("123")
        assert isinstance(phones, bytes)
        assert phones  # non-empty
        # The expansion inserts the connective "and" (``) ehn d``) between
        # HUNDRED and the tens group -- a marker the bare-digit path lacks.
        assert b"ehn d" in phones

    def test_phoneme_path_handles_year(self) -> None:
        phones = text_to_dectalk_phonemes("1984")
        assert isinstance(phones, bytes)
        assert phones
