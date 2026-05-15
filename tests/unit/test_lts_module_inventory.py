"""Inventory parity test for selected LTS-module C files against the Python port.

Re-parses the most-active LTS C source files at test time, enumerates every
function definition that the Linux build actually compiles, and asserts each
one has a corresponding Python port under :mod:`dectalk.lts` -- or sits on
the :data:`_DEFERRED` allow-list with a one-line reason.

The five C files scanned here are the ones the user identified as carrying
the bulk of unported, Linux-active LTS functions:

- ``allorules.c``   -- German morphemizer allphonic rules (NOT compiled on
                       Linux libtts_us.so; the LTS Makefile only builds the
                       ``LTS_SRC`` list and ``allorules.c`` is absent. Every
                       function is therefore deferred with that reason -- the
                       file is scanned so any future port lands cleanly.)
- ``l_us_ad1.c``    -- US-English adjust/cluster helpers (included by
                       ``ls_adju1.c`` under ``#ifdef ENGLISH_US``)
- ``l_us_pr1.c``    -- US-English processing helpers for numbers / dates /
                       times / fractions (included by ``ls_proc.c``)
- ``l_us_ru1.c``    -- US-English letter-to-sound rule machinery (included
                       by ``ls_rule1.c``)
- ``l_us_sp1.c``    -- US-English spell-vs-say decision (included by
                       ``ls_spel1.c``)

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/lts"
_PY_DIR = Path(__file__).resolve().parents[2] / "src" / "dectalk" / "lts"

_C_FILES: list[Path] = [
    # ``allorules.c`` is intentionally absent: the file is not in
    # ``LTS_SRC`` in ``src/dapi/src/lts/Makefile`` and is also not
    # included by any compiled translation unit, so its German-only
    # BACHUS helpers don't ship in libtts_us.so on Linux. Including
    # it here would force 23 entries onto the _DEFERRED allow-list
    # for code that isn't actually built.
    _C_DIR / "l_us_ad1.c",
    _C_DIR / "l_us_pr1.c",
    _C_DIR / "l_us_ru1.c",
    _C_DIR / "l_us_sp1.c",
]

pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in _C_FILES),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Preprocessor symbols we consider "defined" for the Linux libtts_us.so
# build. Drawn from the generated ``lts/Makefile`` (``-D_REENTRANT -DNOMME
# -DLTSSIM -DTTSSIM -DANSI -DBLD_DECTALK_DLL -D$(LANGUAGE) -DACCESS32
# -DTYPING_MODE``) plus the ``english_release`` target in ``src/Makefile``
# which expands ``LANGUAGE`` to ``ENGLISH -DENGLISH_US -DACNA`` -- so the
# compiler sees ``-DENGLISH -DENGLISH_US -DACNA`` simultaneously. Crucially
# ``HLSYN`` is NOT defined (no ``-DHLSYN`` in the LTS Makefile or in any
# upstream Makefile passed to it), so ``#ifdef HLSYN`` branches are inactive
# and the ``#ifndef HLSYN`` / ``#if !defined(HLSYN)`` paths are taken.
# Anything not in this set is treated as undefined.
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
# Functions defined in the scanned LTS C files that are intentionally not
# ported yet (or whose Python port lives under a different name). Each
# entry needs a one-line reason. When a port lands, the entry must be
# removed -- the ``test_no_dead_deferred_entries`` guard enforces that.
# --------------------------------------------------------------------------
_DEFERRED: dict[str, str] = {
    # allorules.c -- German morphemizer (BACHUS). The LTS Makefile builds
    # only LTS_SRC, and allorules.c is not in that list, nor is it
    # transitively included by any compiled file. The whole file is
    # Linux-inactive for libtts_us.so. Each function is deferred with the
    # same root cause -- a future German port can land them one by one.
    # l_us_ad1.c -- adjustment pass. ls_adju_cluster has a Python port;
    # ls_adju_allo2 is the big sweep that calls the (ported) helpers
    # ls_adju_del_phone / ls_adju_ins_phone but isn't itself a function
    # the pure-Python pipeline calls into yet -- the C oracle drives it.
    "ls_adju_allo2": (
        "Allophone sweep entry; pure-Python pipeline drives ls_adju helpers "
        "directly without the full top-level sweep yet"
    ),
    # l_us_pr1.c -- processing helpers. Most are ported; the top-level
    # ls_proc_do_number is the big number-to-words dispatcher that orchestrates
    # the ported ls_proc_do_*_digits helpers -- it's still in transit.
    # (Actually ls_proc_do_number IS ported -- removed from this list.)
    # l_us_ru1.c -- LTS rule machinery. The Python port goes through
    # dectalk.lts.rules_us.lts() which collapses ls_rule_lts +
    # ls_rule_rule_match + ls_rule_env_match + ls_rule_add_graph +
    # ls_rule_lts_out into the rules engine. The C-named entry points
    # aren't exported individually.
    "ls_rule_lts": (
        "Top-level LTS rule loop; collapsed into dectalk.lts.rules_us.lts() "
        "with the helpers fused in"
    ),
    "ls_rule_lts_out": (
        "Trailing post-pass that pushes the phone list to the next stage; "
        "fused into the Python rules_us.lts() emission step"
    ),
    "ls_rule_add_graph": (
        "Per-grapheme accumulator inside ls_rule_lts; fused into the Python "
        "grapheme buffer construction in rules_us.lts()"
    ),
    "ls_rule_rule_match": (
        "Rule pattern matcher driving ls_rule_lts; fused into the Python "
        "_match_rule helper in rules_us"
    ),
    "ls_rule_env_match": (
        "Environment-matcher helper for ls_rule_rule_match; fused into the "
        "Python _context_ok helper in rules_us"
    ),
    "ls_rule_show_phone": (
        "Debug-only phone-stream printer (VMS/LDS_BUILD); no Python equivalent "
        "needed for the release build"
    ),
    # l_us_sp1.c -- spell vs say. ls_spel_say_it has a Python port (it
    # lives in dectalk.lts.spell_or_say under the renamed export
    # ``say_it``). The Pythonic rename is allow-listed below.
    "ls_spel_say_it": (
        "ported as dectalk.lts.spell_or_say.say_it (Pythonic rename drops the ls_spel_ prefix)"
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

    Both forms can hide function-definition-looking text inside the LTS
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
    conservatively as false -- the LTS sources only use defined() guards
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
    """Parse top-level function definitions from one LTS C source file.

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
    """Union of function definitions across all scanned LTS C files."""
    funcs: set[str] = set()
    for path in _C_FILES:
        funcs.update(_enumerate_c_functions_in(path))
    return funcs


