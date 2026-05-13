"""Inventory parity test for the CMD module against the Python port.

Re-parses every ``.c`` file under ``src/dapi/src/cmd/`` that the Linux
``libtts_us.so`` build actually compiles, enumerates each Linux-active
function definition, and asserts each one has a corresponding Python
port under :mod:`dectalk.cmd` -- or sits on the :data:`_DEFERRED`
allow-list with a one-line reason.

This mirrors :mod:`tests.unit.test_kernel_services_inventory` for the
CMD subsystem, which spans many C files instead of one. The walker is
the same preprocessor-aware approach (``#ifdef`` / ``#ifndef`` /
``#if`` evaluated against a fixed set of Linux ``-D`` macros), with two
extensions:

* ``#include "X.c"`` is inlined textually when the included path exists
  in the cmd directory. On Linux ``par_pars.c`` is just an include of
  ``par_pars1.c`` once ``NEW_BINARY_PARSER`` is defined, so the bodies
  live in that included file.
* ``OP_THREAD_ROUTINE(name, args)`` (defined in ``nt/opthread.h``) is
  recognised as a function-defining macro, mapping the first argument
  to the function name. ``cm_main.c``'s ``cmd_main`` entry point uses
  this on Linux.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/cmd")
_PY_DIR = Path(__file__).resolve().parents[2] / "src" / "dectalk" / "cmd"

# C source files that the Linux US-English ``libtts_us.so`` build actually
# compiles (per ``src/dapi/src/cmd/Makefile``). The list excludes
# ``cm_chari.c``, ``cm_vars.c``, ``par_comp.c`` and ``par_pars1.c`` -- those
# are not Linux-built. ``par_pars1.c`` is still scanned because
# ``par_pars.c`` textually ``#include``s it under ``#ifdef NEW_BINARY_PARSER``,
# which is the active branch on Linux.
_LINUX_BUILT_FILES: tuple[str, ...] = (
    "cm_char.c",
    "cm_main.c",
    "cm_text.c",
    "cm_pars.c",
    "cm_cmd.c",
    "cm_util.c",
    "cm_phon.c",
    "cm_copt.c",
    "par_pars.c",
    "par_ambi.c",
    "par_dict.c",
    "par_rule.c",
    "par_char.c",
    "cmd_wav.c",
    "cmd_init.c",
)


pytestmark = pytest.mark.skipif(
    not (_C_DIR.is_dir() and (_C_DIR / "cm_cmd.c").is_file()),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Preprocessor symbols we treat as "defined" for the Linux ``libtts_us.so``
# build. Sources:
#
# 1. ``src/dapi/src/cmd/Makefile``'s ``DEFINES`` line (``-D_REENTRANT``,
#    ``-DNOMME``, ``-DLTSSIM``, ``-DTTSSIM``, ``-DANSI``,
#    ``-DBLD_DECTALK_DLL``, ``-DACCESS32``, ``-DTYPING_MODE``).
# 2. ``src/Makefile``'s ``english_release`` target
#    (``LANGUAGE=ENGLISH -DENGLISH_US -DACNA``).
# 3. ``src/dectalkf_klsyn.h``'s unconditional ``#define``s
#    (``NEW_BINARY_PARSER``, ``HLSYN``, ``SINGLE_THREADED``,
#    ``PARSER_HACK_FOR_OLD_SONGS``, ``ACCESS32`` and many more --
#    that header is the one ``src/dectalkf.h`` actually pulls in).
# 4. ``__linux__`` defined by GCC implicitly.
#
# Anything not in this set is treated as undefined when evaluating
# ``#ifdef`` / ``#if defined(...)`` expressions.
# --------------------------------------------------------------------------
_LINUX_DEFINED: frozenset[str] = frozenset(
    {
        # Implicit GCC predefine on Linux.
        "__linux__",
        # Makefile -D flags.
        "_REENTRANT",
        "NOMME",
        "LTSSIM",
        "TTSSIM",
        "ANSI",
        "BLD_DECTALK_DLL",
        "ACCESS32",
        "TYPING_MODE",
        # Top-level Makefile (english_release).
        "ENGLISH",
        "ENGLISH_US",
        "ACNA",
        # dectalkf_klsyn.h unconditional defines.
        "NEW_BINARY_PARSER",
        "GERMAN_COMPOUND_NOUNS",
        "PH_DEBUG",
        "HLSYN",
        "NEW_ACNA",
        "USE_PORTAUDIO",
        "SLOWTALK",
        "NEW_PHONES",
        "FP_VTM",
        "AD_BASE",
        "SINGLE_THREADED",
        "NEW_INTONATION",
        "LOWCOMPUTE_MITSU",
        "NWS_LA",
        "PARSER_HACK_FOR_OLD_SONGS",
        "OLD_INTONATION_AND_TIMING",
        "VTM1",
        "PC_SAMPLE_RATE",
        "VDF_DECTALK_43",
        "VOICE_ROM_DECTALK_1996M_43F",
        "DEC_SZ",
        "OLD_SETTAR",
        "SOFTWARE_VOLUME",
        "SAPI_MULTI_LANGUAGE_SUPPORT",
        "SAPI_GROUP_F_INTERFACES",
        "SAPI_GROUP_H_TIMING",
    }
)


# --------------------------------------------------------------------------
# Functions defined in the cmd module that are intentionally not ported (or
# ported under a different Pythonic name). Each entry needs a one-line
# reason. When a port lands, the entry must be removed --
# ``test_no_dead_deferred_entries`` guards that.
# --------------------------------------------------------------------------
_DEFERRED: dict[str, str] = {
    # ------------------------------------------------------------------
    # Top-level parser bodies (cm_pars.c). These read from the
    # inter-thread CMD pipe in a blocking loop on Linux. The Python
    # port reimplements this synchronously via dectalk.cmd.commands.parse
    # plus the per-command handlers; the raw loop bodies don't translate.
    # ------------------------------------------------------------------
    "cm_pars_loop": "Inter-thread loop body; Python uses synchronous commands.parse",
    "cm_pars_proc_char": "Per-character pipe-driven dispatcher; Python parser handles directly",
    "cm_pars_getseq": "Reads ESC sequences from the CMD pipe; Python parser reads bytes directly",
    "OutputCharacter": "Writes single byte to the per-handle log pipe; Python has no log pipe",
    # ------------------------------------------------------------------
    # Top-level CMD thread entry. On Linux this is
    # OP_THREAD_ROUTINE(cmd_main, ...) -- a pthread main. The Python
    # port runs synchronously, so there is no equivalent thread main.
    # ------------------------------------------------------------------
    "cmd_main": "pthread main for the CMD task; Python port is single-threaded",
    # ------------------------------------------------------------------
    # cm_cmd.c command-table dispatch internals. The Python parser
    # dispatches on command names directly through commands.parse, so
    # the build_param / do_command / match_comm / error_comm helpers
    # aren't needed.
    # ------------------------------------------------------------------
    "cm_cmd_build_param": "Builds C param array from the pipe; Python passes args via Segment",
    "cm_cmd_do_command": "Dispatches via function-pointer table; Python uses direct calls",
    "cm_cmd_match_comm": "Linear search through command_table; Python uses a dict keyed by name",
    "cm_cmd_error_comm": "Handler when a command fails to parse; Python raises ValueError",
    # ------------------------------------------------------------------
    # cm_copt.c command handlers that have no Python port yet. Most of
    # these are stubs or no-ops in Python's synchronous text path; some
    # depend on inter-thread sync primitives we don't model.
    # ------------------------------------------------------------------
    "cm_cmd_code_page": "Sets pKsd_t->code_page; Python uses Unicode, no code-page model",
    "cm_cmd_comma": "Sets MIN_COMMA_PAUSE; Python preprocessor handles commas directly",
    "cm_cmd_define": "Loads a dictionary entry; Python uses dict_search directly",
    "cm_cmd_dial": "DTMF dialing primitive; not exposed by Python TTS layer",
    "cm_cmd_digitized": "Plays digitized audio; Python TTS hands off to PCM output",
    "cm_cmd_enable": "Sets DTMF/etc enable flags; not exposed by Python TTS layer",
    "cm_cmd_flush": "Drives the pipe-flush state; Python is synchronous, no flush state",
    "cm_cmd_gender": "Selects male/female voice variant; Python uses voice presets directly",
    "cm_cmd_latin": "Sets pKsd_t->latin_curr; Python only models US English so far",
    "cm_cmd_loadv": "[:loadv] reads voice parameter blob; deferred until voice loader lands",
    "cm_cmd_mark": "[:mark] inserts an index marker; Python uses Segment indices",
    "cm_cmd_mode": "[:mode] toggles reader modes; Python has no reader-mode flag yet",
    "cm_cmd_name": "[:name <speaker>] picks Paul/Betty/...; Python exposes voice presets via API",
    "cm_cmd_pause": "[:pause] enqueues silence on the PH pipe; Python is synchronous",
    "cm_cmd_period": "Sets MIN_PERIOD_PAUSE; Python preprocessor handles periods directly",
    "cm_cmd_plang": "Sets pKsd_t->plang; Python only models US English so far",
    "cm_cmd_preamble": "Selects PH preamble (preamble_1/2a/2b/3a/3b); Python ph picks directly",
    "cm_cmd_pronounce": "[:pronounce] runs string through LTS; Python uses lts.lookup_arpa",
    "cm_cmd_rate": "[:rate] command; Python sets rate via dectalk.api.set_rate directly",
    "cm_cmd_samples_per_frame": "Sets VTM sample-per-frame divisor; Python uses fixed 11025 Hz",
    "cm_cmd_stress": "Sets stress prominence; Python ph layer uses defaults",
    "cm_cmd_sync": "[:sync] inter-thread barrier; Python is synchronous so sync is a no-op",
    "cm_cmd_tone": "[:tone] plays sinewave via VTM pipe; Python TTS has no inline tone API",
    "cm_cmd_version": "[:version] writes version string to the pipe; Python exposes __version__",
    "cm_cmd_volume": "[:volume] routes through StereoVolumeControl; Python audio bypasses",
    "cm_cmd_vs": "[:vs] reads compact voice descriptor; deferred along with cm_cmd_loadv",
    # ------------------------------------------------------------------
    # cm_copt.c support helpers (log file management). Static functions
    # whose only callers are [:log] / [:debug]; deferred along with them.
    # ------------------------------------------------------------------
    "OpenLogFile": "Static helper opening pKsd_t->log; deferred along with cm_cmd_log",
    "CloseLogFile": "Static helper closing pKsd_t->log; deferred along with cm_cmd_log",
    "OpenDbgLogFile": "Static helper opening dbglog.txt; deferred along with cm_cmd_debug",
    "CloseDbgLogFile": "Static helper closing dbglog.txt; deferred along with cm_cmd_debug",
    # ------------------------------------------------------------------
    # cm_phon.c uncertain-phoneme replay machinery. The Python phoneme
    # input path doesn't model the C source's hold buffer / replay
    # queue (which exists to retry IPA-style ARPA pairs after a
    # vowel-cluster ambiguity is resolved).
    # ------------------------------------------------------------------
    "cm_phon_check": "Drives the q_flag hold-buffer state machine; Python phoneme path is simpler",
    "cm_phon_flush": "Flushes the hold-buffer at clause boundaries; deferred with cm_phon_check",
    "cm_phon_match": "Matches phoneme triples vs uncertain_phones; only called via cm_phon_check",
    "cm_phon_param_check": "Parses [:phoneme] params; Python handles via cm_cmd_phoneme directly",
    "replay_buffer": "Drains the q_flag hold-buffer back through cm_phon_check",
    # ------------------------------------------------------------------
    # cm_text.c clause splitter and inline index helpers. The Python
    # port uses dectalk.parser.text_get_word for word extraction; the C
    # body of cm_text_getclause runs the per-character clause state
    # machine over the inter-thread pipe.
    # ------------------------------------------------------------------
    "cm_text_getclause": "Per-character clause-boundary state machine over the CMD pipe",
    "par_copy_index_cm_text": "Static inline duplicate of par_copy_index used inside cm_text only",
    "par_copy_index_list_cm_text": "Static inline duplicate of par_copy_index_list used in cm_text",
    "par_is_index_set_cm_text": "Static inline duplicate of par_is_index_set used in cm_text",
    # ------------------------------------------------------------------
    # cm_util.c pipe / typing helpers. These all write to the
    # inter-thread ph_pipe / lts_pipe / vtm_pipe -- Python is
    # synchronous so there is no equivalent.
    # ------------------------------------------------------------------
    "cm_util_initialize": "Initialises pCmd_t->cm array; Python uses static module data",
    "cm_util_flush_init": "Resets the pipe-flush state; Python has no flush state",
    "cm_util_type_out": "Writes ASCII typing chars onto the PH pipe; Python typing path differs",
    "cm_util_dtpc_tones": "Builds DTMF tone packets and writes them to vtm_pipe",
    # ------------------------------------------------------------------
    # cmd_init.c memory teardown. The C function FreeCMDThreadMemory
    # frees malloc()'d pCmd_t state; Python relies on GC. We expose the
    # same surface under the Pythonic snake_case name.
    # ------------------------------------------------------------------
    "FreeCMDThreadMemory": "ported as cmd_init.free_cmd_thread_memory (PEP8 rename)",
    # ------------------------------------------------------------------
    # cmd_wav.c WAV-output handler. The Python port's WAV output runs
    # via dectalk._capi.CAPI and bypasses the C-level [:wave] code,
    # which threads bytes through the kernel pipe and PH layer.
    # ------------------------------------------------------------------
    "wave_file_open": "Static helper to cm_cmd_play; deferred along with it",
    # ------------------------------------------------------------------
    # par_dict.c dictionary lookup engine. The Python port uses the
    # parsed dtalk_us.dic binary directly (dectalk.dic.lookup); the
    # look / find_word / dlook / udlook functions exist mainly to glue
    # the parser's input window onto that dictionary -- not needed yet.
    # ------------------------------------------------------------------
    "par_dict_lookup": "Top-level dict-lookup entry; Python uses dectalk.dic directly",
    "par_dict_find_word": "Bisects against the system dictionary; Python uses dectalk.dic",
    "par_dict_ufind_word": "Bisects against the user dictionary; Python user-dict differs",
    "par_dict_dlook": "Looks up a single word against system dict; Python uses dectalk.dic",
    # ------------------------------------------------------------------
    # par_pars1.c (textually included into par_pars.c) -- the wide
    # rule-table parser machinery. The Python port plans to call into
    # this via dectalk.parser eventually, but most helpers are C-only.
    # ------------------------------------------------------------------
    "ERROR_func1": "Diagnostic helper raised on invalid rule-tab opcode",
    "ERROR_func2": "Diagnostic helper raised on out-of-range rule-tab index",
    "par_process_input": "Main entry of the rule-tabling driver; Python parser routes elsewhere",
    "par_match_rule": "Matches a single compiled rule against the input window",
    "par_match_string": "String-equality matcher for a fixed literal inside a rule",
    "par_match_standard": "Character-class matcher (ALPHA/DIGIT/CONS/VOWEL/etc) for one position",
    "par_match_set": "Matches against an explicit ``[abc]`` character set within a rule",
    "par_match_sets_with_ranges": "Matches ``[a-z0-9]``-style ranges within a rule",
    "par_match_digits": "Matches a digit run with optional lower/upper bounds",
    "par_look_ahead": "Look-ahead helper called by par_match_rule",
    "par_look_ahead_dictionary": "Look-ahead that consults the dictionary; with par_dict_*",
    "par_search_for_word": "Searches for a word boundary inside the rule engine's window",
    "par_dom_dict_search": "Domain dictionary search invoked from inside par_match_rule",
    "par_build_string_from_rule": "Materialises a replacement string from a compiled rule",
    "par_replace_string": "Replaces a matched run with a generated string in the output buffer",
    "par_insert_string": "Inserts a string into the parser's output window",
    "par_insert_string_after": "Variant of par_insert_string anchored after a match",
    "par_insert_string_before": "Variant of par_insert_string anchored before a match",
    "par_status_string": "Builds a debug status string for parser diagnostics",
    # ------------------------------------------------------------------
    # par_pars1.c compound-word machinery. Hooks into German-compound
    # noun splitting, but the Python port doesn't implement compound
    # splitting yet (US English doesn't rely on it for parity).
    # ------------------------------------------------------------------
    "par_break_down_word": "Breaks a word into compound parts; English doesn't exercise it",
    "par_find_word_in_dict": "Helper invoked by par_break_down_word vs the compound dict",
}


# --------------------------------------------------------------------------
# Identifier sets / regexes used by the walker.
# --------------------------------------------------------------------------

_CPP_KEYWORDS: frozenset[str] = frozenset(
    {"if", "while", "for", "switch", "return", "sizeof", "do", "else"}
)

# Macros that themselves emit a function definition. The function name is
# the first argument; the body is the trailing ``{ ... }``. On Linux only
# ``OP_THREAD_ROUTINE`` (from ``nt/opthread.h``) is used this way in the
# cmd module.
_MACRO_FUNCTION_DEFINERS: frozenset[str] = frozenset({"OP_THREAD_ROUTINE"})


# --------------------------------------------------------------------------
# Helpers.
# --------------------------------------------------------------------------


def _read_c(path: Path) -> str:
    """Read ``path`` with CRLF endings normalised."""
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _strip_comments(text: str) -> str:
    """Remove ``/* ... */`` block and ``// ...`` line comments."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _eval_cpp_expr(expr: str, defined: frozenset[str]) -> bool:
    """Evaluate a simple ``#if`` expression against ``defined``."""
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
    """Whether all frames in ``stack`` (excluding the top frame) are active."""
    return all(frame[0] for frame in stack)


