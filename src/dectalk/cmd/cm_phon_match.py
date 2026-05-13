"""``cm_phon_match`` from ``cmd/cm_phon.c``.

Architectural shim for ``src/dapi/src/cmd/cm_phon.c`` lines 765-999.

The C body is the per-character entry point of the phoneme-input state
machine. It dispatches the next character ``c`` to:

* the hold-buffer / replay machinery (when an uncertain phoneme is in
  progress);
* :func:`cm_phon_param_check` (parameter-list arms inside
  ``[:phoneme N V D L S]``);
* the international/language-prefix arm (matching :func:`cm_phon_check`
  but with side effects);
* the ARPA lookup against the active ``q_flag`` (and
  :func:`cm_phon_flush` to push the resolved phoneme onto the LTS pipe).

Because the synchronous Python phoneme pipeline processes whole strings
in one shot, this module ports the **structural decisions** of the C
function but does not drive the inter-thread pipe writes itself.
Callers wire it up by:

* passing an immutable :class:`PhonMatchInput` snapshot of the C-source
  ``pCmd_t`` / ``pKsd_t`` fields the body reads;
* providing callbacks for the side-effects:
  :data:`ArpaLookup` / :data:`LanguageLookup` (lookups),
  :data:`AscLookup` (ASCKY lookup),
  :data:`PhonemeParamCheck` (the ``cm_phon_param_check`` test),
  :data:`PhonFlushCallback` / :data:`ErrorCallback` /
  :data:`NewStateCallback` / :data:`ResetCommCallback` for the
  state-changing back-edges;
* receiving a :class:`PhonMatchResult` with the updated state slots and
  the set of side-effects requested.

The Python port intentionally collapses the ``PARSER_HACK_FOR_OLD_SONGS``
hold-buffer arm into a single ``replay_buffer`` callback so the caller
controls whether and how to replay -- the C source recursively calls
back into ``cm_phon_match`` while the buffer drains, which doesn't fit
the synchronous Python pipeline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dectalk.cmd.cmd_states import (
    PHONEME_ASCKY,
    STATE_COMMAND,
    STATE_NORMAL,
    STATE_TOSS,
    CMD_bad_phoneme,
)
from dectalk.cmd.uncertain_phones import check_uncertain_phones
from dectalk.include.ascii_control import CR, LF

_NO_INTL: int = -1

# ``cm_phon_lookup_arpa`` return codes.
_ARPA_NO_MATCH: int = 0
_ARPA_MATCH_ONE: int = 1
_ARPA_MATCH_TWO: int = 2


@dataclass
class PhonMatchInput:
    """Snapshot of the ``pCmd_t`` / ``pKsd_t`` fields ``cm_phon_match`` reads.

    Attributes:
        c: Current phoneme-input character.
        text_flush: ``pKsd_t->text_flush`` -- short-circuits to return.
        phoneme_mode: ``pKsd_t->phoneme_mode`` (bitfield).
        param_index: ``pCmd_t->param_index``.
        q_flag: ``pCmd_t->q_flag``.
        international_flag: ``pCmd_t->international_flag``.
        international_temp: ``pCmd_t->international_temp``.
        international_phon_lang: ``pCmd_t->international_phon_lang``.
        hold_replay_ignore: ``pCmd_t->hold_replay_ignore`` -- when set,
            uncertain-phoneme re-capture is suppressed.
        hold_phonemes: ``pCmd_t->hold_phonemes`` -- when set, replay is
            in progress.
        hold_count: ``pCmd_t->hold_count`` -- bytes in the hold buffer.
        hold_strbuf_capacity: ``sizeof(pCmd_t->hold_strbuf)`` -- 4096
            in C (the cap-check ``hold_count >= sizeof(hold_strbuf) - 1``
            triggers an immediate replay).
    """

    c: int
    text_flush: int = 0
    phoneme_mode: int = 0
    param_index: int = 0
    q_flag: int = 0
    international_flag: int = _NO_INTL
    international_temp: int = 0
    international_phon_lang: int = _NO_INTL
    hold_replay_ignore: int = 0
    hold_phonemes: int = 0
    hold_count: int = 0
    hold_strbuf_capacity: int = 4096


@dataclass
class PhonMatchResult:
    """Outcome of running :func:`cm_phon_match`.

    Attributes:
        q_flag: Updated ``q_flag`` value.
        international_flag: Updated ``international_flag``.
        international_temp: Updated ``international_temp``.
        international_phon_lang: Updated ``international_phon_lang``.
        hold_phonemes: Updated ``hold_phonemes``.
        hold_count: Updated ``hold_count``.
        error_code: ``CMD_bad_phoneme`` when an error path was taken,
            otherwise ``0``.
        new_state: A ``STATE_*`` value when the C body called
            :func:`cm_pars_new_state` -- otherwise ``-1``.
        reset_state: A ``STATE_*`` value when the C body called
            :func:`cm_cmd_reset_comm` -- otherwise ``-1``.
        flushed: ``True`` if a :func:`cm_phon_flush` call was emitted.
        replay_requested: ``True`` if the body executed the hold-buffer
            replay (caller should drive :func:`replay_buffer`).
    """

    q_flag: int = 0
    international_flag: int = _NO_INTL
    international_temp: int = 0
    international_phon_lang: int = _NO_INTL
    hold_phonemes: int = 0
    hold_count: int = 0
    error_code: int = 0
    new_state: int = -1
    reset_state: int = -1
    flushed: bool = False
    replay_requested: bool = False


# Callback signatures.
ArpaLookup = Callable[[int, int], tuple[int, int]]
"""``(ph1, ph2) -> (match_len, phone_code)`` -- see :func:`cm_phon_lookup_arpa`."""

LanguageLookup = Callable[[int, int], int]
"""``(ph1, ph2) -> language_index_or_-1`` -- see :func:`cm_phon_lookup_language`."""

AscLookup = Callable[[int], int]
"""``(ph) -> index_or_-1`` -- see :func:`cm_phon_lookup_asc`."""

PhonemeParamCheck = Callable[[int], bool]
"""``(c) -> bool`` -- see ``cm_phon_param_check``."""

PhonFlushCallback = Callable[[], None]
"""``() -> None`` -- driver for :func:`cm_phon_flush`."""

ErrorCallback = Callable[[int], None]
"""``(error_code) -> None`` -- driver for :func:`cm_cmd_error_comm`."""

NewStateCallback = Callable[[int], None]
"""``(state) -> None`` -- driver for :func:`cm_pars_new_state`."""

ResetCommCallback = Callable[[int], None]
"""``(state) -> None`` -- driver for :func:`cm_cmd_reset_comm`."""


def cm_phon_match(  # noqa: PLR0912, PLR0915 — faithful translation of a 234-line C function with deeply nested branches
    inp: PhonMatchInput,
    *,
    arpa_lookup: ArpaLookup,
    language_lookup: LanguageLookup,
    asc_lookup: AscLookup,
    param_check: PhonemeParamCheck,
    phon_flush: PhonFlushCallback | None = None,
    error_comm: ErrorCallback | None = None,
    new_state: NewStateCallback | None = None,
    reset_comm: ResetCommCallback | None = None,
) -> PhonMatchResult:
    """Replicate the structural decisions of the C ``cm_phon_match``.

    Args:
        inp: Input snapshot (see :class:`PhonMatchInput`).
        arpa_lookup: ARPA lookup callback.
        language_lookup: Language-prefix lookup callback.
        asc_lookup: ASCKY lookup callback (for
            ``phoneme_mode & PHONEME_ASCKY``).
        param_check: ``cm_phon_param_check`` callback.
        phon_flush: Optional :func:`cm_phon_flush` driver.
        error_comm: Optional :func:`cm_cmd_error_comm` driver.
        new_state: Optional :func:`cm_pars_new_state` driver.
        reset_comm: Optional :func:`cm_cmd_reset_comm` driver.

    Returns:
        A :class:`PhonMatchResult` describing the post-call state and
        side-effects that were requested.

    Note:
        The C body recurses through ``replay_buffer`` and back into
        ``cm_phon_match`` itself when the uncertain-phoneme hold buffer
        drains. The Python port instead surfaces a
        :attr:`PhonMatchResult.replay_requested` flag that callers can
        consume to drive :func:`dectalk.cmd.replay_buffer.replay_buffer`
        themselves -- this avoids the (otherwise mandatory) late-binding
        circular import between this module, ``replay_buffer``, and
        ``cm_phon_check``. If a future caller needs to call those
        functions from inside this body, do so via ``from
        dectalk.cmd.replay_buffer import replay_buffer  # noqa: PLC0415``
        -- late-binding to break the circular import (matching the
        pattern in ``src/dectalk/cmd/par_insert_string.py``).
    """
    result = PhonMatchResult(
        q_flag=inp.q_flag,
        international_flag=inp.international_flag,
        international_temp=inp.international_temp,
        international_phon_lang=inp.international_phon_lang,
        hold_phonemes=inp.hold_phonemes,
        hold_count=inp.hold_count,
    )

    c = inp.c

    # -- CR / LF / text_flush early-out. ----------------------------
    if c in (CR, LF) or inp.text_flush:
        return result

    # -- PARSER_HACK_FOR_OLD_SONGS hold-buffer pre-capture. -------
    # When an uncertain phoneme is detected and replay isn't already
    # running, snapshot the international/q_flag state into the hold
    # slots and request replay capture.
    if not inp.hold_replay_ignore and check_uncertain_phones(result.q_flag, c):
        result.hold_phonemes = 1
        result.hold_count = 0
        # Snapshots flow through the caller-supplied replay machinery;
        # we just flag that capture started.

    # -- Hold-phonemes replay arm. ---------------------------------
    # If we're already accumulating into the hold buffer, check whether
    # the current ``c`` should trigger a replay (closer-to-the-metal
    # version of the C source; we don't recursively call cm_phon_match
    # because Python flow is synchronous).
    if result.hold_phonemes:
        is_delim = (result.q_flag == 0) and c in (
            ord(":"),
            ord("]"),
            ord("<"),
            ord("."),
            ord(","),
            ord("!"),
            ord("?"),
            ord(";"),
            ord(" "),
        )
        at_cap = result.hold_count >= inp.hold_strbuf_capacity - 1
        if is_delim or at_cap:
            # "Perfectly fine, replay" arm.
            result.replay_requested = True
            return result
        # Append to hold buffer and recurse via cm_phon_check.
        result.hold_count += 1
        # The remaining branch (uncertain phoneme / delimiter) sets
        # ``replay_requested`` so the caller drives ``replay_buffer``.
        if check_uncertain_phones(result.q_flag, c) or c == ord("]") or is_delim or at_cap:
            result.hold_count -= 1
            result.replay_requested = True
        return result

    # -- Parameter-list arm (inside ``[:phoneme N V D L S]``). ----
    if inp.param_index and param_check(c):
        return result

    # -- international_phon_lang<0 && international_flag>=0 arm. --
    if result.international_phon_lang < 0 and result.international_flag >= 0:
        if c == ord("_"):
            result.international_temp = 0
            result.q_flag = 0
            result.international_phon_lang = result.international_flag
            result.international_flag = _NO_INTL
            return result
        # Revert pending capture and try ARPA against international_temp.
        result.international_flag = _NO_INTL
        result.international_phon_lang = _NO_INTL
        match_len, _code = arpa_lookup(result.q_flag, result.international_temp)
        if match_len == _ARPA_NO_MATCH:
            result.error_code = CMD_bad_phoneme
            result.new_state = STATE_TOSS
            result.international_temp = 0
            result.q_flag = 0
            result.flushed = True
            if error_comm is not None:
                error_comm(CMD_bad_phoneme)
            if new_state is not None:
                new_state(STATE_TOSS)
            if phon_flush is not None:
                phon_flush()
        elif match_len == _ARPA_MATCH_ONE:
            result.q_flag = result.international_temp
            result.international_temp = 0
            result.flushed = True
            if phon_flush is not None:
                phon_flush()
        elif match_len == _ARPA_MATCH_TWO:
            result.q_flag = 0
            result.international_temp = 0

    # -- q_flag set vs unset dispatch. -----------------------------
    if result.q_flag:
        if c == ord("]"):
            if result.q_flag != ord(" "):
                match_len, _code = arpa_lookup(result.q_flag, ord(" "))
                if match_len == _ARPA_NO_MATCH:
                    result.error_code = CMD_bad_phoneme
                    result.new_state = STATE_NORMAL
                    if error_comm is not None:
                        error_comm(CMD_bad_phoneme)
                    if new_state is not None:
                        new_state(STATE_NORMAL)
                else:
                    # match_len in (1, 2)
                    result.flushed = True
                    if phon_flush is not None:
                        phon_flush()
            result.reset_state = STATE_NORMAL
            if reset_comm is not None:
                reset_comm(STATE_NORMAL)
        elif c == ord(":"):
            match_len, _code = arpa_lookup(result.q_flag, ord(" "))
            if match_len == _ARPA_MATCH_TWO:
                result.flushed = True
                result.reset_state = STATE_COMMAND
                if phon_flush is not None:
                    phon_flush()
                if reset_comm is not None:
                    reset_comm(STATE_COMMAND)
            else:
                result.error_code = CMD_bad_phoneme
                result.new_state = STATE_TOSS
                if error_comm is not None:
                    error_comm(CMD_bad_phoneme)
                if new_state is not None:
                    new_state(STATE_TOSS)
        else:
            # Default arm: try language lookup, else ARPA.
            temp = language_lookup(result.q_flag, c) if result.international_phon_lang < 0 else -1
            if result.international_flag < 0 and temp >= 0:
                result.international_flag = temp
                result.international_temp = c
            else:
                match_len, _code = arpa_lookup(result.q_flag, c)
                if match_len == _ARPA_NO_MATCH:
                    result.error_code = CMD_bad_phoneme
                    result.new_state = STATE_TOSS
                    if error_comm is not None:
                        error_comm(CMD_bad_phoneme)
                    if new_state is not None:
                        new_state(STATE_TOSS)
                elif match_len == _ARPA_MATCH_ONE:
                    result.q_flag = 0 if param_check(c) else c
                elif match_len == _ARPA_MATCH_TWO:
                    result.q_flag = 0
            # Flush if q_flag still set & no pending intl capture.
            if result.q_flag and result.international_flag < 0:
                result.flushed = True
                if phon_flush is not None:
                    phon_flush()
    # q_flag == 0
    elif c == ord("]"):
        result.reset_state = STATE_NORMAL
        if reset_comm is not None:
            reset_comm(STATE_NORMAL)
    elif c == ord(":"):
        result.reset_state = STATE_COMMAND
        if reset_comm is not None:
            reset_comm(STATE_COMMAND)
    elif inp.phoneme_mode & PHONEME_ASCKY:
        idx = asc_lookup(c)
        if idx < 0:
            result.error_code = CMD_bad_phoneme
            result.new_state = STATE_TOSS
            if error_comm is not None:
                error_comm(CMD_bad_phoneme)
            if new_state is not None:
                new_state(STATE_TOSS)
    else:
        result.q_flag = c

    return result


__all__ = [
    "ArpaLookup",
    "AscLookup",
    "ErrorCallback",
    "LanguageLookup",
    "NewStateCallback",
    "PhonFlushCallback",
    "PhonMatchInput",
    "PhonMatchResult",
    "PhonemeParamCheck",
    "ResetCommCallback",
    "cm_phon_match",
]