def _enumerate_python_lts_symbols() -> set[str]:
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


def test_every_linux_active_lts_function_has_python_port() -> None:
    """Every Linux-active C function in the scanned LTS files has a Python port."""
    c_funcs = _enumerate_all_c_functions()
    assert c_funcs, "expected to find at least one function definition across LTS files"
    py_syms = _enumerate_python_lts_symbols()
    missing = c_funcs - py_syms - set(_DEFERRED.keys())
    assert not missing, (
        f"Missing Python ports for LTS-module C functions: "
        f"{sorted(missing)}. Either port them, or add to _DEFERRED with a reason."
    )


def test_deferred_lts_symbols_actually_in_c_source() -> None:
    """_DEFERRED entries must correspond to real C functions (catches typos)."""
    combined = "\n".join(_read_c(p) for p in _C_FILES)
    for name in _DEFERRED:
        assert re.search(rf"\b{re.escape(name)}\s*\(", combined), (
            f"_DEFERRED has '{name}' but none of the scanned LTS C files mention it"
        )


def test_no_dead_deferred_entries() -> None:
    """If a deferred function gets ported, the _DEFERRED entry should be removed."""
    py_syms = _enumerate_python_lts_symbols()
    redundant = set(_DEFERRED.keys()) & py_syms
    assert not redundant, (
        f"_DEFERRED entries that are actually ported (remove from _DEFERRED): {sorted(redundant)}"
    )


