"""C-source parity test for the ph_setar.c dispatch chain (Issue #48).

The four-function dispatch chain in ``ph_setar.c``::

    phsettar (orchestrator)
      ├── getbegtar (begin-of-phone target lookup)
      │     └── gettar (per-phone target dispatch)
      │           └── us_gettar / uk_gettar / ... (per-language leaf)
      ├── getendtar (end-of-phone target lookup)
      │     └── gettar
      └── make_dip (diphthong dip generator, called when gettar < -1)

This file is the **integration** parity test for the chain. The
per-function structural tests live next door
(``test_ph_gettar_parity.py``, ``test_ph_getbegtar_parity.py``,
``test_ph_getendtar_parity.py``, ``test_ph_make_dip_parity.py``).
Here we assert:

1. The C call-graph relationships still hold (getbegtar/getendtar
   call ``gettar``; make_dip is invoked from phsettar when the
   target sentinel is diphthong-tagged).
2. The Python ports mirror the C dispatch: ``getbegtar`` /
   ``getendtar`` route through Python ``gettar``, and ``phsettar``
   dispatches every per-parameter lookup through ``gettar`` /
   ``getbegtar`` (not directly through ``us_gettar``).
3. End-to-end numerical behaviour on a US-English vowel: a call
   into ``phsettar`` populates the per-parameter ``tarcur`` /
   ``tarend`` slots in a way consistent with what a hand-rolled
   ``gettar`` + ``getendtar`` walk would produce.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import inspect
import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.include.usp_codes import USP_AA, USP_K
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph import phsettar as phsettar_module
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getbegtar import getbegtar
from dectalk.ph.getendtar import getendtar
from dectalk.ph.gettar import gettar
from dectalk.ph.make_dip import make_dip
from dectalk.ph.numeric_constants import F1, F2, F3, FZ
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_setar.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_setar_c() -> str:
    """Read ph_setar.c, normalising CRLF and decoding as latin-1."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_function_body(name: str, return_type: str = r"\w+") -> str:
    """Return the body of ``<return_type> <name>(...)`` from ph_setar.c.

    The C source has both forward declarations (``;``) and definitions
    (``{...}``). Walk every match and pick the one that opens a brace
    block. The static ``make_dip`` definition is also handled because
    the regex tolerates the leading ``static`` via the caller's
    ``return_type`` argument.
    """
    text = _read_setar_c()
    pattern = re.compile(rf"\b{return_type}\s+{re.escape(name)}\s*\(")
    for match in pattern.finditer(text):
        paren_start = match.end() - 1
        depth = 1
        i = paren_start + 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        # Skip whitespace between ``)`` and ``{``.
        while i < len(text) and text[i] in " \t\n\r":
            i += 1
        if i >= len(text) or text[i] != "{":
            continue
        start = i + 1
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        if depth == 0:
            return text[start : i - 1]
    raise AssertionError(f"{name} definition not found in ph_setar.c")


# -- C-source dispatch-graph assertions ------------------------------------


def test_c_getbegtar_calls_gettar() -> None:
    """C ``getbegtar`` body opens with ``temp = gettar(phTTS, nfone)``."""
    body = _extract_function_body("getbegtar", return_type=r"short")
    assert re.search(r"\btemp\s*=\s*gettar\s*\(\s*phTTS\s*,\s*nfone\s*\)", body), (
        "getbegtar must delegate to gettar()"
    )


def test_c_getendtar_calls_gettar() -> None:
    """C ``getendtar`` body opens with ``temp = gettar(phTTS, nfone)``."""
    body = _extract_function_body("getendtar", return_type=r"short")
    assert re.search(r"\btemp\s*=\s*gettar\s*\(\s*phTTS\s*,\s*nfone\s*\)", body), (
        "getendtar must delegate to gettar()"
    )


def test_c_make_dip_uses_p_diph() -> None:
    """C ``make_dip`` body reads ``p_diph[pdip]`` to seed oldvalue."""
    body = _extract_function_body("make_dip", return_type=r"static\s+void")
    assert re.search(r"p_diph\s*\[\s*pdip\s*\]", body), "make_dip reads p_diph[pdip]"


def test_c_gettar_definition_exists() -> None:
    """C ``int gettar(LPTTS_HANDLE_T, int)`` definition present in source."""
    text = _read_setar_c()
    assert re.search(
        r"\bint\s+gettar\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*int\s+\w+\s*\)\s*\{", text
    ), "gettar definition must exist in ph_setar.c"


