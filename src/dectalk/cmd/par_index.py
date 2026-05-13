"""Index-array helpers from par_pars.c.

Translated from ``src/dapi/src/cmd/par_pars.c`` lines 1399-1435.

Two small index-array helpers the parser uses to copy and probe
index-marker state stored alongside parser input/output buffers:

- :func:`par_copy_index` — copy one 3-element index record from
  one position to another.
- :func:`par_is_index_set` — return ``True`` iff the index record
  at ``pos`` has any non-zero entry.

The index records are :class:`dectalk.cmd.par_structs.IndexData`
dataclasses (3-int arrays). The C source uses ``pindex_data_t`` —
a flat array of these — addressed by integer position.
"""

from __future__ import annotations

from dectalk.cmd.par_structs import IndexData


def par_copy_index(
    dest_indexes: list[IndexData],
    dest_pos: int,
    src_indexes: list[IndexData],
    src_pos: int,
) -> None:
    """Copy the 3-element index record from ``src[src_pos]`` to ``dest[dest_pos]``.

    Faithful translation of:

    .. code-block:: c

        void par_copy_index(pindex_data_t dest_index, short dest_pos,
                            pindex_data_t src_index,  short src_pos) {
            memcpy(dest_index[dest_pos].index,
                   src_index[src_pos].index,
                   sizeof(index_data_t));
        }

    Args:
        dest_indexes: Destination index array.
        dest_pos: Destination position.
        src_indexes: Source index array.
        src_pos: Source position.
    """
    dest_indexes[dest_pos].index = list(src_indexes[src_pos].index)


def par_is_index_set(indexes: list[IndexData], pos: int) -> bool:
    """Return True iff any of ``indexes[pos].index[0..2]`` is non-zero.

    Faithful translation of:

    .. code-block:: c

        short par_is_index_set(pindex_data_t indexes, short pos) {
            if (indexes[pos].index[0] != 0
                || indexes[pos].index[1] != 0
                || indexes[pos].index[2] != 0) {
                return 1;
            }
            return 0;
        }

    The C function returns ``SUCCESS`` (1) or ``FAIL`` (0); the
    Python port returns ``True`` / ``False`` for idiomatic use.

    Args:
        indexes: Index array.
        pos: Position to check.

    Returns:
        ``True`` if any of the 3 entries at ``indexes[pos]`` is
        non-zero, ``False`` otherwise.
    """
    record = indexes[pos].index
    return record[0] != 0 or record[1] != 0 or record[2] != 0


__all__ = ["par_copy_index", "par_is_index_set"]
