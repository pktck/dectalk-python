"""Inline-command option-string tables from c_us_cde.h.

Translated from ``src/dapi/src/cmd/c_us_cde.h``. Each of these
NULL-terminated string arrays enumerates the valid second-token
keywords for a specific inline command (``[:cmd <keyword> ...]``).
The dispatcher in ``cm_cmd.c`` looks the user's keyword up in the
matching list and converts it to an index that drives the handler's
``switch`` block.

All arrays drop the trailing ``0`` sentinel — Python uses tuple
length instead.
"""

from __future__ import annotations

from typing import Final

# [:phoneme <mode>] — phoneme-direct toggle modes.

phoneme_modes: Final[tuple[str, ...]] = (
    "asky",
    "arpabet",
    "speak",
    "silent",
    "off",
    "on",
)

# [:log <option>] — debug-log channels.

log_options: Final[tuple[str, ...]] = (
    "text",
    "phonemes",
    "types",
    "forms",
    "syllables",
    "outphon",
    "dbglog",
    "on",
    "off",
    "set",
)

# [:say <unit>] — say-by-{clause/word/letter/syllable/line/...}.

say_options: Final[tuple[str, ...]] = (
    "clause",
    "word",
    "letter",
    "filtered_letter",
    "line",
    "syllable",
)

# [:error <mode>] — how the engine reacts to parse errors.

error_options: Final[tuple[str, ...]] = (
    "ignore",
    "text",
    "escape",
    "speak",
    "tone",
)

# [:flush <scope>] — pipeline-flush scope.

flush_options: Final[tuple[str, ...]] = (
    "all",
    "until",
    "mask",
    "after",
    "speech",
)

# [:punct <level>] — how to verbalise punctuation.

punct_options: Final[tuple[str, ...]] = (
    "none",
    "some",
    "all",
    "pass",
)

# [:skip <kind>] — what input categories to silently skip.

skip_options: Final[tuple[str, ...]] = (
    "none",
    "email",
    "punct",
    "rule",
    "all",
    "cpg",
)

# [:volume <op>] — non-MSDOS build. The DOS build had a smaller list.

volume_options: Final[tuple[str, ...]] = (
    "set",
    "up",
    "down",
    "lset",
    "lup",
    "ldown",
    "rset",
    "rup",
    "rdown",
    "sset",
    "att",
)

# [:lang <code>] — language switch keywords.

lang_options: Final[tuple[str, ...]] = (
    "english",
    "british",
    "french",
    "german",
    "spanish",
    "latin_amercian",  # typo preserved verbatim from C source
    "us",
    "uk",
    "fr",
    "gr",
    "sp",
    "la",
)

# [:version <op>] — speak or query the version string.

version_options: Final[tuple[str, ...]] = (
    "speak",
    "status",
)

# [:mode <mode>] — input-mode toggles.

mode_options: Final[tuple[str, ...]] = (
    "math",
    "europe",
    "spell",
    "name",
    "homograph",
    "citation",
    "latin",
    "table",
    "email",
    "on",
    "off",
    "set",
)

# [:pronounce <variant>] — disambiguates homographs.

pronounce_options: Final[tuple[str, ...]] = (
    "alternate",
    "name",
    "primary",
    "noun",
    "verb",
    "adjective",
    "function",
    "interjection",
)

# [:name <voice>] — voice-preset selection. Order encodes the
# 0-based speaker ID the C library uses internally.

voice_names: Final[tuple[str, ...]] = (
    "paul",
    "betty",
    "harry",
    "frank",
    "dennis",
    "kit",
    "ursula",
    "rita",
    "wendy",
    "val",
)

# [:index <kind>] — index-mark types. The 7 extra SAPI bookmark
# keywords (bookmark/wordpos/start/stop/sentence/volume/noise) are
# Win32-only; the Linux build's libtts_us.so stops at "pause".

index_options: Final[tuple[str, ...]] = (
    "mark",
    "reply",
    "query",
    "pause",
)

# [:gender <g>] — grammatical-gender hint for inflected languages.

gender_options: Final[tuple[str, ...]] = (
    "masculine",
    "neuter",
    "feminine",
)

# [:define <field> <value>] — voice-parameter assignment.

define_options: Final[tuple[str, ...]] = (
    "save",
    "sx", "sm", "as", "ap", "pr", "br", "ri", "nf", "la",
    "hs", "f4", "b4", "f5", "b5", "f7", "f8",
    "gf", "gh", "gv", "gn", "g1", "g2", "g3", "g4", "g5",
    "ft", "bf", "lx", "qu", "hr", "sr",
    "ago", "agvo", "aguo", "chink", "oq",
)  # fmt: skip


__all__ = [
    "define_options",
    "error_options",
    "flush_options",
    "gender_options",
    "index_options",
    "lang_options",
    "log_options",
    "mode_options",
    "phoneme_modes",
    "pronounce_options",
    "punct_options",
    "say_options",
    "skip_options",
    "version_options",
    "voice_names",
    "volume_options",
]