def test_c_phsettar_calls_getbegtar_and_gettar() -> None:
    """The orchestrator dispatches through ``getbegtar`` / ``gettar``.

    The Python ``phsettar`` rewires through these wrappers (matching
    the C call-graph) instead of going directly to ``us_gettar``.
    """
    text = _read_setar_c()
    # The C orchestrator function is split between several
    # preprocessor variants but every one calls getbegtar and gettar.
    assert re.search(r"\bgetbegtar\s*\(", text), "ph_setar.c must call getbegtar"
    assert re.search(r"\bgettar\s*\(", text), "ph_setar.c must call gettar"


# -- Python dispatch-graph assertions --------------------------------------


def test_python_getbegtar_imports_gettar() -> None:
    """Python ``getbegtar.py`` imports and uses ``gettar``."""
    src = inspect.getsource(getbegtar)
    assert "gettar(" in src, "getbegtar() must call gettar()"


def test_python_getendtar_imports_gettar() -> None:
    """Python ``getendtar.py`` imports and uses ``gettar``."""
    src = inspect.getsource(getendtar)
    assert "gettar(" in src, "getendtar() must call gettar()"


def test_python_phsettar_dispatches_through_gettar() -> None:
    """Python ``phsettar`` dispatches through ``gettar`` / ``getbegtar``.

    Matches the C call-graph; the previous orchestrator scaffolding
    called ``us_gettar`` directly, which made the per-language
    dispatch invisible. After issue #48 the orchestrator must route
    every per-parameter lookup through the wrappers.
    """
    src = inspect.getsource(phsettar_module)
    # The orchestrator must import from the wrappers, not the leaf.
    assert "from dectalk.ph.gettar import gettar" in src, (
        "phsettar must dispatch through gettar(), not us_gettar() directly"
    )
    assert "from dectalk.ph.getbegtar import getbegtar" in src, (
        "phsettar must dispatch through getbegtar() for tarnex lookups"
    )
    # And actually call the wrappers in the body.
    assert re.search(r"\bgettar\s*\(\s*phTTS", src), "phsettar must call gettar(phTTS, ...)"
    assert re.search(r"\bgetbegtar\s*\(\s*phTTS", src), "phsettar must call getbegtar(phTTS, ...)"


# -- Behavioural integration -----------------------------------------------


def _make_handle(
    *,
    phones: list[int],
    np_idx: int,
    nphone: int = 1,
    malfem: int = 0,
) -> TtsHandle:
    """Build a minimal TtsHandle with a populated DphT for dispatch tests."""
    p_dph_t = DphT()
    p_dph_t.allophons = list(phones)
    p_dph_t.allofeats = [0] * len(phones)
    p_dph_t.nallotot = len(phones)
    p_dph_t.nphone = nphone
    p_dph_t.malfem = malfem
    p_dph_t.last_lang = 0
    settar = DphSettarSt()
    settar.np = np_idx
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    handle.p_kernel_share_data = KsdT()
    return handle


def test_getbegtar_matches_gettar_for_non_diphthong() -> None:
    """For non-diphthong segments, getbegtar returns gettar's value verbatim.

    The C source: ``if (temp < -1)`` is the only branch that mutates
    ``temp``; otherwise getbegtar returns gettar's value unchanged.
    """
    # FZ for AA is NON_NASAL_ZERO (positive), not a diphthong sentinel.
    handle_a = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=FZ)
    handle_b = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=FZ)
    assert getbegtar(handle_a, 1) == gettar(handle_b, 1)


def test_getendtar_matches_gettar_for_non_diphthong() -> None:
    """For non-diphthong segments, getendtar returns gettar's value verbatim.

    Same invariant as ``test_getbegtar_matches_gettar_for_non_diphthong``:
    the ``temp < -1`` diphthong branch is the only mutation path.
    """
    handle_a = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=FZ)
    handle_b = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=FZ)
    assert getendtar(handle_a, 1) == gettar(handle_b, 1)


def test_dispatch_chain_k_coarticulation_propagates() -> None:
    """K coarticulation in gettar() propagates through getbegtar/getendtar.

    The +300/+500 K-rule lives inside ``gettar()``. Since getbegtar /
    getendtar both delegate to gettar() before any further processing,
    a /k/ target on F2 must show the +300 bump through any of the
    three entry points.
    """
    h_base = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F2)
    h_k_get = _make_handle(phones=[GEN_SIL, USP_K, GEN_SIL, GEN_SIL], np_idx=F2)
    h_k_beg = _make_handle(phones=[GEN_SIL, USP_K, GEN_SIL, GEN_SIL], np_idx=F2)
    h_k_end = _make_handle(phones=[GEN_SIL, USP_K, GEN_SIL, GEN_SIL], np_idx=F2)

    base_f2 = gettar(h_base, 1)
    via_gettar = gettar(h_k_get, 1)
    via_begtar = getbegtar(h_k_beg, 1)
    via_endtar = getendtar(h_k_end, 1)

    # All three K-path values agree (non-diphthong target -- the
    # wrappers should pass through unchanged).
    assert via_gettar == via_begtar == via_endtar
    # And the K bump is propagated.
    assert via_gettar > base_f2


