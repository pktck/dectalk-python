"""Inventory parity test for kernel/services.c against the Python port.

Re-parses ``src/dapi/src/kernel/services.c`` at test time, enumerates every
function definition that the Linux build actually compiles, and asserts each
one has a corresponding Python port under :mod:`dectalk.kernel` -- or sits on
the :data:`_DEFERRED` allow-list with a one-line reason.

The point of the test is to catch *missing* C->Python translations early:
adding a new function to ``services.c`` (or noticing that one slipped past
the orchestrator) fails this test loudly with a clear ``missing ports``
message.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/kernel/services.c"
)
_PY_DIR = Path(__file__).resolve().parents[2] / "src" / "dectalk" / "kernel"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Preprocessor symbols we consider "defined" for the Linux libtts_us.so
# build. Anything not in this set is treated as undefined when evaluating
# #ifdef / #if defined() expressions.
# --------------------------------------------------------------------------
_LINUX_DEFINED: frozenset[str] = frozenset({"__linux__"})


# --------------------------------------------------------------------------
# Functions defined in services.c that are intentionally not ported (or
# ported under a different Pythonic name). Each entry needs a one-line
# reason. When a port lands, the entry must be removed -- the
# ``test_no_dead_deferred_entries`` guard enforces that.
# --------------------------------------------------------------------------
_DEFERRED: dict[str, str] = {
    # Windows multimedia / audio-handle helpers. These are dispatched
    # through libtts_us.so's PA_GetVolume / PA_SetVolume on Linux. The
    # Python audio backend does its own gain shaping, so the bridging
    # logic in StereoVolumeControl / SetStereoVolume isn't needed yet.
    "StereoVolumeControl": "Calls PA_GetVolume/PA_SetVolume; Python audio backend bypasses",
    "SetStereoVolume": "Calls PA_SetVolume; Python audio backend bypasses",
    "ModifyVolume": "static helper to StereoVolumeControl; deferred along with it",
    # Pythonic-rename camelCase->snake_case. Python ports live in
    # volume_table.py as encode_dectalk_volume / decode_dectalk_volume.
}


# --------------------------------------------------------------------------
# Helpers.
# --------------------------------------------------------------------------


def _read_services_c() -> str:
    """Read services.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _strip_comments(text: str) -> str:
    """Remove ``/* ... */`` block and ``// ...`` line comments.

    Both forms can hide function-definition-looking text inside ``services.c``
    (especially the large commented-out bodies of ``start_flush`` /
    ``reset_spc``), so we strip them before scanning.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _eval_cpp_expr(expr: str, defined: frozenset[str]) -> bool:
    """Evaluate a simple ``#if`` expression against ``defined``.

    Supports ``defined X`` / ``defined(X)``, ``!``, ``&&``, ``||``, and
    parentheses. Anything else (numeric constants, comparisons) is treated
    conservatively as false -- ``services.c`` only uses defined() guards,
    so that's sufficient for this file.
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


def _scan_definitions(active_text: str, depth_zero_before: list[bool]) -> set[str]:
    """Scan ``active_text`` for top-level function definitions.

    A definition is ``IDENT(...) {`` at brace depth 0. Function pointer
    declarations (``(*ident)(...)``) and control-flow keywords are
    filtered out.
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


def _enumerate_c_functions() -> set[str]:
    """Parse top-level function *definitions* from services.c.

    Tracks ``#ifdef`` / ``#ifndef`` / ``#if`` / ``#else`` / ``#endif``
    nesting so functions defined only in non-Linux branches are skipped.
    Returns the names that the Linux build actually compiles into the
    translation unit.
    """
    raw = _read_services_c()
    no_comments = _strip_comments(raw)
    active_text, depth_zero_before = _collect_active_text(no_comments.split("\n"))
    return _scan_definitions(active_text, depth_zero_before)


def _enumerate_python_kernel_symbols() -> set[str]:
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


def test_every_linux_services_c_function_has_python_port() -> None:
    """Every C function in services.c (Linux build) has a Python port."""
    c_funcs = _enumerate_c_functions()
    assert c_funcs, "expected to find at least one function definition in services.c"
    py_syms = _enumerate_python_kernel_symbols()
    missing = c_funcs - py_syms - set(_DEFERRED.keys())
    assert not missing, (
        f"Missing Python ports for kernel/services.c functions: "
        f"{sorted(missing)}. Either port them, or add to _DEFERRED with a reason."
    )


def test_deferred_kernel_symbols_actually_in_c_source() -> None:
    """_DEFERRED entries must correspond to real C functions (catches typos)."""
    c_text = _read_services_c()
    for name in _DEFERRED:
        assert re.search(rf"\b{re.escape(name)}\s*\(", c_text), (
            f"_DEFERRED has '{name}' but services.c doesn't mention it"
        )


def test_no_dead_deferred_entries() -> None:
    """If a deferred function gets ported, the _DEFERRED entry should be removed."""
    py_syms = _enumerate_python_kernel_symbols()
    redundant = set(_DEFERRED.keys()) & py_syms
    assert not redundant, (
        f"_DEFERRED entries that are actually ported (remove from _DEFERRED): {sorted(redundant)}"
    )


def test_enumerator_finds_known_spc_chain_helpers() -> None:
    """Sanity check: the six SPC-chain helpers are detected by the enumerator.

    If this test fails the regex / preprocessor walker has regressed and the
    inventory test above is unreliable.
    """
    c_funcs = _enumerate_c_functions()
    expected = {
        "save_index",
        "check_index",
        "adjust_index",
        "adjust_allo",
        "set_index_allo",
        "free_index",
    }
    missing = expected - c_funcs
    assert not missing, f"enumerator failed to find SPC-chain helpers: {sorted(missing)}"


def test_enumerator_skips_msdos_only_functions() -> None:
    """MSDOS-only vol_* helpers are gated by #ifdef MSDOS and must be skipped."""
    c_funcs = _enumerate_c_functions()
    for name in ("vol_up", "vol_down", "vol_set"):
        assert name not in c_funcs, (
            f"{name} is defined under #ifdef MSDOS but the enumerator did not skip it"
        )


def test_enumerator_skips_arm7_only_functions() -> None:
    """ARM7-only allocator helpers are gated by #ifdef ARM7 and must be skipped."""
    c_funcs = _enumerate_c_functions()
    for name in ("get_spc_packet", "free_spc_packet"):
        assert name not in c_funcs, (
            f"{name} is defined under #ifdef ARM7 but the enumerator did not skip it"
        )


def test_enumerator_skips_win32_only_sleep() -> None:
    """The ``sleep`` definition lives entirely inside #ifdef WIN32."""
    assert "sleep" not in _enumerate_c_functions()