def _handle_cpp_directive(directive: str, cpp_stack: list[tuple[bool, bool]]) -> None:
    """Apply a ``#`` directive to ``cpp_stack`` in place."""
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

    Only local-quoted includes pointing at sibling ``.c`` files are
    expanded -- everything else (``<stdio.h>``, ``"port.h"``, etc.) is
    left as a directive for the cpp walker.
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
    """Walk lines tracking ``#ifdef`` state and brace depth."""
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
    """Return the index just after the ``)`` matching ``text[open_idx]``."""
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
    """Scan ``active_text`` for top-level function definitions."""
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
        if not depth_zero_before[match.start()]:
            continue

        paren_start = match.end() - 1
        end_idx = _balance_parens(active_text, paren_start)
        if end_idx is None:
            continue

        i = end_idx
        while i < n and active_text[i] in " \t\n\r":
            i += 1
        if i >= n or active_text[i] != "{":
            continue

        if ident in _MACRO_FUNCTION_DEFINERS:
            inner = active_text[paren_start + 1 : end_idx - 1]
            first_arg = inner.split(",", 1)[0].strip()
            inner_match = re.match(r"^([A-Za-z_]\w*)", first_arg)
            if inner_match is not None:
                found.add(inner_match.group(1))
        else:
            found.add(ident)

    return found


