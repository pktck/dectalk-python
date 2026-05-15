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
    # ``-ed`` past-tense suffix: stem stripping + voicing/epenthesis rule
    # (T after voiceless, IX+D after T/D, D after voiced).
    "walked",
    "talked",
    "needed",
    "loved",
    "liked",
    # ``-ing`` gerund / present-participle suffix: stem stripping + IX NG.
    "walking",
    "talking",
    "jumping",
    "running",
    # ``'s`` contraction (``that's`` = ``that is``): strip the apostrophe
    # and append S (voicing handled by the encoder).
    "that's",
    "it's",
    "what's",
    "there's",
    # ``-ness`` noun-forming suffix: stem + ``N IX S``.
    "darkness",
    "sadness",
    "happiness",
    # ``-ful`` / ``-less`` adjective suffixes.
    "helpful",
    "helpless",
    "careless",
    # ``-ment`` noun-forming suffix.
    "payment",
    "shipment",
    "statement",
    # ``-tion`` / ``-sion`` (AH0+N -> IX+N after SH/ZH/CH/JH/R).
    "nation",
    "mission",
    # ``-est`` superlative suffix.
    "smallest",
    "oldest",
    "fastest",
    "biggest",
    # Y -> I morphological alternation in plurals (``cities`` -> ``city``).
    "cities",
    "babies",
    "cherries",
    # Y -> I in -ed past tense (``studied`` -> ``study``).
    "studied",
    "tried",
    # Mono-syllabic AH0+S (``us``) keeps AX; multi-syllabic uses IX.
    "us",
    # ``-n't`` contractions: N becomes syllabic-EN before the trailing T.
    "didn't",
    "couldn't",
    # AH0 + F + L word-final (the ``-iful`` connector): AH0 -> IX.
    "beautiful",
    # -OUS suffix: AH0+S -> AX after M/V/F/etc. obstruents; -> IX after
    # L/N/R sonorants.
    "famous",
    "nervous",
    "jealous",
    # ``-it`` suffix: AH0+T word-final -> IX+T when the stressed vowel is
    # a short monophthong (visit / limit / edit / audit). Diphthong-stressed
    # private / climate keep AX+T.
    "visit",
    "limit",
    "private",
    # Post-stress AH0+N+T after R -> IX (``parent`` -> ``p ' eyr ixn t``).
    "parent",
    # N -> NG velar assimilation before K / G (``pink`` -> ``p ' ihnxk``).
    "pink",
    "tank",
    # -ness with LTS-fallback stem (firm / odd not in lexicon).
    "firmness",
    "oddness",
    # Longer phrasal corpus -- exercises mid-sentence first-verb destressing,
    # function-word reductions, and inflectional morphology together.
    "a good day",
    "three nice gifts",
    "the cat is happy",
    "the dogs ran",
    "you are welcome",
    "an apple tree",
    # Hyphenated compounds: emit ``#`` syllable-break instead of word break.
    "forty",
    "forty-two",
    "twenty-one",
    "self-taught",
    # Teen words: ``*`` MBOUND marker before T+IY+N. Literal forms use
    # secondary stress on IY; digit-expanded forms use primary stress.
    "fourteen",
    "fifteen",
    "sixteen",
    "eighteen",
    "15",
    "18",
    # Sibilant-final plurals: IX+Z epenthesis (classes / horses / roses).
    "classes",
    "horses",
    "kisses",
    "foxes",
    # AH0+Z after sibilant reads as IX+Z (sibilant 3rd-person sg -es).
    "fixes",
    "fishes",
    "watches",
    # M-in-cluster + AH0+S -> IX (``christmas`` -- SM cluster, IX).
    # M-after-vowel + AH0+S -> AX (``famous`` -- EY+M, AX).
    "christmas",
    # ``-ly`` adverb suffix: consonant-final stem + L + IY0.
    "friendly",
    "softly",
    "badly",
    "quickly",
    # ``-it`` short-vowel rule now covers IY / UW tense monophthongs too.
    "spirit",
    # Number / teen edge cases.
    "eleven",
    "thirteen",
    "13",
    # -tion / -sion suffix: stem-strip + SH + AH0 + N.
    "pension",
    "mansion",
    "tension",
    # Syllabic-N before word-final D (``thousand`` -> ``th' awz end``).
    "thousand",
    "second",
    # More multi-word phrasal coverage.
    "a good idea",
    "three small dogs",
    "open the windows",
    "two cats and three dogs",
)


__all__ = ["CORPUS"]
