"""C-source parity test for ``replay_buffer`` against cm_phon.c.

Re-parses the body of ``replay_buffer`` (lines 679-747 in
``src/dapi/src/cmd/cm_phon.c``) using brace-depth tracking and
asserts the load-bearing structural invariants:

- The ``!check`` clears hold_phonemes.
- The four ``hold_international_*`` / ``hold_q_flag`` snapshots are
  restored onto the live ``pCmd_t`` fields.
- ``hold_replay_ignore`` is set to ``1`` before draining.
- The ``insert_space`` arm prepends a ``' '`` via either cm_phon_check
  or cm_phon_match.
- The drain loop iterates over ``hold_strbuf[0..hc-1]``.
- On a ``check`` bail-out ``hold_count`` is restored to the pre-call
  value.

Plus behavioural tests of the Python architectural shim.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.replay_buffer import ReplayResult, ReplayState, replay_buffer

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_phon.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_cm_phon_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate the ``replay_buffer`` body via brace tracking."""
    text = _read_cm_phon_c()
    decl = re.search(r"\bint\s+replay_buffer\s*\(", text)
    assert decl is not None, "replay_buffer declaration not found in cm_phon.c"
    brace_start = text.index("{", decl.end())
    depth = 1
    i = brace_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, "Unbalanced braces extracting replay_buffer body"
    return text[brace_start + 1 : i - 1]


# -- Structural assertions on the C body ----------------------------


def test_c_body_clears_hold_phonemes_when_not_check() -> None:
    """``if (!check) pCmd_t->hold_phonemes = 0;``."""
    body = _extract_body()
    pattern = (
        r"if\s*\(\s*!\s*check\s*\)\s*\{?\s*"
        r"pCmd_t\s*->\s*hold_phonemes\s*=\s*0\s*;"
    )
    assert re.search(pattern, body), "expected ``if (!check) hold_phonemes = 0``"


def test_c_body_restores_hold_international_flag() -> None:
    """The body restores ``international_flag`` from ``hold_international_flag``."""
    body = _extract_body()
    assert re.search(
        r"pCmd_t\s*->\s*international_flag\s*=\s*pCmd_t\s*->\s*hold_international_flag\s*;",
        body,
    )


def test_c_body_restores_hold_q_flag() -> None:
    """The body restores ``q_flag`` from ``hold_q_flag``."""
    body = _extract_body()
    assert re.search(
        r"pCmd_t\s*->\s*q_flag\s*=\s*pCmd_t\s*->\s*hold_q_flag\s*;",
        body,
    )


def test_c_body_sets_hold_replay_ignore_to_one() -> None:
    """The body sets ``hold_replay_ignore = 1`` before draining."""
    body = _extract_body()
    assert re.search(
        r"pCmd_t\s*->\s*hold_replay_ignore\s*=\s*1\s*;",
        body,
    )


def test_c_body_handles_insert_space() -> None:
    """The ``insert_space`` arm exists and runs cm_phon_check or cm_phon_match."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*insert_space\s*\)", body), "expected ``if (insert_space)`` arm"
    # Both cm_phon_check(' ') and cm_phon_match(' ') appear in the body.
    assert re.search(r"cm_phon_check\s*\(\s*phTTS\s*,\s*' '\s*\)", body)
    assert re.search(r"cm_phon_match\s*\(\s*phTTS\s*,\s*' '\s*\)", body)


def test_c_body_drains_hold_strbuf_in_loop() -> None:
    """The body iterates ``for (i = 0; i < hc; i++)`` over ``hold_strbuf[i]``."""
    body = _extract_body()
    assert re.search(r"for\s*\(\s*i\s*=\s*0\s*;\s*i\s*<\s*hc\s*;\s*i\+\+\s*\)", body)
    assert re.search(r"pCmd_t\s*->\s*hold_strbuf\s*\[\s*i\s*\]", body)


def test_c_body_resets_hold_count_after_drain() -> None:
    """Post-loop ``pCmd_t->hold_count = 0;`` is preserved."""
    body = _extract_body()
    assert re.search(r"pCmd_t\s*->\s*hold_count\s*=\s*0\s*;", body)


def test_c_body_restores_hold_count_on_bailout() -> None:
    """On a check bail-out the body restores ``hold_count = hc;``."""
    body = _extract_body()
    assert re.search(r"pCmd_t\s*->\s*hold_count\s*=\s*hc\s*;", body), (
        "expected ``hold_count = hc;`` restore on bail-out"
    )


def test_c_body_returns_zero_on_check_bailout() -> None:
    """The body has ``return 0;`` for the check-bail-out path."""
    body = _extract_body()
    assert re.search(r"return\s+0\s*;", body), "expected ``return 0;`` bail-out arm"


def test_c_body_returns_one_at_end() -> None:
    """The body's final statement is ``return 1;``."""
    body = _extract_body()
    assert re.search(r"return\s+1\s*;\s*$", body.strip()), "expected ``return 1;`` at end of body"


# -- Behavioural tests of the Python shim ---------------------------


def test_python_returns_dataclass_result() -> None:
    """The shim returns a :class:`ReplayResult`."""
    state = ReplayState()
    res = replay_buffer(state, c=0, insert_space=False, check=False, match_cb=lambda _c, _s: None)
    assert isinstance(res, ReplayResult)
    assert isinstance(res.state, ReplayState)


def test_python_check_true_requires_check_cb() -> None:
    """``check=True`` without ``check_cb`` raises."""
    state = ReplayState()
    with pytest.raises(ValueError, match="check=True requires check_cb"):
        replay_buffer(state, c=0, insert_space=False, check=True)


