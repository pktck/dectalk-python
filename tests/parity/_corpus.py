"""Shared bit-parity corpus used by the binary-WAV test and tooling.

The same list is consumed by:

- ``tests/parity/test_binary_wav_parity.py`` -- asserts each prompt
  renders to a byte-identical WAV vs the shipped DECtalk binary.
- ``scripts/diagnose_audio.py`` (with ``--bit-parity-corpus``) --
  materialises the corpus into ``docs/audio_samples/`` for human
  inspection and committed-into-repo audio comparison artefacts.

Edits to this tuple affect both paths.
"""

from __future__ import annotations

CORPUS: tuple[str, ...] = (
    # Original baseline corpus.
    "hello world",
    "the quick brown fox",
    "she sells sea shells",
    "one two three four five",
    "supercalifragilisticexpialidocious",
    "[:rate 250] testing one two three",
    "DECtalk version 6.2.0",
    "this is a test, with a comma, and a period.",
    # Numbers and decimal.
    "the answer is 42",
    "3 point 14",
    "one hundred and one dalmatians",
    "1234567890",
    # Punctuation variants.
    "hello! how are you?",
    "wait... what just happened?",
    "yes; no; maybe.",
    # Inline-command rate.
    "[:rate 100] slow",
    "[:rate 400] fast speech",
    # Inline-command voice presets -- exercise the 9 canonical voices.
    "[:nb] betty speaking",
    "[:nh] harry speaking",
    "[:nf] frank speaking",
    "[:nd] dennis speaking",
    "[:nk] kit the kid",
    "[:nu] ursula speaking",
    "[:nr] rita rough",
    "[:nw] wendy whispery",
    # Spell-out cases (short all-caps).
    "FBI",
    "NASA",
    "USA",
    "MIT",
    # Common English phonotactics.
    "judge thought rhythms",
    "knight light right",
    # Mixed punctuation with abbreviations.
    "Dr. Smith said hello.",
    # Long-ish utterance.
    "the rain in spain falls mainly on the plain",
    # Syllabic-L (US_EL) coverage: word-final L after consonant.
    "apple table bottle",
    "a little bottle",
    "middle of the road",
    # Syllabic-N (US_EN) coverage: word-final N after consonant.
    "button sudden reason",
    "broken eaten",
    # -ING reduction (AH0/IH0 -> ix before NG).
    "morning evening running meeting",
    # WH-question intonation: ``?`` -> ``.`` token when the sentence
    # contains a wh- word; yes/no questions keep the ``?`` marker.
    "how?",
    "what time is it?",
    # Function-word destressing of ``to`` (SBOUND + PPSTART + T + UH).
    "to bed",
    "walk to the store",
    # Function-word destressing of ``for`` (SBOUND + PPSTART + F + ER).
    "for now",
    "for ever",
    # Root-internal S after R must NOT voice to Z (``course`` / ``horse``
    # stay with final S; inflectional ``cars`` / ``sells`` voice to Z).
    "of course",
    "the horse",
    "cars and trucks",
    # First-verb stress (``are``/``had``/``is``/``was``/``were``/``will``)
    # at sentence start gets secondary stress; mid-sentence stays unstressed.
    "is it raining",
    "this is good",
    "it was good",
    # Stem-stripping plurals: lookup falls back to the singular stem
    # (``seconds`` -> ``second``), with syllabic-N / voicing applied.
    "two seconds",
    "three reasons",
    "five days",
    "two trees",
    # ``-er`` agentive / comparative suffix: stem stripping.
    "later",
    "faster",
)


__all__ = ["CORPUS"]
