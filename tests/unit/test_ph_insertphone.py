"""Verify insertphone matches ph_sort.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import COMMA, S1, USPhoneme
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_t import DphT
from dectalk.ph.insertphone import insertphone
from dectalk.ph.numeric_constants import NPHON_MAX


def _state(symbols: list[int]) -> DphT:
    state = DphT()
    state.symbols = list(symbols)
    state.user_durs = [9] * (len(symbols) + 4)  # Non-zero to verify zeroing.
    state.user_f0 = [9] * (len(symbols) + 4)
    state.nsymbtot = len(symbols)
    return state


def test_inserts_and_shifts_later_entries() -> None:
    """``insertphone`` at index 1 shifts symbols 1..end down."""
    state = _state([int(USPhoneme.IY), int(USPhoneme.OW), int(USPhoneme.AA)])
    insertphone(KsdT(), state, 1, COMMA)
    assert state.nsymbtot == 4
    assert state.symbols[:4] == [int(USPhoneme.IY), COMMA, int(USPhoneme.OW), int(USPhoneme.AA)]


def test_user_prosody_cleared_at_insert_position() -> None:
    """The new symbol's user_durs/user_f0 slot is zeroed."""
    state = _state([int(USPhoneme.IY), int(USPhoneme.OW)])
    insertphone(KsdT(), state, 1, COMMA)
    assert state.user_durs is not None
    assert state.user_durs[1] == 0
    assert state.user_f0 is not None
    assert state.user_f0[1] == 0


def test_insert_at_start() -> None:
    """Inserting at index 0 shifts everything."""
    state = _state([int(USPhoneme.IY), int(USPhoneme.OW)])
    insertphone(KsdT(), state, 0, COMMA)
    assert state.nsymbtot == 3
    assert state.symbols[:3] == [COMMA, int(USPhoneme.IY), int(USPhoneme.OW)]


def test_insert_at_end() -> None:
    """Inserting at nsymbtot appends without shifting."""
    state = _state([int(USPhoneme.IY), int(USPhoneme.OW)])
    insertphone(KsdT(), state, 2, COMMA)
    assert state.nsymbtot == 3
    assert state.symbols[:3] == [int(USPhoneme.IY), int(USPhoneme.OW), COMMA]


def test_nsymbtot_at_max_is_noop() -> None:
    """When nsymbtot >= NPHON_MAX, the function returns without inserting."""
    state = DphT()
    state.symbols = [0] * (NPHON_MAX + 1)
    state.user_durs = [0] * (NPHON_MAX + 1)
    state.user_f0 = [0] * (NPHON_MAX + 1)
    state.nsymbtot = NPHON_MAX
    insertphone(KsdT(), state, 0, COMMA)
    assert state.nsymbtot == NPHON_MAX
    # Symbols[0] unchanged.
    assert state.symbols[0] == 0


def test_s1_skips_adjust_index_kbs_fix() -> None:
    """Inserting S1 doesn't call adjust_index (BATS index-mark fix)."""
    from dectalk.kernel.spc_packet import SpcPacket  # noqa: PLC0415

    state = _state([int(USPhoneme.IY)])
    ksd = KsdT()
    pkt = SpcPacket()
    while len(pkt.data) < 7:
        pkt.data.append(0)
    pkt.data[5] = 3  # Marker pointing to allo offset 3.
    pkt.data[4] = 0
    ksd.spc_pkt_save = pkt

    insertphone(ksd, state, 0, S1)
    # adjust_index would have bumped pkt.data[5] for which==loc+1==1.
    # But because fone==S1, the adjust is skipped → pkt.data[5] unchanged.
    assert pkt.data[5] == 3
