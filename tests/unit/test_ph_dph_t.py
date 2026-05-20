"""Verify DphT mirrors ``DPH_T`` struct from ph_data.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.ph.dph_t import DphT
from dectalk.ph.numeric_constants import VOICE_PARS
from dectalk.ph.parameter_struct import Parameter

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_data.h")


def _parse_field_names() -> set[str] | None:
    """Return the set of field names in ``DPH_TAG`` struct."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+DPH_TAG(.*?)\}\s*DPH_T;",
        text,
        re.DOTALL,
    )
    if not match:
        return None
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    names: set[str] = set()
    # Handle: `<type> <name>[<sub>]?, <name2>[<sub>]?, ...;` -- including
    # multi-var declarations on one line, two-token types like
    # `unsigned long`, and pointer-modifier `*name`.
    decl_re = re.compile(
        r"^\s*(?:unsigned\s+|signed\s+|const\s+|volatile\s+)*"
        r"[A-Za-z_][A-Za-z_0-9]*\s+"
        r"((?:\*?\s*[A-Za-z_][A-Za-z_0-9]*\s*(?:\[[^;,]+\])?\s*,\s*)*"
        r"\*?\s*[A-Za-z_][A-Za-z_0-9]*\s*(?:\[[^;]+\])?)\s*;",
        re.MULTILINE,
    )
    name_re = re.compile(r"\*?\s*([A-Za-z_][A-Za-z_0-9]*)")
    for m in decl_re.finditer(body):
        decls = m.group(1)
        for decl in decls.split(","):
            name_match = name_re.match(decl.strip())
            if name_match:
                names.add(name_match.group(1))
    names.discard("DPH_TAG")
    return names


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_field_set_matches_c() -> None:
    """Every C field maps to a Python dataclass attribute."""
    c_fields = _parse_field_names()
    assert c_fields is not None
    py_fields = {f.name for f in fields(DphT)}
    assert c_fields == py_fields


def test_default_construction_does_not_raise() -> None:
    """Default-constructed instance is fully initialised."""
    state = DphT()
    assert state is not None


def test_uses_slots() -> None:
    """``DphT`` is a slots dataclass."""
    state = DphT()
    assert not hasattr(state, "__dict__")


def test_scalar_fields_default_zero() -> None:
    """Spot-check a few scalar fields default to 0."""
    state = DphT()
    for name in ("perpause", "compause", "nphone", "nsymbtot", "delta_pressure"):
        assert getattr(state, name) == 0


def test_array_fields_default_empty_list() -> None:
    """Spot-check that array fields default to empty lists."""
    state = DphT()
    for name in ("parstochip", "symbols", "curspdef", "dipspec"):
        value = getattr(state, name)
        assert isinstance(value, list)
        assert value == []


def test_param_array_default_is_voice_pars_long() -> None:
    """``param`` is a ``VOICE_PARS``-long list of zero-initialised Parameters."""
    state = DphT()
    assert isinstance(state.param, list)
    assert len(state.param) == VOICE_PARS
    assert all(isinstance(p, Parameter) for p in state.param)
    # All slots default-zero on tarend (no init has run yet).
    assert all(p.tarend == 0 for p in state.param)


def test_field_count_around_230() -> None:
    """The C struct has approximately 230 declared fields."""
    n = len(fields(DphT))
    # Tolerate small variation; the C source has revision-history padding.
    assert 220 <= n <= 240
