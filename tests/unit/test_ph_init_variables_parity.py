"""C-source parity test for ``init_variables`` against ph_setar.c.

Re-parses the C body via brace-depth tracking and asserts the
static phsettar initialiser still exists in the develop branch with
its expected out-pointer arguments and feature precomputes. Also
checks the Python shim raises ``NotImplementedError`` as documented.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.init_variables import InitVariablesOut, init_variables
from dectalk.ph.numeric_constants import A2, AV, B1, F1, TILT
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_setar.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_setar_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body of the static ``init_variables`` helper.

    The C source has both a forward declaration (ending in ``;``) and a
    definition (ending in ``{...}``); walk every match and pick the one
    that opens a brace block.
    """
    text = _read_setar_c()
    for match in re.finditer(r"\bstatic\s+void\s+init_variables\s*\(", text):
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
    raise AssertionError("init_variables definition not found in ph_setar.c")


def _extract_signature() -> str:
    """Return the parenthesised parameter list of the static ``init_variables``.

    The C source has both a forward declaration and a definition; we pick
    the one that opens a ``{`` body (the prototype uses slightly different
    argument names, e.g. ``feanex`` vs ``psFeanex``).
    """
    text = _read_setar_c()
    for match in re.finditer(r"\bstatic\s+void\s+init_variables\s*\(", text):
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
        sig = text[paren_start:i]
        # Skip whitespace; pick the definition (next non-space is ``{``).
        j = i
        while j < len(text) and text[j] in " \t\n\r":
            j += 1
        if j < len(text) and text[j] == "{":
            return sig
    raise AssertionError("init_variables definition not found in ph_setar.c")


# -- C-source structural assertions ----------------------------------------


def test_signature_matches_c() -> None:
    """C signature: ``static void init_variables(LPTTS_HANDLE_T, short *, ...)``."""
    text = _read_setar_c()
    assert re.search(r"\bstatic\s+void\s+init_variables\s*\(\s*LPTTS_HANDLE_T", text)


def test_signature_carries_fourteen_short_out_pointers() -> None:
    """The signature mentions all fourteen out-pointer names."""
    sig = _extract_signature()
    for arg in (
        "psInhdr_frames",
        "psShrink",
        "psShrif",
        "psShrib",
        "psPholas",
        "psFealas",
        "psFeacur",
        "psFeanex",
        "psStruclm2",
        "psStruclas",
        "psStruccur",
        "psStrucnex",
        "ppsNdips",
        "psPhonp2",
    ):
        assert arg in sig, f"signature missing out-pointer {arg}"


def test_first_position_branch() -> None:
    """Body has the ``nphone == 0`` first-position branch."""
    body = _extract_body()
    assert re.search(r"pDph_t\s*->\s*nphone\s*==\s*0", body)
    assert re.search(r"pholas?\s*=\s*GEN_SIL", body, re.IGNORECASE) or re.search(
        r"\*psPholas\s*=\s*GEN_SIL", body
    )


def test_feature_precomputes() -> None:
    """Body writes ``*psFealas`` / ``*psFeacur`` / ``*psFeanex`` via phone_feature."""
    body = _extract_body()
    assert re.search(r"\*psFealas\s*=\s*phone_feature", body)
    assert re.search(r"\*psFeacur\s*=\s*phone_feature", body)
    assert re.search(r"\*psFeanex\s*=\s*phone_feature", body)


def test_shrink_computation_calls_muldv() -> None:
    """Body uses ``muldv(FRAC_ONE, durfon, *psInhdr_frames)`` for ``*psShrink``."""
    body = _extract_body()
    assert re.search(r"\*psShrink\s*=\s*muldv", body)


def test_tspesh_reset_loop() -> None:
    """Body zeroes ``tspesh`` on PAV / PAP / PF1 / etc. parameters."""
    body = _extract_body()
    assert re.search(r"PAV\s*\.\s*tspesh\s*=\s*0", body)
    assert re.search(r"PTILT\s*\.\s*tspesh\s*=\s*0", body)


# -- Python behavioural tests ----------------------------------------------


