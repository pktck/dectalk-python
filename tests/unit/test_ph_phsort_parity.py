"""C-source parity test for ``phsort`` against ph_sort.c.

Re-parses the C body via brace-depth tracking and asserts the
dispatcher delegates to ``fr_phsort`` on French and ``all_phsort``
otherwise, matching the Python port.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from dectalk.kernel.lang_codes import LANG_english, LANG_french, LANG_german
from dectalk.ph.phsort import Phsort, phsort

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_sort.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_ph_sort_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of the top-level ``phsort`` dispatcher.

    There's only one ``int phsort (LPTTS_HANDLE_T phTTS)`` definition
    in ph_sort.c (the per-language ``fr_phsort`` and ``all_phsort`` are
    matched by their own names), so a straightforward regex covers it.
    """
    text = _read_ph_sort_c()
    match = re.search(
        r"\bint\s+phsort\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "phsort body not found"
    return match.group(1)


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``int phsort(LPTTS_HANDLE_T phTTS)``."""
    text = _read_ph_sort_c()
    assert re.search(r"\bint\s+phsort\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", text)


def test_dispatches_on_lang_curr() -> None:
    """The body reads ``pKsd_t->lang_curr``."""
    body = _extract_body()
    assert re.search(r"\bpKsd_t\s*->\s*lang_curr\b", body)


def test_french_branch_calls_fr_phsort() -> None:
    """``lang_curr == LANG_french`` -> ``return(fr_phsort(phTTS))``."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*pKsd_t\s*->\s*lang_curr\s*==\s*LANG_french\s*\)",
        body,
    )
    assert re.search(r"return\s*\(\s*fr_phsort\s*\(\s*phTTS\s*\)\s*\)", body)


def test_default_branch_calls_all_phsort() -> None:
    """The ``else`` branch returns ``all_phsort(phTTS)``."""
    body = _extract_body()
    assert re.search(r"return\s*\(\s*all_phsort\s*\(\s*phTTS\s*\)\s*\)", body)


# -- Python behavioural tests ----------------------------------------------


def test_french_routes_to_fr_phsort() -> None:
    """``language == LANG_french`` -> ``target == "fr_phsort"``."""
    dispatch = phsort(LANG_french)
    assert dispatch.target == "fr_phsort"
    assert dispatch.language == LANG_french


def test_english_routes_to_all_phsort() -> None:
    """``language == LANG_english`` -> ``target == "all_phsort"``."""
    dispatch = phsort(LANG_english)
    assert dispatch.target == "all_phsort"
    assert dispatch.language == LANG_english


def test_german_routes_to_all_phsort() -> None:
    """Every non-French language routes to ``all_phsort``."""
    dispatch = phsort(LANG_german)
    assert dispatch.target == "all_phsort"


def test_dispatch_is_a_frozen_dataclass() -> None:
    """:class:`PhsortDispatch` is frozen so callers can't mutate the decision."""
    dispatch = phsort(LANG_french)
    with pytest.raises(FrozenInstanceError):
        dispatch.target = "tampered"  # type: ignore[misc]


def test_c_style_alias_points_to_python_impl() -> None:
    """:data:`Phsort` is the inventory-name alias of :func:`phsort`."""
    assert Phsort is phsort


def test_phsort_dispatch_carries_input_language() -> None:
    """The returned dispatch carries the input language for caller routing."""
    for lang in (LANG_english, LANG_french, LANG_german, 0xFF):
        assert phsort(lang).language == lang
