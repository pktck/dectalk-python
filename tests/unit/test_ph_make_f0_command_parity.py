"""C-source parity test for ``make_f0_command`` against ph_inton2.c.

Re-parses the C function body from the original DECtalk source at test
time, verifies the queue-side invariants (the delay clamp, the four
``f0*`` writes, the cumdur reset, and the ``NPHON_MAX - 1`` cap), and
asserts the Python port behaves identically.

Skips cleanly when ``DECTALK_SRC`` env / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_t import DphT
from dectalk.ph.make_f0_command import make_f0_command
from dectalk.ph.numeric_constants import NPHON_MAX

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_inton2.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_inton_c() -> str:
    """Read ph_inton2.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_make_f0_command_def() -> tuple[str, str]:
    """Return ``(signature, body)`` for the C ``make_f0_command`` definition.

    The C file contains a forward declaration at the top (terminated by
    ``;``) and the real definition near the end (with a body in braces).
    We skip declarations and return the function definition.
    """
    text = _read_inton_c()
    # Find every ``make_f0_command(...)`` header and keep the one followed
    # by a ``{`` body, not by ``;``.
    for match in re.finditer(
        r"(static\s+void\s+make_f0_command\s*\([^)]*\))\s*([;{])",
        text,
        re.DOTALL,
    ):
        if match.group(2) == "{":
            sig = match.group(1)
            # Walk braces from the ``{`` to find the matching ``}``.
            start = match.end(2) - 1
            depth = 0
            end = -1
            for i in range(start, len(text)):
                ch = text[i]
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            assert end > start, "unterminated make_f0_command body"
            body = text[start + 1 : end]
            # Strip block & line comments.
            body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
            body = re.sub(r"//.*", "", body)
            return sig, body
    raise AssertionError("make_f0_command definition not found in ph_inton2.c")


def test_make_f0_command_signature_matches_c() -> None:
    """The C signature carries the eight expected parameters in order."""
    sig, _ = _extract_make_f0_command_def()
    # Whitespace between params is variable; collapse to spaces.
    collapsed = re.sub(r"\s+", " ", sig)
    assert re.search(
        r"static void make_f0_command\s*\(\s*"
        r"LPTTS_HANDLE_T\s+\w+\s*,\s*"
        r"short\s+type\s*,\s*"
        r"short\s+rulenumber\s*,\s*"
        r"short\s+tar\s*,\s*"
        r"short\s+delay\s*,\s*"
        r"short\s+length\s*,\s*"
        r"short\s*\*\s*psCumdur\s*,\s*"
        r"short\s+nphon\s*\)",
        collapsed,
    ), f"unexpected signature: {collapsed!r}"


def test_make_f0_command_clamps_negative_delay() -> None:
    """The C body contains the ``(delay + *psCumdur) < 0`` clamp."""
    _, body = _extract_make_f0_command_def()
    assert re.search(
        r"if\s*\(\s*\(\s*delay\s*\+\s*\*\s*psCumdur\s*\)\s*<\s*0\s*\)",
        body,
    ), "expected `if ((delay + *psCumdur) < 0)` clamp in C body"
    # And the clamp body reassigns delay = -(*psCumdur);
    assert re.search(
        r"delay\s*=\s*-\s*\(\s*\*\s*psCumdur\s*\)\s*;",
        body,
    ), "expected `delay = -(*psCumdur);` clamp assignment"


def test_make_f0_command_writes_four_f0_arrays_in_order() -> None:
    """The C body writes ``f0tim``, ``f0tar``, ``f0type``, ``f0length`` (in that order)."""
    _, body = _extract_make_f0_command_def()
    writes = re.findall(
        r"pDph_t->(f0tim|f0tar|f0type|f0length)\s*\[\s*pDph_t->nf0tot\s*\]\s*=",
        body,
    )
    assert writes == ["f0tim", "f0tar", "f0type", "f0length"], (
        f"expected f0tim, f0tar, f0type, f0length writes in that order; got {writes!r}"
    )


def test_make_f0_command_f0_rhs_matches_c() -> None:
    """Each f0* slot is set to the expected RHS expression."""
    _, body = _extract_make_f0_command_def()
    # f0tim = *psCumdur + delay
    assert re.search(
        r"pDph_t->f0tim\s*\[\s*pDph_t->nf0tot\s*\]\s*=\s*\*\s*psCumdur\s*\+\s*delay\s*;",
        body,
    )
    # f0tar = tar
    assert re.search(
        r"pDph_t->f0tar\s*\[\s*pDph_t->nf0tot\s*\]\s*=\s*tar\s*;",
        body,
    )
    # f0type = type
    assert re.search(
        r"pDph_t->f0type\s*\[\s*pDph_t->nf0tot\s*\]\s*=\s*type\s*;",
        body,
    )
    # f0length = length
    assert re.search(
        r"pDph_t->f0length\s*\[\s*pDph_t->nf0tot\s*\]\s*=\s*length\s*;",
        body,
    )