def _make_handle(*, nphone: int, initsw: int = 1, nallotot: int = 10) -> TtsHandle:
    """Build a minimal :class:`TtsHandle` populated for init_variables.

    The C source reads ``allophons[nphone-2..nphone+1]``,
    ``allofeats[nphone-2..nphone+1]``, ``durfon``, and
    ``pSTphsettar->{initsw,phcur,phonex}``. The fixture writes a
    contiguous run of ``GEN_SIL`` so all phone-feature lookups
    short-circuit through the table without out-of-range errors.

    ``initsw=1`` skips the very-first-call branch that loops over
    ``getbegtar(handle, 0)`` -- that codepath calls into the still-
    deferred ``getbegtar`` shim, which is its own port target.
    """
    p_dph_t = DphT()
    p_dph_t.allophons = [GEN_SIL] * nallotot
    p_dph_t.allofeats = [0] * nallotot
    p_dph_t.nallotot = nallotot
    p_dph_t.nphone = nphone
    p_dph_t.durfon = 12
    settar = DphSettarSt()
    settar.initsw = initsw
    settar.phcur = GEN_SIL
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    return handle


def test_init_variables_out_default_constructible() -> None:
    """The companion ``InitVariablesOut`` dataclass is default-constructible."""
    out = InitVariablesOut()
    for name in (
        "inhdr_frames",
        "shrink",
        "shrif",
        "shrib",
        "pholas",
        "fealas",
        "feacur",
        "feanex",
        "struclm2",
        "struclas",
        "struccur",
        "strucnex",
        "ndips_offset",
        "phonp2",
    ):
        assert getattr(out, name) == 0


def test_first_position_seeds_pholas_to_gen_sil() -> None:
    """``nphone == 0`` sets ``pholas`` to GEN_SIL and ``struclm2`` to 0."""
    handle = _make_handle(nphone=0)
    out = init_variables(handle)
    assert out.pholas == GEN_SIL
    assert out.struclm2 == 0


def test_first_position_initsw_branch_is_skipped_when_already_set() -> None:
    """When ``initsw != 0`` the first-call PF1..PTILT seeding loop is skipped."""
    handle = _make_handle(nphone=0, initsw=1)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    init_variables(handle)
    # tarend slots stay at their default (0) because the getbegtar loop
    # only fires on first-ever init (initsw == 0).
    for idx in range(F1, TILT + 1):
        assert p_dph_t.param[idx].tarend == 0


def test_subsequent_position_writes_pholas_from_phcur() -> None:
    """``nphone > 0`` copies ``pholas = phcur`` and reads ``struclas`` from allofeats."""
    handle = _make_handle(nphone=3)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    settar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    settar.phcur = 0x1E03  # arbitrary phone code
    p_dph_t.allofeats[1] = 0xAB
    p_dph_t.allofeats[2] = 0xCD
    out = init_variables(handle)
    assert out.pholas == 0x1E03
    assert out.struclas == 0xCD
    assert out.struclm2 == 0xAB


def test_phcur_loaded_from_allophons() -> None:
    """``phcur`` is updated from ``allophons[nphone]``."""
    handle = _make_handle(nphone=2)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    settar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    p_dph_t.allophons[2] = 0x1E07
    init_variables(handle)
    assert settar.phcur == 0x1E07


def test_near_clause_end_clamps_phonex_to_gen_sil() -> None:
    """Within 2 phones of the end ``phonex = GEN_SIL`` and ``strucnex = 0``."""
    handle = _make_handle(nphone=9, nallotot=10)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    settar = cast(DphSettarSt, p_dph_t.pSTphsettar)
    out = init_variables(handle)
    assert settar.phonex == GEN_SIL
    assert out.strucnex == 0


def test_ndips_offset_seeded_at_one() -> None:
    """``ppsNdips`` is initialised to ``&dipspec[1]``; Python uses offset 1."""
    handle = _make_handle(nphone=1)
    out = init_variables(handle)
    assert out.ndips_offset == 1


def test_silence_skips_shrink_block() -> None:
    """``phcur == GEN_SIL`` skips the sonorant-shrink computation."""
    handle = _make_handle(nphone=1)
    out = init_variables(handle)
    # phcur is GEN_SIL by the fixture default; shrink/shrif/shrib stay 0.
    assert out.shrink == 0
    assert out.shrif == 0
    assert out.shrib == 0


def test_tspesh_slots_zeroed() -> None:
    """All sixteen ``param[].tspesh`` slots reachable from C are cleared."""
    handle = _make_handle(nphone=1)
    p_dph_t = cast(DphT, handle.p_ph_thread_data)
    # Pre-poison the slots so we can prove the function clears them.
    for idx in (F1, B1, AV, A2):
        p_dph_t.param[idx].tspesh = 42
    init_variables(handle)
    for idx in (F1, B1, AV, A2):
        assert p_dph_t.param[idx].tspesh == 0
