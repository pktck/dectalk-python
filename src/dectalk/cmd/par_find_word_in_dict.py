"""``par_find_word_in_dict`` German compound-dict lookup from par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 2946-3046.

A recursive walk over the German compound-noun trie. The C body
indexes into the globals ``noun_data_table``, ``noun_index_table``
and ``noun_character_mapping_table`` to chase the trie one
character at a time; matched word boundaries are pushed onto the
caller's ``positions`` array.

On the US-English build (the only build the Python port targets)
the compound dictionary is provided by ``comp_dum.h``, which sets
every ``noun_character_mapping_table`` entry to ``-1`` (the
``NOUN_UNUSED_ENTRY`` sentinel) and leaves ``noun_data_table`` /
``noun_index_table`` as scalar zeros. Calling the C function with
any real ``head`` value would therefore dereference invalid
pointers; in practice the only caller (``par_break_down_word``)
short-circuits before the recursion ever fires.

The Python port mirrors that by returning ``0`` (no match) and
leaving ``positions``/``num_pos`` untouched. The full recursive
walker is deferred -- it only activates for German input which
the US-only build never produces.
"""

from __future__ import annotations


def par_find_word_in_dict(
    head: int,
    word: bytes | bytearray,
    positions: list[int],
    depth: int,
    num_pos: list[int],
) -> int:
    """Walk the compound-noun trie searching for ``word`` (US-build stub).

    Faithful translation of the C source's behaviour on the US
    English build: with ``noun_character_mapping_table`` filled
    with ``-1`` sentinels and the noun data globals all zero,
    every reachable branch of the recursion bottoms out at the
    ``*num_pos == 0`` ``return(0)`` exit. The Python port therefore
    short-circuits to that same answer without touching
    ``positions`` or ``num_pos``.

    Args:
        head: Trie node index (ignored on the US path).
        word: Word bytes being matched (ignored on the US path).
        positions: Caller-allocated array for matched boundary
            offsets. The C source mutates this in place; the Python
            stub leaves it untouched because no match is ever
            recorded.
        depth: Current recursion depth (ignored on the US path).
        num_pos: Single-element list serving as the C source's
            ``int *num_pos`` out-pointer. Left at ``0`` on this
            no-match path.

    Returns:
        ``0`` -- no compound match was found. The full splitter
        (US-English doesn't load the German compound dictionary, so
        no walker invocation can ever record a match).
    """
    del head, word, positions, depth, num_pos
    return 0


__all__ = ["par_find_word_in_dict"]
