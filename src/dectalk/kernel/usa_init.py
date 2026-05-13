"""``usa_init`` helper from kernel/usa.c.

Translated from ``src/dapi/src/kernel/usa.c`` lines 85-182.

:func:`usa_init` is the US-English language constructor. It:

1. Allocates a fresh :class:`DtpcLanguageTables` node.
2. Populates the node with the US-English data tables
   (``usa_ascky``, ``usa_ascky_rev``, ``usa_arpa``, ``usa_type``,
   ``usa_error``).
3. Threads the node onto the kernel's ``loaded_languages`` linked
   list.
4. Calls :func:`default_lang` with ``LANG_tables_ready`` to mark the
   "tables loaded" ready bit for US English.

The C source has ``#ifdef`` blocks for each language; on a
US-English-only ``libtts_us.so`` build (``ENGLISH_US`` defined,
others not), only the US block compiles in. The Python port models
just that branch — supporting only US English at the moment.
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
    """Convert the ``tuple[str, ...]`` form into ``list[bytes]``.

    The C source's ``usa_type`` / ``usa_error`` are
    ``const unsigned char *const[]`` arrays — pointers to byte
    strings. The Python literals are tuples of ``str`` for ergonomic
    editing; this helper renders them to the byte form
    :class:`DtpcLanguageTables` expects.
    """
    return [s.encode("latin-1") for s in seq]


def usa_init(p_ksd_t: KsdT) -> None:
    """Install US-English language tables and mark them ready.

    Faithful translation of the ENGLISH_US branch of:

    .. code-block:: c

        void usa_init(PKSD_T pKsd_t) {
            struct dtpc_language_tables *pnlt = malloc(...);
            pnlt->link = NULL_LT;
            pnlt->lang_id = LANG_english;
        #ifdef ENGLISH_US
            pnlt->lang_ascky = usa_ascky;
            pnlt->lang_ascky_size = sizeof(usa_ascky);
            pnlt->lang_reverse_ascky = usa_ascky_rev;
            pnlt->lang_arpabet = usa_arpa;
            pnlt->lang_arpa_size = sizeof(usa_arpa);
            pnlt->lang_arpa_case = FALSE;
            pnlt->lang_typing = usa_type;
            pnlt->lang_error = usa_error;
        #endif
            // thread on chain
            lt = pKsd_t->loaded_languages;
            if (lt == NULL_LT)
                pKsd_t->loaded_languages = pnlt;
            else {
                while ((*lt).link != NULL_LT)
                    lt = (*lt).link;
                (*lt).link = pnlt;
            }
            default_lang(pKsd_t, LANG_english, LANG_tables_ready);
        }

    Args:
        p_ksd_t: Kernel shared-data struct to mutate. The new node
            is appended to ``p_ksd_t.loaded_languages``, and the
            ``LANG_english`` ready bit ``LANG_tables_ready`` is set
            via :func:`default_lang`.
    """
    pnlt = DtpcLanguageTables(
        link=None,
        lang_id=LANG_english,
        lang_ascky=usa_ascky,
        lang_ascky_size=len(usa_ascky),
        lang_reverse_ascky=list(usa_ascky_rev),
        lang_arpabet=usa_arpa,
        lang_arpa_size=len(usa_arpa),
        lang_arpa_case=0,  # FALSE
        lang_typing=_join_strings(usa_type),
        lang_error=_join_strings(usa_error),
    )

    # Thread on chain.
    if p_ksd_t.loaded_languages is None:
        p_ksd_t.loaded_languages = pnlt
    else:
        lt = p_ksd_t.loaded_languages
        while lt.link is not None:
            lt = lt.link
        lt.link = pnlt

    # Install the language bit flag.
    default_lang(p_ksd_t, LANG_english, LANG_tables_ready)


__all__ = ["usa_init"]
