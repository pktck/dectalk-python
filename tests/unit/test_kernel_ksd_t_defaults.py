"""Invariant tests for :class:`dectalk.kernel.ksd_t.KsdT` defaults.

These tests pin the field set and default values of ``KsdT`` against
the C ``struct share_data`` defined in
``src/dapi/src/include/kernel.h`` (lines 551-877) and the
boot-time mutations performed by C source we can inspect — chiefly
``cmd_init`` in ``src/dapi/src/cmd/cmd_init.c``.

The audit covered every field currently modelled on ``KsdT``; the
table below records the C origin for each default. Where a default
differs from C ``malloc()``'s indeterminate output (which on Linux
fresh pages is zero), the rationale is captured in the per-field
test below.

+----------------------+--------+---------------------------+
| Field                | Pydef  | C origin                  |
+======================+========+===========================+
| spc_pkt_save         | None   | ``spc_packet *`` pointer  |
| cmd_flush            | 0      | ``volatile int``          |
| wbreak               | 0      | ``volatile unsigned int`` |
| sayflag              | 0      | SAY_CLAUSE == 0           |
| input_timeout        | 0      | ``volatile unsigned int`` |
| phoneme_mode         | 0      | overwritten by cmd_init   |
| spc_sync             | sem(0) | ``DT_SEMAPHORE`` zero     |
| lang_curr            | 0xFFFF | LANG_none (kernel init)   |
| lang_ready[]         | [0]*N  | ``volatile int`` zero     |
| lang_lts/ph[]        | [None] | ``P_PIPE`` NULL           |
| lts_pipe / ph_pipe   | None   | ``P_PIPE`` NULL           |
| loaded_languages     | None   | linked-list head NULL     |
| ascky/arpabet/...    | None   | per-language table ptrs   |
| ascky_size           | 0      | ``volatile int``          |
| arpa_size/arpa_case  | 0      | ``volatile int``          |
| reverse_ascky        | None   | ``unsigned int *``        |
| typing_table         | None   | table-of-tables ptr       |
| error_table          | None   | table-of-tables ptr       |
| sprate               | 0      | ``volatile short``        |
| halting              | 0      | ``volatile int``          |
| modeflag             | 0      | ``volatile unsigned int`` |
| pitch_delta          | 0      | overwritten to 35 by      |
|                      |        | ``cmd_init`` reset path   |
+----------------------+--------+---------------------------+
"""

from __future__ import annotations

import pytest

from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_none
from dectalk.kernel.misc_constants import MAX_languages
from dectalk.kernel.sync_primitives import DtSemaphore


def test_ksd_t_uses_slots() -> None:
    """``KsdT`` must use ``__slots__`` so unmodelled attributes raise.

    Without slots, a typo like ``ksd.pitch_delts = 35`` would silently
    create a new attribute instead of routing through the dataclass —
    leaving rule code reading the (still zero) ``pitch_delta`` slot.
    """
    ksd = KsdT()
    with pytest.raises(AttributeError):
        ksd.this_field_does_not_exist = 1  # type: ignore[attr-defined]


def test_ksd_t_default_scalars_are_zero() -> None:
    """Scalar fields mirror C ``malloc()`` zero-init.

    Exception: ``lang_curr`` defaults to ``LANG_none`` (see
    :func:`test_ksd_t_lang_curr_defaults_to_lang_none`).
    """
    ksd = KsdT()
    assert ksd.cmd_flush == 0
    assert ksd.wbreak == 0
    assert ksd.sayflag == 0  # SAY_CLAUSE == 0 — clause is the kernel default
    assert ksd.input_timeout == 0
    assert ksd.phoneme_mode == 0
    assert ksd.ascky_size == 0
    assert ksd.arpa_size == 0
    assert ksd.arpa_case == 0
    assert ksd.sprate == 0
    assert ksd.halting == 0
    assert ksd.modeflag == 0
    assert ksd.pitch_delta == 0


def test_ksd_t_default_pointer_fields_are_none() -> None:
    """Pointer-like fields default to ``None`` (mirror C ``NULL``)."""
    ksd = KsdT()
    assert ksd.spc_pkt_save is None
    assert ksd.lts_pipe is None
    assert ksd.ph_pipe is None
    assert ksd.loaded_languages is None
    assert ksd.ascky is None
    assert ksd.reverse_ascky is None
    assert ksd.arpabet is None
    assert ksd.typing_table is None
    assert ksd.error_table is None


