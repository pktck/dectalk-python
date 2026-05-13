"""Inventory parity test for the VTM-module C files against the Python port.

Re-parses every VTM C source file that the Linux ``libtts_us.so`` build
actually compiles, enumerates every Linux-active function definition, and
asserts each one has a corresponding Python port under :mod:`dectalk.vtm`
-- or sits on the :data:`_DEFERRED` allow-list with a one-line reason.

The VTM module is almost entirely unported today (only a handful of
lookup tables and the :func:`tone` helper have been translated), so
:data:`_DEFERRED` is large by design: each entry is a TODO with a reason,
and the test serves as a precise progress meter -- every new Python port
that lands removes one entry.

Files scanned, per ``src/dapi/src/vtm/Makefile`` (``VTM_SRC``):

- ``vtm.c``       -- thin ``#include`` dispatcher; defaults to ``vtm3.c``
- ``vtm3.c``      -- the implementation pulled in by ``vtm.c`` for our
  build (none of ``VTM1`` / ``VTM2`` / ``FP_VTM`` are defined, so the
  ``#else`` branch of ``vtm.c`` selects ``vtm3.c``)
- ``sync.c``      -- VTM sync thread + ``WaitForAudioSampleToPlay``
- ``vtmiont.c``   -- VTM output thread, pipe drain, visual notifications
- ``playtone.c``  -- DTMF / sine-pair tone injection

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/vtm"
_PY_DIR = Path(__file__).resolve().parents[2] / "src" / "dectalk" / "vtm"

# ``vtm.c`` itself is a small ``#include`` dispatcher; the implementation
# functions live in ``vtm3.c`` (the default branch for our build). We scan
# both so the dispatcher's structural sanity is checked too, even though
# it contributes no function definitions.
_C_FILES: list[Path] = [
    _C_DIR / "vtm.c",
    _C_DIR / "vtm3.c",
    _C_DIR / "sync.c",
    _C_DIR / "vtmiont.c",
    _C_DIR / "playtone.c",
]

pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in _C_FILES),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Preprocessor symbols we consider "defined" for the Linux libtts_us.so
# build. Drawn from the generated ``vtm/Makefile`` plus the
# ``english_release`` target in ``src/Makefile`` (``LANGUAGE=ENGLISH
# -DENGLISH_US -DACNA``). Anything not in this set is treated as
# undefined when evaluating #ifdef / #if defined() expressions --
# crucially, ``HLSYN``, ``VTM1``, ``VTM2``, ``FP_VTM``, ``ACI_LICENSE``,
# ``ARM7``, ``MSDOS``, ``WIN32``, ``__osf__`` and ``VXWORKS`` are NOT in
# our build, so the corresponding branches are inactive.
# --------------------------------------------------------------------------
_LINUX_DEFINED: frozenset[str] = frozenset(
    {
        "__linux__",
        "_REENTRANT",
        "NOMME",
        "LTSSIM",
        "TTSSIM",
        "ANSI",
        "BLD_DECTALK_DLL",
        "ENGLISH",
        "ENGLISH_US",
        "ACNA",
        "ACCESS32",
        "TYPING_MODE",
    }
)


# --------------------------------------------------------------------------
# Functions defined in the scanned VTM C files that are intentionally not
# ported yet (or ported under a different Pythonic name). Each entry needs
# a one-line reason. When a port lands, the entry must be removed -- the
# ``test_no_dead_deferred_entries`` guard enforces that.
#
# VTM is almost entirely unported today (only :mod:`dectalk.vtm.tone` and
# a clutch of lookup-table modules exist), so this dict shrinks over time
# as ports land. Every removed entry == one C function newly available
# in Python.
# --------------------------------------------------------------------------
_DEFERRED: dict[str, str] = {
    # ---- vtm3.c -- the speech waveform generator (Klatt synthesiser). --
    "InitializeVTM": (
        "Top-level VTM init; depends on the full speaker-definition / "
        "filter-state layout not yet ported"
    ),
    "SetSampleRate": (
        "Switches the synth sample rate (8k/11k); depends on the VTM "
        "state struct and resampler chain"
    ),
    "speech_waveform_generator": (
        "Inner Klatt waveform loop; the bit-accurate synth lives in "
        "src/dectalk/hlsyn/, this is the C-style entry not yet wrapped"
    ),
    "read_speaker_definition": (
        "Parses the speaker .def files into VTM state; deferred with the speaker-table layout"
    ),
    "getmax": (
        "Static debug helper that tracks absolute-value peaks across the "
        "VTM pipeline; deferred until a debug surface exists"
    ),
    "checkmax": (
        "Static debug helper that flags out-of-range coefficients; deferred along with getmax"
    ),
    # ---- sync.c -- the VTM-side sync thread and WFASTP helper. --------
    "OP_THREAD_ROUTINE": (
        "OP_THREAD_ROUTINE() expands to a thread-entry function "
        "definition; the two underlying entries (sync_main in sync.c and "
        "vtm_main in vtmiont.c) are both deferred until threading lands"
    ),
    "WaitForAudioSampleToPlay": (
        "Blocks the sync thread until PA_GetPosition crosses a sample "
        "boundary; deferred along with the rest of the audio sync layer"
    ),
    # ---- vtmiont.c -- the VTM output thread and pipe machinery. -------
    "EmptyVtmPipe": (
        "Drains pending VTM packets back into the audio queue; depends "
        "on the unported VTM pipe/packet layout"
    ),
    "OutputData": (
        "Pushes a buffer of synthesised samples onto the audio handle; "
        "the Python audio backend uses a different output path"
    ),
    "SendVisualNotification": (
        "Posts phoneme/duration events back to the host (for lipsync "
        "UIs); no visual-notification surface in the Python port yet"
    ),
    # ---- playtone.c -- DTMF / sine-pair tone injection. ---------------
    "PlayTones": (
        "Multi-tone scheduler that fills the audio pipe with [INTONE..] "
        "tone packets; depends on the unported pipe layer"
    ),
    "Tone": "ported as vtm.tone.tone (PEP8 rename)",
}


# --------------------------------------------------------------------------
# Helpers.
# --------------------------------------------------------------------------


def _read_c(path: Path) -> str:
    """Read a C source file with CRLF endings normalised."""
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _strip_comments(text: str) -> str:
    """Remove ``/* ... */`` block and ``// ...`` line comments.

    Both forms can hide function-definition-looking text inside the VTM
    sources (large commented-out bodies are common), so we strip them
    before scanning.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _eval_cpp_expr(expr: str, defined: frozenset[str]) -> bool:
    """Evaluate a simple ``#if`` expression against ``defined``.

    Supports ``defined X`` / ``defined(X)``, ``!``, ``&&``, ``||``, and
    parentheses. Anything else (numeric constants, comparisons) is treated
    conservatively as false -- the VTM sources only use defined() guards
    in their conditionals, so that's sufficient.
    """
    # Normalise: ``defined X`` and ``defined ( X )`` -> ``defined(X)``.
    expr = re.sub(r"defined\s*\(\s*(\w+)\s*\)", r"defined(\1)", expr)
    expr = re.sub(r"defined\s+(\w+)", r"defined(\1)", expr)

    # Replace each ``defined(NAME)`` with True / False.
    def _sub_defined(match: re.Match[str]) -> str:
        return "True" if match.group(1) in defined else "False"

    expr = re.sub(r"defined\(\s*(\w+)\s*\)", _sub_defined, expr)

    # Map C boolean operators to Python.
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"(?<![=!<>])!(?!=)", " not ", expr)

    # If anything non-trivial remains (bare identifiers, numbers, etc.)
    # we treat the whole expression as False rather than risking an
    # eval exception. The remaining tokens we expect are: True, False,
    # and, or, not, parentheses, whitespace.
    if not re.fullmatch(r"[\s\w()]*", expr.replace("True", "").replace("False", "")):
        return False
    leftovers = re.sub(r"\b(True|False|and|or|not)\b|[\s()]+", "", expr)
    if leftovers:
        return False

    try:
        return bool(eval(expr, {"__builtins__": {}}, {}))
    except (SyntaxError, NameError, ValueError):
        return False


