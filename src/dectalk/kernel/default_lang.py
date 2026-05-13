"""``default_lang`` helper from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 698-758.

The first language to have both LTS and PH loaded becomes the
default language. Each subsystem (LTS, PH, possibly others) calls
:func:`default_lang` with a different ``ready_code`` bit; once
``lang_ready[lang_code]`` ORs to ``LANG_both_ready`` and no
language has been selected yet, this language wins.

When a language wins, ``default_lang`` walks the
``loaded_languages`` linked list to find the per-language table
node and installs its ASCKY / reverse-ASCKY / ARPABET / typing /
error tables into the current-language pointers.
"""

from __future__ import annotations

from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_both_ready, LANG_none


def default_lang(p_ksd_t: KsdT, lang_code: int, ready_code: int) -> None:
    """Mark a language ready and install its tables if it wins.

    Faithful translation of:

    .. code-block:: c

        void default_lang(PKSD_T pKsd_t, unsigned int lang_code,
                          unsigned int ready_code) {
            unsigned int flags;
            volatile struct dtpc_language_tables _far *cp;

            if (pKsd_t->lang_ready[lang_code] == 0) {
        #ifndef SINGLE_THREADED
                pKsd_t->lang_lts[lang_code] = pKsd_t->lang_lts[lang_code];
                pKsd_t->lang_ph[lang_code]  = pKsd_t->lang_ph[lang_code];
        #endif
            }
            pKsd_t->lang_ready[lang_code] |= ready_code;
            flags = kernel_disable(pKsd_t);
            if ((pKsd_t->lang_ready[lang_code] == LANG_both_ready) &&
                (pKsd_t->lang_curr == LANG_none || ready_code == 0)) {
                pKsd_t->lang_curr = lang_code;
        #ifndef SINGLE_THREADED
                pKsd_t->lts_pipe = pKsd_t->lang_lts[lang_code];
                pKsd_t->ph_pipe  = pKsd_t->lang_ph[lang_code];
        #endif
                cp = pKsd_t->loaded_languages;
                while (cp != NULL_LT) {
                    if ((*cp).lang_id == (int)lang_code) {
                        pKsd_t->ascky          = (*cp).lang_ascky;
                        pKsd_t->ascky_size     = (*cp).lang_ascky_size;
                        pKsd_t->reverse_ascky  = (*cp).lang_reverse_ascky;
                        pKsd_t->arpabet        = (*cp).lang_arpabet;
                        pKsd_t->arpa_size      = (*cp).lang_arpa_size;
                        pKsd_t->arpa_case      = (*cp).lang_arpa_case;
                        pKsd_t->typing_table   = (*cp).lang_typing;
                        pKsd_t->error_table    = (*cp).lang_error;
                    }
                    cp = (*cp).link;
                }
            }
            kernel_enable(pKsd_t, flags);
        }

    The ``kernel_disable`` / ``kernel_enable`` bracket is an
    interrupt-disable pair on MSDOS; on Linux both functions are
    no-ops, so the Python port simply runs the body inline.

    The non-SINGLE_THREADED self-assignment of ``lang_lts`` /
    ``lang_ph`` (``foo = foo``) is preserved as a no-op for
    fidelity, even though it does nothing observable in Python.

    Args:
        p_ksd_t: Kernel shared-data struct to mutate.
        lang_code: Language index (``LANG_*`` code) becoming ready.
        ready_code: Bit pattern indicating which subsystem just
            reported in (``LANG_PH_ready`` / ``LANG_LTS_ready``).
            A ``ready_code`` of 0 forces the language switch even
            if another language is already current.
    """
    p_ksd_t.lang_ready[lang_code] |= ready_code

    if not (
        p_ksd_t.lang_ready[lang_code] == LANG_both_ready
        and (p_ksd_t.lang_curr == LANG_none or ready_code == 0)
    ):
        return

    p_ksd_t.lang_curr = lang_code
    p_ksd_t.lts_pipe = p_ksd_t.lang_lts[lang_code]
    p_ksd_t.ph_pipe = p_ksd_t.lang_ph[lang_code]

    cp = p_ksd_t.loaded_languages
    while cp is not None:
        if cp.lang_id == lang_code:
            p_ksd_t.ascky = cp.lang_ascky
            p_ksd_t.ascky_size = cp.lang_ascky_size
            p_ksd_t.reverse_ascky = cp.lang_reverse_ascky
            p_ksd_t.arpabet = cp.lang_arpabet
            p_ksd_t.arpa_size = cp.lang_arpa_size
            p_ksd_t.arpa_case = cp.lang_arpa_case
            p_ksd_t.typing_table = cp.lang_typing
            p_ksd_t.error_table = cp.lang_error
        cp = cp.link


__all__ = ["default_lang"]