def test_make_f0_command_resets_cumdur_to_neg_delay() -> None:
    """The C body assigns ``*psCumdur = (-delay);`` after the writes."""
    _, body = _extract_make_f0_command_def()
    assert re.search(
        r"\*\s*psCumdur\s*=\s*\(?\s*-\s*delay\s*\)?\s*;",
        body,
    ), "expected `*psCumdur = (-delay);` reset"


def test_make_f0_command_caps_nf0tot_at_nphon_max_minus_one() -> None:
    """The C body increments ``nf0tot`` only while ``nf0tot < NPHON_MAX - 1``."""
    _, body = _extract_make_f0_command_def()
    assert re.search(
        r"if\s*\(\s*pDph_t->nf0tot\s*<\s*NPHON_MAX\s*-\s*1\s*\)",
        body,
    ), "expected `if (pDph_t->nf0tot < NPHON_MAX - 1)` predicate"
    assert re.search(
        r"pDph_t->nf0tot\+\+\s*;",
        body,
    ), "expected `pDph_t->nf0tot++;` increment"


# ---------------------------------------------------------------------------
# Behavioural parity tests — Python port matches the C semantics.
# ---------------------------------------------------------------------------


def test_python_initial_state_then_first_command_populates_slot_zero() -> None:
    """From ``nf0tot == 0`` the first call writes slot [0] and bumps to 1."""
    state = DphT()
    assert state.nf0tot == 0
    cumdur = [0]
    make_f0_command(
        state, f0_type=7, rulenumber=1, tar=1200, delay=5, length=10, ps_cumdur=cumdur, nphon=0
    )
    assert state.nf0tot == 1
    assert state.f0tim[0] == 5  # *psCumdur (0) + delay (5)
    assert state.f0tar[0] == 1200
    assert state.f0type[0] == 7
    assert state.f0length[0] == 10
    # *psCumdur reset to -delay.
    assert cumdur[0] == -5


def test_python_multiple_calls_accumulate_in_slots() -> None:
    """Consecutive calls populate consecutive slots (0, 1, 2, ...)."""
    state = DphT()
    cumdur = [0]
    make_f0_command(
        state, f0_type=1, rulenumber=0, tar=100, delay=2, length=4, ps_cumdur=cumdur, nphon=0
    )
    make_f0_command(
        state, f0_type=2, rulenumber=0, tar=200, delay=3, length=5, ps_cumdur=cumdur, nphon=0
    )
    make_f0_command(
        state, f0_type=3, rulenumber=0, tar=300, delay=4, length=6, ps_cumdur=cumdur, nphon=0
    )
    assert state.nf0tot == 3
    assert state.f0type[:3] == [1, 2, 3]
    assert state.f0tar[:3] == [100, 200, 300]
    assert state.f0length[:3] == [4, 5, 6]


def test_python_negative_delay_clamps_against_cumdur() -> None:
    """``cumdur=5, delay=-10`` → effective delay clamps to -5."""
    state = DphT()
    cumdur = [5]
    make_f0_command(
        state, f0_type=0, rulenumber=0, tar=0, delay=-10, length=0, ps_cumdur=cumdur, nphon=0
    )
    # delay + cumdur = -10 + 5 = -5 < 0, so delay := -cumdur = -5.
    # f0tim = cumdur + delay = 5 + (-5) = 0.
    assert state.f0tim[0] == 0
    # cumdur reset to -delay = -(-5) = 5.
    assert cumdur[0] == 5


def test_python_nf0tot_caps_at_nphon_max_minus_one() -> None:
    """``nf0tot`` stops bumping once it reaches ``NPHON_MAX - 1``."""
    state = DphT()
    state.nf0tot = NPHON_MAX - 1
    cumdur = [0]
    make_f0_command(
        state, f0_type=0, rulenumber=0, tar=0, delay=0, length=0, ps_cumdur=cumdur, nphon=0
    )
    # Should not have incremented past NPHON_MAX - 1.
    assert state.nf0tot == NPHON_MAX - 1
    # A second call also keeps it pinned.
    make_f0_command(
        state, f0_type=0, rulenumber=0, tar=0, delay=0, length=0, ps_cumdur=cumdur, nphon=0
    )
    assert state.nf0tot == NPHON_MAX - 1
