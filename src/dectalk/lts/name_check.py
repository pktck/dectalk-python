"""ACNA name-detection helper from ls_util.c.

Translated from ``src/dapi/src/lts/ls_util.c`` lines 451-482.

:func:`ls_util_is_name` decides whether a word looks like a
proper-name candidate so the LTS engine can route it through the
ACNA (Automatic Computer Name Analyser) name-pronunciation
sub-system instead of the regular LTS rules.

The C source has a multi-stage decision:

- If ``MODE_NAME`` is *off*, every word is treated as a name
  (the engine doesn't try to filter).
- If the previous preamble command was 3 (``[:name on]`` /
  ``[:dv ...]`` etc.), force-mark the word a name.
- If ``PRON_ACNA_NAME`` is already set, the answer is yes.
- Otherwise, names must be at non-zero word position, have a
  capitalised first letter (``A``-``Z`` or accented variants),
  and lowercase tail.

The non-ACNA branch (i.e. when ``ACNA`` is not compiled in)
always returns ``False``.
"""

from __future__ import annotations

from dectalk.kernel.mode_flags import MODE_NAME, PRON_ACNA_NAME


def ls_util_is_name(  # noqa: PLR0911 — faithful C control-flow with multiple early returns
    word: bytes,
    *,
    mode_flag: int = 0,
    pron_flag: int = 0,
    last_preamble_command: int = 0,
    cur_word_index: int = 0,
    acna_enabled: bool = True,
) -> tuple[bool, int]:
    """Return ``(is_name, new_pron_flag)`` per ls_util_is_name semantics.

    Faithful translation of:

    .. code-block:: c

        int ls_util_is_name(LPTTS_HANDLE_T phTTS, LETTER *llp, LETTER *rlp) {
        #ifdef ACNA
            // ... uses pKsd_t->pronflag / pKsd_t->modeflag / last_preamble_command
        #else
            return FALSE;
        #endif
        }

    The Python port returns a tuple ``(is_name, new_pron_flag)``:
    the C side mutates ``pKsd_t->pronflag`` to set
    :data:`PRON_ACNA_NAME` on a True result, so we return the
    updated flag too.

    Args:
        word: The word's bytes (the C source iterates the
            ``llp..rlp`` LETTER range; we accept the raw bytes
            for parity).
        mode_flag: Current ``pKsd_t->modeflag`` value.
        pron_flag: Current ``pKsd_t->pronflag`` value.
        last_preamble_command: Most-recent preamble command code;
            value 3 = ``[:name on]`` and forces name detection.
        cur_word_index: Index of the current word in the clause
            (0 = first word; first word is never a name).
        acna_enabled: Whether the ACNA build is compiled in (the
            ``#ifdef ACNA`` branch). When False, always returns
            ``(False, pron_flag)`` per the C source's else branch.

    Returns:
        Tuple ``(is_name, new_pron_flag)``.
    """
    if not acna_enabled:
        return False, pron_flag

    if pron_flag & PRON_ACNA_NAME:
        return True, pron_flag

    if last_preamble_command == 3:  # noqa: PLR2004 — preamble-command code from C
        return True, pron_flag | PRON_ACNA_NAME

    if (mode_flag & MODE_NAME) == 0:
        return True, pron_flag

    if cur_word_index == 0:
        return False, pron_flag

    if not word:
        return False, pron_flag

    # C source: '(*llp).l_ch < 64 || (*llp).l_ch > 97' for first char.
    # This is the range A..Z (0x40..0x60) - the conditional is odd but faithful.
    first = word[0]
    if first < 64 or first > 97:  # noqa: PLR2004 — uppercase range from C
        return False, pron_flag

    # Tail must be lowercase a..z (0x61..0x7A) per the C source.
    for ch in word[1:]:
        if ch > 122 or ch < 97:  # noqa: PLR2004 — lowercase range from C
            return False, pron_flag

    return True, pron_flag | PRON_ACNA_NAME


__all__ = ["ls_util_is_name"]
