"""C-source parity test for the N-prefixed ``LLFrame`` struct.

Re-parses ``src/dapi/src/ph/hlsynapi.h`` -- specifically the
``tagLLFrame`` typedef near line 389 -- enumerates every ``short`` field
in declaration order, and asserts each one is an attribute on the Python
:class:`dectalk.hlsyn.ll_frame_n.LLFrameN` dataclass.

The C struct is the N-prefixed variant used by the HL-to-LL bridge code
in ``hlsyn/hlframe.c`` -- not to be confused with the non-prefixed
``LLFrame`` in ``hlsyn/llsyn.h`` (which is already ported as
:class:`dectalk.hlsyn.llsyn.LLFrame`).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from dataclasses import fields
from pathlib import Path

import pytest

from dectalk.hlsyn.ll_frame_n import LLFrameN

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/hlsynapi.h"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_hlsynapi_h() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_tag_llframe_body() -> str:
    """Return the body of the ``tagLLFrame`` typedef as a string.

    The struct lives in ``hlsynapi.h`` between ``typedef struct tagLLFrame {``
    and the matching ``} LLFrame;`` -- we use that closing form to make
    sure we don't accidentally pick up a different struct.
    """
    text = _read_hlsynapi_h()
    match = re.search(
        r"typedef\s+struct\s+tagLLFrame\s*\{(.+?)\}\s*LLFrame\s*;",
        text,
        re.DOTALL,
    )
    assert match is not None, "tagLLFrame typedef not found in ph/hlsynapi.h"
    return match.group(1)


def _extract_c_field_names() -> list[str]:
    """Extract every ``short <NAME>;`` field from the ``tagLLFrame`` body.

    Returns the names in declaration order; the order matters because the
    C struct is sometimes initialised by positional designators elsewhere
    in the codebase.
    """
    body = _extract_tag_llframe_body()
    # Each field is ``short NAME;`` with optional whitespace. The struct
    # has no nested structs or function-pointer fields, so this matches
    # exactly the fields we want.
    return re.findall(r"\bshort\s+([A-Za-z_]\w*)\s*;", body)


def test_tag_llframe_typedef_present() -> None:
    """The N-prefixed ``tagLLFrame`` typedef is in ``ph/hlsynapi.h``."""
    text = _read_hlsynapi_h()
    assert re.search(
        r"typedef\s+struct\s+tagLLFrame\s*\{.+?\}\s*LLFrame\s*;",
        text,
        re.DOTALL,
    )


def test_all_c_fields_are_short() -> None:
    """Every field in ``tagLLFrame`` is a plain ``short`` (no pointers / structs).

    This protects the field-extraction regex: if a future revision of
    ``hlsynapi.h`` added a non-``short`` field, ``_extract_c_field_names``
    would silently skip it and the parity check below would still pass.
    """
    body = _extract_tag_llframe_body()
    # Strip whitespace and inspect every non-empty declaration.
    decls = [line.strip() for line in body.split(";") if line.strip()]
    for decl in decls:
        # Each declaration we expect is ``short NAME`` or ``short N1, N2``.
        assert re.fullmatch(r"short\s+[A-Za-z_]\w*(\s*,\s*[A-Za-z_]\w*)*", decl), (
            f"unexpected non-short field in tagLLFrame: {decl!r}"
        )


def test_every_c_field_has_python_attribute() -> None:
    """Every N-prefixed C field has a corresponding attribute on ``LLFrameN``."""
    c_names = _extract_c_field_names()
    assert c_names, "expected to find at least one short field in tagLLFrame"
    py_names = {f.name for f in fields(LLFrameN)}
    missing = [name for name in c_names if name not in py_names]
    assert not missing, (
        f"LLFrameN missing fields from C tagLLFrame: {missing}. C declares: {c_names}"
    )


def test_python_has_no_extra_fields_beyond_c() -> None:
    """``LLFrameN`` does not declare attributes the C struct doesn't have.

    Extra Python fields would silently desync the port; pin the field set
    exactly to the C declaration.
    """
    c_names = set(_extract_c_field_names())
    py_names = {f.name for f in fields(LLFrameN)}
    extras = sorted(py_names - c_names)
    assert not extras, f"LLFrameN declares fields not in C tagLLFrame: {extras}"


def test_every_c_field_is_n_prefixed() -> None:
    """Every field in ``tagLLFrame`` (the bridge variant) starts with ``N``.

    The other ``LLFrame`` -- in ``hlsyn/llsyn.h`` -- has non-prefixed
    fields (``F0``, ``AV``, ...). This test guards against accidentally
    extracting the wrong struct.
    """
    c_names = _extract_c_field_names()
    not_prefixed = [name for name in c_names if not name.startswith("N")]
    assert not not_prefixed, f"tagLLFrame fields without N prefix (wrong struct?): {not_prefixed}"


def test_field_defaults_are_zero() -> None:
    """Every field on a freshly constructed ``LLFrameN`` defaults to ``0``."""
    frame = LLFrameN()
    for f in fields(LLFrameN):
        assert getattr(frame, f.name) == 0, f"{f.name} default should be 0"


def test_field_count_matches_c_source() -> None:
    """Spot-check: the field count agrees with a manual read of the C source.

    The C struct (``ph/hlsynapi.h`` lines ~389-442) declares 48 ``short``
    fields. Pinning this number guards against the C source silently
    growing a new field without us noticing.
    """
    c_names = _extract_c_field_names()
    assert len(c_names) == 48, f"expected 48 C fields, found {len(c_names)}: {c_names}"
    py_names = [f.name for f in fields(LLFrameN)]
    assert len(py_names) == 48, f"expected 48 Python fields, found {len(py_names)}"