def _enumerate_c_functions_in(path: Path) -> set[str]:
    """Return the set of Linux-active function definitions in ``path``."""
    raw = _read_c(path)
    no_comments = _strip_comments(raw)
    lines = no_comments.split("\n")
    lines = _expand_local_c_includes(lines, path.parent)
    active_text, depth0 = _collect_active_text(lines)
    return _scan_definitions(active_text, depth0)


def _enumerate_all_cmd_functions() -> set[str]:
    """Enumerate every Linux-active function definition in the cmd module."""
    funcs: set[str] = set()
    for name in _LINUX_BUILT_FILES:
        path = _C_DIR / name
        if not path.is_file():
            continue
        funcs |= _enumerate_c_functions_in(path)
    return funcs


def _extract_all_entries(value: ast.expr) -> set[str]:
    """Extract string-literal entries from an ``__all__`` AST node."""
    entries: set[str] = set()
    if isinstance(value, ast.List | ast.Tuple):
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                entries.add(elt.value)
    return entries


def _enumerate_python_cmd_symbols() -> set[str]:
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
    """Concatenated text of every Linux-active cmd C file (CRLF normalised).

    Used to confirm that ``_DEFERRED`` keys actually correspond to something
    that appears in the C source -- catches typos when the allow-list is
    edited. Includes ``par_pars1.c`` because that file is textually pulled
    into ``par_pars.c`` on Linux (``#include "par_pars1.c"`` inside the
    ``NEW_BINARY_PARSER`` branch).
    """
    chunks: list[str] = []
    files = [*_LINUX_BUILT_FILES, "par_pars1.c"]
    for name in files:
        path = _C_DIR / name
        if path.is_file():
            chunks.append(_read_c(path))
    return "\n".join(chunks)


