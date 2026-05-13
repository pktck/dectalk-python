"""``par_search_for_word`` domain-dictionary lookup from par_pars1.c.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 3677-3804.

Binary-searches one of the rule-engine's per-letter domain
dictionaries (selected by ``dict_num``) for ``input``. On a hit
the matching entry's payload text is copied into ``output``; on a
miss the function returns 0 without writing to ``output``.

The C body indexes into three module-global tables:

* ``dict_point[]`` -- the per-dict start/end offset pairs
  (``const dict_pointers_t dict_point[27]`` in par_rule2.h).
* ``dict_index_table[]`` -- maps a search position to a byte
  offset inside the data blob (``const int dict_index_table[378]``).
* ``dict_data_table[]`` -- the raw NUL-terminated entry strings
  followed by their payloads (``const unsigned char
  dict_data_table[3786]``).

These tables are linked statically into ``libtts_us.so`` on the
Linux build, so the C code does find matches when the rule engine
calls it from inside ``par_match_rule``'s ``BIN_DOM_DICT_SEARCH``
branch. The Python port hasn't yet ported the rule-engine driver
itself or those data tables, so this function returns a "no
match" stub. Wiring the tables up is deferred along with the
parser entry point ``par_process_input`` and the matcher
``par_match_rule`` -- once both land, this stub will be replaced
with a faithful binary search against the embedded data.
"""

from __future__ import annotations


def par_search_for_word(
    input_: bytes | bytearray,
    input_length: int,
    output: bytearray,
    dict_num: int,
    dict_state_flag: int,
) -> int:
    """Look up ``input_`` in domain dictionary ``dict_num`` (stub).

    Faithful translation of the C source's failure path: every
    bisection step exits with ``value != 0`` and falls through to
    ``return(0)``. Under the current Python port the parser
    machinery that would invoke this function isn't wired in yet,
    so the stub always reports no match.

    Args:
        input_: NUL-terminated bytes to look up. Ignored by the
            stub.
        input_length: Length of ``input_`` (the C source uses this
            as the offset to the payload text once a hit is found).
            Ignored by the stub.
        output: Bytearray that would receive the entry's payload
            text on a hit. Left untouched by the stub.
        dict_num: 1-based dictionary index into ``dict_point[]``
            (the C source subtracts 1 to get the zero-based slot).
            Ignored by the stub.
        dict_state_flag: ``0`` for the full search, ``1`` to bail
            out on the first case-insensitive match. Ignored by
            the stub.

    Returns:
        ``0`` -- no match. The full bisection logic against
        ``dict_data_table`` / ``dict_index_table`` / ``dict_point``
        is deferred until the rule-engine driver lands.
    """
    del input_, input_length, output, dict_num, dict_state_flag
    return 0


__all__ = ["par_search_for_word"]
