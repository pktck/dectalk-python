"""Parser state-machine transitions from cm_pars.c.

Translated from ``src/dapi/src/cmd/cm_pars.c`` lines 1699-1734
and ``cm_cmd.c`` lines 766-799.

Two state-mutating helpers the inline-command parser uses to
move between parse states:

- :func:`cm_pars_new_state` — install a new ``STATE_*`` value
  with the special-case rule that ``STATE_TOSS`` after ``']'``
  bumps the state back to ``STATE_NORMAL``.
- :func:`cm_cmd_reset_comm` — clear the parser's per-command
  scratch state (params / defaults / match-array) and dispatch
  through :func:`cm_pars_new_state`.

Both functions take a :class:`dectalk.cmd.cmd_t.CmdT` instance
and mutate it in-place. The C source has a couple of
PARSER_HACK_FOR_OLD_SONGS branches that we mirror exactly.
"""

from __future__ import annotations

from dectalk.cmd.cmd_states import STATE_KEEP, STATE_NORMAL, STATE_PARAM, STATE_TOSS
from dectalk.cmd.cmd_t import CmdT
from dectalk.include.dectalk import NPARAM


def cm_pars_new_state(p_cmd_t: CmdT, state: int) -> None:
    """Install ``state`` as ``p_cmd_t.parse_state``, with the ``']'`` fix-up.

    Faithful translation of:

    .. code-block:: c

        void cm_pars_new_state(PCMD_T pCmd_t, int state) {
            pCmd_t->p_count = 0;
            pCmd_t->cmd_p_flag = 0;
            // PARSER_HACK_FOR_OLD_SONGS clears hold_* fields here.

            if (state == STATE_PARAM && pCmd_t->parse_state == STATE_PARAM) {
                (pCmd_t->param_index) += 1;
            }
            if (state == STATE_TOSS && pCmd_t->last_char == ']') {
                pCmd_t->parse_state = STATE_NORMAL;
            } else {
                pCmd_t->parse_state = state;
            }
        }

    Args:
        p_cmd_t: CMD thread-state instance to mutate.
        state: New parser state (one of the ``STATE_*`` constants).
    """
    p_cmd_t.p_count = 0
    p_cmd_t.cmd_p_flag = 0
    # PARSER_HACK_FOR_OLD_SONGS would reset hold_phonemes / hold_count /
    # hold_replay_ignore here; the Linux build doesn't define it.

    if state == STATE_PARAM and p_cmd_t.parse_state == STATE_PARAM:
        p_cmd_t.param_index += 1

    if state == STATE_TOSS and p_cmd_t.last_char == ord("]"):
        p_cmd_t.parse_state = STATE_NORMAL
    else:
        p_cmd_t.parse_state = state


def cm_cmd_reset_comm(
    p_cmd_t: CmdT,
    state: int,
    total_commands: int = 0,
) -> None:
    """Reset CMD-parser scratch state and install a new parser state.

    Faithful translation of:

    .. code-block:: c

        void cm_cmd_reset_comm(PCMD_T pCmd_t, unsigned int state) {
            int i;
            if (state != STATE_KEEP) {
                for (i = 0; i < NPARAM; i++)
                    pCmd_t->defaults[i] = TRUE;
                for (i = 0; i < total_commands; i++)
                    *((pCmd_t->cm) + i) = 0;
                pCmd_t->total_matches = total_commands;
                cm_pars_new_state(pCmd_t, state);
                pCmd_t->format_index = 0;
            }
            pCmd_t->next_char = 0;
            pCmd_t->param_index = 0;
            pCmd_t->cmd_p_flag = 0;
            pCmd_t->q_flag = 0;
            pCmd_t->p_count = 0;
            pCmd_t->international_flag = -1;
            pCmd_t->international_temp = 0;
            pCmd_t->international_phon_lang = -1;
        }

    The C source's ``total_commands`` is a file-scope global set
    by the language-init code; we pass it as an argument since
    Python doesn't have C-style externs.

    Args:
        p_cmd_t: CMD thread-state instance to mutate.
        state: New parser state. If ``STATE_KEEP``, the
            per-command match array is preserved (only the
            character-position counters reset).
        total_commands: Number of installed command-table entries
            (size of the ``cm`` match array). Defaults to ``len(cm)``.
    """
    if state != STATE_KEEP:
        # Reset per-param defaults flags to TRUE (= 1).
        if len(p_cmd_t.defaults) < NPARAM:
            p_cmd_t.defaults.extend([0] * (NPARAM - len(p_cmd_t.defaults)))
        for i in range(NPARAM):
            p_cmd_t.defaults[i] = 1

        # Clear the per-command match array.
        n_commands = total_commands or len(p_cmd_t.cm)
        if len(p_cmd_t.cm) < n_commands:
            p_cmd_t.cm.extend([0] * (n_commands - len(p_cmd_t.cm)))
        for i in range(n_commands):
            p_cmd_t.cm[i] = 0

        p_cmd_t.total_matches = n_commands
        cm_pars_new_state(p_cmd_t, state)
        p_cmd_t.format_index = 0

    # Always reset character / parameter cursors.
    p_cmd_t.next_char = 0
    p_cmd_t.param_index = 0
    p_cmd_t.cmd_p_flag = 0
    p_cmd_t.q_flag = 0
    p_cmd_t.p_count = 0
    p_cmd_t.international_flag = -1
    p_cmd_t.international_temp = 0
    p_cmd_t.international_phon_lang = -1


__all__ = ["cm_cmd_reset_comm", "cm_pars_new_state"]