# --------------------------------------------------------------------------
# Tests.
# --------------------------------------------------------------------------


def test_every_linux_active_cmd_function_has_python_port() -> None:
    """Every Linux-active function in the cmd module has a Python port."""
    c_funcs = _enumerate_all_cmd_functions()
    assert c_funcs, "expected to find at least one cmd function definition"
    py_syms = _enumerate_python_cmd_symbols()
    missing = c_funcs - py_syms - set(_DEFERRED.keys())
    assert not missing, (
        f"Missing Python ports for cmd module functions: {sorted(missing)}. "
        f"Either port them, or add to _DEFERRED with a one-line reason."
    )


def test_deferred_cmd_symbols_actually_in_c_source() -> None:
    """``_DEFERRED`` entries must correspond to real C functions (catches typos)."""
    c_text = _concatenated_c_source()
    for name in _DEFERRED:
        assert re.search(rf"\b{re.escape(name)}\s*\(", c_text), (
            f"_DEFERRED has '{name}' but the Linux-built cmd C sources don't mention it"
        )


def test_no_dead_deferred_entries() -> None:
    """If a deferred function gets ported, the ``_DEFERRED`` entry should be removed."""
    py_syms = _enumerate_python_cmd_symbols()
    redundant = set(_DEFERRED.keys()) & py_syms
    assert not redundant, (
        f"_DEFERRED entries that are actually ported (remove from _DEFERRED): {sorted(redundant)}"
    )


