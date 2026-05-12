"""PHONE linked-list manipulation from ls_rule2.c and ls_util.c.

Translated from:

- ``src/dapi/src/lts/ls_rule2.c`` — ``ls_rule_add_phone``: insert a
  new PHONE at the front of the generated list.
- ``src/dapi/src/lts/ls_util.c`` — ``ls_util_copyword``:
  copy a LETTER-terminated word.
- ``src/dapi/src/lts/ls_util.c`` — ``ls_util_send_phone_list``:
  iterate a SIL-terminated phoneme byte string sending each phone.

The C originals operate on linked-list nodes via ``pLts_t->phead``
(a sentinel head) and the allocator pool ``ls_rule_phone_alloc``.
The Python port models the "generated PHONE list" as a plain
Python list — the linked-list shape and the sentinel head are
preserved because the in-engine code walks them via the pointer
fields, but here we expose constructor helpers that build the same
shape from sequences.
"""

from __future__ import annotations

from collections.abc import Iterable

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.phoneme_codes import PFUSA
from dectalk.lts.structs import Letter, Phone

EOS: int = 0
"""Null terminator for LETTER words."""

SNONE: int = 71  # PHO_SYM_TOT + 0; matches the C ``#define SNONE (PHO_SYM_TOT)``
"""Stress code for "no stress" — placeholder until pho-defs.h imports it."""

SUN: int = SNONE + 1
"""Stress code for ``[1]`` — primary phonemic stress (unstressed-vowel form)."""

SSEC: int = SNONE + 2
"""Stress code for ``[2]`` — secondary stress."""

SPRI: int = SNONE + 3
"""Stress code for ``[3]`` — primary stress."""

S1LEFT: int = SNONE + 4
"""Stress code for ``[4]`` — primary stress, left-fused syllable."""

S2LEFT: int = SNONE + 5
"""Stress code for ``[5]`` — secondary stress, left-fused syllable."""

SIL_US: int = (PFUSA << PSFONT) | 0
"""Font-encoded silence phoneme for US English (PFUSA << 8 | 0).

Used as the terminator byte in the C ``ls_util_send_phone_list`` /
``ls_util_send_asky_phone_list`` while-loops. The C source compares
against the plain SIL value (no font byte) because the loop already
strips the font, but for the Python port we keep both shapes.
"""


def ls_util_copyword(source: Iterable[Letter]) -> list[Letter]:
    """Return a copy of ``source`` up to the first EOS LETTER.

    Faithful translation of:

    .. code-block:: c

        void ls_util_copyword(LETTER *tlp, LETTER *flp) {
            while (flp->l_ch != EOS) {
                tlp->l_ch = flp->l_ch;
                ++tlp; ++flp;
            }
            tlp->l_ch = EOS;
        }

    The C version writes into a caller-provided destination buffer
    and assumes it's big enough. The Python port returns a fresh
    list of :class:`Letter` objects with a trailing EOS sentinel
    appended, so the caller doesn't need to manage memory.

    Args:
        source: Iterable of LETTER source codes, terminated by an
            EOS (``l_ch == 0``) sentinel.

    Returns:
        A new list of LETTER objects mirroring ``source`` up to —
        and including — the EOS terminator.
    """
    out: list[Letter] = []
    for lp in source:
        if lp.l_ch == EOS:
            break
        out.append(Letter(l_ch=lp.l_ch))
    out.append(Letter(l_ch=EOS))
    return out


def iter_phone_list_until_sil(byte_string: bytes | Iterable[int]) -> list[int]:
    """Return phonemes from ``byte_string`` up to but not including SIL.

    Faithful translation of the inner loop of:

    .. code-block:: c

        void ls_util_send_phone_list(LPTTS_HANDLE_T phTTS,
                                      const char *pp) {
            int ph;
            while ((ph = *pp++) != SIL && !phTTS->pKernelShareData->halting)
                ls_util_send_phone(phTTS, ph);
        }

    The C source pushes each phone into a downstream pipe; the
    Python port simply returns the sequence of phone codes the
    caller would have sent. The ``halting`` check is omitted —
    that's a kernel concern that no caller can model without the
    full kernel state.

    Args:
        byte_string: Sequence of phoneme byte codes terminated by
            ``SIL`` (zero, or ``PFUSA << 8 | 0``).

    Returns:
        List of phone codes up to but not including the SIL byte.
    """
    out: list[int] = []
    for ph in byte_string:
        if ph in (0, SIL_US):
            break
        out.append(ph)
    return out


def ls_rule_add_phone(plist: list[Phone], sph: int, uph: int) -> Phone:
    """Prepend a new PHONE to ``plist`` and return it.

    Faithful translation of:

    .. code-block:: c

        void ls_rule_add_phone(PLTS_T pLts_t, int sph, int uph) {
            PHONE *fp, *pp;
            if ((pp = ls_rule_phone_alloc(pLts_t)) != NULL) {
                fp = pLts_t->phead.p_fp;
                pLts_t->phead.p_fp = pp;
                pp->p_fp = fp;
                fp->p_bp = pp;
                pp->p_bp = &pLts_t->phead;
                pp->p_flag = 0;
                pp->p_sphone = sph;
                pp->p_uphone = uph;
                pp->p_stress = SNONE;
            }
        }

    The C source inserts the new PHONE at the front of the list
    behind a sentinel head. The Python port models the list as a
    plain ``list[Phone]`` where index 0 is the front; the linked-
    list pointers are still maintained on each Phone so the
    downstream engine code that walks via ``p_fp``/``p_bp`` keeps
    working.

    Args:
        plist: Existing PHONE list (front-most first). The new
            PHONE is inserted at index 0.
        sph: Stressed allophone code (``p_sphone``).
        uph: Unstressed allophone code (``p_uphone``).

    Returns:
        The newly allocated :class:`Phone`.
    """
    new_phone = Phone(p_flag=0, p_sphone=sph, p_uphone=uph, p_stress=SNONE)
    # Splice into the linked-list pointers.
    if plist:
        old_head = plist[0]
        new_phone.p_fp = old_head
        old_head.p_bp = new_phone
    plist.insert(0, new_phone)
    return new_phone


__all__ = [
    "EOS",
    "S1LEFT",
    "S2LEFT",
    "SIL_US",
    "SNONE",
    "SPRI",
    "SSEC",
    "SUN",
    "iter_phone_list_until_sil",
    "ls_rule_add_phone",
    "ls_util_copyword",
]
