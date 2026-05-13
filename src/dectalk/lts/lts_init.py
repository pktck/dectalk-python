"""LTS-thread init from ls_util.c.

Translated from ``src/dapi/src/lts/ls_util.c`` lines 1524-1546.

:func:`ls_util_lts_init` resets the per-thread LTS state at the
start of each clause:

- ``wstate`` -> :data:`UNK_WH` (first word not yet examined).
- ``lphone`` -> :data:`WBOUND` (boundary at clause start).
- ``num_indexes`` -> 0 (no index markers collected yet).
- ``cur_index`` -> -1 (no current index).
- (``NEW_LTS``) ``cur_word_index`` -> 0.
- (else)       ``fc_index`` -> 0, ``old_fc_index`` -> -1.

The function is called by ``ls_main()`` at engine startup and
by the per-clause restart in the LTS dispatcher.
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND
from dectalk.lts.lts_t import LtsT
from dectalk.lts.wh_state_codes import UNK_WH


def ls_util_lts_init(p_lts_t: LtsT) -> None:
    """Initialise per-thread LTS state at clause boundary.

    Faithful translation of:

    .. code-block:: c

        void ls_util_lts_init(PLTS_T pLts_t, PKSD_T pKsd_t) {
            pLts_t->wstate = UNK_WH;
            pLts_t->lphone = WBOUND;
            pLts_t->num_indexes = 0;
            pLts_t->cur_index = -1;

            // SINGLE_THREADED branch (Linux build): also reset
            pLts_t->first_pass = 0;
            pLts_t->cur_input_pos = 0;
            pLts_t->num_indexes = 0;
            pLts_t->cur_index = -1;

            // NEW_LTS branch:
            pLts_t->cur_word_index = 0;
        }

    The C ``PKSD_T`` parameter is unused in the function body
    (the C source only takes it for symmetry with other init
    functions). The Python port drops it.

    Args:
        p_lts_t: LTS thread-state instance to mutate.
    """
    p_lts_t.wstate = UNK_WH
    p_lts_t.lphone = WBOUND
    p_lts_t.num_indexes = 0
    p_lts_t.cur_index = -1

    # SINGLE_THREADED branch (Linux build).
    p_lts_t.first_pass = 0
    p_lts_t.cur_input_pos = 0

    # NEW_LTS branch.
    p_lts_t.cur_word_index = 0


__all__ = ["ls_util_lts_init"]