_CPP_KEYWORDS = frozenset({"if", "while", "for", "switch", "return", "sizeof", "do", "else"})


def _active_no_self(stack: list[tuple[bool, bool]]) -> bool:
    """Whether all frames in ``stack`` (excluding any pushed top frame) are active."""
    return all(frame[0] for frame in stack)


def _handle_cpp_directive(directive: str, cpp_stack: list[tuple[bool, bool]]) -> None:
    """Apply a ``#`` directive to ``cpp_stack`` in place.

    Supports ``#ifdef`` / ``#ifndef`` / ``#if`` / ``#elif`` / ``#else`` /
    ``#endif``. Other directives are ignored.
    """
    if directive.startswith("ifdef"):
        name_part = directive[5:].strip()
        name = name_part.split()[0] if name_part else ""
        branch = name in _LINUX_DEFINED
        cpp_stack.append((branch and _active_no_self(cpp_stack), branch))
    elif directive.startswith("ifndef"):
        name_part = directive[6:].strip()
        name = name_part.split()[0] if name_part else ""
        branch = name not in _LINUX_DEFINED
        cpp_stack.append((branch and _active_no_self(cpp_stack), branch))
    elif directive.startswith("if "):
        expr = directive[3:].strip()
        branch = _eval_cpp_expr(expr, _LINUX_DEFINED)
        cpp_stack.append((branch and _active_no_self(cpp_stack), branch))
    elif directive.startswith("if("):
        expr = directive[2:].strip()
        branch = _eval_cpp_expr(expr, _LINUX_DEFINED)
        cpp_stack.append((branch and _active_no_self(cpp_stack), branch))
    elif directive.startswith("elif") and cpp_stack:
        expr = directive[4:].strip()
        _, prev_taken = cpp_stack[-1]
        branch = (not prev_taken) and _eval_cpp_expr(expr, _LINUX_DEFINED)
        cpp_stack[-1] = (
            branch and _active_no_self(cpp_stack[:-1]),
            prev_taken or branch,
        )
    elif directive.startswith("else") and cpp_stack:
        _, prev_taken = cpp_stack[-1]
        branch = not prev_taken
        cpp_stack[-1] = (branch and _active_no_self(cpp_stack[:-1]), True)
    elif directive.startswith("endif") and cpp_stack:
        cpp_stack.pop()