def test_python_check_false_requires_match_cb() -> None:
    """``check=False`` without ``match_cb`` raises."""
    state = ReplayState()
    with pytest.raises(ValueError, match="check=False requires match_cb"):
        replay_buffer(state, c=0, insert_space=False, check=False)


def test_python_match_mode_clears_hold_phonemes() -> None:
    """``check=False`` resets ``hold_phonemes = 0``."""
    state = ReplayState(hold_phonemes=1)
    res = replay_buffer(state, c=0, insert_space=False, check=False, match_cb=lambda _c, _s: None)
    assert res.rc == 1
    assert res.state.hold_phonemes == 0


def test_python_check_mode_preserves_hold_phonemes() -> None:
    """``check=True`` does not touch ``hold_phonemes``."""
    state = ReplayState(hold_phonemes=1)
    res = replay_buffer(state, c=0, insert_space=False, check=True, check_cb=lambda _c, _s: 1)
    assert res.rc == 1
    assert res.state.hold_phonemes == 1


def test_python_restores_hold_snapshots_onto_live_fields() -> None:
    """The four ``hold_*`` snapshots flow into the live fields."""
    state = ReplayState(
        hold_q_flag=ord("r"),
        hold_international_flag=2,
        hold_international_temp=ord("s"),
        hold_international_phon_lang=3,
    )
    res = replay_buffer(state, c=0, insert_space=False, check=False, match_cb=lambda _c, _s: None)
    assert res.state.q_flag == ord("r")
    assert res.state.international_flag == 2
    assert res.state.international_temp == ord("s")
    assert res.state.international_phon_lang == 3


def test_python_drives_match_cb_over_hold_buffer() -> None:
    """``check=False`` drives the match callback over the buffer's first hc bytes."""
    state = ReplayState(hold_count=3)
    state.hold_strbuf[0] = ord("a")
    state.hold_strbuf[1] = ord("b")
    state.hold_strbuf[2] = ord("c")

    seen: list[int] = []

    def match_cb(byte: int, _st: ReplayState) -> None:
        seen.append(byte)

    res = replay_buffer(state, c=0, insert_space=False, check=False, match_cb=match_cb)
    assert res.rc == 1
    assert seen == [ord("a"), ord("b"), ord("c")]
    assert res.state.hold_count == 0


def test_python_insert_space_drives_match_cb_for_space_first() -> None:
    """``insert_space=True`` prepends a ``' '`` call to match_cb."""
    state = ReplayState(hold_count=1)
    state.hold_strbuf[0] = ord("x")

    seen: list[int] = []

    def match_cb(byte: int, _st: ReplayState) -> None:
        seen.append(byte)

    res = replay_buffer(state, c=0, insert_space=True, check=False, match_cb=match_cb)
    assert res.rc == 1
    assert seen[0] == ord(" ")
    assert seen[1] == ord("x")


def test_python_check_mode_bailout_restores_hold_count() -> None:
    """``check_cb`` returning 0 restores hold_count and bails with rc=0."""
    state = ReplayState(hold_count=3)
    state.hold_strbuf[0] = ord("a")
    state.hold_strbuf[1] = ord("b")
    state.hold_strbuf[2] = ord("c")

    def check_cb(byte: int, _st: ReplayState) -> int:
        return 0 if byte == ord("b") else 1

    res = replay_buffer(state, c=0, insert_space=False, check=True, check_cb=check_cb)
    assert res.rc == 0
    assert res.state.hold_count == 3  # restored to pre-call hc


def test_python_check_mode_success_restores_hold_count() -> None:
    """On full successful check drain, hold_count is restored to hc."""
    state = ReplayState(hold_count=2)
    state.hold_strbuf[0] = ord("a")
    state.hold_strbuf[1] = ord("b")
    res = replay_buffer(state, c=0, insert_space=False, check=True, check_cb=lambda _c, _s: 1)
    assert res.rc == 1
    assert res.state.hold_count == 2


def test_python_match_mode_trailing_c_runs_match() -> None:
    """Non-zero trailing ``c`` is driven through match_cb after the loop."""
    state = ReplayState(hold_count=1)
    state.hold_strbuf[0] = ord("a")
    seen: list[int] = []

    def match_cb(byte: int, _st: ReplayState) -> None:
        seen.append(byte)

    res = replay_buffer(state, c=ord("z"), insert_space=False, check=False, match_cb=match_cb)
    assert res.rc == 1
    assert seen == [ord("a"), ord("z")]


def test_python_match_mode_zero_c_skips_trailing() -> None:
    """``c=0`` skips the trailing-character call."""
    state = ReplayState(hold_count=1)
    state.hold_strbuf[0] = ord("a")
    seen: list[int] = []

    def match_cb(byte: int, _st: ReplayState) -> None:
        seen.append(byte)

    res = replay_buffer(state, c=0, insert_space=False, check=False, match_cb=match_cb)
    assert res.rc == 1
    assert seen == [ord("a")]


def test_python_empty_buffer_no_calls() -> None:
    """hold_count=0 with c=0 makes no callback calls."""
    state = ReplayState(hold_count=0)
    seen: list[int] = []

    def match_cb(byte: int, _st: ReplayState) -> None:
        seen.append(byte)

    res = replay_buffer(state, c=0, insert_space=False, check=False, match_cb=match_cb)
    assert res.rc == 1
    assert seen == []
