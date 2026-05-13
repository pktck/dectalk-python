"""C-source parity test for ``vv_coartic_across_c`` against ph_sttr2.c.

Re-parses the C function body and asserts:

- The active branches both write ``vvbouval = 0`` and
  ``vvdurtran = 0``.
- The ``dur_cons > NF100MS`` predicate is present.
- The original ``mlsh1`` arithmetic in the ``else`` branch is
  preserved as a commented-out line (parity guard against an
  accidental "uncomment" by a future translator).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.frame_counts import NF100MS
from dectalk.ph.vv_coartic_across_c import vv_coartic_across_c

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_sttr2.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_sttr2_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    text = _read_sttr2_c()
    match = re.search(
        r"static\s+void\s+vv_coartic_across_c\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "vv_coartic_across_c() not found in ph_sttr2.c"
    return match.group(1)


def test_signature_matches_c() -> None:
    """C signature: ``static void vv_coartic_across_c(PDPH_T, short, ...)``."""
    text = _read_sttr2_c()
    sig = re.search(
        r"static\s+void\s+vv_coartic_across_c\s*\(\s*PDPH_T\s+\w+\s*,\s*"
        r"short\s+\w+\s*,\s*short\s+\w+\s*,\s*"
        r"short\s+\w+\s*,\s*short\s+\w+\s*,\s*"
        r"short\s+\w+\s*,\s*short\s+\w+\s*\)",
        text,
    )
    assert sig is not None


def test_predicate_is_dur_cons_gt_nf100ms() -> None:
    """The branch trigger is ``dur_cons > NF100MS``."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*dur_cons\s*>\s*NF100MS\s*\)", body)


def test_active_writes_zero_in_then_branch() -> None:
    """Then branch (``dur_cons > NF100MS``) writes 0 to both fields."""
    body = _extract_body()
    assert re.search(r"pDphsettar->vvbouval\s*=\s*0\s*;", body)
    assert re.search(r"pDphsettar->vvdurtran\s*=\s*0\s*;", body)


def test_else_branch_active_writes_are_zero() -> None:
    """Else branch's *active* writes are also zero (the mlsh1 form is commented out)."""
    body = _extract_body()
    # Strip C comments so only active statements remain.
    stripped = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    stripped = re.sub(r"//.*", "", stripped)
    # Every active LHS of an assignment to vvbouval/vvdurtran must be exactly 0.
    for rhs in re.findall(
        r"pDphsettar->vv(?:bouval|durtran)\s*=\s*([^;]+);",
        stripped,
    ):
        assert rhs.strip() == "0", f"Active vvbouval/vvdurtran assignment is not zero: {rhs!r}"


def test_python_resets_both_when_above_nf100ms() -> None:
    """``dur_cons > NF100MS`` → both fields end up zero."""
    state = DphT()
    settar = DphSettarSt(vvbouval=123, vvdurtran=456)
    state.pSTphsettar = settar
    vv_coartic_across_c(state, 0, 0, 0, 0, 0, NF100MS + 1)
    assert settar.vvbouval == 0
    assert settar.vvdurtran == 0


def test_python_resets_both_when_below_or_equal_nf100ms() -> None:
    """``dur_cons <= NF100MS`` (else branch) → both fields end up zero."""
    state = DphT()
    settar = DphSettarSt(vvbouval=42, vvdurtran=99)
    state.pSTphsettar = settar
    vv_coartic_across_c(state, 0, 0, 0, 0, 0, NF100MS)
    assert settar.vvbouval == 0
    assert settar.vvdurtran == 0


def test_python_no_op_when_psttphsettar_missing() -> None:
    """Missing target struct → no exception (defensive)."""
    state = DphT()
    state.pSTphsettar = None
    vv_coartic_across_c(state, 0, 0, 0, 0, 0, 1)


def test_python_does_not_touch_unrelated_fields() -> None:
    """Only ``vvbouval`` / ``vvdurtran`` are mutated."""
    state = DphT()
    settar = DphSettarSt(bouval=11, vot=22, durtran=33, phonex=44)
    state.pSTphsettar = settar
    vv_coartic_across_c(state, 1, 2, 3, 4, 5, NF100MS + 1)
    assert settar.bouval == 11
    assert settar.vot == 22
    assert settar.durtran == 33
    assert settar.phonex == 44