def test_enumerator_finds_known_ported_cmd_functions() -> None:
    """Sanity check: the walker locates a handful of known-ported names.

    If this regresses, the regex / preprocessor walker has broken and the
    inventory test above is unreliable.
    """
    c_funcs = _enumerate_all_cmd_functions()
    expected = {
        # cm_cmd.c (the command-dispatch core).
        "cm_cmd_reset_comm",
        # cm_copt.c (per-keyword handlers).
        "cm_cmd_break",
        "cm_cmd_cpu_rate",
        "cm_cmd_error",
        "cm_cmd_language",
        "cm_cmd_phoneme",
        "cm_cmd_punct",
        "cm_cmd_remove",
        "cm_cmd_say",
        "cm_cmd_setv",
        "cm_cmd_skip",
        "cm_cmd_timeout",
        # cm_pars.c.
        "cm_pars_new_state",
        "cm_pars_icommand",
        # cm_phon.c.
        "cm_phon_lookup_arpa",
        "cm_phon_lookup_asc",
        "cm_phon_lookup_language",
        # cm_text.c / cm_util.c.
        "cm_text_get_word",
        "cm_util_dtpc_tones_reset",
        "cm_util_init_type",
        "cm_util_string_match",
        # cmd_init.c.
        "cmd_init",
        # par_pars / par_pars1 helpers that landed early.
        "par_check_word_string",
        "par_convert_number",
        "par_convert_number_new2",
        "par_copy_word_to_output",
        "par_delete_string",
        "par_get_int_length",
        "par_print_rule_error",
        "par_save_string",
        "par_skip_white_space",
        "par_dict_where_to_look",
    }
    missing = expected - c_funcs
    assert not missing, f"enumerator failed to find known ported cmd functions: {sorted(missing)}"