def _collect_active_text(lines: list[str]) -> tuple[str, list[bool]]:
    """Walk lines tracking ``#ifdef`` state.

    Returns the concatenation of Linux-active lines and a parallel list
    where entry ``i`` is True iff the character at ``active_text[i]`` is
    encountered with brace_depth == 0 *before* consuming that character.
    """
    cpp_stack: list[tuple[bool, bool]] = []
    brace_depth = 0
    active_text: list[str] = []
    depth_zero_before: list[bool] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            _handle_cpp_directive(stripped[1:].lstrip(), cpp_stack)
            continue

        if not all(frame[0] for frame in cpp_stack):
            continue

        for ch in line + "\n":
            depth_zero_before.append(brace_depth == 0)
            active_text.append(ch)
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth = max(brace_depth - 1, 0)

    return "".join(active_text), depth_zero_before


def _balance_parens(text: str, open_idx: int) -> int | None:
    """Return the index just after the ``)`` matching ``text[open_idx] == '('``.

    Returns None if the parens are unbalanced (shouldn't happen for real C).
    """
    depth = 1
    i = open_idx + 1
    n = len(text)
    while i < n and depth > 0:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    return i if depth == 0 else None


def _scan_definitions(active_text: str, depth_zero_before: list[bool]) -> set[str]:
    """Scan ``active_text`` for top-level function definitions.

    A definition is ``IDENT(...) {`` at brace depth 0. Function pointer
    declarations (``(*ident)(...)``) and control-flow keywords are
    filtered out, as are prototype declarations ending with ``;``.
    """
    name_re = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
    found: set[str] = set()
    pos = 0
    n = len(active_text)
    while pos < n:
        match = name_re.search(active_text, pos)
        if match is None:
            break

        ident = match.group(1)
        pos = match.end()

        if ident in _CPP_KEYWORDS:
            continue
        # Must be at top-level (depth 0 right before the identifier).
        if not depth_zero_before[match.start()]:
            continue

        # Balance parens to find the end of the arg list.
        i = _balance_parens(active_text, match.end() - 1)
        if i is None:
            continue

        # Look ahead past whitespace: ``{`` -> definition; ``;`` -> decl.
        while i < n and active_text[i] in " \t\n\r":
            i += 1
        if i < n and active_text[i] == "{":
            found.add(ident)

    return found


