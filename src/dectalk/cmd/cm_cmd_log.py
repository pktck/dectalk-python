"""``[:log]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 286-425.

The ``[:log <category> on|off|set]`` command opens, closes, or sets
a debug log capturing one of six categories (text, phonemes,
name-types, form-types, syllables, outphon). On Linux the body
fans out into ``OpenLogFile`` / ``CloseLogFile`` / ``OpenDbgLogFile``
/ ``CloseDbgLogFile`` and toggles bits in ``pKsd_t->logflag``.

None of these surfaces exist in the Python port yet:

* ``pKsd_t->logflag`` — no Python debug-log bitfield.
* ``OpenLogFile`` / ``CloseLogFile`` — sit on the deferred
  allow-list in :mod:`tests.unit.test_cmd_module_inventory`.
* ``OpenDbgLogFile`` / ``CloseDbgLogFile`` — likewise deferred.

The Python port therefore reduces to a no-op returning
:data:`CMD_success` until the log infrastructure lands.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT


def cm_cmd_log(p_cmd_t: CmdT) -> int:
    """Apply ``[:log ...]`` — no-op until the Python log surface lands.

    Faithful summary of:

    .. code-block:: c

        int cm_cmd_log(LPTTS_HANDLE_T phTTS) {
            int i, value;
            unsigned int flag_mask;
            PKSD_T pKsd_t = phTTS->pKernelShareData;
            PCMD_T pCmd_t = phTTS->pCMDThreadData;

            if (cm_cmd_sync(phTTS) == CMD_flushing)
                return CMD_flushing;

            flag_mask = 0;
            for (i = 0; i < pCmd_t->param_index; i++) {
                value = cm_util_string_match(log_options, pCmd_t->pString[i]);
                if (value == NO_STRING_MATCH) return CMD_bad_string;
                switch (i) {
                  case 0:  // category: text / phonemes / name_types /
                           //           form_types / syllables / outphon / dbglog
                    switch (value) {
                      case 0: flag_mask |= LOG_TEXT; break;
                      case 1: flag_mask |= LOG_PHONEMES; break;
                      case 2: flag_mask |= LOG_NAME_TYPES; break;
                      case 3: flag_mask |= LOG_FORM_TYPES; break;
                      case 4: flag_mask |= LOG_SYLLABLES; break;
                      case 5: flag_mask |= LOG_OUTPHON; break;
                      case 6: flag_mask |= LOG_DBGLOG; break;
                      default: return CMD_bad_param;
                    }
                    break;
                  case 1:  // action: on / off / set
                    switch (value) {
                      case 7:  /* on */  ...OpenLogFile / OpenDbgLogFile...
                                          pKsd_t->logflag |= flag_mask; break;
                      case 8:  /* off */ ...CloseLogFile / CloseDbgLogFile...
                                          pKsd_t->logflag &= ~flag_mask; break;
                      case 9:  /* set */ ...OpenLogFile...
                                          pKsd_t->logflag = flag_mask; break;
                      default: return CMD_bad_param;
                    }
                    break;
                  default: return CMD_bad_param;
                }
            }
            return CMD_success;
        }

    The Python port defers the entire body — the underlying log-file
    helpers (``OpenLogFile``, ``CloseLogFile``, ``OpenDbgLogFile``,
    ``CloseDbgLogFile``) and the ``pKsd_t->logflag`` bitfield are
    not modelled. The handler is preserved so command-table dispatch
    doesn't break when a ``[:log ...]`` command is parsed; it simply
    accepts the command without effect.

    Args:
        p_cmd_t: CMD thread state (unused — kept for signature
            parity with the surrounding handlers).

    Returns:
        :data:`CMD_success` unconditionally.
    """
    _ = p_cmd_t  # Deferred until Python gains a debug-log surface.
    return CMD_success


__all__ = ["cm_cmd_log"]
