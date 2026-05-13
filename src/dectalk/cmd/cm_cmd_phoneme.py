"""``[:phoneme <mode>...]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 226-263.

The ``[:phoneme]`` command takes one or more keyword arguments and
sets / clears bits in ``pKsd_t->phoneme_mode``:

- ``ascky``  → set PHONEME_ASCKY (phoneme-input-as-DECtalk-ASCII)
- ``arpabet`` → clear PHONEME_ASCKY (default: phoneme-input-as-ARPABET)
- ``speak`` → set PHONEME_SPEAK   (speak phonemes aloud)
- ``silent`` → clear PHONEME_SPEAK (suppress phoneme speech)
- ``off``  → set PHONEME_OFF      (don't interpret phoneme syntax)
- ``on``   → clear PHONEME_OFF    (do interpret phoneme syntax)
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import (
    PHONEME_ASCKY,
    PHONEME_OFF,
    PHONEME_SPEAK,
    CMD_bad_param,
    CMD_bad_string,
    CMD_success,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.cmd.option_tables import phoneme_modes
from dectalk.cmd.string_match import NO_STRING_MATCH, cm_util_string_match
from dectalk.kernel.ksd_t import KsdT

_PHONEME_MODES_BYTES: tuple[bytes, ...] = tuple(s.encode("latin-1") for s in phoneme_modes)


def cm_cmd_phoneme(p_ksd_t: KsdT, p_cmd_t: CmdT) -> int:
    """Apply each ``[:phoneme]`` keyword to ``pKsd_t->phoneme_mode``.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_phoneme(LPTTS_HANDLE_T phTTS) {
            for (i = 0; i < pCmd_t->param_index; i++) {
                value = cm_util_string_match(phoneme_modes, pCmd_t->pString[i]);
                if (value == NO_STRING_MATCH) return CMD_bad_string;
                switch (value) {
                    case 0: pKsd_t->phoneme_mode |=  PHONEME_ASCKY; break; // ascky
                    case 1: pKsd_t->phoneme_mode &= ~PHONEME_ASCKY; break; // arpa
                    case 2: pKsd_t->phoneme_mode |=  PHONEME_SPEAK; break; // speak
                    case 3: pKsd_t->phoneme_mode &= ~PHONEME_SPEAK; break; // silent
                    case 4: pKsd_t->phoneme_mode |=  PHONEME_OFF;   break; // off
                    case 5: pKsd_t->phoneme_mode &= ~PHONEME_OFF;   break; // on
                    default: return CMD_bad_param;
                }
            }
            return CMD_success;
        }

    Args:
        p_ksd_t: Kernel shared-data struct to mutate.
        p_cmd_t: CMD thread state with the parsed parameters.

    Returns:
        :data:`CMD_success` on success;
        :data:`CMD_bad_string` if any keyword is unknown;
        :data:`CMD_bad_param` if the match index is outside the
        switch range (shouldn't happen with the canonical table).
    """
    int_mask = 0xFFFFFFFF  # Emulate C's 32-bit unsigned int AND/OR/NOT.
    for i in range(p_cmd_t.param_index):
        if i >= len(p_cmd_t.pString):
            break  # Defensive: parser shouldn't promise more than it has.
        value = cm_util_string_match(_PHONEME_MODES_BYTES, p_cmd_t.pString[i])
        if value == NO_STRING_MATCH:
            return CMD_bad_string
        if value == 0:  # ascky
            p_ksd_t.phoneme_mode |= PHONEME_ASCKY
        elif value == 1:  # arpabet
            p_ksd_t.phoneme_mode &= (~PHONEME_ASCKY) & int_mask
        elif value == 2:  # speak  # noqa: PLR2004
            p_ksd_t.phoneme_mode |= PHONEME_SPEAK
        elif value == 3:  # silent  # noqa: PLR2004
            p_ksd_t.phoneme_mode &= (~PHONEME_SPEAK) & int_mask
        elif value == 4:  # off  # noqa: PLR2004
            p_ksd_t.phoneme_mode |= PHONEME_OFF
        elif value == 5:  # on  # noqa: PLR2004
            p_ksd_t.phoneme_mode &= (~PHONEME_OFF) & int_mask
        else:
            return CMD_bad_param
    return CMD_success


__all__ = ["cm_cmd_phoneme"]
