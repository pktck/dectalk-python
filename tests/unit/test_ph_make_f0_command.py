"""Verify make_f0_command matches the active ph_inton0.c definition.

The production build stores only ``f0tim`` + ``f0tar`` (command type is
encoded in ``tar``); there is no ``type`` parameter and no
``f0type`` / ``f0length`` array.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.make_f0_command import make_f0_command
from dectalk.ph.numeric_constants import NPHON_MAX


def test_first_command_appends_to_arrays() -> None:
    """A first command writes ``f0tim`` + ``f0tar`` at index 0."""
    state = DphT()
    cumdur = [0]
    make_f0_command(state, rulenumber=1, tar=1200, delay=5, length=10, ps_cumdur=cumdur)
    assert state.f0tim[0] == 5  # cumdur (0) + delay (5)
    assert state.f0tar[0] == 1200
    assert state.nf0tot == 1


def test_ps_cumdur_reset_to_neg_delay() -> None:
    """``*psCumdur`` is reset to ``-delay`` after the call."""
    state = DphT()
    cumdur = [42]
    make_f0_command(state, rulenumber=0, tar=0, delay=8, length=0, ps_cumdur=cumdur)
    assert cumdur[0] == -8


def test_negative_delay_clamped() -> None:
    """If ``delay + *psCumdur < 0``, delay is clamped to ``-*psCumdur``."""
    state = DphT()
    cumdur = [3]
    # delay = -10, cumdur = 3; clamped delay = -3.
    make_f0_command(state, rulenumber=0, tar=0, delay=-10, length=0, ps_cumdur=cumdur)
    # f0tim = cumdur (3) + clamped_delay (-3) = 0
    assert state.f0tim[0] == 0
    # cumdur reset to -clamped_delay = 3
    assert cumdur[0] == 3


def test_count_caps_at_nphon_max_minus_one() -> None:
    """``nf0tot`` stops bumping at ``NPHON_MAX - 1``."""
    state = DphT()
    state.nf0tot = NPHON_MAX - 1
    cumdur = [0]
    make_f0_command(state, rulenumber=0, tar=0, delay=0, length=0, ps_cumdur=cumdur)
    # Count should NOT have incremented past NPHON_MAX - 1.
    assert state.nf0tot == NPHON_MAX - 1


def test_two_commands_appended_in_order() -> None:
    """Two consecutive commands occupy indices 0 and 1."""
    state = DphT()
    cumdur = [0]
    make_f0_command(state, rulenumber=0, tar=100, delay=2, length=4, ps_cumdur=cumdur)
    make_f0_command(state, rulenumber=0, tar=200, delay=3, length=5, ps_cumdur=cumdur)
    assert state.f0tar[0] == 100
    assert state.f0tar[1] == 200
    assert state.nf0tot == 2


def test_value_encoded_command_types_stored_verbatim() -> None:
    """The command type lives in ``tar`` (reset / user / step / impulse)."""
    state = DphT()
    cumdur = [0]
    # reset (0), user note (>=2000), step (even), impulse (odd).
    make_f0_command(state, rulenumber=7, tar=0, delay=0, length=0, ps_cumdur=cumdur)
    make_f0_command(state, rulenumber=0, tar=2042, delay=0, length=0, ps_cumdur=cumdur)
    make_f0_command(state, rulenumber=1, tar=120, delay=0, length=0, ps_cumdur=cumdur)
    make_f0_command(state, rulenumber=2, tar=181, delay=0, length=0, ps_cumdur=cumdur)
    assert state.f0tar[:4] == [0, 2042, 120, 181]


def test_buffers_grow_to_nphon_max() -> None:
    """The two stored f0 arrays grow to ``NPHON_MAX`` entries on first call."""
    state = DphT()
    cumdur = [0]
    make_f0_command(state, rulenumber=0, tar=0, delay=0, length=0, ps_cumdur=cumdur)
    assert len(state.f0tim) == NPHON_MAX
    assert len(state.f0tar) == NPHON_MAX
