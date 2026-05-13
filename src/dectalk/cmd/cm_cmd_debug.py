"""``[:debug]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 3554-3564.

The ``[:debug <n>]`` command stores its single integer parameter in
``pKsd_t->debug_switch`` (a bitfield read by various ``#ifdef
PH_DEBUG`` / ``#ifdef LTSDBG`` instrumentation points in the C
sources). It also calls ``cm_cmd_sync`` once on entry to flush any
pending text through the LTS pipe before the new debug mask takes
effect.

Both dependencies are deferred in the Python port:

* ``cm_cmd_sync`` — the inter-thread CMD barrier is a no-op in the
  synchronous Python pipeline.
* ``pKsd_t->debug_switch`` — there is no Python debug-switch surface;
  the C source's debug bits gate ``#ifdef``-only ``fprintf`` calls
  that don't compile into ``libtts_us.so`` either.

The Python port therefore reduces to a no-op returning
:data:`CMD_success`. The function's signature still accepts a
:class:`CmdT` so the parsed parameter is observable in tests.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import CMD_success
from dectalk.cmd.cmd_t import CmdT


def cm_cmd_debug(p_cmd_t: CmdT) -> int:
    """Apply ``[:debug <n>]`` — no-op on Linux build.

    Faithful translation of:

    .. code-block:: c

        int cm_cmd_debug(LPTTS_HANDLE_T phTTS) {
            PKSD_T pKsd_t = phTTS->pKernelShareData;
            PCMD_T pCmd_t = phTTS->pCMDThreadData;

            cm_cmd_sync(phTTS);            /* mfg 04/27/1998 */
            pKsd_t->debug_switch = pCmd_t->params[0];
            //cm_cmd_sync(phTTS);

            return(CMD_success);
        }

    The C body is mostly flag-setting: a sync barrier (no-op in
    Python) followed by ``pKsd_t->debug_switch = params[0]``. Since
    ``debug_switch`` has no Python surface — the C bits gate
    debug-only ``#ifdef PH_DEBUG`` instrumentation that doesn't
    compile into ``libtts_us.so`` — the Python port reduces to
    ``return CMD_success``.

    Args:
        p_cmd_t: CMD thread state. ``p_cmd_t.params[0]`` would carry
            the new debug-switch mask in the C build; the Python
            port reads it but discards it (kept for signature
            parity).

    Returns:
        :data:`CMD_success` unconditionally.
    """
    _ = p_cmd_t  # Linux body's only effect is on a non-Python-surfaced flag.
    return CMD_success


__all__ = ["cm_cmd_debug"]
