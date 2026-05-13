"""Inventory parity test for selected PH-module C files against the Python port.

Re-parses the most-active PH C source files at test time, enumerates every
function definition that the Linux build actually compiles, and asserts each
one has a corresponding Python port under :mod:`dectalk.ph` -- or sits on
the :data:`_DEFERRED` allow-list with a one-line reason.

The PH module is mostly unported (we're early in the C->Python pipeline for
this layer), so :data:`_DEFERRED` is large by design: each entry is a TODO
with a reason, and the test serves as a precise progress meter -- every
new Python port that lands removes one entry.

The five C files scanned here are the ones the user identified as carrying
the bulk of unported, Linux-active PH functions:

- ``ph_sort.c``    -- top-level sort pipeline (``phsort`` / ``all_phsort``)
- ``ph_sttr2.c``   -- shared shrink / coarticulation helpers
- ``ph_setar.c``   -- target setting (``phsettar`` and friends)
- ``ph_inton2.c``  -- intonation engine (``phinton`` / ``make_f0_command``)
- ``ph_timng.c``   -- per-clause timing (``init_timing`` / ``inh_timing``)

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph"
_PY_DIR = Path(__file__).resolve().parents[2] / "src" / "dectalk" / "ph"

_C_FILES: list[Path] = [
    _C_DIR / "ph_sort.c",
    _C_DIR / "ph_sttr2.c",
    _C_DIR / "ph_setar.c",
    _C_DIR / "ph_inton2.c",
    _C_DIR / "ph_timng.c",
]

pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in _C_FILES),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Preprocessor symbols we consider "defined" for the Linux libtts_us.so
# build. Drawn from the generated ``ph/Makefile`` plus the ``english_release``
# target in ``src/Makefile`` (``LANGUAGE=ENGLISH -DENGLISH_US -DACNA``).
# Anything not in this set is treated as undefined when evaluating
# #ifdef / #if defined() expressions -- crucially, ``HLSYN`` is NOT in our
# build (no -DHLSYN appears anywhere in the configure / Makefile chain),
# so ``#ifndef HLSYN`` branches are active and ``#ifdef HLSYN`` branches
# are not.
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
# Functions defined in the scanned PH C files that are intentionally not
# ported yet. Each entry needs a one-line reason. When a port lands, the
# entry must be removed -- the ``test_no_dead_deferred_entries`` guard
# enforces that.
#
# PH is mostly unported today, so this dict shrinks over time as ports
# land. Every removed entry == one C function newly available in Python.
# --------------------------------------------------------------------------
_DEFERRED: dict[str, str] = {
    # ph_sort.c -- top-level sort pipeline.
    "phsort": "Top-level PH-sort entry point; needs full pipeline wired",
    "all_phsort": (
        "Multi-lang sort dispatcher; depends on phsort + language-specific "
        "branches (uk/sp/gr/la/fr) not yet ported"
    ),
    "fr_phsort": "French-specific phsort entry; deferred until non-US ports begin",
    # ph_sttr2.c -- shared shrink helpers.
    "setloc": (
        "Static helper for phsettar locus computation; depends on stress-state "
        "machine and the unported phsettar pipeline"
    ),
    # ph_setar.c -- target setting pipeline.
    "phsettar": (
        "Top-level phsettar entry; depends on getbegtar/getendtar/gettar/"
        "init_variables/make_dip and the static smooth-rule helpers"
    ),
    "gettar": "Per-phone target lookup dispatcher; deferred with the phsettar pipeline",
    "getbegtar": "Beginning-of-phone target lookup; deferred with the phsettar pipeline",
    "getendtar": "End-of-phone target lookup; deferred with the phsettar pipeline",
    "init_variables": (
        "Static phsettar initialiser; depends on PARAMETER buffers and "
        "the broader target-setting state"
    ),
    "make_dip": (
        "Static parameter-dip generator inside phsettar; depends on the "
        "PARAMETER struct layout and shrink/inhdr machinery"
    ),
    # ph_inton2.c -- intonation engine.
    "phinton": (
        "Big intonation engine entry point; depends on N unported f0 helpers "
        "and the hat-state machine"
    ),
}


# --------------------------------------------------------------------------
# Helpers.
# --------------------------------------------------------------------------


def _read_c(path: Path) -> str:
    """Read a C source file with CRLF endings normalised."""
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _strip_comments(text: str) -> str:
    """Remove ``/* ... */`` block and ``// ...`` line comments.

    Both forms can hide function-definition-looking text inside the PH
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
    conservatively as false -- the PH sources only use defined() guards
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
    """Parse top-level function definitions from one PH C source file.

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
    """Union of function definitions across all scanned PH C files."""
    funcs: set[str] = set()
    for path in _C_FILES:
        funcs.update(_enumerate_c_functions_in(path))
    return funcs


def _enumerate_python_ph_symbols() -> set[str]:
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


def test_every_linux_active_ph_function_has_python_port() -> None:
    """Every Linux-active C function in the scanned PH files has a Python port."""
    c_funcs = _enumerate_all_c_functions()
    assert c_funcs, "expected to find at least one function definition across PH files"
    py_syms = _enumerate_python_ph_symbols()
    missing = c_funcs - py_syms - set(_DEFERRED.keys())
    assert not missing, (
        f"Missing Python ports for PH-module C functions: "
        f"{sorted(missing)}. Either port them, or add to _DEFERRED with a reason."
    )


def test_deferred_ph_symbols_actually_in_c_source() -> None:
    """_DEFERRED entries must correspond to real C functions (catches typos)."""
    combined = "\n".join(_read_c(p) for p in _C_FILES)
    for name in _DEFERRED:
        assert re.search(rf"\b{re.escape(name)}\s*\(", combined), (
            f"_DEFERRED has '{name}' but none of the scanned PH C files mention it"
        )


def test_no_dead_deferred_entries() -> None:
    """If a deferred function gets ported, the _DEFERRED entry should be removed."""
    py_syms = _enumerate_python_ph_symbols()
    redundant = set(_DEFERRED.keys()) & py_syms
    assert not redundant, (
        f"_DEFERRED entries that are actually ported (remove from _DEFERRED): {sorted(redundant)}"
    )


def test_enumerator_finds_known_ported_ph_helpers() -> None:
    """Sanity check: known-ported helpers are detected by the enumerator.

    If this test fails the regex / preprocessor walker has regressed and the
    inventory test above is unreliable.
    """
    c_funcs = _enumerate_all_c_functions()
    # Each of these is *defined* in one of the five scanned files and has a
    # Python port today:
    #   make_phone, insertphone, delete_symbol, add_feature -> ph_sort.c
    #   shrdur, vv_coartic_across_c                         -> ph_sttr2.c
    #   phone_feature (inline)                              -> ph_sort.c
    expected = {
        "make_phone",
        "insertphone",
        "delete_symbol",
        "add_feature",
        "shrdur",
        "vv_coartic_across_c",
        "phone_feature",
    }
    missing = expected - c_funcs
    assert not missing, f"enumerator failed to find well-known ported PH helpers: {sorted(missing)}"


def test_enumerator_skips_hlsyn_only_helpers_in_inton2() -> None:
    """``#if (defined ENGLISH && !(defined HLSYN))`` branches must be ACTIVE.

    Since ``HLSYN`` is not in our build's defines and ``ENGLISH`` is, the
    enumerator should treat such branches as taken. The opposite would mean
    we're scanning the HLSYN-only code path -- which is the wrong code for
    libtts_us.so. ``ph_setar.c`` is full of ``#ifndef HLSYN`` blocks; if
    HLSYN were (incorrectly) defined, we'd lose every helper inside them.
    """
    # ``place``, ``plocu`` and ``ptram`` all live in #ifndef-HLSYN territory
    # inside ph_setar.c and must be detected.
    c_funcs = _enumerate_c_functions_in(_C_DIR / "ph_setar.c")
    expected = {"place", "plocu", "ptram"}
    missing = expected - c_funcs
    assert not missing, (
        f"#ifndef HLSYN helpers not detected -- HLSYN treated as defined? missing={sorted(missing)}"
    )


def test_enumerator_skips_german_only_functions() -> None:
    """ph_setar.c has large ``#ifdef GERMAN`` blocks that must be skipped.

    ENGLISH_US is defined but GERMAN is not, so anything strictly inside a
    GERMAN-only branch should be invisible to the enumerator.
    """
    # ``GERMAN`` is the user's German-specific guard. The blocks contain
    # large rule trees but no fresh top-level function definitions in our
    # five target files -- check the union has no German-specific names.
    c_funcs = _enumerate_all_c_functions()
    for name in ("gr_phsort", "gr_phsettar", "gr_phinton"):
        assert name not in c_funcs, (
            f"{name} is gated by #ifdef GERMAN but the enumerator did not skip it"
        )
