"""Phoneme-parameter PIPE packing from ``cmd/cm_phon.c``.

Architectural shim for ``cm_phon_flush`` in
``src/dapi/src/cmd/cm_phon.c`` (definition near line 365). The C
function reads accumulated phoneme parameters from
``pCmd_t->params[]``, packs them into ``DT_PIPE_T`` (unsigned 16-bit)
slots using the layout below, and writes them through
``cm_util_write_pipe`` onto ``pKsd_t->lts_pipe`` for the LTS thread to
consume. It also mutates ``pCmd_t->param_index`` /
``pCmd_t->cmd_p_flag`` / ``pCmd_t->p_count``.

Faithful translation of:

.. code-block:: c

    void cm_phon_flush(LPTTS_HANDLE_T phTTS) {
        PKSD_T pKsd_t = phTTS->pKernelShareData;
        PCMD_T pCmd_t = phTTS->pCMDThreadData;
        short temp;
        unsigned short temp2;
    #ifndef MSDOS
        unsigned int i;
        DT_PIPE_T pipe_values[NPARAM];
    #endif
        if (pCmd_t->param_index && (pKsd_t->phoneme_mode & PHONEME_SPEAK)) {
            if (pCmd_t->param_index > 3) {
                /* pipe[1] = TTTT VVVV VVVV VV_D */
                /* pipe[2] = DDDD DDDD DD_S SSSS */
                /* pipe[3] = ____ ___L LLLL LLLL */ /* full 16 bits */

                /* type */
                temp = pCmd_t->params[1] & 0x000F;
                temp <<= 10;
                pipe_values[1] = 0;
                pipe_values[1] |= temp;
                /* value */
                temp = pCmd_t->params[2];
                temp <<= 2;
                temp2 = (temp & 0x0FFC);
                pipe_values[1] |= temp2;
                /* delay */
                pipe_values[2] = 0;
                temp = pCmd_t->params[3];
                if (temp > 900) { pipe_values[1] |= 0x0001; temp -= 900; }
                if (temp < -900) { pipe_values[1] |= 0x0001; temp += 900; }
                temp <<= 6;
                pipe_values[2] |= temp;
                /* syl_count */
                temp = pCmd_t->params[5];
                temp &= 0x003F;
                pipe_values[2] |= temp;
                /* length */
                pipe_values[3] = pCmd_t->params[4];
                pCmd_t->param_index = 4;
                pCmd_t->params[1] = pipe_values[1];
                pCmd_t->params[2] = pipe_values[2];
                pCmd_t->params[3] = pipe_values[3];
            }
            if (pCmd_t->params[0] & 0xff00) {
                pCmd_t->params[0] |= ((pCmd_t->param_index - 1) << PSNEXTRA);
            } else {
                switch (pKsd_t->lang_curr) {
                case LANG_english:   pCmd_t->params[0] |= (PFUSA << PSFONT) | ...;
                case LANG_british:   pCmd_t->params[0] |= (PFUK  << PSFONT) | ...;
                case LANG_german:    pCmd_t->params[0] |= (PFGR  << PSFONT) | ...;
                case LANG_spanish:   pCmd_t->params[0] |= (PFSP  << PSFONT) | ...;
                case LANG_latin_american:
                                     pCmd_t->params[0] |= (PFLA  << PSFONT) | ...;
                case LANG_french:    pCmd_t->params[0] |= (PFFR  << PSFONT) | ...;
                }
            }
            /* write packed pipe_values[0..param_index-1] to lts_pipe */
        }
        pCmd_t->param_index = 0;
        pCmd_t->cmd_p_flag  = 0;
        pCmd_t->p_count     = 0;
    }

The Python port is **bit-for-bit faithful to the packing logic** but
deliberately **does not** touch any pCmd_t / pKsd_t state, nor write
to any pipe. Callers above this layer drive the state machine; this
function just answers "given these unpacked params and this language
code, what bit pattern should the LTS pipe see?" The post-flush
``param_index = 0`` / ``cmd_p_flag = 0`` / ``p_count = 0`` resets and
the ``phoneme_mode & PHONEME_SPEAK`` early-out are caller policy --
this helper assumes its caller already gated on those.

The C bit layout (from the function's own comments) is:

- ``pipe_values[0]``: phoneme code in the low 8 bits, font in
  ``PFONT``-shift bits (``PSFONT`` = 8), extra-slot count in
  ``PSNEXTRA``-shift bits (= 13).
- ``pipe_values[1]`` = ``TTTT VVVV VVVV VV_D``: 4 bits of *type*
  shifted by 10, 10 bits of *value* shifted by 2 (masked 0x0FFC),
  and the ``is_percent`` flag in bit 0. Note the type shift is
  ``<< 10`` (not ``<< 12``), so type and value share bits 10-11 --
  ``temp2 = temp & 0x0FFC`` deliberately masks them off the value
  side so the OR keeps the type's bits intact.
- ``pipe_values[2]`` = ``DDDD DDDD DD_S SSSS``: 10 bits of *delay*
  shifted by 6 (masked at OR time by the 16-bit pipe width) and 6
  bits of *syl_count* (``& 0x003F``).
- ``pipe_values[3]``: full 16 bits of *length* (the C comment says
  9 bits but the source assigns ``pipe_values[3] = pCmd_t->params[4]``
  with no mask, so the full 16 are passed through).

``DT_PIPE_T`` is ``unsigned short`` (``src/dapi/src/include/port.h``
line 73), so the Python port masks each slot to 16 bits the way the
C compiler would when storing the signed-short ``temp`` back into
``pipe_values[]``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dectalk.include.cmd_codes import PSFONT, PSNEXTRA
from dectalk.include.phoneme_codes import PFFR, PFGR, PFLA, PFSP, PFUK, PFUSA
from dectalk.kernel.lang_codes import (
    LANG_british,
    LANG_english,
    LANG_french,
    LANG_german,
    LANG_latin_american,
    LANG_spanish,
)

# ``DT_PIPE_T`` is ``unsigned short`` -- every pipe slot is masked to
# this width to mirror the C compiler's truncation when storing a
# signed-short ``temp`` back into the unsigned-short array.
_PIPE_MASK = 0xFFFF

# Empirical threshold from the C body: ``temp > 900`` and ``temp < -900``
# set the percent bit and adjust the delay magnitude by 900. This is the
# encoding for ``%``-suffixed phoneme delays: ``CURR_PHONE += 900`` in
# the lexer (cm_phon.c line ~342) marks them, and the flush undoes that
# offset while raising bit 0 of ``pipe_values[1]``.
_PERCENT_BIAS = 900

# The C ``if (pCmd_t->param_index > 3)`` gate controls whether the full
# PIPE-style packing kicks in. Below the gate the packed slots are
# untouched; at or above the gate type/value/delay/syl_count/length get
# squeezed into pipe_values[1..3].
_PACK_THRESHOLD = 3

# Sign-bit / wrap-around constants for the signed-short reinterpretation
# in :func:`_to_signed16`. The C ``short temp`` field is 16 bits wide.
_SIGN_BIT = 0x8000
_WRAP_RANGE = 0x10000


@dataclass
class PhonFlushPacket:
    """Packed phoneme parameters destined for the LTS pipe.

    Mirrors the in-memory contents the C ``cm_phon_flush`` would push
    onto ``pKsd_t->lts_pipe``. Only the first ``param_index`` slots of
    :attr:`params` are meaningful -- exactly as the C call
    ``cm_util_write_pipe(..., pipe_values, pCmd_t->param_index)``.

    Attributes:
        params: The four pipe slots ``pipe_values[0..3]``, each masked
            to 16 bits (``DT_PIPE_T`` = ``unsigned short``). When the
            input had ``param_index <= 3`` (no PIPE-style packing
            needed), slots 1..3 of this list copy the input params
            verbatim (also masked to 16 bits).
        param_index: How many of :attr:`params` are populated -- 1, 2,
            3, or 4. Matches the post-pack ``pCmd_t->param_index``
            value.
        language_font: The font code derived from the language argument
            (one of :data:`PFUSA` / :data:`PFUK` / :data:`PFGR` /
            :data:`PFSP` / :data:`PFLA` / :data:`PFFR`) -- already
            merged into ``params[0]`` at ``PSFONT`` position. Stored
            separately so callers can audit which font was selected
            without re-decoding the packed word.
    """

    params: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    param_index: int = 0
    language_font: int = 0


# Maps the C ``switch (pKsd_t->lang_curr)`` arms onto font codes. The
# arms with no font assignment (``LANG_japanese``, ``LANG_italian``,
# ``LANG_none``) fall through to the default, which leaves
# ``params[0]`` unchanged on the font side -- exactly as the C body's
# empty ``default:`` arm does.
_LANG_FONT: dict[int, int] = {
    LANG_english: PFUSA,
    LANG_british: PFUK,
    LANG_german: PFGR,
    LANG_spanish: PFSP,
    LANG_latin_american: PFLA,
    LANG_french: PFFR,
}


def _to_signed16(value: int) -> int:
    """Coerce ``value`` into the signed-short range the C ``temp`` uses.

    The C body declares ``short temp`` and assigns ``params[N]`` to it.
    ``params[]`` is ``unsigned short`` storage that the compiler
    reinterprets as signed when copied into ``temp`` -- so e.g. 0x8000
    becomes -32768 and the ``temp > 900`` / ``temp < -900`` checks fire
    differently depending on the sign. The Python port mirrors that
    reinterpretation before applying the percent-bias adjustment.
    """
    value &= _PIPE_MASK
    if value >= _SIGN_BIT:
        value -= _WRAP_RANGE
    return value


def cm_phon_flush(params: list[int], language: int) -> PhonFlushPacket:
    """Pack accumulated phoneme parameters into the LTS-pipe layout.

    Mirrors the bit-twiddling in ``cm_phon_flush`` without mutating any
    inter-thread state. The caller is expected to have already checked
    that ``pCmd_t->param_index`` is non-zero and
    ``pKsd_t->phoneme_mode & PHONEME_SPEAK`` is set -- this helper
    unconditionally produces the would-be pipe payload.

    Args:
        params: The unpacked ``pCmd_t->params[0..5]`` slots:

            * ``params[0]`` -- phoneme code (low 8 bits) plus any
              pre-existing font/extra bits (high 8 bits). If the high
              byte is non-zero, the font dispatch is skipped (matches
              the C ``if (pCmd_t->params[0] & 0xff00)`` shortcut).
            * ``params[1]`` -- 4-bit *type* field.
            * ``params[2]`` -- 10-bit *value* field (signed).
            * ``params[3]`` -- 10-bit *delay* (positive or negative);
              magnitudes greater than 900 set the percent bit and the
              magnitude is reduced by 900.
            * ``params[4]`` -- *length* (full 16 bits passed through).
            * ``params[5]`` -- 6-bit *syl_count* (the C masks
              ``& 0x003F`` -- so the practical width is 6 bits even
              though the comment says 5).

            The length of ``params`` is the C ``param_index`` -- 1,
            2, 3, or 4-and-above. The "above-3" branch reads all six
            slots; anything in 1..3 only consults ``params[0]``.
        language: One of the ``LANG_*`` constants from
            :mod:`dectalk.kernel.lang_codes`. Languages without a font
            mapping (``LANG_japanese``, ``LANG_italian``,
            ``LANG_none``) leave the font field alone -- matching the
            C ``switch``'s empty ``default:`` arm.

    Returns:
        A :class:`PhonFlushPacket` whose first ``param_index`` slots
        carry the would-be pipe bytes. ``param_index`` is 4 if the
        caller passed enough params to trigger packing; otherwise it
        is ``len(params)`` (the C drops back through with the
        untouched slots).
    """
    if not params:
        return PhonFlushPacket(params=[0, 0, 0, 0], param_index=0, language_font=0)

    param_index = len(params)

    # Start with the four pipe slots zero-initialised. Slots beyond
    # the active prefix stay at zero -- the C never reads them.
    pipe_values = [0, 0, 0, 0]
    pipe_values[0] = params[0] & _PIPE_MASK

    if param_index > _PACK_THRESHOLD:
        # ---- type field: ``temp = params[1] & 0x000F; temp <<= 10`` ----
        # The 4-bit type goes into bits 10..13 of pipe[1] -- note this
        # is ``<< 10`` (not ``<< 12``) per the C source; the value
        # field's ``& 0x0FFC`` mask is what keeps the two from
        # clobbering each other.
        temp = params[1] & 0x000F
        temp <<= 10
        pipe1 = temp & _PIPE_MASK

        # ---- value field: ``temp = params[2]; temp <<= 2; temp & 0x0FFC`` ----
        temp = _to_signed16(params[2])
        temp <<= 2
        temp2 = temp & 0x0FFC
        pipe1 |= temp2

        # ---- delay field: percent handling + ``<<= 6`` ----
        temp = _to_signed16(params[3])
        if temp > _PERCENT_BIAS:
            pipe1 |= 0x0001
            temp -= _PERCENT_BIAS
        if temp < -_PERCENT_BIAS:
            pipe1 |= 0x0001
            temp += _PERCENT_BIAS
        temp <<= 6
        pipe2 = temp & _PIPE_MASK

        # ---- syl_count field: ``temp = params[5]; temp &= 0x003F`` ----
        temp = _to_signed16(params[5])
        temp &= 0x003F
        pipe2 |= temp & _PIPE_MASK

        # ---- length field: full 16 bits of params[4] ----
        pipe3 = params[4] & _PIPE_MASK

        pipe_values[1] = pipe1 & _PIPE_MASK
        pipe_values[2] = pipe2 & _PIPE_MASK
        pipe_values[3] = pipe3 & _PIPE_MASK

        # C sets pCmd_t->param_index = 4 here. In the Python port we
        # surface that via PhonFlushPacket.param_index so callers can
        # see the post-pack slot count without inspecting pCmd_t.
        param_index = 4
    else:
        # No packing -- forward params[1..param_index-1] verbatim (the
        # C's ``pipe_values[i] = pCmd_t->params[i]`` fall-through loop
        # at the bottom of the function), all masked to 16 bits.
        for i in range(1, min(param_index, 4)):
            pipe_values[i] = params[i] & _PIPE_MASK

    # ---- params[0] font / extra-slot field ----
    # If the high byte is already non-zero the C skips the font
    # dispatch (the caller has pre-assembled the font); otherwise it
    # ORs in the language-derived font in PSFONT position.
    language_font = 0
    p0 = pipe_values[0]
    if p0 & 0xFF00:
        p0 |= ((param_index - 1) << PSNEXTRA) & _PIPE_MASK
    else:
        font = _LANG_FONT.get(language, 0)
        if font:
            language_font = font
            p0 |= ((font << PSFONT) | ((param_index - 1) << PSNEXTRA)) & _PIPE_MASK
    pipe_values[0] = p0 & _PIPE_MASK

    return PhonFlushPacket(
        params=pipe_values,
        param_index=param_index,
        language_font=language_font,
    )


__all__ = ["PhonFlushPacket", "cm_phon_flush"]