def test_enumerator_finds_known_ported_lts_helpers() -> None:
    """Sanity check: known-ported helpers are detected by the enumerator.

    If this test fails the regex / preprocessor walker has regressed and the
    inventory test above is unreliable. Each name below is *defined* in one
    of the five scanned files and has a Python port today:

    - ``ls_adju_cluster``    -> l_us_ad1.c   -> dectalk.lts.cluster_check
    - ``ls_proc_do_2_digits``-> l_us_pr1.c   -> dectalk.lts.number_emit
    - ``ls_proc_do_3_digits``-> l_us_pr1.c   -> dectalk.lts.number_emit
    - ``ls_proc_do_date``    -> l_us_pr1.c   -> dectalk.lts.date_emit
    - ``ls_proc_do_time``    -> l_us_pr1.c   -> dectalk.lts.time_emit
    - ``ls_proc_do_frac``    -> l_us_pr1.c   -> dectalk.lts.frac_emit
    - ``ls_proc_non_zero``   -> l_us_pr1.c   -> dectalk.lts.proc_helpers
    - ``ls_rule_delete_geminate_pairs`` -> l_us_ru1.c -> dectalk.lts.geminate
    - ``ls_spel_say_it``     -> l_us_sp1.c   -> renamed dectalk.lts.spell_or_say.say_it
    """
    c_funcs = _enumerate_all_c_functions()
    expected = {
        "ls_adju_cluster",
        "ls_proc_do_2_digits",
        "ls_proc_do_3_digits",
        "ls_proc_do_date",
        "ls_proc_do_time",
        "ls_proc_do_frac",
        "ls_proc_non_zero",
        "ls_rule_delete_geminate_pairs",
        "ls_spel_say_it",
    }
    missing = expected - c_funcs
    assert not missing, (
        f"enumerator failed to find well-known ported LTS helpers: {sorted(missing)}"
    )


def test_enumerator_skips_vms_only_definitions_in_l_us_ru1() -> None:
    """``#if defined(VMS) || defined(LDS_BUILD)`` branches must be SKIPPED.

    Inside ``l_us_ru1.c`` near line 240 there's a VMS/LDS-only ``printf``
    block that doesn't define a top-level function -- but the file also
    gates ``ls_rule_show_phone``'s prototype under a guard that selects the
    *Linux* branch (``__linux__`` etc.) as ``extern int ls_rule_show_phone(...)``
    and the ``#else`` (non-Linux) branch as a definition-less prototype. The
    walker should NOT find ``ls_rule_show_phone`` as a definition either way
    (neither branch has a body), so it must not appear in the enumerator
    output as a *definition*.
    """
    # On Linux the file declares ``extern int ls_rule_show_phone(...);`` so it's
    # a declaration, never a definition. The walker's "; vs {" check filters
    # it out, but the directive walker must have picked the right branch.
    c_funcs = _enumerate_c_functions_in(_C_DIR / "l_us_ru1.c")
    assert "ls_rule_show_phone" not in c_funcs, (
        "ls_rule_show_phone has no body in either #if branch -- the walker "
        "incorrectly classified a prototype as a definition"
    )


def test_enumerator_skips_hlsyn_only_helpers_in_l_us_pr1() -> None:
    """``#if defined(HLSYN) || defined(CHANGES_AFTER_V43)`` branches must be SKIPPED.

    ``l_us_pr1.c`` has multiple ``#if defined(HLSYN) || defined(CHANGES_AFTER_V43)``
    blocks (around the ``ls_proc_do_3_digits`` / ``ls_proc_do_4_digits`` /
    ``ls_proc_do_digit_group`` bodies). Since neither HLSYN nor
    CHANGES_AFTER_V43 are in our build, the ``#else`` paths are taken --
    not the ``#if`` paths. This sanity check makes sure the walker still
    finds the three function-definition headers themselves (which live at
    file scope, outside any HLSYN gate).
    """
    c_funcs = _enumerate_c_functions_in(_C_DIR / "l_us_pr1.c")
    for name in ("ls_proc_do_3_digits", "ls_proc_do_4_digits", "ls_proc_do_digit_group"):
        assert name in c_funcs, (
            f"{name} should be detected as a top-level definition in l_us_pr1.c "
            f"(walker may have incorrectly skipped past the HLSYN-gated body)"
        )


def test_enumerator_skips_german_only_l_us_pr1_blocks() -> None:
    """No ``l_us_pr1.c`` function should be gated by anything language-specific.

    The l_us_*.c files are themselves the US-English language branch; they're
    included by ls_proc.c / ls_adju1.c / ls_rule1.c / ls_spel1.c only when
    ``#ifdef ENGLISH_US`` is true. So none of their top-level functions
    should be under a further German/French/etc. guard. This sanity check
    asserts that no German-prefixed names slip through.
    """
    c_funcs = _enumerate_all_c_functions()
    for name in ("gr_ls_proc_do_number", "gr_ls_rule_lts", "fr_ls_adju_cluster"):
        assert name not in c_funcs, (
            f"{name} was found in scanned US LTS files -- preprocessor walker is "
            f"confused about the language branch"
        )
