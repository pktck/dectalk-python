"""WH-word detection from ls_task.c.

Translated from ``src/dapi/src/lts/ls_task.c``:

- :func:`is_wh_word` — pure variant of the wh-word check inside
  ``ls_task_set_what_state``. Returns True iff the word is one of
  ``what``, ``when``, ``where``, ``why``, ``who``, ``how``,
  ``which``, ``whose``, ``whom`` (the entries in ``whdic``).

The C source mutates ``pLts_t->wstate`` to ``IS_WH`` when a match
is found; the Python port returns a bool so the caller can route
the result.

The C also walks past leading ``lsctype[c]&LS`` characters before
looking up — those are typically opening quotes / whitespace.
:func:`is_wh_word` skips them too, mirroring the C structure.
"""

from __future__ import annotations

from dectalk.lts.phone_list import EOS
from dectalk.lts.short_dict import whdic
from dectalk.lts.structs import Letter
from dectalk.lts.word_scan import wlookup


def is_wh_word(cword: list[Letter], skip: int = 0) -> bool:
    """Return True iff ``cword`` (at offset ``skip``) is a recognised wh-word.

    Faithful translation of the wh-word branch of:

    .. code-block:: c

        int ls_task_set_what_state(LPTTS_HANDLE_T phTTS, PLTS_T pLts_t) {
            LETTER *llp;
            if (pLts_t->wstate == UNK_WH && pLts_t->cword[0].l_ch != EOS) {
                pLts_t->wstate = NOT_WH;
                llp = &(pLts_t->cword[0]);
                while ((lsctype[llp->l_ch] & LS) != 0)
                    ++llp;
                if ((ls_task_wlookup(pLts_t, llp, &whdic[0])) != NULL) {
                    pLts_t->wstate = IS_WH;
                }
                ...
            }
        }

    Args:
        cword: Current word as an EOS-terminated LETTER list.
        skip: Initial index to start the lookup from (default 0).
            The C source walks past quote / leading-whitespace
            characters using ``lsctype & LS``; callers supply the
            post-skip index here.

    Returns:
        ``True`` iff the word starting at ``cword[skip]`` matches one
        of the 9 entries in :data:`whdic`.
    """
    if skip >= len(cword) or cword[skip].l_ch == EOS:
        return False
    return wlookup(cword, whdic, left=skip) is not None


__all__ = ["is_wh_word"]
