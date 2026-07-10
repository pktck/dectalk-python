r"""Derive compound-marker and form-class sidecars from ``Dic_us.txt``.

The bundled ARPABET lexicon (``src/dectalk/data/lexicon_us_full.txt``)
strips the DECtalk source's ``*`` MBOUND markers and the form-class
column. Three LTS divergences vs the C oracle stem from this loss:

1. Closed compounds (``breakfast``, ``pipeline``, ``database``) miss
   the C source's compound ``*`` marker between the two components,
   which downstream PH-stage stress/timing uses.

2. The ``)`` VPSTART phrase-start marker is hand-curated to a small
   verb list in :func:`dectalk.api.text_to_dectalk_phonemes`; the C
   source derives it from the form-class column via the rule in
   ``src/dapi/src/lts/ls_dict.c`` lines 759-763::

       (fc & (FC_VERB|FC_CHARACTER)) == (FC_VERB|FC_CHARACTER)
       || fc == FC_VERB

3. Homograph disambiguation (``ls_homo_homo``) needs the *full*
   form-class mask of every word — both the homograph's own ``P``/``S``
   entries and the neighbouring context words (issue #295).

This script reads a DECtalk dictionary file and emits three sidecar
tables under ``src/dectalk/data/``:

- ``lexicon_<lang>_markers.txt`` — only the entries containing ``*``;
  ARPABET phonemes plus ``__PUNCT__*`` markers preserved so
  :func:`dectalk.dic.dectalk_phonemes.encode_to_dectalk` re-emits the
  compound boundary byte-identically to the C oracle.

- ``vpstart_<lang>.txt`` — one upper-cased word per line whose
  form-class mask satisfies the C rule above. Loaded by
  :func:`dectalk.dic.markers.load_vpstart_words` to replace the hand
  curated ``vpstart_words`` set in :mod:`dectalk.api.speak`. The rule
  is evaluated on the *built* mask (homograph flags applied — see
  below), and paired ``P``/``S`` homographs are excluded: their ``)``
  emission depends on which entry the disambiguator selects, so
  :func:`dectalk.api.speak.text_to_dectalk_phonemes` decides it
  dynamically.

- ``formclass_<lang>.txt`` — ``WORD[|P|S] <hex mask>`` rows carrying
  the built form-class mask of every entry. "Built" means the mask
  the runtime dictionary compiler embeds in ``dtalk_us.dic``: the
  file's 29-bit column plus the homograph-field flags added by
  ``src/dapi/src/dic/dic_comm.c`` (``P`` rows gain
  ``FC_CHARACTER|FC_HOMOGRAPH``, ``S`` rows gain ``FC_HOMOGRAPH``).
  Verified byte-for-byte against the masks embedded in the shipped
  ``dtalk_us.dic`` (all 15,466 entries).

Usage::

    uv run python scripts/build_dic_sidecars.py \
        --source /tmp/dectalk-source/src/dapi/src/dic/Dic_us.txt \
        --markers-out src/dectalk/data/lexicon_us_markers.txt \
        --vpstart-out src/dectalk/data/vpstart_us.txt \
        --formclass-out src/dectalk/data/formclass_us.txt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dectalk.dic.dectalk_phonemes_multi import decode_lang_with_markers
from dectalk.dic.form_class_bits import (
    FC_CHARACTER,
    FC_HOMOGRAPH,
    FC_M_CONTRACTION,
    FC_VERB,
)

# The dictionary compiler reads the 29-char column positionally
# (dic_comm.c lines 525-610). Positions 0-23 and 25-26 map to bits
# 0-23 / 25-26; position 24 is FC_M_CONTRACTION (bit 30), *not* bit
# 24. Positions 27-28 are the unused filler and the name-flag column,
# neither of which lands in the entry's fc word.
_COLUMN_BITS: tuple[int, ...] = tuple(
    FC_M_CONTRACTION if i == 24 else (1 << i) for i in range(27)
)

# Homograph-field flags dic_comm.c ORs into the entry mask ("P" also
# marks the primary entry with FC_CHARACTER; both carry FC_HOMOGRAPH).
_HOMOGRAPH_FIELD_FLAGS: dict[str, int] = {
    "P": FC_CHARACTER | FC_HOMOGRAPH,
    "S": FC_HOMOGRAPH,
    "N": 0,
}

def _parse_formclass_mask(bits: str) -> int:
    """Decode a 29-char ``Dic_us.txt`` form-class column into a bit mask.

    The dictionary's form-class column is a left-to-right bit string
    read positionally by the dictionary compiler (``dic_comm.c``):
    position 0 (leftmost) is ``FC_ADJ`` (bit 0), position 1 is
    ``FC_ADV`` (bit 1), and so on — except position 24, which the
    compiler maps to ``FC_M_CONTRACTION`` (bit 30). Positions 27-28
    (filler + name flag) don't contribute to the mask.

    Args:
        bits: 28-or-29-character string of ``0``/``1`` from column 4
            of the dictionary entry.

    Returns:
        Equivalent integer bit mask. Non-``0``/``1`` characters are
        skipped (defensive against trailing whitespace).
    """
    mask = 0
    for i, ch in enumerate(bits[: len(_COLUMN_BITS)]):
        if ch == "1":
            mask |= _COLUMN_BITS[i]
    return mask


def _emits_vpstart(fc_mask: int) -> bool:
    """True iff a dict entry with form-class ``fc_mask`` emits ``)`` (VPSTART).

    Mirrors ``src/dapi/src/lts/ls_dict.c`` lines 759-763::

        VPHRASE = FC_VERB | FC_CHARACTER
        if (((fc & VPHRASE) == VPHRASE) || fc == FC_VERB) ...

    This is the C source's authoritative rule. ``no_pars`` is normally
    false during text-to-speech, so we ignore that guard here.
    """
    vphrase = FC_VERB | FC_CHARACTER
    return (fc_mask & vphrase) == vphrase or fc_mask == FC_VERB


def _convert(
    source_path: Path, lang: str
) -> tuple[dict[str, list[str]], set[str], dict[str, int]]:
    """Parse one DECtalk dictionary file into the three sidecar tables.

    Walks each entry, decoding the phonemic column with
    :func:`decode_lang_with_markers` (preserves ``__PUNCT__*``),
    building the per-entry form-class mask (with the ``dic_comm.c``
    homograph-field flags applied), and deciding via
    :func:`_emits_vpstart` whether the mask qualifies for the VPSTART
    sidecar. Paired ``P``/``S`` homographs never enter the VPSTART
    set — their ``)`` emission is context-dependent and resolved at
    runtime from the form-class sidecar.

    Args:
        source_path: Path to a ``Dic_*.txt`` source dictionary.
        lang: Language tag passed to :func:`decode_lang_with_markers`.

    Returns:
        Tuple of:

        - ``markers_lex`` — mapping from upper-cased word to the decoded
          phoneme list (only entries containing ``*``).
        - ``vpstart_words`` — set of upper-cased words whose built
          form-class mask satisfies the VPSTART rule.
        - ``formclass`` — mapping from ``WORD`` / ``WORD|P`` /
          ``WORD|S`` to the built form-class mask.
    """
    markers: dict[str, list[str]] = {}
    vpstart: set[str] = set()
    formclass: dict[str, int] = {}
    vpstart_candidates: dict[str, int] = {}
    try:
        text = source_path.read_text(encoding="latin-1")
    except UnicodeDecodeError:
        text = source_path.read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        # Commas can appear escaped inside the phonemic field
        # (``furthermore,N,f'RDRmor\,,...``); split on unescaped
        # commas only, mirroring the dictionary compiler's
        # backslash handling.
        parts = re.split(r"(?<!\\),", line)
        min_fields = 4  # word, single-letter formclass, phonemic, bitmask
        if len(parts) < min_fields:
            continue
        word = parts[0]
        if not word:
            continue
        sanitised = "".join(c for c in word if c.isalnum())
        if not sanitised:
            continue
        letter = parts[1].strip().upper()
        phonemic = parts[2]
        fc_bits = parts[3]
        decoded = decode_lang_with_markers(phonemic, lang=lang)
        if not decoded:
            continue
        upper = word.upper()
        if "*" in phonemic:
            # Per-word: keep the LAST occurrence we encounter, matching
            # the bundled lexicon's "later overrides earlier" semantics.
            markers[upper] = decoded
        if not fc_bits:
            continue
        fc_mask = _parse_formclass_mask(fc_bits) | _HOMOGRAPH_FIELD_FLAGS.get(letter, 0)
        if letter in ("P", "S"):
            # First P row / first S row wins (the C find lands on the
            # adjacent pair; later duplicates are unreachable).
            formclass.setdefault(f"{upper}|{letter}", fc_mask)
        else:
            formclass.setdefault(upper, fc_mask)
        if _emits_vpstart(fc_mask):
            vpstart_candidates.setdefault(upper, fc_mask)
    # Unpaired P/S rows (IMPACT, KENNT, REPEAT in Dic_us.txt) behave
    # as ordinary entries at runtime: ls_homo_homo's neighbour-text
    # compare fails and the entry is returned as-is, flags included.
    # Surface them under the bare key so context tagging finds them.
    for key in [k for k in formclass if "|" in k]:
        word, letter = key.split("|", 1)
        partner = f"{word}|{'S' if letter == 'P' else 'P'}"
        if partner not in formclass:
            formclass.setdefault(word, formclass.pop(key))
    # Paired homographs resolve their VPSTART dynamically; only words
    # without a P+S pair keep a static entry.
    paired = {
        key.split("|", 1)[0]
        for key in formclass
        if key.endswith("|P") and f"{key.split('|', 1)[0]}|S" in formclass
    }
    vpstart = {w for w in vpstart_candidates if w not in paired}
    return markers, vpstart, formclass


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: derive the sidecar tables from a dictionary file."""
    parser = argparse.ArgumentParser(
        description="Derive compound-marker and VPSTART sidecars from a Dic_*.txt file.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to the DECtalk Dic_*.txt source file.",
    )
    parser.add_argument(
        "--markers-out",
        type=Path,
        required=True,
        help="Path to write the compound-marker lexicon sidecar.",
    )
    parser.add_argument(
        "--vpstart-out",
        type=Path,
        required=True,
        help="Path to write the VPSTART verb-list sidecar.",
    )
    parser.add_argument(
        "--formclass-out",
        type=Path,
        default=None,
        help="Path to write the form-class mask sidecar (optional).",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default="us",
        choices=("us", "uk", "fr", "de", "sp", "la"),
        help="Source dictionary language. Selects the per-language phoneme map.",
    )
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"error: source not found: {args.source}", file=sys.stderr)
        return 2

    markers, vpstart, formclass = _convert(args.source, lang=args.lang)

    with args.markers_out.open("w", encoding="utf-8") as fh:
        fh.write("# Generated by scripts/build_dic_sidecars.py\n")
        fh.write(f"# Source: {args.source}\n")
        fh.write("# Compound-boundary marker lexicon: each row carries the\n")
        fh.write("# ``__PUNCT__*`` sentinel at every position where the C\n")
        fh.write("# dictionary places its ``*`` (MBOUND) marker. Loaded by\n")
        fh.write("# :func:`dectalk.dic.markers.load_marker_lexicon`.\n\n")
        for word in sorted(markers):
            fh.write(f"{word} {' '.join(markers[word])}\n")
    print(f"wrote {len(markers)} marker entries to {args.markers_out}", file=sys.stderr)

    with args.vpstart_out.open("w", encoding="utf-8") as fh:
        fh.write("# Generated by scripts/build_dic_sidecars.py\n")
        fh.write(f"# Source: {args.source}\n")
        fh.write("# Words whose form-class mask satisfies the C VPSTART rule\n")
        fh.write("# from ``src/dapi/src/lts/ls_dict.c`` lines 759-763:\n")
        fh.write("#     (fc & (FC_VERB|FC_CHARACTER)) == (FC_VERB|FC_CHARACTER)\n")
        fh.write("#     || fc == FC_VERB\n")
        fh.write("# Loaded by :func:`dectalk.dic.markers.load_vpstart_words`.\n\n")
        for word in sorted(vpstart):
            fh.write(f"{word}\n")
    print(f"wrote {len(vpstart)} VPSTART entries to {args.vpstart_out}", file=sys.stderr)

    if args.formclass_out is not None:
        with args.formclass_out.open("w", encoding="utf-8") as fh:
            fh.write("# Generated by scripts/build_dic_sidecars.py\n")
            fh.write(f"# Source: {args.source}\n")
            fh.write("# Built form-class mask per dictionary entry: the 29-bit\n")
            fh.write("# Dic_*.txt column plus the homograph-field flags added by\n")
            fh.write("# ``src/dapi/src/dic/dic_comm.c`` (P rows gain\n")
            fh.write("# FC_CHARACTER|FC_HOMOGRAPH, S rows gain FC_HOMOGRAPH),\n")
            fh.write("# matching the masks embedded in the runtime dtalk dictionary.\n")
            fh.write("# Loaded by :func:`dectalk.dic.markers.load_formclass_lexicon`.\n\n")
            for key in sorted(formclass):
                fh.write(f"{key} 0x{formclass[key]:08X}\n")
        print(
            f"wrote {len(formclass)} form-class entries to {args.formclass_out}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
