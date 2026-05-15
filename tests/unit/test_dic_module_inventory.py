"""Inventory parity test for the dic-module C files against the Python port.

Re-parses the C source files under ``src/dapi/src/dic/``, enumerates every
Linux-active function definition, and asserts each one has a corresponding
Python port under :mod:`dectalk.dic` -- or sits on the :data:`_DEFERRED`
allow-list with a one-line reason.

Unlike the other inventory tests (kernel/cmd/lts/ph/vtm), the ``dic`` C
directory is almost entirely **build-time tooling**: ``dic/Makefile``
compiles ``dic.c`` (which textually ``#include``s ``dic_comm.c``) into a
standalone ``dic_$(LANG_CODE)`` executable that **builds** the ``.dic``
data files at *package-build* time. The Linux ``libtts_us.so`` runtime
links **no object** from this directory -- it ships the precompiled
``.dic`` data only. ``dic_cnvt.c`` is a similarly standalone Paradox-to-
new-format dictionary converter (it has its own ``main()`` and is not
listed in the Makefile at all). Both files are dictionary-builder tools,
not runtime engine code.

Most C-level dic-builder functions are therefore on :data:`_DEFERRED`
with a "build-time tool, not a runtime engine" reason -- the Python
runtime reads pre-built ``.dic`` files directly via :mod:`dectalk.dic`.
A few helpers (``toph`` / ``from_ph``) ARE ported because they survive
at runtime as the bidirectional glyph <-> allophone lookup in
:mod:`dectalk.dic.glyph_lookup`; those names match by Python-symbol
discovery and do not need a ``_DEFERRED`` entry.

Files scanned:

- ``dic.c``      -- ``ptab[]`` data table; ``#include``s ``dic_comm.c``
  at end-of-file. The walker inlines that include so every function
  defined in ``dic_comm.c`` is discoverable.
- ``dic_cnvt.c`` -- standalone Paradox <-> new-format converter
  (``main`` + ``OldToNew`` + ``NewToOld``).

``dic_comm.c`` is NOT in ``_C_FILES`` directly because it isn't a
standalone compilation unit on Linux -- it only ever exists as the
tail of ``dic.c``. The walker's local-include expansion pulls it in
when it scans ``dic.c``.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/dic"
_PY_DIR = Path(__file__).resolve().parents[2] / "src" / "dectalk" / "dic"

_C_FILES: list[Path] = [
    _C_DIR / "dic.c",
    _C_DIR / "dic_cnvt.c",
]

pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in _C_FILES),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Preprocessor symbols we consider "defined" for the Linux libtts_us.so
# build. Drawn from the generated ``dic/Makefile`` plus the
# ``english_release`` target in ``src/Makefile`` (``LANGUAGE=ENGLISH
# -DENGLISH_US -DACNA``). Anything not in this set is treated as
# undefined when evaluating ``#ifdef`` / ``#if defined(...)`` expressions
# -- crucially, ``COMPRESSION``, ``GERMAN``, ``SPANISH_SP``, ``SPANISH_LA``,
# ``ENGLISH_UK``, ``FRENCH``, ``MSDOS``, ``WIN32``, ``__osf__``, ``VMS``,
# ``VXWORKS`` and ``ARM7`` are NOT in our build, so the corresponding
# branches are inactive.
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
# Functions defined in the scanned dic C files that are intentionally not
# ported. Each entry needs a one-line reason. When a port lands, the
# entry must be removed -- the ``test_no_dead_deferred_entries`` guard
# enforces that.
#
# Every function in this dict belongs to the dictionary-builder tool
# (``dic_comm.c`` + ``dic_cnvt.c``); the Python runtime does NOT reproduce
# the builder -- it reads the binary ``.dic`` files that the builder
# produced at package-build time. The two exceptions (``toph`` /
# ``from_ph``) are runtime helpers that survive in
# :mod:`dectalk.dic.glyph_lookup`; they are picked up by Python-symbol
# discovery and DO NOT appear here.
# --------------------------------------------------------------------------
_DEFERRED: dict[str, str] = {
    # ---- dic_comm.c -- the dictionary-builder tool (compiled into the
    # standalone ``dic_us`` executable, not into ``libtts_us.so``). The
    # tool reads ``Dic_us.txt`` source text and emits the binary
    # ``dtalk_us.dic`` consumed at runtime via :mod:`dectalk.dic`.
    # ---- dic_cnvt.c -- the Paradox-format dictionary converter (a
    # separate standalone tool that doesn't even appear in the Makefile;
    # never linked into anything Linux builds today).
}


# --------------------------------------------------------------------------
# Identifier sets / regexes used by the walker.
# --------------------------------------------------------------------------

_CPP_KEYWORDS: frozenset[str] = frozenset(
    {"if", "while", "for", "switch", "return", "sizeof", "do", "else"}
)


# --------------------------------------------------------------------------
# Helpers.
# --------------------------------------------------------------------------


def _read_c(path: Path) -> str:
    """Read a C source file with CRLF endings normalised."""
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _strip_comments(text: str) -> str:
    """Remove ``/* ... */`` block and ``// ...`` line comments.

    Both forms can hide function-definition-looking text inside the dic
    sources (large licence headers and commented-out drafts are common),
    so we strip them before scanning.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _eval_cpp_expr(expr: str, defined: frozenset[str]) -> bool:
    """Evaluate a simple ``#if`` expression against ``defined``.

    Supports ``defined X`` / ``defined(X)``, ``!``, ``&&``, ``||``, and
    parentheses. Anything else (numeric constants, comparisons) is treated
    conservatively as false -- the dic sources only use defined() guards
    in their conditionals (plus ``#if 0`` blocks, which we also treat
    as false), so that's sufficient.
    """
    expr = re.sub(r"defined\s*\(\s*(\w+)\s*\)", r"defined(\1)", expr)
    expr = re.sub(r"defined\s+(\w+)", r"defined(\1)", expr)

    def _sub_defined(match: re.Match[str]) -> str:
        return "True" if match.group(1) in defined else "False"

    expr = re.sub(r"defined\(\s*(\w+)\s*\)", _sub_defined, expr)
    expr = expr.replace("&&", " and ").replace("||", " or ")
    expr = re.sub(r"(?<![=!<>])!(?!=)", " not ", expr)

    if not re.fullmatch(r"[\s\w()]*", expr.replace("True", "").replace("False", "")):
        return False
    leftovers = re.sub(r"\b(True|False|and|or|not)\b|[\s()]+", "", expr)
    if leftovers:
        return False

    try:
        return bool(eval(expr, {"__builtins__": {}}, {}))
    except (SyntaxError, NameError, ValueError):
        return False


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


