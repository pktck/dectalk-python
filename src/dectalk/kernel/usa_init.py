"""``usa_init`` helper from kernel/usa_init.c.

Translated from ``src/dapi/src/kernel/usa_init.c`` lines 210-374
(the file actually compiled into ``libtts_us.so``; the sibling
``usa.c`` defines an older single-language variant of the same
function that is NOT in the Makefile and isn't linked into the
shipped binary).

:func:`usa_init` is the language constructor. It:

1. Allocates a fresh :class:`DtpcLanguageTables` node.
2. Inspects ``pKsd_t->lang_curr`` (set earlier by
   ``TextToSpeechStartup``) and populates the node with that
   language's data tables.
3. Copies the populated node fields straight into
   ``pKsd_t->ascky`` / ``arpabet`` / ``typing_table`` /
   ``error_table`` etc. — this happens unconditionally even though
   ``default_lang`` (called below) won't install them yet because
   only the ``LANG_tables_ready`` bit is set.
4. Threads the node onto the kernel's ``loaded_languages`` linked
   list.
5. Calls :func:`default_lang` with ``LANG_tables_ready`` to mark
   that ready bit for the configured language.

On a US-English-only ``libtts_us.so`` build (``ENGLISH_US``
defined, others not), only the ``LANG_english`` branch can match
because ``TextToSpeechStartup`` sets ``lang_curr = LANG_english``
unconditionally and only the ``ENGLISH_US`` ``default_lang`` call
compiles. The Python port models that build.
"""

from __future__ import annotations

from dectalk.include.usa_arpa import usa_arpa
from dectalk.include.usa_ascky import usa_ascky
from dectalk.include.usa_phon_tables import usa_ascky_rev
from dectalk.kernel.default_lang import default_lang
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english, LANG_tables_ready
from dectalk.kernel.language_tables import DtpcLanguageTables
from dectalk.kernel.usa_tables import usa_error, usa_type


def _join_strings(seq: tuple[str, ...]) -> list[bytes]:
    """Render a ``tuple[str, ...]`` row table to ``list[bytes]``.

    The C source's ``usa_type`` / ``usa_error`` are
    ``const unsigned char *const[]`` arrays — arrays of pointers to
    byte strings. The Python literals use ``tuple[str, ...]`` for
    ergonomic editing; this helper encodes the rows.
    """
    return [s.encode("latin-1") for s in seq]


def usa_init(p_ksd_t: KsdT) -> None:
    """Install the current language's tables and set the ready bit.

    Faithful translation of the ``ENGLISH_US`` build of:

    .. code-block:: c

        void usa_init(PKSD_T pKsd_t) {
            volatile struct dtpc_language_tables _far *lt;
            struct dtpc_language_tables *pnlt = malloc(...);
            pnlt->link = NULL_LT;
            if (pKsd_t->lang_curr == LANG_english) {
                pnlt->lang_id            = LANG_english;
                pnlt->lang_ascky         = usa_ascky;
                pnlt->lang_ascky_size    = sizeof(usa_ascky);
                pnlt->lang_reverse_ascky = usa_ascky_rev;
                pnlt->lang_arpabet       = usa_arpa;
                pnlt->lang_arpa_size     = sizeof(usa_arpa);
                pnlt->lang_arpa_case     = FALSE;
                pnlt->lang_typing        = usa_type;
                pnlt->lang_error         = usa_error;
            }
            // (similar branches for british, latin_american, spanish,
            // german, french — only the lang_curr-matching branch fires)

            pKsd_t->ascky          = pnlt->lang_ascky;
            pKsd_t->ascky_size     = pnlt->lang_ascky_size;
            pKsd_t->reverse_ascky  = pnlt->lang_reverse_ascky;
            pKsd_t->arpabet        = pnlt->lang_arpabet;
            pKsd_t->arpa_size      = pnlt->lang_arpa_size;
            pKsd_t->arpa_case      = pnlt->lang_arpa_case;
            pKsd_t->typing_table   = pnlt->lang_typing;
            pKsd_t->error_table    = pnlt->lang_error;

            lt = pKsd_t->loaded_languages;
            if (lt == NULL_LT)
                pKsd_t->loaded_languages = pnlt;
            else {
                while ((*lt).link != NULL_LT)
                    lt = (*lt).link;
                (*lt).link = pnlt;
            }
        #ifdef ENGLISH_US
            default_lang(pKsd_t, LANG_english, LANG_tables_ready);
        #endif
        }

    Args:
        p_ksd_t: Kernel shared-data struct to mutate. The new node
            is appended to ``loaded_languages``, the per-language
            tables are copied into the top-level KSD fields, and
            the ``LANG_tables_ready`` bit is set for the configured
            language.
    """
    pnlt = DtpcLanguageTables(link=None)

    # Language-curr dispatch. Only LANG_english is modelled here
    # because libtts_us.so is ENGLISH_US-only and TextToSpeechStartup
    # always assigns lang_curr = LANG_english.
    if p_ksd_t.lang_curr == LANG_english:
        pnlt.lang_id = LANG_english
        pnlt.lang_ascky = usa_ascky
        pnlt.lang_ascky_size = len(usa_ascky)
        pnlt.lang_reverse_ascky = list(usa_ascky_rev)
        pnlt.lang_arpabet = usa_arpa
        pnlt.lang_arpa_size = len(usa_arpa)
        pnlt.lang_arpa_case = 0  # FALSE
        pnlt.lang_typing = _join_strings(usa_type)
        pnlt.lang_error = _join_strings(usa_error)

    # Unconditional copy from pnlt into the KSD's current-language
    # fields — happens regardless of whether a branch matched
    # (matches the C behaviour where unmatched malloc memory is
    # garbage; on a real build the branch always matches).
    p_ksd_t.ascky = pnlt.lang_ascky
    p_ksd_t.ascky_size = pnlt.lang_ascky_size
    p_ksd_t.reverse_ascky = pnlt.lang_reverse_ascky
    p_ksd_t.arpabet = pnlt.lang_arpabet
    p_ksd_t.arpa_size = pnlt.lang_arpa_size
    p_ksd_t.arpa_case = pnlt.lang_arpa_case
    p_ksd_t.typing_table = pnlt.lang_typing
    p_ksd_t.error_table = pnlt.lang_error

    # Thread on chain.
    if p_ksd_t.loaded_languages is None:
        p_ksd_t.loaded_languages = pnlt
    else:
        lt = p_ksd_t.loaded_languages
        while lt.link is not None:
            lt = lt.link
        lt.link = pnlt

    # Install the LANG_tables_ready ready-bit for English (the
    # only #ifdef'd branch compiled into libtts_us.so).
    default_lang(p_ksd_t, LANG_english, LANG_tables_ready)


__all__ = ["usa_init"]