def test_enumerator_skips_vocal_only_definitions() -> None:
    """``VOCAL``-guarded definitions in cm_pars.c must be skipped.

    ``cm_pars.c`` contains a large ``#ifdef VOCAL`` block (with the
    pre-redesign code path) followed by an ``#else`` body that the Linux
    build actually uses. The duplicate VOCAL definitions of
    ``cm_pars_loop`` / ``cm_pars_new_state`` must not be double-counted,
    and ``VOCAL``-only helpers must be omitted entirely.
    """
    c_funcs = _enumerate_c_functions_in(_C_DIR / "cm_pars.c")
    assert "cm_pars_loop" in c_funcs
    assert "cm_pars_new_state" in c_funcs
    # cmd_loop is guarded by #ifdef ARM7 in cm_pars.c -- Linux never sees it.
    assert "cmd_loop" not in c_funcs, "cmd_loop is ARM7-only and must be skipped"


def test_enumerator_skips_arm7_only_definitions() -> None:
    """``ARM7``-guarded definitions across the cmd module are skipped."""
    funcs = _enumerate_all_cmd_functions()
    # cmd_loop lives inside ``#ifdef ARM7`` in cm_pars.c.
    assert "cmd_loop" not in funcs
    # The MSDOS-only ``main`` in cm_main.c must also stay out.
    assert "main" not in funcs