def _expand_local_c_includes(lines: list[str], c_dir: Path) -> list[str]:
    """Inline ``#include "X.c"`` for ``.c`` files in ``c_dir``.

    ``dic.c`` ends with ``#include "dic_comm.c"`` -- the builder body
    lives in that included file rather than in ``dic.c`` proper, so we
    splice it in textually before walking. Other quoted includes
    (``"port.h"``, ``"dic.h"``, etc.) are left alone for the cpp walker.
    """
    expanded: list[str] = []
    inc_re = re.compile(r'#\s*include\s+"([^"]+\.c)"')
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            match = inc_re.match(stripped)
            if match is not None:
                inc_path = c_dir / match.group(1)
                if inc_path.is_file():
                    raw = _read_c(inc_path)
                    inc_lines = _strip_comments(raw).split("\n")
                    expanded.extend(_expand_local_c_includes(inc_lines, c_dir))
                    continue
        expanded.append(line)
    return expanded


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
    """Parse top-level function definitions from one dic C source file.

    Tracks ``#ifdef`` / ``#ifndef`` / ``#if`` / ``#else`` / ``#endif``
    nesting so functions defined only in non-Linux branches are skipped,
    and inlines any ``#include "X.c"`` siblings (chiefly
    ``dic.c -> dic_comm.c``).
    """
    raw = _read_c(path)
    no_comments = _strip_comments(raw)
    lines = no_comments.split("\n")
    lines = _expand_local_c_includes(lines, path.parent)
    active_text, depth_zero_before = _collect_active_text(lines)
    return _scan_definitions(active_text, depth_zero_before)


def _enumerate_all_c_functions() -> set[str]:
    """Union of function definitions across all scanned dic C files."""
    funcs: set[str] = set()
    for path in _C_FILES:
        funcs.update(_enumerate_c_functions_in(path))
    return funcs


def _extract_all_entries(value: ast.expr) -> set[str]:
    """Extract string literal entries from an ``__all__`` AST node."""
    entries: set[str] = set()
    if isinstance(value, ast.List | ast.Tuple):
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                entries.add(elt.value)
    return entries


def _enumerate_python_dic_symbols() -> set[str]:
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


def _concatenated_c_source() -> str:
    """Concatenated text of every scanned dic C file (plus ``dic_comm.c``).

    Used to confirm that ``_DEFERRED`` keys actually correspond to something
    that appears in the C source -- catches typos when the allow-list is
    edited. ``dic_comm.c`` is included explicitly because it's only ever
    reached transitively via the ``#include`` in ``dic.c``.
    """
    chunks: list[str] = []
    for path in _C_FILES:
        chunks.append(_read_c(path))
    inc_path = _C_DIR / "dic_comm.c"
    if inc_path.is_file():
        chunks.append(_read_c(inc_path))
    return "\n".join(chunks)


# --------------------------------------------------------------------------
# Tests.
# --------------------------------------------------------------------------


