"""Tests for the text tokenizer (`dectalk.kernel.text`)."""

from __future__ import annotations

from dectalk.kernel.text import Token, TokenKind, tokenize


def test_simple_word_split() -> None:
    tokens = tokenize("hello world")
    assert tokens == [
        Token(TokenKind.WORD, "HELLO"),
        Token(TokenKind.WORD, "WORLD"),
    ]


def test_uppercases_words() -> None:
    tokens = tokenize("Hello World")
    assert tokens[0].text == "HELLO"
    assert tokens[1].text == "WORLD"


def test_sentence_punctuation_emits_long_pause() -> None:
    tokens = tokenize("hello. world")
    assert tokens == [
        Token(TokenKind.WORD, "HELLO"),
        Token(TokenKind.PAUSE_LONG, "."),
        Token(TokenKind.WORD, "WORLD"),
    ]


def test_clause_punctuation_emits_short_pause() -> None:
    tokens = tokenize("hello, world")
    assert tokens == [
        Token(TokenKind.WORD, "HELLO"),
        Token(TokenKind.PAUSE_SHORT, ","),
        Token(TokenKind.WORD, "WORLD"),
    ]


def test_question_and_exclamation_are_long_pauses() -> None:
    tokens = tokenize("really? yes!")
    assert tokens == [
        Token(TokenKind.WORD, "REALLY"),
        Token(TokenKind.PAUSE_LONG, "?"),
        Token(TokenKind.WORD, "YES"),
        Token(TokenKind.PAUSE_LONG, "!"),
    ]


def test_leading_punctuation_is_stripped() -> None:
    tokens = tokenize('"hello"')
    assert tokens == [Token(TokenKind.WORD, "HELLO")]


def test_numbers_are_spoken_as_words() -> None:
    tokens = tokenize("year 2024")
    text = [t.text for t in tokens if t.kind is TokenKind.WORD]
    # 2024 -> "TWO THOUSAND TWENTY FOUR" via the number_to_words helper.
    assert text == ["YEAR", "TWO", "THOUSAND", "TWENTY", "FOUR"]


def test_small_number_in_text() -> None:
    tokens = tokenize("17")
    assert [t.text for t in tokens] == ["SEVENTEEN"]


def test_empty_input_returns_empty_list() -> None:
    assert tokenize("") == []
    assert tokenize("   ") == []


def test_pause_strength_dominated_by_strongest() -> None:
    """A token with both clause and sentence punctuation should produce one long pause."""
    tokens = tokenize("wait,.")
    # Trailing chars: "," then "." - sentence punct wins.
    assert tokens == [
        Token(TokenKind.WORD, "WAIT"),
        Token(TokenKind.PAUSE_LONG, "."),
    ]


def test_hyphen_splits_compound() -> None:
    tokens = tokenize("self-driving car")
    assert [t.text for t in tokens] == ["SELF", "DRIVING", "CAR"]


def test_currency_prefix_emits_dollars() -> None:
    tokens = tokenize("$5")
    assert [t.text for t in tokens] == ["FIVE", "DOLLARS"]


def test_currency_with_thousands_separator() -> None:
    tokens = tokenize("$1,000")
    assert [t.text for t in tokens] == ["ONE", "THOUSAND", "DOLLARS"]


def test_hyphenated_number() -> None:
    """Hyphenated numbers like 'twenty-four' should not be word-classed."""
    tokens = tokenize("twenty-four")
    assert [t.text for t in tokens] == ["TWENTY", "FOUR"]