def test_enumerator_skips_msdos_only_definitions() -> None:
    """``MSDOS``-only definitions are skipped on Linux."""
    funcs = _enumerate_all_cmd_functions()
    # The first ``OutputCharacter(unsigned char c)`` overload in cm_pars.c
    # lives in ``#ifdef MSDOS``; the active one takes ``LPTTS_HANDLE_T``.
    # Either way the walker should still see exactly one ``OutputCharacter``.
    cm_pars_funcs = _enumerate_c_functions_in(_C_DIR / "cm_pars.c")
    assert "OutputCharacter" in cm_pars_funcs
    # MSDOS-only main() in cm_main.c is filtered.
    assert "main" not in funcs


def test_enumerator_includes_par_pars1_via_par_pars() -> None:
    """``par_pars1.c`` is textually included into ``par_pars.c`` on Linux.

    With ``NEW_BINARY_PARSER`` defined, ``par_pars.c`` is reduced to just
    ``#include "par_pars1.c"`` -- meaning every par_pars1 function is
    Linux-active. The walker must therefore pull them in when scanning
    ``par_pars.c``.
    """
    par_pars_funcs = _enumerate_c_functions_in(_C_DIR / "par_pars.c")
    assert "par_match_rule" in par_pars_funcs
    assert "par_check_word_string" in par_pars_funcs
    assert "par_save_string" in par_pars_funcs


def test_enumerator_recognises_op_thread_routine_macro() -> None:
    """``OP_THREAD_ROUTINE(cmd_main, ...)`` is treated as a definition of ``cmd_main``.

    On Linux this macro expands to ``void cmd_main(LPTTS_HANDLE_T phTTS)``.
    The walker has to extract the first argument as the function name.
    """
    cm_main_funcs = _enumerate_c_functions_in(_C_DIR / "cm_main.c")
    assert "cmd_main" in cm_main_funcs, (
        f"expected cmd_main in cm_main.c, got {sorted(cm_main_funcs)}"
    )


def test_enumerator_skips_tab_files() -> None:
    """``*.tab`` data-only files contribute no function definitions.

    They live in the same directory and could otherwise pollute the walker
    if it tried to scan them. We just confirm the loop only touches the
    Linux-built ``.c`` files.
    """
    for name in _LINUX_BUILT_FILES:
        assert name.endswith(".c")
        assert not name.endswith(".tab")