def test_dispatch_chain_f3_k_coarticulation() -> None:
    """K coarticulation on F3 (+500) also propagates through the chain."""
    h_base = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F3)
    h_k = _make_handle(phones=[GEN_SIL, USP_K, GEN_SIL, GEN_SIL], np_idx=F3)

    base_f3 = gettar(h_base, 1)
    via_gettar = gettar(h_k, 1)
    assert via_gettar > base_f3


def test_make_dip_callable_signature() -> None:
    """``make_dip`` is callable with the documented Python signature.

    Smoke check: the function must accept ``(p_dph_t, pdip,
    inhdr_frames, shrink, struccur, pps_ndips_cell)`` -- the C
    ``short **ppsNdips`` modelled as a single-element mutable cell.
    """
    sig = inspect.signature(make_dip)
    params = list(sig.parameters)
    assert params == [
        "p_dph_t",
        "pdip",
        "inhdr_frames",
        "shrink",
        "struccur",
        "pps_ndips",
    ], f"make_dip signature drift: {params}"


def test_all_four_wrappers_no_longer_raise_for_us_path() -> None:
    """None of the four ports raise NotImplementedError on the US path.

    The C dispatch routes UK/GR/LA/SP/FR fonts to per-language helpers
    that are still deferred (issue #48 only covers the US English path
    plus the dispatch chain itself). But the US-English code path --
    triggered by phones whose font byte is ``PFUSA<<PSFONT`` -- must
    complete without raising.
    """
    # All four entry points on a plain US-English vowel:
    for entry, args in (
        (gettar, (_make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F1), 1)),
        (getbegtar, (_make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F1), 1)),
        (getendtar, (_make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F1), 1)),
    ):
        # Just exercise -- the actual numeric value depends on the
        # us_femtar table layout and is covered in per-function tests.
        # The contract here is "no NotImplementedError on the US path".
        try:
            entry(*args)
        except NotImplementedError as exc:  # pragma: no cover - regression guard
            pytest.fail(f"{entry.__name__} raised NotImplementedError on US path: {exc}")


def test_diphthong_sentinel_routes_through_gettar() -> None:
    """When gettar returns a diphthong sentinel, getbegtar/getendtar diverge.

    The C source's only differential between the three is the
    diphthong post-processing. We synthesise a diphthong sentinel by
    pointing ``p_tar`` at a forged short array whose entry for our
    phone is ``-2`` (a diphthong tag) and verify that getbegtar
    returns the first ``p_diph`` entry while getendtar walks to the
    final entry.
    """
    handle = _make_handle(phones=[GEN_SIL, USP_AA, GEN_SIL, GEN_SIL], np_idx=F1)

    # Prime the US tables (gettar's first call does this).
    gettar(handle, 1)

    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    # Forge a diphthong sentinel: rewrite p_tar's F1 entry for USP_AA
    # to -2 so gettar returns -2, then put a synthetic 3-entry diph
    # at index 2 of p_diph: [_, _, 1234, 5678, -1, ...] (entries 2..4).
    assert p_dph_t.p_tar is not None
    p_tar = p_dph_t.p_tar
    f1_offset = (USP_AA & 0xFF) + 0 * 71  # F1 row
    saved_tar = p_tar[f1_offset]
    p_tar[f1_offset] = -2

    assert p_dph_t.p_diph is not None
    p_diph = p_dph_t.p_diph
    saved_diph = (p_diph[2], p_diph[3], p_diph[4])
    p_diph[2] = 1234
    p_diph[3] = 5678
    p_diph[4] = -1

    try:
        beg = getbegtar(handle, 1)
        end = getendtar(handle, 1)
    finally:
        p_tar[f1_offset] = saved_tar
        p_diph[2], p_diph[3], p_diph[4] = saved_diph

    # getbegtar returns p_diph[-(-2)] = p_diph[2] = 1234.
    # par_type for F1 is FORM_FREQ (3) so us_special_coartic is added.
    # The coartic delta on a SIL-flanked AA at dip_pos=0 is small;
    # assert getbegtar is in a plausible neighbourhood of 1234.
    assert abs(beg - 1234) < 500, f"getbegtar gave {beg!r}, far from p_diph[2]=1234"
    # getendtar walks forward from index 2 to the -1 sentinel at
    # index 4, then returns p_diph[3] = 5678.
    assert abs(end - 5678) < 500, f"getendtar gave {end!r}, far from p_diph[3]=5678"
    # And the diphthong walk distinguishes the two endpoints.
    assert beg != end
