"""Verify ls_util_lts_init matches ls_util.c."""

from __future__ import annotations

from dectalk.include.phoneme_codes import WBOUND
from dectalk.lts.lts_init import ls_util_lts_init
from dectalk.lts.lts_t import LtsT
from dectalk.lts.wh_state_codes import IS_WH, NOT_WH, UNK_WH


def test_wstate_reset_to_unknown() -> None:
    """``wstate`` resets to :data:`UNK_WH` regardless of starting value."""
    for start in (UNK_WH, IS_WH, NOT_WH, 42):
        state = LtsT(wstate=start)
        ls_util_lts_init(state)
        assert state.wstate == UNK_WH


def test_lphone_reset_to_wbound() -> None:
    """``lphone`` resets to :data:`WBOUND`."""
    state = LtsT(lphone=99)
    ls_util_lts_init(state)
    assert state.lphone == WBOUND


def test_index_counters_reset() -> None:
    """``num_indexes`` → 0 and ``cur_index`` → -1."""
    state = LtsT(num_indexes=5, cur_index=3)
    ls_util_lts_init(state)
    assert state.num_indexes == 0
    assert state.cur_index == -1


def test_single_threaded_state_reset() -> None:
    """``first_pass`` / ``cur_input_pos`` reset (SINGLE_THREADED branch)."""
    state = LtsT(first_pass=1, cur_input_pos=42)
    ls_util_lts_init(state)
    assert state.first_pass == 0
    assert state.cur_input_pos == 0


def test_new_lts_word_index_reset() -> None:
    """``cur_word_index`` resets to 0 (NEW_LTS branch)."""
    state = LtsT(cur_word_index=7)
    ls_util_lts_init(state)
    assert state.cur_word_index == 0


def test_unrelated_fields_preserved() -> None:
    """Fields not touched by init are preserved (e.g., other scratch state)."""
    state = LtsT(rpart=99)  # rpart isn't reset by ls_util_lts_init
    ls_util_lts_init(state)
    assert state.rpart == 99


def test_idempotent_reinit() -> None:
    """Calling ``ls_util_lts_init`` twice produces the same state."""
    a = LtsT()
    b = LtsT(wstate=2, lphone=99, num_indexes=10, cur_index=5)
    ls_util_lts_init(a)
    ls_util_lts_init(b)
    ls_util_lts_init(b)  # Second call.
    assert a.wstate == b.wstate
    assert a.lphone == b.lphone
    assert a.num_indexes == b.num_indexes
    assert a.cur_index == b.cur_index
