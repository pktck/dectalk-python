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
        Token(TokenKind.PAUSE_LONG),
        Token(TokenKind.WORD, "WORLD"),
    ]


def test_clause_punctuation_emits_short_pause() -> None:
    tokens = tokenize("hello, world")
    assert tokens == [
        Token(TokenKind.WORD, "HELLO"),
        Token(TokenKind.PAUSE_SHORT),
        Token(TokenKind.WORD, "WORLD"),
    ]


def test_question_and_exclamation_are_long_pauses() -> None:
    tokens = tokenize("really? yes!")
    assert tokens == [
        Token(TokenKind.WORD, "REALLY"),
        Token(TokenKind.PAUSE_LONG),
        Token(TokenKind.WORD, "YES"),
        Token(TokenKind.PAUSE_LONG),
    ]


def test_leading_punctuation_is_stripped() -> None:
    tokens = tokenize('"hello"')
    assert tokens == [Token(TokenKind.WORD, "HELLO")]


def test_digits_are_spelled_out() -> None:
    tokens = tokenize("call 911")
    assert tokens == [
        Token(TokenKind.WORD, "CALL"),
        Token(TokenKind.WORD, "NINE"),
        Token(TokenKind.WORD, "ONE"),
        Token(TokenKind.WORD, "ONE"),
    ]


def test_empty_input_returns_empty_list() -> None:
    assert tokenize("") == []
    assert tokenize("   ") == []


def test_pause_strength_dominated_by_strongest() -> None:
    """A token with both clause and sentence punctuation should produce one long pause."""
    tokens = tokenize("wait,.")
    # Trailing chars: "," then "." - sentence punct wins.
    assert tokens == [
        Token(TokenKind.WORD, "WAIT"),
        Token(TokenKind.PAUSE_LONG),
    ]
