"""C-source parity test for ``UnusedLLParameters``.

Re-parses ``src/dapi/src/hlsyn/hlframe.c`` -- specifically the
``UnusedLLParameters`` static helper near line 741 -- and asserts:

- Each N-prefixed field written by the C body is written by
  :func:`dectalk.hlsyn.unused_ll_parameters.unused_ll_parameters` to the
  same value.
- The ``REMOVE_FORMANT`` / ``REMOVE_BANDWIDTH`` constants in
  ``hlsyn.h`` agree with the Python module's values.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.hlsyn.ll_frame_n import LLFrameN
from dectalk.hlsyn.unused_ll_parameters import (
    REMOVE_BANDWIDTH,
    REMOVE_FORMANT,
    unused_ll_parameters,
)

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn"
_HLFRAME_C = _C_DIR / "hlframe.c"
_HLSYN_H = _C_DIR / "hlsyn.h"

pytestmark = pytest.mark.skipif(
    not (_HLFRAME_C.is_file() and _HLSYN_H.is_file()),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read(path: Path) -> str:
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _strip_comments(text: str) -> str:
    """Drop ``/* ... */`` block and ``// ...`` line comments.

    The ``UnusedLLParameters`` body has both forms (large block comments
    explaining each group, and a ``// llframe->DB1 = 0;`` line). Stripping
    them up front lets us match the assignment statements directly.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _extract_unused_ll_parameters_body() -> str:
    """Return the body of ``UnusedLLParameters`` (comments stripped)."""
    text = _strip_comments(_read(_HLFRAME_C))
    match = re.search(
        r"static\s+void\s*\n?\s*UnusedLLParameters\s*\(\s*LLFrame\s*\*\s*\w+\s*\)"
        r"\s*\{(.+?)\n\}",
        text,
        re.DOTALL,
    )
    assert match is not None, "UnusedLLParameters() definition not found in hlframe.c"
    return match.group(1)


def _parse_simple_assignments(body: str) -> dict[str, int]:
    """Parse ``llframe-><FIELD> = <VALUE>;`` and chained ``A = B = VALUE;``.

    Returns a mapping from field name to its assigned integer value. The
    C body uses two forms:

    - ``llframe->NSQ = 0;``
    - ``llframe->NFTP = llframe->NFTZ = REMOVE_FORMANT;``

    Both must resolve to a known integer (we substitute
    ``REMOVE_FORMANT``/``REMOVE_BANDWIDTH`` after extracting them from
    ``hlsyn.h``).
    """
    constants = _extract_remove_constants()
    assignments: dict[str, int] = {}
    # Match the full statement up to the trailing ``;``. Each statement
    # is a chain ``llframe->A = llframe->B = ... = VALUE``.
    for stmt in re.findall(r"([^;{}]+?);", body):
        stripped = stmt.strip()
        if not stripped:
            continue
        # The statement must start with ``llframe->`` for us to consider it.
        if not stripped.startswith("llframe->"):
            continue
        # Split on ``=`` while keeping the RHS as the last piece.
        parts = [p.strip() for p in stripped.split("=")]
        if len(parts) < 2:
            continue
        rhs = parts[-1]
        # Resolve the RHS to an integer.
        if rhs in constants:
            value = constants[rhs]
        else:
            try:
                value = int(rhs)
            except ValueError:
                pytest.fail(f"unexpected RHS in UnusedLLParameters: {rhs!r} (stmt: {stripped!r})")
        # Every LHS in the chain (except the final RHS) is ``llframe->FIELD``.
        for lhs in parts[:-1]:
            match = re.fullmatch(r"llframe->([A-Za-z_]\w*)", lhs)
            assert match is not None, f"unexpected LHS in UnusedLLParameters: {lhs!r}"
            assignments[match.group(1)] = value
    return assignments


def _extract_remove_constants() -> dict[str, int]:
    """Read ``REMOVE_FORMANT`` / ``REMOVE_BANDWIDTH`` from ``hlsyn.h``."""
    text = _read(_HLSYN_H)
    result: dict[str, int] = {}
    for name in ("REMOVE_FORMANT", "REMOVE_BANDWIDTH"):
        match = re.search(rf"#define\s+{name}\s+(\d+)", text)
        assert match is not None, f"{name} not found in hlsyn.h"
        result[name] = int(match.group(1))
    return result


# --------------------------------------------------------------------------
# Constant parity.
# --------------------------------------------------------------------------


def test_remove_formant_matches_c() -> None:
    """``REMOVE_FORMANT`` in ``hlsyn.h`` matches the Python value."""
    c_constants = _extract_remove_constants()
    assert c_constants["REMOVE_FORMANT"] == REMOVE_FORMANT


def test_remove_bandwidth_matches_c() -> None:
    """``REMOVE_BANDWIDTH`` in ``hlsyn.h`` matches the Python value."""
    c_constants = _extract_remove_constants()
    assert c_constants["REMOVE_BANDWIDTH"] == REMOVE_BANDWIDTH


def test_remove_formant_specific_value() -> None:
    """``REMOVE_FORMANT == 1000`` per ``hlsyn.h``."""
    assert REMOVE_FORMANT == 1000


def test_remove_bandwidth_specific_value() -> None:
    """``REMOVE_BANDWIDTH == 200`` per ``hlsyn.h``."""
    assert REMOVE_BANDWIDTH == 200


# --------------------------------------------------------------------------
# Function-signature parity.
# --------------------------------------------------------------------------


def test_unused_ll_parameters_is_static() -> None:
    """The C definition is ``static void UnusedLLParameters(LLFrame *)``."""
    text = _strip_comments(_read(_HLFRAME_C))
    assert re.search(
        r"static\s+void\s*\n?\s*UnusedLLParameters\s*\(\s*LLFrame\s*\*\s*\w+\s*\)",
        text,
    )


# --------------------------------------------------------------------------
# Body parity: every assigned field matches.
# --------------------------------------------------------------------------


def test_every_c_assignment_matches_python() -> None:
    """Every ``llframe->FIELD = VALUE;`` in the C body matches Python."""
    c_assignments = _parse_simple_assignments(_extract_unused_ll_parameters_body())
    assert c_assignments, "no assignments parsed from UnusedLLParameters body"
    frame = LLFrameN()
    unused_ll_parameters(frame)
    for field, expected in c_assignments.items():
        actual = getattr(frame, field)
        assert actual == expected, (
            f"after unused_ll_parameters: {field} == {actual!r}, "
            f"C source sets {field} = {expected!r}"
        )


def test_expected_assignments_are_all_present() -> None:
    """The set of assigned fields matches the manual transcription of the C body.

    Pinning the set guards against the C source quietly adding or
    removing an assignment without us updating the Python.
    """
    c_assignments = _parse_simple_assignments(_extract_unused_ll_parameters_body())
    expected_fields = {
        "NFTP",
        "NFTZ",
        "NBTP",
        "NBTZ",
        "NSQ",
        "NFL",
        "NDF1",
        "NANV",
        "NA1V",
        "NA2V",
        "NA3V",
        "NA4V",
        "NATV",
        "NB6",
    }
    assert set(c_assignments.keys()) == expected_fields, (
        f"UnusedLLParameters assignment set drift: "
        f"got {sorted(c_assignments.keys())}, expected {sorted(expected_fields)}"
    )


def test_specific_assigned_values() -> None:
    """Spot-check the exact values from the C body."""
    c_assignments = _parse_simple_assignments(_extract_unused_ll_parameters_body())
    assert c_assignments["NFTP"] == 1000  # REMOVE_FORMANT
    assert c_assignments["NFTZ"] == 1000
    assert c_assignments["NBTP"] == 200  # REMOVE_BANDWIDTH
    assert c_assignments["NBTZ"] == 200
    assert c_assignments["NSQ"] == 0
    assert c_assignments["NFL"] == 0
    assert c_assignments["NDF1"] == 0
    assert c_assignments["NANV"] == 0
    assert c_assignments["NA1V"] == 0
    assert c_assignments["NA2V"] == 0
    assert c_assignments["NA3V"] == 0
    assert c_assignments["NA4V"] == 0
    assert c_assignments["NATV"] == 0
    assert c_assignments["NB6"] == 1000


def test_unused_ll_parameters_does_not_touch_other_fields() -> None:
    """Fields the C body does not assign retain their pre-call values.

    The C helper only writes a specific subset of fields; everything
    else must be left untouched. A regression that overwrote ``NF0`` or
    ``NAV`` would silently break the HL-to-LL pipeline.
    """
    frame = LLFrameN(NF0=123, NAV=45, NOQ=67, NTL=89, NDI=11, NAH=22, NAF=33, NF1=400)
    unused_ll_parameters(frame)
    # These untouched fields must still hold the values we set above.
    assert frame.NF0 == 123
    assert frame.NAV == 45
    assert frame.NOQ == 67
    assert frame.NTL == 89
    assert frame.NDI == 11
    assert frame.NAH == 22
    assert frame.NAF == 33
    assert frame.NF1 == 400
