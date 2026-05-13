"""``cm_phon_check`` from ``cmd/cm_phon.c``.

Architectural shim for ``src/dapi/src/cmd/cm_phon.c`` lines 535-677.

The C body validates the next phoneme-input character ``c`` against the
active ARPA/language tables and mutates per-thread bookkeeping
(``pCmd_t->q_flag``, ``pCmd_t->international_flag`` /
``international_temp`` / ``international_phon_lang``) as it goes. Its
return value is ``0`` when the character is rejected (so the caller
should replay the hold buffer) and ``1`` when it was accepted or
absorbed.

Because the Python parser receives full phoneme strings rather than
the per-character pipe the C source consumes, this shim:

* takes an immutable :class:`PhonCheckInput` of the inputs the C body
  reads (``c``, ``text_flush``, ``hold_count``, ``phoneme_mode`` plus
  the four ``q_flag`` / ``international_*`` slots);
* returns a :class:`PhonCheckResult` carrying the post-call values of
  those four slots plus the ``return`` value;
* exposes the ARPA / language lookups via injectable callbacks so the
  caller can wire them to either the in-process Python ports
  (:func:`cm_phon_lookup_arpa` / :func:`cm_phon_lookup_language`) or
  test doubles.

The decoded structural pieces are:

* CR / LF / text_flush early-out (returns 1 without state change).
* The ``international_phon_lang < 0 && international_flag >= 0`` branch
  that either captures ``_`` as a "language commit" or runs the ARPA
  lookup against ``international_temp``.
* The uncertain-phoneme replay guard (``hold_count > 1`` plus
  ``check_uncertain_phones``).
* The ``q_flag`` set vs unset dispatch, including the ``]`` / ``:`` /
  default branches.

Faithful translation of (abbreviated):

.. code-block:: c

    int cm_phon_check(LPTTS_HANDLE_T phTTS, unsigned int c) {
        if (c == CR || c == LF || pKsd_t->text_flush) return 1;
        if (international_phon_lang<0 && international_flag>=0) {
            if (c=='_') { ... return 1; }
            else { switch(cm_phon_lookup_arpa(...)) { ... } }
        }
        if (hold_count > 1 && check_uncertain_phones(q_flag,c)) return 1;
        if (q_flag) {
            switch (c) {
            case ']': ...
            case ':': ...
            default:
                if (international_phon_lang<0)
                    temp = cm_phon_lookup_language(q_flag, c);
                if (international_flag<0 && temp>=0)
                    { international_flag=temp; international_temp=c; }
                else
                    switch (cm_phon_lookup_arpa(q_flag, c)) { ... }
            }
        } else {
            switch (c) {
            case ']': break;
            case ':': break;
            default:
                if (!(phoneme_mode & PHONEME_ASCKY)) q_flag = c;
            }
        }
        return 1;
    }
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dectalk.cmd.cmd_states import PHONEME_ASCKY
from dectalk.cmd.uncertain_phones import check_uncertain_phones
from dectalk.include.ascii_control import CR, LF

# Sentinel "no language captured yet" value matching the C ``-1``
# initialiser for ``international_flag`` / ``international_phon_lang``.
_NO_INTL: int = -1

# ``cm_phon_lookup_arpa`` return codes (see :mod:`dectalk.cmd.arpa_lookup`).
_ARPA_NO_MATCH: int = 0
_ARPA_MATCH_ONE: int = 1
_ARPA_MATCH_TWO: int = 2


@dataclass
class PhonCheckInput:
    """Inputs the C ``cm_phon_check`` body reads.

    Attributes:
        c: The current phoneme-input character (the C ``unsigned int c``).
        text_flush: ``pKsd_t->text_flush`` -- non-zero short-circuits to
            ``return 1`` at the top of the function.
        hold_count: ``pCmd_t->hold_count`` -- used by the uncertain-
            phoneme guard (``hold_count > 1``).
        phoneme_mode: ``pKsd_t->phoneme_mode`` (bitfield); the
            ``PHONEME_ASCKY`` bit influences the no-q_flag default branch.
        q_flag: ``pCmd_t->q_flag`` -- the pending first byte of a
            two-byte ARPA pair.
        international_flag: ``pCmd_t->international_flag`` -- pending
            language-prefix arm (``-1`` = none).
        international_temp: ``pCmd_t->international_temp`` -- the
            character captured when a language prefix was detected.
        international_phon_lang: ``pCmd_t->international_phon_lang`` --
            committed language index (``-1`` = none).
    """

    c: int
    text_flush: int = 0
    hold_count: int = 0
    phoneme_mode: int = 0
    q_flag: int = 0
    international_flag: int = _NO_INTL
    international_temp: int = 0
    international_phon_lang: int = _NO_INTL


@dataclass
class PhonCheckResult:
    """Outcome of running :func:`cm_phon_check`.

    Attributes:
        rc: The C ``return`` value -- ``1`` if accepted/absorbed,
            ``0`` if rejected (caller must replay the hold buffer).
        q_flag: Updated ``q_flag`` value.
        international_flag: Updated ``international_flag`` value.
        international_temp: Updated ``international_temp`` value.
        international_phon_lang: Updated ``international_phon_lang``.
    """

    rc: int
    q_flag: int = 0
    international_flag: int = _NO_INTL
    international_temp: int = 0
    international_phon_lang: int = _NO_INTL


# Callback signatures: the caller injects the ARPA / language lookups so
# this module doesn't have to import them statically (and so unit tests
# can mock them).
ArpaLookup = Callable[[int, int], tuple[int, int]]
"""``(ph1, ph2) -> (match_len, phone_code)`` -- see :func:`cm_phon_lookup_arpa`."""

LanguageLookup = Callable[[int, int], int]
"""``(ph1, ph2) -> language_index_or_-1`` -- see :func:`cm_phon_lookup_language`."""


def cm_phon_check(  # noqa: PLR0911, PLR0912 — faithful translation of a 142-line C function with many return arms
    inp: PhonCheckInput,
    *,
    arpa_lookup: ArpaLookup,
    language_lookup: LanguageLookup,
) -> PhonCheckResult:
    """Replicate the structural decisions of the C ``cm_phon_check``.

    Args:
        inp: The input snapshot (see :class:`PhonCheckInput`).
        arpa_lookup: ARPA lookup callback. Returns ``(2, code)`` /
            ``(1, code)`` / ``(0, -1)`` -- only the first element is
            consulted, matching the C ``switch`` arms 0/1/2.
        language_lookup: Language-prefix lookup callback. Returns a
            language index or ``-1``.

    Returns:
        A :class:`PhonCheckResult` reporting the updated state slots.
    """
    c = inp.c
    q_flag = inp.q_flag
    international_flag = inp.international_flag
    international_temp = inp.international_temp
    international_phon_lang = inp.international_phon_lang

    # -- CR / LF / text_flush early-out (returns 1, no state change). --
    if c in (CR, LF) or inp.text_flush:
        return PhonCheckResult(
            rc=1,
            q_flag=q_flag,
            international_flag=international_flag,
            international_temp=international_temp,
            international_phon_lang=international_phon_lang,
        )

    # -- ``international_phon_lang<0 && international_flag>=0`` arm. --
    if international_phon_lang < 0 and international_flag >= 0:
        if c == ord("_"):
            # Commit the captured language as the active phoneme lang.
            international_temp = 0
            q_flag = 0
            international_phon_lang = international_flag
            international_flag = _NO_INTL
            return PhonCheckResult(
                rc=1,
                q_flag=q_flag,
                international_flag=international_flag,
                international_temp=international_temp,
                international_phon_lang=international_phon_lang,
            )
        # Not ``_``: revert the pending capture and ARPA-check the
        # ``q_flag`` against ``international_temp``.
        international_flag = _NO_INTL
        international_phon_lang = _NO_INTL
        match_len, _code = arpa_lookup(q_flag, international_temp)
        if match_len == _ARPA_NO_MATCH:
            return PhonCheckResult(
                rc=0,
                q_flag=q_flag,
                international_flag=international_flag,
                international_temp=international_temp,
                international_phon_lang=international_phon_lang,
            )
        if match_len == _ARPA_MATCH_ONE:
            q_flag = international_temp
            international_temp = 0
        elif match_len == _ARPA_MATCH_TWO:
            q_flag = 0
            international_temp = 0
        # Fall through to the rest of the function with the
        # post-switch state.

    # -- Uncertain-phoneme replay guard. ----------------------------
    if inp.hold_count > 1 and check_uncertain_phones(q_flag, c):
        return PhonCheckResult(
            rc=1,
            q_flag=q_flag,
            international_flag=international_flag,
            international_temp=international_temp,
            international_phon_lang=international_phon_lang,
        )

    # -- ``q_flag`` set vs unset dispatch. --------------------------
    if q_flag:
        if c == ord("]"):
            # ``]`` while a ``q_flag`` byte is pending: try ``q_flag + ' '``.
            if q_flag != ord(" "):
                match_len, _code = arpa_lookup(q_flag, ord(" "))
                if match_len == _ARPA_NO_MATCH:
                    return PhonCheckResult(
                        rc=0,
                        q_flag=q_flag,
                        international_flag=international_flag,
                        international_temp=international_temp,
                        international_phon_lang=international_phon_lang,
                    )
                # match_len == 1 or 2: clear ``q_flag``.
                q_flag = 0
            return PhonCheckResult(
                rc=1,
                q_flag=q_flag,
                international_flag=international_flag,
                international_temp=international_temp,
                international_phon_lang=international_phon_lang,
            )
        if c == ord(":"):
            # ``:`` while ``q_flag`` is pending: require a 2-byte ARPA
            # match against ``q_flag + ' '`` (return 0 otherwise).
            match_len, _code = arpa_lookup(q_flag, ord(" "))
            if match_len != _ARPA_MATCH_TWO:
                return PhonCheckResult(
                    rc=0,
                    q_flag=q_flag,
                    international_flag=international_flag,
                    international_temp=international_temp,
                    international_phon_lang=international_phon_lang,
                )
            # Fall through to the bottom-of-function ``return 1``.
        else:
            # Default arm: try language lookup, else ARPA.
            temp = language_lookup(q_flag, c) if international_phon_lang < 0 else -1
            if international_flag < 0 and temp >= 0:
                international_flag = temp
                international_temp = c
            else:
                match_len, _code = arpa_lookup(q_flag, c)
                if match_len == _ARPA_NO_MATCH:
                    return PhonCheckResult(
                        rc=0,
                        q_flag=q_flag,
                        international_flag=international_flag,
                        international_temp=international_temp,
                        international_phon_lang=international_phon_lang,
                    )
                if match_len == _ARPA_MATCH_ONE:
                    q_flag = c
                elif match_len == _ARPA_MATCH_TWO:
                    q_flag = 0
    # q_flag == 0
    elif c in (ord("]"), ord(":")):
        # Both bracketed delimiters: no-op in cm_phon_check.
        pass
    # default: in ASCKY phoneme mode the C body is a no-op; in
    # ARPA mode (the common one) the character becomes the new
    # ``q_flag``.
    elif not (inp.phoneme_mode & PHONEME_ASCKY):
        q_flag = c

    return PhonCheckResult(
        rc=1,
        q_flag=q_flag,
        international_flag=international_flag,
        international_temp=international_temp,
        international_phon_lang=international_phon_lang,
    )


__all__ = ["ArpaLookup", "LanguageLookup", "PhonCheckInput", "PhonCheckResult", "cm_phon_check"]