def _enumerate_c_functions_in(path: Path) -> set[str]:
    """Parse top-level function definitions from one VTM C source file.

    Tracks ``#ifdef`` / ``#ifndef`` / ``#if`` / ``#else`` / ``#endif``
    nesting so functions defined only in non-Linux branches are skipped.
    Returns the names that the Linux build actually compiles into the
    translation unit.
    """
    raw = _read_c(path)
    no_comments = _strip_comments(raw)
    active_text, depth_zero_before = _collect_active_text(no_comments.split("\n"))
    return _scan_definitions(active_text, depth_zero_before)


def _enumerate_all_c_functions() -> set[str]:
    """Union of function definitions across all scanned VTM C files."""
    funcs: set[str] = set()
    for path in _C_FILES:
        funcs.update(_enumerate_c_functions_in(path))
    return funcs


def _enumerate_python_vtm_symbols() -> set[str]:
    """Collect top-level ``def`` names plus every ``__all__`` entry."""
    names: set[str] = set()
    for py_file in sorted(_PY_DIR.glob("*.py")):
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:  # pragma: no cover -- defensive
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        names.update(_extract_all_entries(node.value))
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and node.value is not None
                ):
                    names.update(_extract_all_entries(node.value))
    return names


def _extract_all_entries(value: ast.expr) -> set[str]:
    """Extract string literal entries from an ``__all__`` AST node."""
    entries: set[str] = set()
    if isinstance(value, ast.List | ast.Tuple):
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                entries.add(elt.value)
    return entries


# --------------------------------------------------------------------------
# Tests.
# --------------------------------------------------------------------------


def test_every_linux_active_vtm_function_has_python_port() -> None:
    """Every Linux-active C function in the scanned VTM files has a Python port."""
    c_funcs = _enumerate_all_c_functions()
    assert c_funcs, "expected to find at least one function definition across VTM files"
    py_syms = _enumerate_python_vtm_symbols()
    missing = c_funcs - py_syms - set(_DEFERRED.keys())
    assert not missing, (
        f"Missing Python ports for VTM-module C functions: "
        f"{sorted(missing)}. Either port them, or add to _DEFERRED with a reason."
    )


def test_deferred_vtm_symbols_actually_in_c_source() -> None:
    """_DEFERRED entries must correspond to real C functions (catches typos)."""
    combined = "\n".join(_read_c(p) for p in _C_FILES)
    for name in _DEFERRED:
        assert re.search(rf"\b{re.escape(name)}\s*\(", combined), (
            f"_DEFERRED has '{name}' but none of the scanned VTM C files mention it"
        )


def test_no_dead_deferred_entries() -> None:
    """If a deferred function gets ported, the _DEFERRED entry should be removed."""
    py_syms = _enumerate_python_vtm_symbols()
    redundant = set(_DEFERRED.keys()) & py_syms
    assert not redundant, (
        f"_DEFERRED entries that are actually ported (remove from _DEFERRED): {sorted(redundant)}"
    )


