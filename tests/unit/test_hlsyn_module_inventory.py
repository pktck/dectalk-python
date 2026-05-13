"""Inventory parity test for the hlsyn-module C files against the Python port.

Re-parses every hlsyn C source file that the Linux ``libtts_us.so`` build
actually compiles, enumerates every Linux-active function definition, and
asserts each one has a corresponding Python port under :mod:`dectalk.hlsyn`
-- or sits on the :data:`_DEFERRED` allow-list with a one-line reason.

The hlsyn module is the high-level synthesiser layer that maps one frame
of HL parameters (areas, flows, pressures) to LL Klatt parameters. The
Klatt back-end itself (:mod:`dectalk.hlsyn.sample` / :mod:`.voice` /
:mod:`.synthesize` / ...) is bit-accurate already, but it lives in
``frame.c`` / ``llinit.c`` / ``reson.c`` / ``sample.c`` / ``voice.c`` --
NONE of which the Linux Makefile compiles. The Linux build only pulls in
the HL-to-LL mapping files listed below, and that whole layer is still
unported today; the C oracle dispatches through ``libtts_us.so``'s
``HLSynthesizeLLFrame`` instead.

Consequently :data:`_DEFERRED` is large by design: each entry is a TODO
with a reason, and the test serves as a precise progress meter -- every
new Python port that lands removes one entry.

Files scanned, per ``src/dapi/src/hlsyn/Makefile`` (``HL_SRC``):

- ``acxf1c.c``     -- tongue-body acoustic / Helmholtz frequencies
- ``hlframe.c``    -- top-level ``HLSynthesizeLLFrame`` + private helpers
- ``log10table.c`` -- ``DT_f_log10`` lookup wrapper around ``log10``
- ``brent.c``      -- Brent's-method root finder (used by circuit / nasal)
- ``inithl.c``     -- ``InitializeHLSynthesizer`` speaker-constant init
- ``nasalf1x.c``   -- nasal pole/zero finite-bracket + interpolation
- ``sqrttable.c``  -- ``DT_f_sqrt`` lookup wrapper around ``sqrt``
- ``circuit.c``    -- ``SpeechCircuit`` glottal/vocal-tract aerodynamics

The other ``.c`` files in ``src/dapi/src/hlsyn/`` (``frame.c``,
``llinit.c``, ``reson.c``, ``sample.c``, ``voice.c``, ``diffuse.c``,
``fixfft32.c``) have rules in the Makefile but are NOT listed in
``HL_SRC``, so they are not compiled into ``libtts_us.so`` and are
intentionally not scanned here. (The Klatt-side Python ports under
:mod:`dectalk.hlsyn` correspond to those un-built variants.)

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/hlsyn"
_PY_DIR = Path(__file__).resolve().parents[2] / "src" / "dectalk" / "hlsyn"

# The Linux ``HL_SRC`` set, in Makefile order. Anything outside this set
# is not in ``libtts_us.so`` and is intentionally not scanned.
_C_FILES: list[Path] = [
    _C_DIR / "acxf1c.c",
    _C_DIR / "hlframe.c",
    _C_DIR / "log10table.c",
    _C_DIR / "brent.c",
    _C_DIR / "inithl.c",
    _C_DIR / "nasalf1x.c",
    _C_DIR / "sqrttable.c",
    _C_DIR / "circuit.c",
]

pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in _C_FILES),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Preprocessor symbols we consider "defined" for the Linux libtts_us.so
# build. Drawn from ``src/dapi/src/hlsyn/Makefile`` (``DEFINES``) plus the
# ``english_release`` target in ``src/Makefile``
# (``LANGUAGE=ENGLISH -DENGLISH_US -DACNA``). Anything not in this set is
# treated as undefined -- crucially, ``DEBUG``, ``WARNINGS``, ``UNDER_CE``,
# ``ARM7``, ``EPSON_ARM7``, ``FAKE_HLSYN``, ``FAKE_HLSYN_notyet``,
# ``FLAV_NO_ACXF1C``, ``FLAV_STDCALL``, ``TONGUE_BODY_AREA``,
# ``LOWCOMPUTE_MITSU``, ``MSDOS``, ``WIN32`` and ``__osf__`` are NOT in our
# build, so the corresponding branches are inactive.
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
# Functions defined in the scanned hlsyn C files that are intentionally not
# ported yet (or ported under a different Pythonic name). Each entry needs
# a one-line reason. When a port lands, the entry must be removed -- the
# ``test_no_dead_deferred_entries`` guard enforces that.
#
# The HL-to-LL mapping is unported today (the C oracle handles it via
# ``libtts_us.so``), so this dict shrinks over time as ports land. Every
# removed entry == one C function newly available in Python.
# --------------------------------------------------------------------------
_DEFERRED: dict[str, str] = {
    # ---- acxf1c.c -- tongue-body acoustic / Helmholtz frequencies. ----
    "HelmholtzFrequency": "ported as hlsyn.helmholtz.helmholtz_frequency (PEP8 rename)",
    "HelmholtzConstriction": "ported as hlsyn.helmholtz.helmholtz_constriction (PEP8 rename)",
    "Compute_acl": "ported as hlsyn.compute_ac.compute_acl (PEP8 rename)",
    "Compute_acd": "ported as hlsyn.compute_ac.compute_acd (PEP8 rename)",
    "Set_acx_loc": "ported as hlsyn.set_acx_loc.set_acx_loc (PEP8 rename)",
    "Tongue_acx_f1c": (
        "Top-level tongue-body -> (acx, f1c) mapping; called first inside HLSynthesizeLLFrame"
    ),
    # ---- hlframe.c -- top-level HL->LL frame mapping. ------------------
    "HLSynthesizeLLFrame": (
        "Top-level HL->LL frame mapping; the C oracle dispatches through "
        "libtts_us.so so the Python pipeline never calls this"
    ),
    "MapGlottalFormantsNotF1": (
        "Adjusts F2..F6 / B3..B5 / TL for tracheal coupling; private to "
        "hlframe.c, deferred along with HLSynthesizeLLFrame"
    ),
    "FricativeFilters": (
        "Sets the parallel fricative-branch resonators (F2P..F6P, AB); "
        "private to hlframe.c, deferred along with HLSynthesizeLLFrame"
    ),
    "SourceAmplitudes": (
        "Maps ag/agf/agm/agx and ps to AV / AF / AH source amplitudes; "
        "private to hlframe.c, deferred along with HLSynthesizeLLFrame"
    ),
    "InterpolateAF": (
        "Smooths AF across frames during the AC/DC transition; private "
        "to hlframe.c, deferred along with HLSynthesizeLLFrame"
    ),
    "GlottalInteraction": (
        "Computes B1, B2 (and F0 jitter) from agf and ps for glottal "
        "coupling; private to hlframe.c, deferred along with HLSynthesizeLLFrame"
    ),
    "SourceSpecifics": (
        "Sets OQ / TL / FL spectral-shape parameters from ag, ap, ps; "
        "private to hlframe.c, deferred along with HLSynthesizeLLFrame"
    ),
    "UnusedLLParameters": (
        "Zeros LL-frame slots the HL layer does not drive (DI, JV, JF, "
        "...); private cleanup helper deferred along with HLSynthesizeLLFrame"
    ),
    # ---- log10table.c / sqrttable.c -- tiny math wrappers. -------------
    "DT_f_log10": (
        "Lookup-table wrapper around log10(); the Python ports use "
        "math.log10 directly (no need for the LUT speedup)"
    ),
    "DT_f_sqrt": (
        "Lookup-table wrapper around sqrt(); the Python ports use "
        "math.sqrt directly (no need for the LUT speedup)"
    ),
    # ---- brent.c -- Brent's-method root finder. ------------------------
    "Brent": "ported as hlsyn.brent.brent (PEP8 rename)",
    "BrentBracket": "ported as hlsyn.brent.brent_bracket (PEP8 rename)",
    # ---- inithl.c -- HL synthesiser initialisation. --------------------
    "InitializeHLSynthesizer": (
        "Initialises HLSpeaker constants (alveolar table, anfnTable, "
        "f1LOverATable, ...) for a male/female voice; deferred with the "
        "rest of the HL layer"
    ),
    # ---- nasalf1x.c -- nasal pole/zero placement. ----------------------
    "SetNasals_f1x": (
        "Top-level nasal pole/zero setter called from HLSynthesizeLLFrame; "
        "deferred with the rest of the HL layer"
    ),
    "NasalZero": (
        "Sets the nasal anti-resonance (FNZ, BNZ) from an area; private "
        "to nasalf1x.c, deferred along with SetNasals_f1x"
    ),
    "Compute_fm": (
        "Computes the nasal-tract Helmholtz frequency fm from f1c and an; "
        "private to nasalf1x.c, deferred along with SetNasals_f1x"
    ),
    "NasalFirstFormant": (
        "Places the nasal first formant F1 from f1c, an, ap; private to "
        "nasalf1x.c, deferred along with SetNasals_f1x"
    ),
    "NasalPole": (
        "Places the nasal pole FNP via Brent root-finding on the "
        "susceptance sum; private to nasalf1x.c, deferred along with SetNasals_f1x"
    ),
    "SusceptanceSum": (
        "Brent target function: sum of nasal-branch susceptances at a "
        "trial FNP; private to nasalf1x.c, deferred along with NasalPole"
    ),
    "FiniteBracketFNP": (
        "Walks outward from a singularity to find a finite bracket for "
        "Brent; private to nasalf1x.c, deferred along with NasalPole"
    ),
    "InterpolateTable": "ported as hlsyn.interpolate.interpolate_table (PEP8 rename)",
    "LinearInterpolate": "ported as hlsyn.interpolate.linear_interpolate (PEP8 rename)",
    # ---- circuit.c -- glottal/vocal-tract aerodynamic circuit. ---------
    "SpeechCircuit": (
        "Newton-style aerodynamic circuit solver for Pm/Pcw/Uw/agx/Ug/"
        "Uacx/Un/Uw across one frame; deferred with the rest of the HL layer"
    ),
    "PmRootFunction": (
        "Brent target function for the SpeechCircuit Pm solve; private "
        "to circuit.c, deferred along with SpeechCircuit"
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

    Both forms can hide function-definition-looking text inside the hlsyn
    sources (large commented-out alternate implementations are common in
    ``inithl.c`` and ``hlframe.c``), so we strip them before scanning.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _eval_cpp_expr(expr: str, defined: frozenset[str]) -> bool:
    """Evaluate a simple ``#if`` expression against ``defined``.

    Supports ``defined X`` / ``defined(X)``, ``!``, ``&&``, ``||``, and
    parentheses. Anything else (numeric constants, comparisons, bare
    ``#if 0`` / ``#if 1``) is treated conservatively as false. That's
    the right call for hlsyn: every ``#if 0`` block in the scanned
    files wraps already-superseded alternate implementations of
    ``SetAlveolar`` / ``Atf3Setf2Range``, which the Linux build does
    not compile.
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
    """Parse top-level function definitions from one hlsyn C source file.

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
    """Union of function definitions across all scanned hlsyn C files."""
    funcs: set[str] = set()
    for path in _C_FILES:
        funcs.update(_enumerate_c_functions_in(path))
    return funcs


def _enumerate_python_hlsyn_symbols() -> set[str]:
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


def test_every_linux_active_hlsyn_function_has_python_port() -> None:
    """Every Linux-active C function in the scanned hlsyn files has a Python port."""
    c_funcs = _enumerate_all_c_functions()
    assert c_funcs, "expected to find at least one function definition across hlsyn files"
    py_syms = _enumerate_python_hlsyn_symbols()
    missing = c_funcs - py_syms - set(_DEFERRED.keys())
    assert not missing, (
        f"Missing Python ports for hlsyn-module C functions: "
        f"{sorted(missing)}. Either port them, or add to _DEFERRED with a reason."
    )


def test_deferred_hlsyn_symbols_actually_in_c_source() -> None:
    """_DEFERRED entries must correspond to real C functions (catches typos)."""
    combined = "\n".join(_read_c(p) for p in _C_FILES)
    for name in _DEFERRED:
        assert re.search(rf"\b{re.escape(name)}\s*\(", combined), (
            f"_DEFERRED has '{name}' but none of the scanned hlsyn C files mention it"
        )


def test_no_dead_deferred_entries() -> None:
    """If a deferred function gets ported, the _DEFERRED entry should be removed."""
    py_syms = _enumerate_python_hlsyn_symbols()
    redundant = set(_DEFERRED.keys()) & py_syms
    assert not redundant, (
        f"_DEFERRED entries that are actually ported (remove from _DEFERRED): {sorted(redundant)}"
    )


def test_enumerator_finds_known_hlsyn_entry_points() -> None:
    """Sanity check: well-known hlsyn entry points are detected by the enumerator.

    If this test fails the regex / preprocessor walker has regressed and the
    inventory test above is unreliable. The chosen names span all eight
    scanned files so any one walker regression -- a botched #ifdef, a
    comment-strip bug, etc -- breaks at least one of them.
    """
    c_funcs = _enumerate_all_c_functions()
    expected = {
        # acxf1c.c
        "Tongue_acx_f1c",
        "HelmholtzFrequency",
        # hlframe.c
        "HLSynthesizeLLFrame",
        "MapGlottalFormantsNotF1",
        # log10table.c
        "DT_f_log10",
        # brent.c
        "Brent",
        "BrentBracket",
        # inithl.c
        "InitializeHLSynthesizer",
        # nasalf1x.c
        "SetNasals_f1x",
        "InterpolateTable",
        "LinearInterpolate",
        # sqrttable.c
        "DT_f_sqrt",
        # circuit.c
        "SpeechCircuit",
        "PmRootFunction",
    }
    missing = expected - c_funcs
    assert not missing, (
        f"enumerator failed to find well-known hlsyn entry points: {sorted(missing)}"
    )


def test_enumerator_skips_if_zero_blocks_in_inithl() -> None:
    """inithl.c wraps two alternate static helpers in ``#if 0`` ... ``#endif``.

    ``SetAlveolar`` and ``Atf3Setf2Range`` live inside ``#if 0`` blocks in
    ``inithl.c`` (the live tables are now generated elsewhere); the
    enumerator must not pick them up as Linux-active definitions.
    """
    c_funcs = _enumerate_c_functions_in(_C_DIR / "inithl.c")
    for name in ("SetAlveolar", "Atf3Setf2Range"):
        assert name not in c_funcs, (
            f"{name} is defined under #if 0 in inithl.c but the enumerator did not skip it"
        )


def test_enumerator_skips_epson_arm7_branches() -> None:
    """Several hlsyn files have ``#ifdef EPSON_ARM7`` / ``#ifdef ARM7`` blocks.

    EPSON_ARM7 and ARM7 are not in our Linux build's defines, so anything
    strictly inside those branches must be invisible to the enumerator.
    No Linux-active function is named to clash with the ARM-only paths,
    so we check this indirectly by asserting the per-file function sets
    are exactly the Linux-active set listed above. A botched ARM7
    handler would leak extra identifiers.
    """
    expected_per_file = {
        "acxf1c.c": {
            "HelmholtzFrequency",
            "HelmholtzConstriction",
            "Compute_acl",
            "Compute_acd",
            "Set_acx_loc",
            "Tongue_acx_f1c",
        },
        "hlframe.c": {
            "HLSynthesizeLLFrame",
            "MapGlottalFormantsNotF1",
            "FricativeFilters",
            "SourceAmplitudes",
            "InterpolateAF",
            "GlottalInteraction",
            "SourceSpecifics",
            "UnusedLLParameters",
        },
        "log10table.c": {"DT_f_log10"},
        "brent.c": {"Brent", "BrentBracket"},
        "inithl.c": {"InitializeHLSynthesizer"},
        "nasalf1x.c": {
            "SetNasals_f1x",
            "NasalZero",
            "Compute_fm",
            "InterpolateTable",
            "LinearInterpolate",
            "NasalFirstFormant",
            "NasalPole",
            "SusceptanceSum",
            "FiniteBracketFNP",
        },
        "sqrttable.c": {"DT_f_sqrt"},
        "circuit.c": {"SpeechCircuit", "PmRootFunction"},
    }
    for fname, expected in expected_per_file.items():
        c_funcs = _enumerate_c_functions_in(_C_DIR / fname)
        assert c_funcs == expected, (
            f"{fname} enumerator drift -- expected exactly {sorted(expected)}, "
            f"got {sorted(c_funcs)}"
        )


def test_enumerator_skips_non_makefile_hlsyn_variants() -> None:
    """The Makefile's HL_SRC compiles only 8 files; the others are dead.

    Files like ``frame.c`` / ``llinit.c`` / ``reson.c`` / ``sample.c`` /
    ``voice.c`` / ``diffuse.c`` / ``fixfft32.c`` have rules in the
    Makefile but are NOT in ``HL_SRC``, so they're never compiled into
    libtts_us.so. The Klatt-side Python ports under :mod:`dectalk.hlsyn`
    correspond to those un-built variants. This guard ensures we haven't
    accidentally added one of them to ``_C_FILES``.
    """
    scanned = {p.name for p in _C_FILES}
    for forbidden in (
        "frame.c",
        "llinit.c",
        "reson.c",
        "sample.c",
        "voice.c",
        "diffuse.c",
        "fixfft32.c",
    ):
        assert forbidden not in scanned, (
            f"{forbidden} is not in HL_SRC on Linux; remove it from _C_FILES"
        )
