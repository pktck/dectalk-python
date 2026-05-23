r"""Derive compound-marker and form-class sidecars from ``Dic_us.txt``.

The bundled ARPABET lexicon (``src/dectalk/data/lexicon_us_full.txt``)
strips the DECtalk source's ``*`` MBOUND markers and the form-class
column. Two LTS divergences vs the C oracle stem from this loss:

1. Closed compounds (``breakfast``, ``pipeline``, ``database``) miss
   the C source's compound ``*`` marker between the two components,
   which downstream PH-stage stress/timing uses.

2. The ``)`` VPSTART phrase-start marker is hand-curated to a small
   verb list in :func:`dectalk.api.text_to_dectalk_phonemes`; the C
   source derives it from the form-class column via the rule in
   ``src/dapi/src/lts/ls_dict.c`` lines 759-763::

       (fc & (FC_VERB|FC_CHARACTER)) == (FC_VERB|FC_CHARACTER)
       || fc == FC_VERB

This script reads a DECtalk dictionary file and emits two sidecar
lexicons under ``src/dectalk/data/``:

- ``lexicon_<lang>_markers.txt`` — only the entries containing ``*``;
  ARPABET phonemes plus ``__PUNCT__*`` markers preserved so
  :func:`dectalk.dic.dectalk_phonemes.encode_to_dectalk` re-emits the
  compound boundary byte-identically to the C oracle.

- ``vpstart_<lang>.txt`` — one upper-cased word per line whose
  form-class mask satisfies the C rule above. Loaded by
  :func:`dectalk.dic.markers.load_vpstart_words` to replace the hand
  curated ``vpstart_words`` set in :mod:`dectalk.api.speak`.

Usage::

    uv run python scripts/build_dic_sidecars.py \
        --source /tmp/dectalk-source/src/dapi/src/dic/Dic_us.txt \
        --markers-out src/dectalk/data/lexicon_us_markers.txt \
        --vpstart-out src/dectalk/data/vpstart_us.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dectalk.dic.dectalk_phonemes_multi import decode_lang_with_markers
from dectalk.dic.form_class_bits import FC_CHARACTER, FC_VERB


def _parse_formclass_mask(bits: str) -> int:
    """Decode a 29-char ``Dic_us.txt`` form-class column into a bit mask.

    The dictionary's form-class column is a left-to-right bit string:
    position 0 (leftmost) is ``FC_ADJ`` (bit 0), position 1 is
    ``FC_ADV`` (bit 1), and so on up to position 28. This matches the
    ``FC_V_*`` (bit-index) constants exported by
    :mod:`dectalk.dic.form_class_bits`.

    Args:
        bits: 28-or-29-character string of ``0``/``1`` from column 4
            of the dictionary entry.

    Returns:
        Equivalent integer bit mask. Each ``1`` at left-position ``i``
        contributes ``(1 << i)`` to the mask. Non-``0``/``1`` characters
        are skipped (defensive against trailing whitespace).
    """
    mask = 0
    for i, ch in enumerate(bits):
        if ch == "1":
            mask |= 1 << i
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
) -> tuple[dict[str, list[str]], set[str]]:
    """Parse one DECtalk dictionary file into ``(markers_lex, vpstart_words)``.

    Walks each entry, decoding the phonemic column with
    :func:`decode_lang_with_markers` (preserves ``__PUNCT__*``) and
    deciding via :func:`_emits_vpstart` whether the form-class mask
    qualifies for the VPSTART sidecar.

    Args:
        source_path: Path to a ``Dic_*.txt`` source dictionary.
        lang: Language tag passed to :func:`decode_lang_with_markers`.

    Returns:
        Tuple of:

        - ``markers_lex`` — mapping from upper-cased word to the decoded
          phoneme list (only entries containing ``*``).
        - ``vpstart_words`` — set of upper-cased words whose form-class
          satisfies the VPSTART rule.
    """
    markers: dict[str, list[str]] = {}
    vpstart: set[str] = set()
    try:
        text = source_path.read_text(encoding="latin-1")
    except UnicodeDecodeError:
        text = source_path.read_text(encoding="utf-8", errors="replace")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        parts = line.split(",")
        min_fields = 4  # word, single-letter formclass, phonemic, bitmask
        if len(parts) < min_fields:
            continue
        word = parts[0]
        if not word:
            continue
        sanitised = "".join(c for c in word if c.isalnum())
        if not sanitised:
            continue
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
        if fc_bits and _emits_vpstart(_parse_formclass_mask(fc_bits)):
            vpstart.add(upper)
    return markers, vpstart


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

    markers, vpstart = _convert(args.source, lang=args.lang)

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
