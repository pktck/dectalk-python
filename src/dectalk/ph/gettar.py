# ruff: noqa: PLR2004 -- C-literal table positions kept inline
"""``gettar`` -- per-phone target-lookup dispatcher from ph_setar.c.

Translated from ``src/dapi/src/ph/ph_setar.c`` line 1879 (~190 lines).

The C function looks up the per-parameter target value for a given
phone, switching between per-language target tables (US English,
UK English, German, Latin American Spanish, Spanish, French) based
on the high bits (``PFONT``) of the phone index.

The body walks four candidate positions (``index = [0, 1, 2, -1]``):
the current phone, the next two phones (for forward look-ahead),
and the previous phone. For each candidate it:

1. Reads the language-font byte of the phone via :func:`get_phone`.
2. On language transition, repoints ``pDph_t->p_diph`` / ``p_tar``
   / ``p_amp`` to the correct per-language ROM tables. The C source
   selects male vs. female tables via ``pDph_t->malfem``.
3. Calls the per-language ``*_gettar`` helper (currently only
   :func:`us_gettar` is translated; the other-language branches
   raise :class:`NotImplementedError`).
4. Applies a USP_K coarticulation tweak (+300 Hz on F2, +500 Hz on
   F3 when the candidate phone is /k/).
5. Returns the candidate value if it's "real" (non-sentinel for
   position 0; positive or sentinel-resolved for forward look-ahead;
   resolves diphthong sentinels for the previous phone).

Returns 0 if no candidate yields a real target.
"""

from __future__ import annotations

from typing import cast

from dectalk.include.cmd_codes import PFONT, PSFONT
from dectalk.include.phoneme_codes import PFFR, PFGR, PFLA, PFSP, PFUK, PFUSA
from dectalk.include.usp_codes import USP_K
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.get_phone import get_phone
from dectalk.ph.numeric_constants import F1, F2, F3, MALE
from dectalk.ph.parameter_tables import parini
from dectalk.ph.rom_tables import (
    us_femamp,
    us_femdip,
    us_femtar,
    us_malamp,
    us_maldip,
    us_maltar,
)
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.uk_gettar import uk_gettar
from dectalk.ph.uk_rom_tables import (
    uk_femamp,
    uk_femdip,
    uk_femtar,
    uk_malamp,
    uk_maldip,
    uk_maltar,
)
from dectalk.ph.us_gettar import us_gettar

_FONT_USA: int = PFUSA << PSFONT
_FONT_UK: int = PFUK << PSFONT
_FONT_GR: int = PFGR << PSFONT
_FONT_LA: int = PFLA << PSFONT
_FONT_SP: int = PFSP << PSFONT
_FONT_FR: int = PFFR << PSFONT


def _load_us_tables(p_dph_t: DphT) -> None:
    """Repoint ``p_diph`` / ``p_tar`` / ``p_amp`` to the US tables."""
    if p_dph_t.malfem == MALE:
        p_dph_t.p_diph = list(us_maldip)
        p_dph_t.p_tar = list(us_maltar)
        p_dph_t.p_amp = list(us_malamp)
    else:
        p_dph_t.p_diph = list(us_femdip)
        p_dph_t.p_tar = list(us_femtar)
        p_dph_t.p_amp = list(us_femamp)


def _load_uk_tables(p_dph_t: DphT) -> None:
    """Repoint ``p_diph`` / ``p_tar`` / ``p_amp`` to the UK tables."""
    if p_dph_t.malfem == MALE:
        p_dph_t.p_diph = list(uk_maldip)
        p_dph_t.p_tar = list(uk_maltar)
        p_dph_t.p_amp = list(uk_malamp)
    else:
        p_dph_t.p_diph = list(uk_femdip)
        p_dph_t.p_tar = list(uk_femtar)
        p_dph_t.p_amp = list(uk_femamp)


