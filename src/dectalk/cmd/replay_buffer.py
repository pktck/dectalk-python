"""``replay_buffer`` from ``cmd/cm_phon.c``.

Architectural shim for ``src/dapi/src/cmd/cm_phon.c`` lines 679-747.

The C function drains the per-character "hold buffer" (``hold_strbuf``
of size 4096) back through either :func:`cm_phon_check` or
:func:`cm_phon_match`, with optional leading space insertion. It is
the recovery path for the uncertain-phoneme replay machinery: when a
two-byte ARPA pair is ambiguous (see :data:`uncertain_phones`), the
parser captures characters into ``hold_strbuf`` and then replays them
once the ambiguity is resolved.

Inputs the C function reads:

* ``hold_count`` -- number of bytes currently held.
* ``hold_strbuf[]`` -- the held bytes themselves.
* ``hold_international_flag`` / ``hold_international_temp`` /
  ``hold_international_phon_lang`` / ``hold_q_flag`` -- snapshot of the
  international/q_flag state at the time the hold buffer started.
* ``c`` -- the optional trailing character (``0`` = none).
* ``insert_space`` -- whether to drive a leading space through
  ``cm_phon_check`` / ``cm_phon_match`` first.
* ``check`` -- ``True`` to drive through ``cm_phon_check`` (returning
  ``0`` on rejection); ``False`` to drive through ``cm_phon_match``
  (no return value, just side-effects).

Outputs (post-call state):

* ``hold_phonemes`` -- cleared when ``check`` is false.
* ``international_flag`` / ``international_temp`` /
  ``international_phon_lang`` / ``q_flag`` -- restored from the
  ``hold_*`` snapshots.
* ``hold_replay_ignore`` -- temporarily set to ``1`` to suppress the
  uncertain-phoneme re-capture inside ``cm_phon_match``.
* ``hold_count`` -- reset to ``0`` after a successful replay; on a
  check that bails out we restore the pre-call value.

Faithful (abbreviated) translation of:

.. code-block:: c

    int replay_buffer(LPTTS_HANDLE_T phTTS, unsigned int c,
                      int insert_space, int check) {
        int hc = pCmd_t->hold_count;
        int ret;
        int i;

        if (!check) pCmd_t->hold_phonemes = 0;
        pCmd_t->international_flag = pCmd_t->hold_international_flag;
        pCmd_t->international_temp = pCmd_t->hold_international_temp;
        pCmd_t->international_phon_lang =
            pCmd_t->hold_international_phon_lang;
        pCmd_t->q_flag = pCmd_t->hold_q_flag;

        pCmd_t->hold_replay_ignore = 1;
        if (insert_space) {
            if (check) {
                pCmd_t->hold_count = -1;
                ret = cm_phon_check(phTTS, ' ');
                if (!ret) { pCmd_t->hold_count = hc; return 0; }
            } else {
                cm_phon_match(phTTS, ' ');
            }
            pCmd_t->hold_replay_ignore = 0;
        }
        for (i = 0; i < hc; i++) {
            if (check) {
                pCmd_t->hold_count++;
                ret = cm_phon_check(phTTS, pCmd_t->hold_strbuf[i]);
                if (!ret) { pCmd_t->hold_count = hc; return 0; }
            } else {
                cm_phon_match(phTTS, pCmd_t->hold_strbuf[i]);
            }
            pCmd_t->hold_replay_ignore = 0;
        }
        pCmd_t->hold_count = 0;
        if (c != 0) {
            if (check) {
                ret = cm_phon_check(phTTS, pCmd_t->hold_strbuf[i]);
                if (!ret) { pCmd_t->hold_count = hc; return 0; }
            } else {
                cm_phon_match(phTTS, c);
            }
        }
        if (check) pCmd_t->hold_count = hc;
        return 1;
    }

Note the C body's ``check`` arm in the trailing ``c != 0`` branch
reads ``hold_strbuf[i]`` -- which is past the end of the buffer
because ``i`` has stepped to ``hc``. The Python port mirrors that
suspicious access (the byte at index ``hc``, which is either
zero-initialised or the leftover from a previous replay) to keep
the parity test honest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ReplayState:
    """Snapshot of the ``pCmd_t`` fields ``replay_buffer`` reads/writes.

    Attributes:
        hold_phonemes: ``pCmd_t->hold_phonemes`` -- the "replay is
            in progress" flag.
        hold_strbuf: ``pCmd_t->hold_strbuf[]`` (capacity 4096 in C;
            the shim accepts an arbitrary-length bytearray).
        hold_count: ``pCmd_t->hold_count`` -- number of bytes in
            :attr:`hold_strbuf` that are populated.
        hold_q_flag: Snapshot of ``q_flag`` at hold start.
        hold_international_flag: Snapshot of ``international_flag``.
        hold_international_temp: Snapshot of ``international_temp``.
        hold_international_phon_lang: Snapshot of
            ``international_phon_lang``.
        hold_replay_ignore: ``pCmd_t->hold_replay_ignore`` -- set to
            ``1`` while replay is driving the buffer back through
            ``cm_phon_match`` so the per-character entry point doesn't
            re-capture into the hold buffer.
        q_flag: ``pCmd_t->q_flag`` -- current pending first byte.
        international_flag: ``pCmd_t->international_flag``.
        international_temp: ``pCmd_t->international_temp``.
        international_phon_lang: ``pCmd_t->international_phon_lang``.
    """

    hold_phonemes: int = 0
    hold_strbuf: bytearray = field(default_factory=lambda: bytearray(4096))
    hold_count: int = 0
    hold_q_flag: int = 0
    hold_international_flag: int = -1
    hold_international_temp: int = 0
    hold_international_phon_lang: int = -1
    hold_replay_ignore: int = 0
    q_flag: int = 0
    international_flag: int = -1
    international_temp: int = 0
    international_phon_lang: int = -1


@dataclass
class ReplayResult:
    """Outcome of running :func:`replay_buffer`.

    Attributes:
        rc: ``1`` on success, ``0`` on a ``check=True`` bail-out.
        state: The mutated :class:`ReplayState`. On a bail-out
            ``hold_count`` is restored to the original ``hold_count``;
            on success it's reset to ``0``.
    """

    rc: int
    state: ReplayState


# Callbacks: the caller wires these to either the in-process
# :func:`cm_phon_check` / :func:`cm_phon_match` ports, or to test
# doubles. The check callback returns ``1``/``0`` like the C source; the
# match callback returns nothing.
CheckCallback = Callable[[int, ReplayState], int]
"""``(c, state) -> 1|0`` mirroring the C ``cm_phon_check`` semantics."""

MatchCallback = Callable[[int, ReplayState], None]
"""``(c, state) -> None`` mirroring the C ``cm_phon_match``."""


def replay_buffer(  # noqa: PLR0912, PLR0915 — faithful translation of the C source's hold-buffer drain loop
    state: ReplayState,
    c: int,
    insert_space: bool,
    check: bool,
    *,
    check_cb: CheckCallback | None = None,
    match_cb: MatchCallback | None = None,
) -> ReplayResult:
    """Drain the hold buffer through ``cm_phon_check`` or ``cm_phon_match``.

    Args:
        state: Mutable :class:`ReplayState` -- updated in place and
            returned via :attr:`ReplayResult.state`.
        c: Trailing character (``0`` = none).
        insert_space: When truthy, drive a leading ``' '`` through the
            chosen callback first.
        check: ``True`` to drive through ``check_cb`` (returning ``0``
            on first rejection); ``False`` to drive through ``match_cb``
            (no return value, all side-effects).
        check_cb: Required when ``check=True``. Must be a
            :data:`CheckCallback`.
        match_cb: Required when ``check=False``. Must be a
            :data:`MatchCallback`.

    Returns:
        A :class:`ReplayResult` capturing the new state and the C
        ``return`` value.

    Raises:
        ValueError: When the appropriate callback for the chosen mode
            wasn't supplied.
    """
    if check and check_cb is None:
        raise ValueError("check=True requires check_cb")
    if not check and match_cb is None:
        raise ValueError("check=False requires match_cb")

    hc = state.hold_count

    if not check:
        state.hold_phonemes = 0

    # Restore the international / q_flag state from the snapshots.
    state.international_flag = state.hold_international_flag
    state.international_temp = state.hold_international_temp
    state.international_phon_lang = state.hold_international_phon_lang
    state.q_flag = state.hold_q_flag

    state.hold_replay_ignore = 1

    if insert_space:
        if check:
            state.hold_count = -1
            assert check_cb is not None  # narrowed above
            rc = check_cb(ord(" "), state)
            if not rc:
                state.hold_count = hc
                return ReplayResult(rc=0, state=state)
        else:
            assert match_cb is not None
            match_cb(ord(" "), state)
        state.hold_replay_ignore = 0

    last_i = 0
    for i in range(hc):
        last_i = i
        if check:
            state.hold_count += 1
            assert check_cb is not None
            rc = check_cb(state.hold_strbuf[i], state)
            if not rc:
                state.hold_count = hc
                return ReplayResult(rc=0, state=state)
        else:
            assert match_cb is not None
            match_cb(state.hold_strbuf[i], state)
        state.hold_replay_ignore = 0

    state.hold_count = 0

    if c != 0:
        if check:
            # The C source reads ``hold_strbuf[i]`` here -- after the
            # loop ``i`` has stepped to ``hc`` so this reads one past
            # the populated bytes. Mirror that quirk faithfully.
            idx = hc if hc > 0 else last_i
            if idx >= len(state.hold_strbuf):
                idx = len(state.hold_strbuf) - 1 if state.hold_strbuf else 0
            assert check_cb is not None
            byte = state.hold_strbuf[idx] if state.hold_strbuf else 0
            rc = check_cb(byte, state)
            if not rc:
                state.hold_count = hc
                return ReplayResult(rc=0, state=state)
        else:
            assert match_cb is not None
            match_cb(c, state)

    if check:
        state.hold_count = hc

    return ReplayResult(rc=1, state=state)


__all__ = ["CheckCallback", "MatchCallback", "ReplayResult", "ReplayState", "replay_buffer"]