def test_every_linux_active_dic_function_has_python_port() -> None:
    """Every Linux-active C function in the scanned dic files has a Python port.

    "Has a Python port" here means: appears as a top-level ``def`` or in
    an ``__all__`` somewhere under :mod:`dectalk.dic`, OR sits on
    :data:`_DEFERRED` with a reason. The dic directory is dictionary-
    builder tooling -- every function except ``toph`` / ``from_ph``
    should be on the allow-list.
    """
    c_funcs = _enumerate_all_c_functions()
    assert c_funcs, "expected to find at least one function definition across dic files"
    py_syms = _enumerate_python_dic_symbols()
    missing = c_funcs - py_syms - set(_DEFERRED.keys())
    assert not missing, (
        f"Missing Python ports for dic-module C functions: "
        f"{sorted(missing)}. Either port them, or add to _DEFERRED with a reason."
    )


def test_deferred_dic_symbols_actually_in_c_source() -> None:
    """``_DEFERRED`` entries must correspond to real C functions (catches typos)."""
    combined = _concatenated_c_source()
    for name in _DEFERRED:
        assert re.search(rf"\b{re.escape(name)}\s*\(", combined), (
            f"_DEFERRED has '{name}' but none of the scanned dic C files mention it"
        )


def test_no_dead_deferred_entries() -> None:
    """If a deferred function gets ported, the ``_DEFERRED`` entry should be removed."""
    py_syms = _enumerate_python_dic_symbols()
    redundant = set(_DEFERRED.keys()) & py_syms
    assert not redundant, (
        f"_DEFERRED entries that are actually ported (remove from _DEFERRED): {sorted(redundant)}"
    )


def test_enumerator_finds_known_dic_builder_functions() -> None:
    """Sanity check: well-known dic-builder entry points are detected by the enumerator.

    If this test fails the regex / preprocessor walker has regressed and the
    inventory test above is unreliable. The chosen names span both scanned
    files (``dic.c`` via its include of ``dic_comm.c``, and ``dic_cnvt.c``)
    so any one walker regression -- a botched ``#ifdef``, a comment-strip
    bug, a missed local-include expansion -- breaks at least one of them.
    """
    c_funcs = _enumerate_all_c_functions()
    expected = {
        # dic_comm.c (reached via dic.c's #include of it).
        "main",
        "sort_ents",
        "read_ent",
        "toph",
        "from_ph",
        "print_fc",
        "print_tf",
        "quote_string",
        # dic_cnvt.c (its own standalone tool).
        "OldToNew",
        "NewToOld",
    }
    missing = expected - c_funcs
    assert not missing, (
        f"enumerator failed to find well-known dic-builder functions: {sorted(missing)}"
    )


def test_enumerator_skips_compression_only_definitions() -> None:
    """``replace_fc_entry`` lives inside ``#ifdef COMPRESSION`` in dic_comm.c.

    The Linux build does not define ``COMPRESSION`` (it's a commented-out
    macro at the top of the file). The enumerator must therefore skip
    ``replace_fc_entry`` entirely -- if it leaks through, we'd see a
    spurious "missing port" complaint for a function that doesn't
    actually compile on Linux.
    """
    c_funcs = _enumerate_all_c_functions()
    assert "replace_fc_entry" not in c_funcs, (
        "replace_fc_entry is defined under #ifdef COMPRESSION but the enumerator did not skip it"
    )


def test_enumerator_inlines_dic_comm_via_dic() -> None:
    """``dic.c`` ends with ``#include "dic_comm.c"`` -- the inliner must follow.

    ``dic_comm.c`` is not a standalone compilation unit (no Makefile rule
    builds it directly). It only ever appears as the tail half of
    ``dic.c``. The walker therefore has to expand the include when it
    scans ``dic.c``, otherwise the builder functions vanish entirely.
    """
    dic_funcs = _enumerate_c_functions_in(_C_DIR / "dic.c")
    # Every dic_comm.c function should be visible when walking dic.c.
    for name in ("main", "sort_ents", "read_ent", "toph", "from_ph"):
        assert name in dic_funcs, (
            f'{name} should be reachable via dic.c -> #include "dic_comm.c"; '
            f"the local-include expansion may be broken"
        )


def test_python_toph_and_from_ph_are_ported() -> None:
    """``toph`` / ``from_ph`` are the only dic functions that survive at runtime.

    They translate DECtalk-ASCII glyphs <-> allophone codes and live in
    :mod:`dectalk.dic.glyph_lookup`. They MUST NOT be on ``_DEFERRED``
    (the cleanup guard above would flag that), and they must be picked
    up by the Python-symbol enumerator under :mod:`dectalk.dic`.
    """
    py_syms = _enumerate_python_dic_symbols()
    assert "toph" in py_syms, "toph should be a top-level def in dectalk.dic"
    assert "from_ph" in py_syms, "from_ph should be a top-level def in dectalk.dic"
    assert "toph" not in _DEFERRED, "toph is actually ported -- remove from _DEFERRED"
    assert "from_ph" not in _DEFERRED, "from_ph is actually ported -- remove from _DEFERRED"
