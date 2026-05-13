"""``[:remove]`` command handler from cmd/cm_copt.c.

Translated from ``src/dapi/src/cmd/cm_copt.c`` lines 1836-1858.

The ``[:remove]`` command tears down the currently-loaded language:
clears the language's ``lang_ready`` bit, signals the LTS / PH
worker threads to terminate via a ``KILL_TASK`` pipe write, and
nulls the per-thread pipe references on ``pKsd_t``.

In the Linux build the ``#else`` branch hard-codes
``LANG_english`` for ``lang_ready``; the Python port follows that
behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dectalk.cmd.cmd_states import CMD_success
from dectalk.include.cmd_codes import KILL_TASK
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english

if TYPE_CHECKING:
    from collections.abc import Callable


def _no_pipe_write(_pipe: object, _phone: int) -> None:
    """Default LTS-pipe sink — silently drops the KILL_TASK signal."""


def cm_cmd_remove(
    p_ksd_t: KsdT,
    *,
    lts_pipe_write: Callable[[object, int], None] = _no_pipe_write,
) -> int:
    """Tear down the current language and signal the LTS / PH threads.

    Faithful translation of the non-MSDOS branch of:

    .. code-block:: c

        int cm_cmd_remove(PKSD_T pKsd_t) {
            DT_PIPE_T pipe_value;
            pKsd_t->lang_ready[LANG_english] = 0;
            pipe_value = KILL_TASK;
            cm_util_write_pipe(pKsd_t, pKsd_t->lts_pipe, &pipe_value, 1);
            pKsd_t->lts_pipe = NULL_PIPE;
            pKsd_t->ph_pipe = NULL_PIPE;
            return CMD_success;
        }

    The C source's inter-thread pipe write is modelled as a
    callable so tests can verify the signal without needing real
    pipe infrastructure.

    Args:
        p_ksd_t: Kernel shared-data struct to mutate.
        lts_pipe_write: Optional sink for the KILL_TASK signal.
            Defaults to a no-op. Called as
            ``lts_pipe_write(pKsd_t.lts_pipe, KILL_TASK)``.

    Returns:
        :data:`CMD_success` (the C source has no error path).
    """
    p_ksd_t.lang_ready[LANG_english] = 0
    lts_pipe_write(p_ksd_t.lts_pipe, KILL_TASK)
    p_ksd_t.lts_pipe = None  # NULL_PIPE
    p_ksd_t.ph_pipe = None  # NULL_PIPE
    return CMD_success


__all__ = ["cm_cmd_remove"]