def test_enumerator_finds_known_vtm_entry_points() -> None:
    """Sanity check: well-known VTM entry points are detected by the enumerator.

    If this test fails the regex / preprocessor walker has regressed and the
    inventory test above is unreliable. The chosen names span all five
    scanned files (vtm3.c, sync.c, vtmiont.c, playtone.c) so any one walker
    regression -- a botched #ifdef, a comment-strip bug, etc -- breaks at
    least one of them.
    """
    c_funcs = _enumerate_all_c_functions()
    expected = {
        # vtm3.c (pulled in via ``#include "vtm3.c"`` from vtm.c)
        "InitializeVTM",
        "speech_waveform_generator",
        "setzeroabc",
        # sync.c -- OP_THREAD_ROUTINE expands to a function definition
        "OP_THREAD_ROUTINE",
        "WaitForAudioSampleToPlay",
        # vtmiont.c
        "EmptyVtmPipe",
        "OutputData",
        # playtone.c
        "PlayTones",
        "Tone",
    }
    missing = expected - c_funcs
    assert not missing, f"enumerator failed to find well-known VTM entry points: {sorted(missing)}"


def test_enumerator_skips_arm7_only_blocks_in_vtm3() -> None:
    """vtm3.c opens with ``#ifdef ARM7`` ``#pragma`` blocks that must be skipped.

    ARM7 is not in our build's defines, so anything strictly inside an
    ARM7-only branch should be invisible to the enumerator. ``vtm3.c``
    is gated by ``#pragma arm section`` regions and several ARM-only
    optimisation paths; the enumerator must not pick up identifiers
    introduced inside those branches.
    """
    # No production function in vtm3.c is unconditionally ARM7-only, so we
    # check this indirectly by asserting that the scanned function set is
    # exactly the 7 Linux-active ones (catches the case where the walker
    # mis-handles ARM7 and starts spuriously emitting ARM-only helpers).
    c_funcs = _enumerate_c_functions_in(_C_DIR / "vtm3.c")
    expected = {
        "InitializeVTM",
        "SetSampleRate",
        "checkmax",
        "getmax",
        "read_speaker_definition",
        "setzeroabc",
        "speech_waveform_generator",
    }
    assert c_funcs == expected, (
        f"vtm3.c enumerator drift -- expected exactly {sorted(expected)}, got {sorted(c_funcs)}"
    )


def test_enumerator_skips_aci_license_only_doit() -> None:
    """vtm3.c's ``doit()`` body lives inside ``#ifdef ACI_LICENSE``.

    ACI_LICENSE is not in our build, so the empty ``doit()`` stub must
    be invisible to the enumerator. If it leaks through, we'd see a
    spurious "missing port" complaint for a function that doesn't
    actually exist on Linux.
    """
    c_funcs = _enumerate_c_functions_in(_C_DIR / "vtm3.c")
    assert "doit" not in c_funcs, (
        "doit is defined under #ifdef ACI_LICENSE but the enumerator did not skip it"
    )


def test_enumerator_skips_alternative_vtm_variants() -> None:
    """vtm.c selects vtm3.c at compile time; vtm1.c / vtm2.c / vtm_fa.c are dead.

    The Linux build does NOT define ``VTM1`` / ``VTM2`` / ``FP_VTM``, so
    ``vtm.c`` falls through to ``#include "vtm3.c"``. The other variant
    files (``vtm1.c``, ``vtm2.c``, ``vtm_fa.c``) are never compiled. The
    inventory test scans only ``vtm3.c`` for that reason; this guard
    ensures we haven't accidentally added one of the alternate variants
    to ``_C_FILES``.
    """
    variant_names = {p.name for p in _C_FILES}
    for forbidden in ("vtm1.c", "vtm2.c", "vtm_fa.c", "vtm_f.c", "vtm_i.c"):
        assert forbidden not in variant_names, (
            f"{forbidden} is not selected by vtm.c on Linux; remove it from _C_FILES"
        )
