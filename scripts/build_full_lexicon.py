r"""Convert a DECtalk dictionary file into our CMUDict-style lexicon.

Reads the per-language source dictionary (default for US English:
``Dic_us_2002.txt`` — the 2002 revision shipped as the live US
runtime dictionary), decodes each entry's
``WORD,FORMCLASS,DECTALK_PHONEMIC,FC_BITS,FREQ`` row through
:func:`dectalk.dic.dectalk_phonemes_multi.decode_lang`, and writes
a CMUDict-style output that the ``--lexicon`` flag (or
:func:`dectalk.dic.set_extra_lexicon`) can load.

The output preserves the *form-class* column (``N`` for normal,
``P`` for primary, ``S`` for secondary stress) as a ``|P``/``|S``
suffix on the word key. ``N`` is the default and is emitted
without a suffix to keep the file format backward compatible with
the previous build.

Usage::

    uv run python scripts/build_full_lexicon.py \
        --source /tmp/dectalk-source/src/dapi/src/dic/Dic_us_2002.txt \
        --out src/dectalk/data/lexicon_us_full.txt

.. warning:: **Do not regenerate blindly** — the checked-in
   ``lexicon_us_full.txt`` carries ~130 hand-applied corrections that
   align entries with what the C *runtime* actually speaks rather
   than the raw dictionary text: the 34 sole-secondary stress
   corrections from issue #270 (``quick`` / ``brown`` stored with
   `` ` `` but spoken with primary stress; ``has`` / ``over`` stored
   with `` ` `` but spoken unstressed) plus the ~96 stress/vowel
   alignments from the issue #281 full-corpus sweep (invariant
   runtime stress on you/i/she/that/when/which/...; vowel identity
   on than/at/can/on/had/took/...; added rows). This converter
   reproduces the raw text, so a regeneration reverts those fixes,
   reopens the fox-class timing drift, and drops the corpus phoneme
   gate from ~99.96% back to ~46%. Issue #280 tracks teaching the
   conversion (or a post-pass) the runtime stress rules; until then,
   diff any regenerated file against the checked-in one, re-apply the
   corrections (``git log -p -- src/dectalk/data/lexicon_us_full.txt``
   has the authoritative list), and re-verify with
   ``scripts/corpus_phoneme_sweep.py`` before committing.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dectalk.dic.dectalk_phonemes_multi import decode_lang


def _convert(source_path: Path, lang: str) -> list[tuple[str, str, list[str], str]]:
    """Parse one DECtalk dictionary file.

    Returns a list of ``(word_upper, form_class, phonemes, source_word)``
    tuples in source order. ``source_word`` preserves the original casing
    so :func:`_resolve_case_collisions` can pick the right reading when the
    same word appears under several cases (see that function). Multiple
    entries for the same word with different form-class letters (e.g. the
    ``record,P,...`` / ``record,S,...`` noun/verb minimal pair) are kept
    as separate rows so the lookup layer can pick by context.
    """
    out: list[tuple[str, str, list[str], str]] = []
    # The non-English dictionaries (fr, de, sp, la) use Latin-1 encoding
    # for accented characters; UTF-8 decoding with errors="replace" loses
    # them. Try Latin-1 first, fall back to UTF-8.
    try:
        text = source_path.read_text(encoding="latin-1")
    except UnicodeDecodeError:
        text = source_path.read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        parts = line.split(",")
        min_fields = 3  # word, formclass, phonemic, ...
        if len(parts) < min_fields:
            continue
        word = parts[0]
        if not word:
            continue
        # Skip pure-punctuation entries like '!', '?', etc.
        sanitised = "".join(c for c in word if c.isalnum())
        if not sanitised:
            continue
        # Form-class letter: N (normal), P (primary stress), S (secondary).
        # Older Dic_us.txt files only carry "N"; Dic_us_2002.txt adds P/S
        # for noun/verb minimal pairs.
        fc_letter = parts[1].strip().upper() if len(parts) > 1 else "N"
        if fc_letter not in {"N", "P", "S"}:
            fc_letter = "N"
        decoded = decode_lang(parts[2], lang=lang)
        if not decoded:
            continue
        out.append((word.upper(), fc_letter, decoded, word))
    return out


def _resolve_case_collisions(
    rows: list[tuple[str, str, list[str], str]],
) -> list[tuple[str, str, list[str]]]:
    r"""Collapse case-distinct duplicate keys to the runtime reading.

    ``Dic_us.txt`` is *case-sensitive*: it carries separate entries for
    e.g. ``new,N,n'uw`` (the common adjective, primary stress) and
    ``New,N,n\`uw`` (the proper-noun/compound form, secondary stress).
    The C runtime looks the input token up case-sensitively, so lowercased
    corpus text (``the new book``) resolves to the lowercase reading —
    verified against the oracle: ``new`` -> ``n ' uww``, ``New`` ->
    ``n \` uww``. Our lexicon is keyed by upper-case word only, so the two
    collide on ``NEW``. Keeping the wrong one flips 300+ common words to
    secondary stress (issue #332 stress-collision regression).

    Resolution, per ``(WORD, form-class)`` group: prefer the entry whose
    source word is all-lower-case (the citation/common-word reading);
    tie-break toward a primary-stress vowel, then source order. Groups
    without a lower-case member (pure proper nouns) keep their first
    entry. Different form-class letters never merge, so the ``record|P`` /
    ``record|S`` homograph pairs are untouched.
    """
    best: dict[tuple[str, str], tuple[str, str, list[str]]] = {}
    rank: dict[tuple[str, str], tuple[int, int]] = {}
    for word_upper, fc_letter, decoded, source_word in rows:
        key = (word_upper, fc_letter)
        is_lower = 1 if source_word.islower() else 0
        has_primary = 1 if any(tok.endswith("1") for tok in decoded) else 0
        score = (is_lower, has_primary)
        if key not in best or score > rank[key]:
            best[key] = (word_upper, fc_letter, decoded)
            rank[key] = score
    return list(best.values())


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: convert one DECtalk dictionary file to ARPABET."""
    parser = argparse.ArgumentParser(
        description="Convert a DECtalk dictionary file to ARPABET lexicon format.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the DECtalk Dic_*.txt source file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Path to write the ARPABET lexicon to.",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="us",
        choices=("us", "uk", "fr", "de", "sp", "la"),
        help="Source dictionary language. Selects the per-language phoneme map.",
    )
    parser.add_argument(
        "--corrections",
        type=Path,
        default=None,
        help=(
            "Optional CMUDict-style overlay applied AFTER decoding: each "
            "``WORD[|FC] PHONEME ...`` line overrides (or adds) that key. "
            "Carries the runtime-alignment fixes that are not derivable from "
            "the source dictionary text (LTS-override entries the source omits, "
            "binary-wins pronunciations). Replaces the previous manual "
            "diff-and-re-apply step; see the module docstring."
        ),
    )
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"error: source not found: {args.source}", file=sys.stderr)
        return 2

    resolved = _resolve_case_collisions(_convert(args.source, lang=args.lang))
    # Keyed by the on-disk display key so a corrections overlay can override.
    entries: dict[str, list[str]] = {}
    for word, fc_letter, phonemes in resolved:
        entries[word if fc_letter == "N" else f"{word}|{fc_letter}"] = phonemes

    n_override = n_add = 0
    if args.corrections is not None:
        if not args.corrections.exists():
            print(f"error: corrections not found: {args.corrections}", file=sys.stderr)
            return 2
        for raw in args.corrections.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:  # noqa: PLR2004 — key + >=1 phoneme
                continue
            key = parts[0].upper()
            if key in entries:
                n_override += 1
            else:
                n_add += 1
            entries[key] = parts[1:]

    # Sort by word, then by form-class (N before P before S) so the file
    # is deterministic and reproducible.
    fc_order = {"N": 0, "P": 1, "S": 2}

    def _sort_key(item: tuple[str, list[str]]) -> tuple[str, int]:
        key = item[0]
        word, _, fc = key.partition("|")
        return (word, fc_order.get(fc, 0))

    with args.out.open("w", encoding="utf-8") as fh:
        fh.write("# Generated by scripts/build_full_lexicon.py\n")
        fh.write(f"# Source: {args.source}\n")
        if args.corrections is not None:
            fh.write(f"# Corrections overlay: {args.corrections}\n")
        fh.write(
            "# Subject to the licence of the source dictionary; keep private unless\n"
            "# you have explicit redistribution permission from the rights holder.\n"
        )
        fh.write(
            "#\n"
            "# Format: WORD[|FC] PHONEME PHONEME ...\n"
            "# FC is the form-class letter: N (default, omitted), P (primary stress,\n"
            "# typically noun in a noun/verb minimal pair), S (secondary stress,\n"
            "# typically verb). Multiple entries for the same WORD with different FC\n"
            "# letters are kept separate so the lookup layer can disambiguate by\n"
            "# context. See dectalk.dic.lexicon for the parser.\n\n"
        )
        for key, phonemes in sorted(entries.items(), key=_sort_key):
            fh.write(f"{key} {' '.join(phonemes)}\n")
    msg = f"wrote {len(entries)} entries to {args.out}"
    if args.corrections is not None:
        msg += f" ({n_override} overridden, {n_add} added from {args.corrections.name})"
    print(msg, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
