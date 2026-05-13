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

import pytest

from dectalk.ph.init_variables import InitVariablesOut, init_variables
from dectalk.ph.tts_handle import TtsHandle

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


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError, match=r"dectalk\._capi"):
        init_variables(handle)


def test_python_shim_error_mentions_phase_plan() -> None:
    """Error message points at the plan file so callers can find context."""
    handle = TtsHandle()
    with pytest.raises(NotImplementedError) as exc_info:
        init_variables(handle)
    assert "Phase E" in str(exc_info.value)


def test_init_variables_out_default_constructible() -> None:
    """The companion ``InitVariablesOut`` dataclass is default-constructible."""
    out = InitVariablesOut()
    # Default-zero across all fourteen out-parameters keeps shim semantics
    # explicit until a full port lands.
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
