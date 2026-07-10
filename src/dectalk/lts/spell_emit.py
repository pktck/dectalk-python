"""Spell-out emission from ls_spel.c::ls_spel_spell.

Translated from ``src/dapi/src/lts/ls_spel.c``:

- :func:`ls_spel_spell` — emit the phoneme sequence for each
  letter / digit of a word spelled out one-character-at-a-time
  (e.g. ``AT&T`` → "ay tee ampersand tee").
"""

from __future__ import annotations

from dectalk.include.phoneme_codes import S1, WBOUND, USPhoneme
from dectalk.include.usa_phon_tables import NULL_ASCKY, usa_ascky_rev
from dectalk.kernel.usa_tables import usa_type
from dectalk.lts.char_features import ls_lower
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.math_mode import do_math
from dectalk.lts.phoneme_words import punits

_US_EY: int = int(USPhoneme.EY)


def ls_spel_spell(emitter: LtsEmitter, word: bytes, *, math_mode: bool = False) -> None:
    """Emit the phoneme sequence for each character in ``word``.

    Faithful translation of:

    .. code-block:: c

        void ls_spel_spell(LPTTS_HANDLE_T phTTS, LETTER *lp1, LETTER *lp2) {
            while (lp1 < lp2) {
                if (ls_math_do_math(pKsd_t, lp1->l_ch) == false) {
                    c = ls_lower[lp1->l_ch];
                    if (c == 'a') {                    // ENGLISH_US special
                        ls_util_send_phone(phTTS, S1);
                        ls_util_send_phone(phTTS, US_EY);
                    } else if (c >= '0' && c <= '9') {
                        ls_util_send_phone_list(phTTS,
                                                 punits[c - '0']);
                    } else {
                        for (tp = pKsd_t->typing_table[c]; *tp; tp++) {
                            phone = pKsd_t->reverse_ascky[*tp];
                            ls_util_write_pipe(pKsd_t, &phone, 1);
                        }
                    }
                }
                ++lp1;
                if (lp1 != lp2) ls_util_send_phone(phTTS, WBOUND);
            }
        }

    Special case: the letter ``a`` always emits ``S1 US_EY`` (the
    ASCII letter A is stressed differently from the article "a").
    All other letters use the typing table (``usa_type``) which
    maps each character to a sequence of ASCKY glyphs.

    The C ``ls_math_do_math`` call is a no-op unless the kernel's
    ``MODE_MATH`` flag is set (``ls_math.c:83`` returns false before
    consulting the symbol table otherwise). MODE_MATH is **off** by
    default, so ``-`` spells as "dash" (``usa_type`` row 0x2D) rather
    than the math-mode "minus". Pass ``math_mode=True`` to model a
    ``[:mode math on]`` session.

    Args:
        emitter: The LTS emitter state.
        word: The word to spell out, as bytes.
        math_mode: Mirror of ``pKsd_t->modeflag & MODE_MATH``.
    """
    for i, ch in enumerate(word):
        # Math symbols get their dedicated phoneme sequence — but only
        # when MODE_MATH is on, exactly as ls_math_do_math gates it.
        math_phones = do_math(ch) if math_mode else None
        if math_phones:
            for p in math_phones:
                emitter.send_phone(p)
        else:
            folded = ls_lower[ch]
            if folded == ord("a"):
                emitter.send_phone(S1)
                emitter.send_phone(_US_EY)
            elif ord("0") <= folded <= ord("9"):
                emitter.send_phone_list(punits[folded - ord("0")])
            elif folded < len(usa_type):
                # Use usa_type to look up the ASCKY glyph string.
                glyphs = usa_type[folded]
                for glyph in glyphs.encode("latin-1", errors="replace"):
                    if glyph == 0:
                        break
                    if glyph >= len(usa_ascky_rev):
                        continue
                    code = usa_ascky_rev[glyph]
                    if code != NULL_ASCKY:
                        emitter.send_phone(code)

        # WBOUND between letters (but not after the last).
        if i + 1 < len(word):
            emitter.send_phone(WBOUND)


__all__ = ["ls_spel_spell"]