def gettar(phTTS: TtsHandle, phone: int) -> int:  # noqa: N803, PLR0912, PLR0915 -- faithful C translation
    """Look up the per-phone target value, dispatching by language font.

    Faithful translation of the C ``int gettar(LPTTS_HANDLE_T, int)``.
    The Python port dispatches to :func:`us_gettar` for US English
    phones and :func:`uk_gettar` for UK English phones; other-language
    fonts (GR/LA/SP/FR) raise :class:`NotImplementedError` since their
    per-language target helpers are not yet ported.

    Args:
        phTTS: Two-pointer engine handle. ``p_ph_thread_data`` must
            be a populated :class:`~dectalk.ph.dph_t.DphT`.
        phone: Index into ``allophons[]`` naming the phone whose
            target is wanted.

    Returns:
        The target value (``int`` in C; ``int`` here too). Returns
        ``0`` if no candidate position yields a real target.

    Raises:
        NotImplementedError: When a non-US/UK phone font is
            encountered; GR/LA/SP/FR ``*_gettar`` helpers are still
            deferred.
    """
    p_dph_t = cast(DphT, phTTS.p_ph_thread_data)
    p_dphsettar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    index = (0, 1, 2, -1)
    count = 0
    tartemp = 0

    while count <= 3:
        # C: `if (index[count] == 2 && pDph_t->nallotot >= phone+index[count]+1) count++;`
        # This skip-on-have-enough-phones gate looks reversed, but it's
        # what the source does; preserve verbatim.
        if index[count] == 2 and p_dph_t.nallotot >= phone + index[count] + 1:
            count += 1
            if count > 3:
                break

        tmp = get_phone(p_dph_t, phone + index[count]) & PFONT

        # On language-font transition, swap the active ROM tables.
        if tmp != p_dph_t.last_lang:
            p_dph_t.last_lang = tmp
            if tmp == _FONT_USA:
                _load_us_tables(p_dph_t)
            elif tmp == _FONT_UK:
                _load_uk_tables(p_dph_t)
            elif tmp in (_FONT_GR, _FONT_LA, _FONT_SP, _FONT_FR):
                raise NotImplementedError(
                    f"gettar: per-language tables for font 0x{tmp:04x} "
                    "(GR/LA/SP/FR) are not yet ported; only US/UK English "
                    "are wired up. See docs/PLAN.md Phase E."
                )
            else:
                # Default fallback in C: call us_gettar with phone & PVALUE.
                # Reach this branch only when font is unrecognised.
                tartemp = us_gettar(phTTS, phone & 0xFF)

        # Per-language dispatch (US and UK wired up).
        if tmp == _FONT_USA:
            tartemp = us_gettar(phTTS, phone + index[count])
        elif tmp == _FONT_UK:
            tartemp = uk_gettar(phTTS, phone + index[count])
        elif tmp in (_FONT_GR, _FONT_LA, _FONT_SP, _FONT_FR):
            raise NotImplementedError(
                f"gettar: US/UK English are wired up but font 0x{tmp:04x} "
                "is not. Pending gr_/la_/sp_/fr_gettar ports."
            )

        # USP_K coarticulation: F2 += 300, F3 += 500 when phone is /k/.
        if p_dph_t.allophons[phone + index[count]] == USP_K:
            if p_dphsettar.np == F2:
                tartemp += 300
            elif p_dphsettar.np == F3:
                tartemp += 500

        # Per-candidate return policy.
        idx = index[count]
        if idx == -1:
            # Previous phone: use target or last-dip-position.
            if tartemp > 0:
                return tartemp
            if tartemp < -1:
                # Diphthongised seg: walk to the last entry of the diph
                # run and return it.
                p_diph = cast(list[int], p_dph_t.p_diph)
                while p_diph[-tartemp] != -1:
                    tartemp -= 1
                tartemp = p_diph[-tartemp - 1]
            if tartemp == -1:
                npar = p_dphsettar.np - F1
                tartemp = parini[npar]
            return tartemp
        elif idx == 0:
            # Current phone: return unless it's a sentinel.
            if tartemp != -1:
                return tartemp
        else:
            # Forward look-ahead (1 or 2): resolve diph or return value.
            if tartemp < -1:
                p_diph = cast(list[int], p_dph_t.p_diph)
                return p_diph[-tartemp]
            if tartemp > 0:
                return tartemp

        count += 1

    return 0


__all__ = ["gettar"]
