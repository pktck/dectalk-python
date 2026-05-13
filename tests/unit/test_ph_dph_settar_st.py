"""Verify DphSettarSt mirrors ``DPHSETTAR_ST`` from ph_data.h."""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt

_C_HEADER: Path = Path("/tmp/dectalk-src/src/dapi/src/ph/ph_data.h")


def _parse_field_names() -> set[str] | None:
    """Return the set of field names in ``DPHSETTAR_ST``."""
    if not _C_HEADER.exists():
        return None
    text = _C_HEADER.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"typedef\s+struct\s+phsettar_static_tag(.*?)DPHSETTAR_ST;",
        text,
        re.DOTALL,
    )
    if not match:
        return None
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return {
        m.group(2)
        for m in re.finditer(
            r"^\s*(short|int|char|PARAMETER)\s+\*?\s*([a-zA-Z_][a-zA-Z_0-9]*)\s*;",
            body,
            re.MULTILINE,
        )
    }


@pytest.mark.skipif(not _C_HEADER.exists(), reason="C source not available")
def test_field_set_matches_c() -> None:
    """Every C field maps to a Python dataclass attribute (and vice versa)."""
    c_fields = _parse_field_names()
    assert c_fields is not None
    py_fields = {f.name for f in fields(DphSettarSt)}
    assert c_fields == py_fields


def test_default_construction_zero_filled() -> None:
    """Default-constructed instance has every int field zeroed."""
    state = DphSettarSt()
    for f in fields(state):
        value = getattr(state, f.name)
        if f.name == "np":
            assert value is None
        else:
            assert value == 0


def test_uses_slots() -> None:
    """``DphSettarSt`` is a slots dataclass."""
    state = DphSettarSt()
    assert not hasattr(state, "__dict__")


def test_field_count_is_98() -> None:
    """The C struct has 98 declared fields after comment-stripping."""
    assert len(fields(DphSettarSt)) == 98


def test_setar_phase_fields_present() -> None:
    """Spot-check key PH_SETAR.C fields are present."""
    for name in ("bouval", "vot", "vvbouval", "phonex", "gencoartic", "np"):
        assert hasattr(DphSettarSt(), name)


def test_drawt0_phase_fields_present() -> None:
    """Spot-check key PH_DRWT0.C fields are present."""
    for name in ("basecntr", "basestep", "f0command", "glide_step", "f0a1"):
        assert hasattr(DphSettarSt(), name)


def test_inton_phase_fields_present() -> None:
    """Spot-check key PH_INTON.C fields are present."""
    for name in ("nrises_sofar", "hatsize", "tarstop", "numsyllables"):
        assert hasattr(DphSettarSt(), name)