def test_ksd_t_lang_curr_defaults_to_lang_none() -> None:
    """``lang_curr`` defaults to ``LANG_none`` (0xFFFF), not 0.

    In C the kernel start-up code sets ``KS.lang_curr = LANG_none``
    before any LTS/PH subsystem reports in. ``default_lang`` reads
    this sentinel to decide whether to install a winning language
    (see ``src/dapi/src/kernel/services.c`` and
    :mod:`dectalk.kernel.default_lang`).
    """
    ksd = KsdT()
    assert ksd.lang_curr == LANG_none
    assert ksd.lang_curr == 0xFFFF  # spot-check the literal


def test_ksd_t_lang_ready_default_is_zero_per_slot() -> None:
    """``lang_ready[]`` mirrors C zero-init: no subsystem ready yet."""
    ksd = KsdT()
    assert ksd.lang_ready == [0] * MAX_languages
    assert len(ksd.lang_ready) == MAX_languages


def test_ksd_t_lang_pipe_arrays_default_to_nones() -> None:
    """Per-language pipe arrays default to ``[None, ..., None]``."""
    ksd = KsdT()
    assert ksd.lang_lts == [None] * MAX_languages
    assert ksd.lang_ph == [None] * MAX_languages
    assert len(ksd.lang_lts) == MAX_languages
    assert len(ksd.lang_ph) == MAX_languages


def test_ksd_t_default_factories_are_independent() -> None:
    """Two ``KsdT`` instances must not share mutable default state.

    A common bug with ``@dataclass`` is using a mutable literal as a
    default (``= [0] * N`` evaluated once at class-definition time).
    ``KsdT`` should use ``default_factory`` so each instance owns
    its own list / semaphore.
    """
    a = KsdT()
    b = KsdT()
    assert a.lang_ready is not b.lang_ready
    assert a.lang_lts is not b.lang_lts
    assert a.lang_ph is not b.lang_ph
    assert a.spc_sync is not b.spc_sync

    a.lang_ready[0] = 7
    a.lang_lts[1] = object()
    assert b.lang_ready[0] == 0
    assert b.lang_lts[1] is None


def test_ksd_t_spc_sync_is_dtsemaphore_with_zero_value() -> None:
    """``spc_sync`` is a fresh ``DtSemaphore`` with counter == 0.

    In C the field is ``volatile DT_SEMAPHORE spc_sync`` — a struct
    holding a counter and an event handle. Zero-initialised. The
    Python ``DtSemaphore`` factory matches that initial state.
    """
    ksd = KsdT()
    assert isinstance(ksd.spc_sync, DtSemaphore)
    assert ksd.spc_sync.value == 0


def test_ksd_t_pitch_delta_is_an_actual_slot() -> None:
    """Regression for issue #84: ``pitch_delta`` is a real ``KsdT`` slot.

    ``cmd_init`` (cmd_init.c line 92) writes ``pKsd_t->pitch_delta = 35;``
    on every full reset. Before this audit the Python ``KsdT``
    didn't declare ``pitch_delta``, so calling ``cmd_init(...,
    b_reset_all=True, p_ksd_t=KsdT())`` raised ``AttributeError``
    — the test suite worked around the gap by passing a
    ``SimpleNamespace``.
    """
    ksd = KsdT()
    ksd.pitch_delta = 35  # must not raise.
    assert ksd.pitch_delta == 35


def test_ksd_t_cmd_init_runs_on_real_ksd_t() -> None:
    """End-to-end smoke: ``cmd_init`` resets a real ``KsdT`` cleanly.

    Companion to :func:`test_ksd_t_pitch_delta_is_an_actual_slot` —
    routes through the real call site to catch any future regression
    in either the field set or the reset path.
    """
    from dectalk.cmd.cmd_init import cmd_init
    from dectalk.cmd.cmd_states import PHONEME_OFF, PHONEME_SPEAK
    from dectalk.cmd.cmd_t import CmdT

    cmd_t = CmdT()
    ksd_t = KsdT()
    cmd_init(cmd_t, ksd_t, b_reset_all=True, total_commands=0)
    assert ksd_t.phoneme_mode == (PHONEME_OFF | PHONEME_SPEAK)
    assert ksd_t.pitch_delta == 35


def test_ksd_t_no_reset_path_does_not_touch_pitch_delta() -> None:
    """``cmd_init(..., b_reset_all=False)`` must leave ``pitch_delta`` alone."""
    from dectalk.cmd.cmd_init import cmd_init
    from dectalk.cmd.cmd_t import CmdT

    cmd_t = CmdT()
    ksd_t = KsdT()
    ksd_t.pitch_delta = 99  # user-tuned value
    ksd_t.phoneme_mode = 42  # likewise

    cmd_init(cmd_t, ksd_t, b_reset_all=False, total_commands=0)

    assert ksd_t.pitch_delta == 99
    assert ksd_t.phoneme_mode == 42
