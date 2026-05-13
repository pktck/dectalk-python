"""Parser-state structs from par_def.h.

Translated from ``src/dapi/src/cmd/par_def.h``. The CMD rule engine
threads three small bookkeeping structs through its recursive match
loop:

- :class:`DictPointers` — start/end/count for one dictionary slice.
- :class:`ReturnValue` — recursion-state object the matchers carry
  through each section of a rule.
- :class:`RangeValue` — start/end/min/range_set for ``<DIGIT>``
  range matches.
- :class:`MatchArrays` — temporary storage for shuffle/match
  operations (10 arrays of 30 bytes each).
- :class:`IndexData` — 3-entry index-pipeline data buffer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

PAR_MAX_ARRAYS: Final[int] = 10
"""Number of temporary match arrays in :class:`MatchArrays`."""

PAR_MAX_MATCH_ARRAY: Final[int] = 30
"""Capacity of each match array in :class:`MatchArrays`."""


@dataclass(slots=True)
class DictPointers:
    """One slice of dict_data_table — start/end/count for binary search.

    Faithful translation of:

    .. code-block:: c

        struct dict_pointers_s {
            S16 start;
            S16 end;
            S16 num_entries;
        };

    Attributes:
        start: First index in dict_index_table.
        end: One past the last index.
        num_entries: ``end - start``.
    """

    start: int = 0
    end: int = 0
    num_entries: int = 0


@dataclass(slots=True)
class ReturnValue:
    """Recursion-state object passed between rule-matching functions.

    Faithful translation of:

    .. code-block:: c

        struct return_value_s {
            S16 input_pos;     // position to start matching at
            S16 input_offset;  // chars matched in the input
            S16 output_pos;    // start position for output writes
            S16 output_offset; // chars written to output
            S16 rule;          // offset into the current rule
            S16 value;         // function return (status)
            S16 optional;      // optional-failure flag
            S16 state;         // current state for lookahead
            U16 parser_flag;   // status_state -> kernel-variable flag
            struct return_value_s *prev;  // caller's ret_value (lookahead)
        };

    The ``prev`` pointer becomes a Python ``ReturnValue | None``
    reference so the parser can rewind on lookahead failures.

    Attributes:
        input_pos: Position in input_array to start matching.
        input_offset: Number of characters matched so far.
        output_pos: Position in output_array to start writing.
        output_offset: Number of characters written.
        rule: Offset into the current rule string.
        value: Function-return status (FAIL/SUCCESS/OPT_FAIL/etc.).
        optional: Optional-failure flag.
        state: Current lookahead state.
        parser_flag: Status-state setting forwarded to a kernel variable.
        prev: Caller's :class:`ReturnValue` for lookahead rewind (or None).
    """

    input_pos: int = 0
    input_offset: int = 0
    output_pos: int = 0
    output_offset: int = 0
    rule: int = 0
    value: int = 0
    optional: int = 0
    state: int = 0
    parser_flag: int = 0
    prev: ReturnValue | None = None


@dataclass(slots=True)
class RangeValue:
    """Range-match state for ``<DIGIT>`` rules.

    Faithful translation of:

    .. code-block:: c

        struct range_value_s {
            S16 start;     // start of digit range
            S16 end;       // end of digit range
            S16 min;
            S16 range_set;
        };

    Attributes:
        start: Lower bound of the digit range.
        end: Upper bound.
        min: Minimum number of matches required.
        range_set: Boolean flag — non-zero if a range was set.
    """

    start: int = 0
    end: int = 0
    min: int = 0
    range_set: int = 0


def _default_match_arrays() -> list[bytearray]:
    """Factory: 10 empty bytearrays of length 30 each."""
    return [bytearray(PAR_MAX_MATCH_ARRAY) for _ in range(PAR_MAX_ARRAYS)]


def _default_array_lengths() -> list[int]:
    """Factory: 10 zero-initialised lengths (one per match array)."""
    return [0 for _ in range(PAR_MAX_ARRAYS)]


@dataclass(slots=True)
class MatchArrays:
    """10 by 30-byte temporary buffers for the rule matcher.

    Faithful translation of:

    .. code-block:: c

        struct match_arrays_s {
            int array_lengths[PAR_MAX_ARRAYS];
            unsigned char array[PAR_MAX_ARRAYS][PAR_MAX_MATCH_ARRAY];
        };

    Attributes:
        array_lengths: Per-slot count of bytes saved into ``array``
            by ``par_save_string`` (and friends). The matcher's
            ``BIN_RESTORE`` branches read this when re-applying a
            saved span.
        array: List of 10 :class:`bytearray` of length 30 each.
    """

    array_lengths: list[int] = field(default_factory=_default_array_lengths)
    array: list[bytearray] = field(default_factory=_default_match_arrays)


@dataclass(slots=True)
class IndexData:
    """3-entry index-pipeline data buffer.

    Faithful translation of:

    .. code-block:: c

        struct index_data_s {
            DT_PIPE_T index[3];
        };

    Attributes:
        index: 3-element list of pipe-word values.
    """

    index: list[int] = field(default_factory=lambda: [0, 0, 0])


__all__ = [
    "PAR_MAX_ARRAYS",
    "PAR_MAX_MATCH_ARRAY",
    "DictPointers",
    "IndexData",
    "MatchArrays",
    "RangeValue",
    "ReturnValue",
]
