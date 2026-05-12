"""Mini-dictionary search from ls_task.c.

Translated from ``src/dapi/src/lts/ls_task.c``:

- :func:`ls_task_minidic_search` — look up the current word in the
  3-entry ``sdic`` (for/and/to) mini-dictionary. The C source
  emits the matched phoneme run via ``ls_util_send_phone_list`` and
  returns ``FINISHED_WORD``; the Python port returns the phoneme
  bytes instead so the caller can route them however it likes.
"""

from __future__ import annotations

from dectalk.lts.short_dict import sdic
from dectalk.lts.structs import Letter
from dectalk.lts.word_scan import wlookup


def ls_task_minidic_search(cword: list[Letter]) -> bytes | None:
    """Return the matched phoneme run for ``cword`` in ``sdic``, or None.

    Faithful translation of:

    .. code-block:: c

        int ls_task_minidic_search(LPTTS_HANDLE_T phTTS,
                                    LETTER *llp, LETTER *rlp) {
            char *cp;
            if ((cp = ls_task_wlookup(pLts_t, llp, &sdic[0])) != NULL) {
                ls_util_send_phone_list(phTTS, cp);
                pLts_t->lbphone = WBOUND;
                pLts_t->rbphone = WBOUND;
                return FINISHED_WORD;
            }
            return KEEP_SEARCHING;
        }

    The Python port omits the WBOUND assignment to ``lbphone`` /
    ``rbphone`` since we don't yet have the LTS thread-state struct.
    Callers can do that step themselves when wiring up.

    Args:
        cword: Current word as an EOS-terminated LETTER list.

    Returns:
        The phoneme byte run (without the SIL terminator) for the
        matched mini-dictionary entry, or ``None`` if no match.
    """
    return wlookup(cword, sdic)


__all__ = ["ls_task_minidic_search"]
