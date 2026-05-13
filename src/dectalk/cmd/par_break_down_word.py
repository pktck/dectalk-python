"""``par_break_down_word`` German compound-noun decomposer.

Translated from ``src/dapi/src/cmd/par_pars1.c`` lines 2871-2935.

Recursively breaks a German compound word into its constituent
parts using the loaded ``noun_conjunction`` table. On the
US-English build the compound dictionary is never loaded so
``par_find_word_in_dict`` always returns 0 and this function
returns ``-1`` (no match) without exercising the recursion.

The Python port mirrors the US-build behaviour as a stub
returning ``-1``. The full recursive splitter (and its
``par_find_word_in_dict`` lookup chain) remain deferred — only
relevant to German input which the US-only build never produces.
"""

from __future__ import annotations


def par_break_down_word(input_: bytes | bytearray, output: bytearray) -> int:
    """Decompose ``input_`` into compound parts (US-build no-op).

    Faithful translation of the C source's early-fail path. On
    the US-English build ``par_find_word_in_dict(head, input, ...)``
    always returns 0 (the noun dictionary is never loaded), so the
    C function takes the immediate ``return(-1)`` exit.

    Args:
        input_: Input word bytes (unused on the US path).
        output: Output buffer (unused on the US path).

    Returns:
        ``-1`` — no compound match found.
    """
    del input_, output
    return -1


__all__ = ["par_break_down_word"]
