"""Inventory parity test for the API module against the Python port.

Re-parses every ``.c`` file under ``src/dapi/src/api/`` that the Linux
``libtts_us.so`` build actually compiles, enumerates each Linux-active
function definition, and asserts each one has a corresponding Python
port under :mod:`dectalk.api` -- or sits on the :data:`_DEFERRED`
allow-list with a one-line reason.

This mirrors :mod:`tests.unit.test_kernel_services_inventory` for the
API subsystem, which spans the high-level public ``TextToSpeech*``
entry points plus a handful of helpers. The walker is the same
preprocessor-aware approach (``#ifdef`` / ``#ifndef`` / ``#if``
evaluated against a fixed set of Linux ``-D`` macros), with one
extension:

* ``OP_THREAD_ROUTINE(name, args)`` (defined in ``nt/opthread.h``) is
  recognised as a function-defining macro, mapping the first argument
  to the function name. ``ttsapi.c``'s ``TextToSpeechThreadMain`` entry
  point uses this on Linux.

Files scanned, per ``src/dapi/src/api/Makefile`` (``API_SRC`` plus
``crypt2.c`` which is built into ``crypt2.o``):

- ``crypt2.c``    -- FONIX license-string encryption helpers
- ``decstd97.c``  -- DEC STD 97 copyright-notice payload (defines no
                     functions on Linux -- the file is only a static
                     string literal)
- ``init.c``      -- per-DLL shared-memory init/fini stubs (Linux
                     branches are essentially empty)
- ``ttsapi.c``    -- the bulk of the API: ``TextToSpeechStartup`` /
                     ``TextToSpeechSpeak`` and friends, plus internal
                     helpers for buffer management, the worker thread
                     entry, error reporting and so on

Note ``epsonapi.c`` is NOT in ``API_SRC`` and therefore never
compiled into ``libtts_us.so`` -- it stays out of ``_C_FILES``.

The Linux build of ``ttsapi.c`` also picks up
``TextToSpeechConvertToPhonemes`` thanks to the in-tree patch
``tests/parity/c_patches/0001-expose-convert-to-phonemes-on-linux.patch``
which moves the surrounding ``#endif /* WIN32 */`` marker so the
function is exposed on Linux/macOS too. The walker correctly identifies
it as Linux-active.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

_C_DIR = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/api"
_PY_DIR = Path(__file__).resolve().parents[2] / "src" / "dectalk" / "api"

# C source files that the Linux US-English ``libtts_us.so`` build actually
# compiles into the API module (per ``src/dapi/src/api/Makefile``'s
# ``API_OBJ`` rule: ``ttsapi_mme.o``, ``decstd97.o``, ``init.o`` and
# ``crypt2.o``). ``epsonapi.c`` is NOT in the build -- its functions are
# excluded by omission. ``ttsapi_demo.o`` shares the ``ttsapi.c`` source
# but is rebuilt with ``-DDEMO``; we scan the non-DEMO compilation since
# that's the symbol set exported by the public ``libtts_us.so``.
_C_FILES: list[Path] = [
    _C_DIR / "crypt2.c",
    _C_DIR / "decstd97.c",
    _C_DIR / "init.c",
    _C_DIR / "ttsapi.c",
]


pytestmark = pytest.mark.skipif(
    not all(p.is_file() for p in _C_FILES),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Preprocessor symbols we treat as "defined" for the Linux ``libtts_us.so``
# build of the API module. Sources:
#
# 1. ``src/dapi/src/api/Makefile``'s ``DEFINES`` line
#    (``-D_REENTRANT -DNOMME -DLTSSIM -DTTSSIM -DANSI -DBLD_DECTALK_DLL
#    -DACCESS32 -DTYPING_MODE``).
# 2. ``src/Makefile``'s ``english_release`` target
#    (``LANGUAGE=ENGLISH -DENGLISH_US -DACNA``).
# 3. ``-DDEC`` -- passed to ``ttsapi_mme.o`` / ``ttsapi_demo.o`` /
#    ``init.o`` / ``init_demo.o`` via per-target rules in the Makefile.
# 4. ``__linux__`` defined by GCC implicitly.
# 5. ``HLSYN`` / ``NEW_BINARY_PARSER`` / ``SINGLE_THREADED`` /
#    ``PARSER_HACK_FOR_OLD_SONGS`` come in via ``src/dectalkf_klsyn.h``
#    (the header ``src/dectalkf.h`` actually pulls in), matching the
#    rest of the codebase's inventory tests.
#
# Symbols deliberately NOT in this set: ``DEMO`` (we scan the non-DEMO
# compilation, ``ttsapi_mme.o`` / ``init.o``), ``WIN32``, ``MSDOS``,
# ``ARM7``, ``VXWORKS``, ``__osf__``, ``_SPARC_SOLARIS_``, ``OLEDECTALK``,
# ``SAPI5DECTALK``, ``UNDER_CE``, ``LICENSES``, ``THIRD_PARTY``,
# ``__EMSCRIPTEN__``, ``__APPLE__`` -- so the corresponding branches are
# inactive on Linux.
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
        "DEC",
        # Language flags from src/Makefile's english_release target.
        "ENGLISH",
        "ENGLISH_US",
        "ACNA",
        # Headers in src/dectalkf_klsyn.h.
        "HLSYN",
        "NEW_BINARY_PARSER",
        "SINGLE_THREADED",
        "PARSER_HACK_FOR_OLD_SONGS",
    }
)


# --------------------------------------------------------------------------
# Function-defining macros: ``OP_THREAD_ROUTINE(name, args) { ... }``
# (defined in ``nt/opthread.h``) expands to ``void name(args) { ... }``
# on Linux. The walker treats the macro identifier as a sigil and uses
# the first macro argument as the actual function name. ``ttsapi.c``
# uses this on Linux for ``TextToSpeechThreadMain``.
# --------------------------------------------------------------------------
_MACRO_FUNCTION_DEFINERS: frozenset[str] = frozenset({"OP_THREAD_ROUTINE"})


# --------------------------------------------------------------------------
# Functions defined in the scanned API C files that are intentionally not
# ported yet (or whose Python port lives under a different Pythonic name).
# Each entry needs a one-line reason. When a port lands, the entry must be
# removed -- the ``test_no_dead_deferred_entries`` guard enforces that.
#
# The Python port is a high-level rewrite: ``dectalk.api.speak`` /
# ``dectalk.api.to_wav`` route through ``dectalk._capi.CAPI`` (a ctypes
# wrapper over ``libtts_us.so``) for byte-identical WAVs, with a
# pure-Python fallback for non-US-English languages. None of the C entry
# points exist verbatim under the same name in Python, so every
# Linux-active definition is deferred for now -- the test serves as a
# precise progress meter and a documentation surface for which
# ``TextToSpeech*`` entry points still need a Pythonic equivalent.
# --------------------------------------------------------------------------
_DEFERRED: dict[str, str] = {
    # ----- crypt2.c -- FONIX license-key obfuscation helpers. -----------
    # The Python port doesn't perform a runtime license check; libtts_us.so
    # does, and ``dectalk._capi`` happily uses its bundled license. There
    # is no need for a Pythonic equivalent unless we ever ship a pure-
    # Python license validator (which we have no plans to do).
    "encryptString": (
        "FONIX license obfuscation; Python port relies on libtts_us.so's bundled check"
    ),
    "decryptString": (
        "FONIX license obfuscation; Python port relies on libtts_us.so's bundled check"
    ),
    "sixencode24": (
        "static helper to encryptString (24-bit -> 4 sixel encoding); deferred along with it"
    ),
    "sixdecode24": (
        "static helper to decryptString (4 sixel -> 24-bit decoding); deferred along with it"
    ),
    "trand": "tiny LCG used to seed the FONIX cipher; deferred with the rest of crypt2.c",
    "rot24": "24-bit rotate helper for the FONIX cipher; deferred with the rest of crypt2.c",
    "unrot24": (
        "24-bit reverse-rotate helper for the FONIX cipher; deferred with the rest of crypt2.c"
    ),
    "rot32": "32-bit rotate helper for the FONIX cipher; deferred with the rest of crypt2.c",
    # ----- init.c -- per-DLL shared-memory init/fini. -------------------
    # On Linux every actual body sits inside an ``#ifdef __osf__`` or a
    # ``#if defined VXWORKS || defined _SPARC_SOLARIS_`` branch, so the
    # Linux compilation is functionally a no-op. The Python port has no
    # shared-memory layer at all (it uses regular process memory through
    # ctypes), so no equivalent is needed.
    # ----- ttsapi.c -- internal helpers. --------------------------------
    "GetBuffer": (
        "Pops a TTS_BUFFER_T off the free list; Python audio backend "
        "uses bytes / numpy arrays directly with no buffer pool"
    ),
    "DeleteTextToSpeechObjects": (
        "Frees all per-handle pthread/queue resources; the Python port "
        "owns no per-handle state -- ``_capi.CAPI`` does"
    ),
    "SetSpeaker": (
        "Internal helper that copies SPEAKER_T fields into the TTS "
        "handle; Python's ``dectalk.voices`` resolves preset names "
        "directly through libtts_us.so's SetSpeaker"
    ),
    "TextToSpeechThreadMain": (
        "OP_THREAD_ROUTINE worker pumping the text queue; Python port "
        "is single-threaded and dispatches synchronously through _capi"
    ),
    "PutIndexMarkInBuffer": (
        "Stages an index-mark token in the current output buffer; "
        "Python emits marks through ``IndexMarkEvent`` callbacks"
    ),
    "PutPhonemeInBuffer": (
        "Stages a phoneme token in the current output buffer; Python "
        "exposes phoneme transcripts via ``text_to_phonemes``"
    ),
    "QueueToMemory": (
        "Splits a synthesised buffer between in-memory consumers; "
        "Python's ``to_wav`` returns the whole buffer as bytes"
    ),
    "Report_TTS_Status": (
        "Posts a status-change message to the host (WM_DECTALKMESSAGE "
        "on Windows, callback on Linux); Python uses regular Python "
        "exceptions and return values"
    ),
    "ReturnRemainingBuffers": (
        "Drains the in-flight buffer queue back to the host; Python "
        "audio backend has no host-owned buffer queue"
    ),
    "SendBuffer": (
        "Hands a filled buffer to the audio device or in-memory sink; "
        "Python writes to bytes / sounddevice directly"
    ),
    "DrainPipes": (
        "Forces an LTS/PH/VTM pipe drain at shutdown; Python pipeline "
        "is synchronous so there's nothing left to drain"
    ),
    "TextToSpeechErrorHandler": (
        "Posts MMRESULT errors to the host's error callback; Python raises exceptions instead"
    ),
    "WaitForLtsFlush": (
        "Spins until the LTS pipe drains its current sentence; not "
        "needed in the synchronous Python pipeline"
    ),
    "WriteAudioToFile": (
        "Internal RIFF/WAV header writer used by the worker thread; "
        "Python uses the stdlib ``wave`` module via ``to_wav``"
    ),
    # ----- ttsapi.c -- per-stage boundary-dump hooks (Phase A.4). -------
    # Added by tests/parity/c_patches/0002-stage-boundary-dumps.patch.
    # These are C-only test instrumentation, gated on DECTALK_DUMP_DIR.
    # The Python side reads the resulting dump files via
    # ``dectalk._capi.CAPI.dump_pipeline`` (which is itself the Python
    # equivalent of "what these helpers do").
    "_dectalk_dump_kernel_open": (
        "C-only test hook (lazy fopen of kernel.dump); Python-side "
        "equivalent is ``CAPI.dump_pipeline`` setting DECTALK_DUMP_DIR"
    ),
    "_dectalk_dump_kernel_chunk": (
        "C-only test hook (per-write_pipe-chunk record emitter); "
        "Python-side equivalent is ``CAPI.dump_pipeline`` reading the dump file"
    ),
    # ----- ttsapi.c -- public TextToSpeech* entry points. ---------------
    # These are the symbols ``libtts_us.so`` exports. ``dectalk._capi.CAPI``
    # binds the ones the Python port needs (``TextToSpeechStartup`` /
    # ``TextToSpeechSpeak`` / ``TextToSpeechSync`` / ...) via ctypes;
    # ``dectalk.api.speak`` / ``dectalk.api.to_wav`` / ``dectalk.api.sing``
    # are the user-facing Pythonic wrappers. None of these entry points is
    # re-exported under its original camelCase name, so each is deferred
    # with that explanation.
    "TextToSpeechAddBuffer": (
        "Public entry; called from libtts_us.so via _capi when in-memory "
        "queueing is needed -- Python doesn't expose host-supplied buffers"
    ),
    "TextToSpeechCloseInMemory": (
        "Public entry; closes an in-memory sink. Python's ``to_wav`` "
        "returns bytes directly, no sink lifecycle to manage"
    ),
    "TextToSpeechCloseLang": (
        "Public entry; closes a loaded language. Python loads languages "
        "via the dectalkml dispatcher, not a per-handle close"
    ),
    "TextToSpeechCloseLogFile": (
        "Public entry; closes a phoneme-log file. Python returns phoneme "
        "transcripts directly through ``text_to_phonemes``"
    ),
    "TextToSpeechCloseSapi5Output": ("Public entry; SAPI5 only. Python port has no SAPI5 surface"),
    "TextToSpeechCloseWaveOutFile": (
        "Public entry; closes a WAV file the engine was writing into. "
        "Python's ``to_wav`` writes the whole file atomically"
    ),
    "TextToSpeechConvertToPhonemes": (
        "Public entry (exposed on Linux by 0001-expose-convert-to-phonemes-on-linux.patch); "
        "ported as ``dectalk.api.text_to_phonemes`` (Pythonic rename)"
    ),
    "TextToSpeechEnumLangs": (
        "Public entry; enumerates loaded languages. Python's "
        "``dectalk.api.available_voices`` covers the common case"
    ),
    "TextToSpeechGetFeatures": (
        "Public entry; returns the feature bitmask. The constants live "
        "in ``dectalk.api.tts_feats`` but no Python wrapper exists yet"
    ),
    "TextToSpeechGetPhVdefParams": (
        "Public entry; returns per-voice PH parameter overrides. "
        "Python ``dectalk.voices`` exposes per-preset parameters directly"
    ),
    "TextToSpeechGetRate": (
        "Public entry; returns the current speaking rate. Python "
        "callers pass ``rate=...`` to ``speak`` / ``to_wav`` directly"
    ),
    "TextToSpeechGetSpeaker": (
        "Public entry; returns the current SPEAKER_T id. Python uses "
        "``dectalk.voices`` preset names, not numeric ids"
    ),
    "TextToSpeechGetStatus": (
        "Public entry; queries TTS_STATUS_T bits. Python returns the "
        "result of ``speak`` synchronously, no async status to poll"
    ),
    "TextToSpeechGetVolume": (
        "Public entry; returns 16-bit master volume. Python doesn't "
        "expose a master-volume knob -- callers post-process audio"
    ),
    "TextToSpeechLoadUserDictionary": (
        "Public entry; loads a per-handle pronunciation dictionary. "
        "Python's pure-Python pipeline uses a built-in dictionary only"
    ),
    "TextToSpeechOpenInMemory": (
        "Public entry; opens an in-memory sink. Python's ``to_wav`` "
        "returns bytes directly, no sink lifecycle"
    ),
    "TextToSpeechOpenLogFile": (
        "Public entry; opens a phoneme-log file. Python returns "
        "transcripts through ``text_to_phonemes`` instead"
    ),
    "TextToSpeechOpenSapi5Output": ("Public entry; SAPI5 only. Python port has no SAPI5 surface"),
    "TextToSpeechOpenWaveOutFile": (
        "Public entry; opens a WAV file for the engine to stream into. "
        "Python's ``to_wav`` writes the whole file atomically"
    ),
    "TextToSpeechPause": (
        "Public entry; pauses the worker thread. Python pipeline is synchronous -- nothing to pause"
    ),
    "TextToSpeechReset": (
        "Public entry; flushes the worker queues. Python pipeline is "
        "synchronous so there's nothing to reset between calls"
    ),
    "TextToSpeechResume": (
        "Public entry; resumes the paused worker. Python pipeline is "
        "synchronous, no pause/resume state"
    ),
    "TextToSpeechReturnBuffer": (
        "Public entry; recycles a host-supplied buffer. Python doesn't expose host-supplied buffers"
    ),
    "TextToSpeechSelectLang": (
        "Public entry; switches the active language for a handle. Python "
        "passes ``lang=`` per call instead of mutating handle state"
    ),
    "TextToSpeechSetRate": (
        "Public entry; sets the speaking rate. Python callers pass "
        "``rate=...`` to ``speak`` / ``to_wav`` directly"
    ),
    "TextToSpeechSetSpeaker": (
        "Public entry; sets the SPEAKER_T id. Python callers pass "
        "a voice preset name to ``speak`` / ``to_wav`` directly"
    ),
    "TextToSpeechSetVolume": (
        "Public entry; sets 16-bit master volume. Python doesn't expose a master-volume knob"
    ),
    "TextToSpeechShutdown": (
        "Public entry; tears down a handle. ``_capi.CAPI`` calls this "
        "transparently when the wrapper is finalised"
    ),
    "TextToSpeechSpeak": (
        "Public entry; queues text for the worker. Ported as the "
        "Pythonic ``dectalk.api.speak`` / ``to_wav`` (no host-supplied handle)"
    ),
    "TextToSpeechSpeakEx": (
        "Public entry; ``Speak`` variant with extra flags. Ported "
        "behaviour is covered by ``dectalk.api.speak`` / ``to_wav``"
    ),
    "TextToSpeechStartLang": (
        "Public entry; loads a language into a handle. Python loads "
        "languages through the dectalkml dispatcher transparently"
    ),
    "TextToSpeechStartup": (
        "Public entry; allocates a handle and worker thread. "
        "``_capi.CAPI`` calls this transparently"
    ),
    "TextToSpeechStartupEx": (
        "Public entry; ``Startup`` variant with callback hooks. "
        "Python doesn't expose host callbacks"
    ),
    "TextToSpeechStartupExFonix": (
        "Public entry; FONIX licensee ``StartupEx``. Python port "
        "relies on libtts_us.so's bundled license"
    ),
    "TextToSpeechSync": (
        "Public entry; blocks until the worker drains. The synchronous "
        "Python pipeline already returns only when fully drained"
    ),
    "TextToSpeechTuning": (
        "Public entry; enables / extracts VTM tuning data. Python "
        "port has no tuning-data surface yet"
    ),
    "TextToSpeechTyping": (
        "Public entry; per-character interactive synthesis. Python "
        "port has no streaming character-by-character surface yet"
    ),
    "TextToSpeechUnloadUserDictionary": (
        "Public entry; unloads a per-handle user dictionary. Python "
        "port has no user-dictionary surface"
    ),
    "TextToSpeechVersionEx": (
        "Public entry; ``Version`` variant with extended fields. "
        "Same status as ``TextToSpeechVersion``"
    ),
    "TextToSpeechVisualMarks": (
        "Public entry; enables phoneme/duration visual notifications. "
        "Python port has no visual-mark callback surface yet"
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

    Both forms can hide function-definition-looking text inside the API
    sources (the long copyright headers and the file-prologue revision
    histories are full of ``Function: Name`` lines that should not be
    mistaken for definitions), so we strip them before scanning.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _eval_cpp_expr(expr: str, defined: frozenset[str]) -> bool:
    """Evaluate a simple ``#if`` expression against ``defined``.

    Supports ``defined X`` / ``defined(X)``, ``!``, ``&&``, ``||``, and
    parentheses. Anything else (numeric constants, comparisons) is treated
    conservatively as false -- the API sources only use defined() guards
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
    filtered out, as are prototype declarations ending with ``;``. When
    ``IDENT`` is one of the :data:`_MACRO_FUNCTION_DEFINERS`, the first
    argument inside the parens is used as the actual function name (for
    ``OP_THREAD_ROUTINE(TextToSpeechThreadMain, ...) { ... }``).
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

        paren_start = match.end() - 1
        end_idx = _balance_parens(active_text, paren_start)
        if end_idx is None:
            continue

        # Look ahead past whitespace: ``{`` -> definition; ``;`` -> decl.
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
    """Parse top-level function definitions from one API C source file.

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
    """Union of function definitions across all scanned API C files."""
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


def _enumerate_python_api_symbols() -> set[str]:
    """Collect top-level ``def`` names plus every ``__all__`` entry."""
    names: set[str] = set()
    for py_file in sorted(_PY_DIR.glob("*.py")):
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:  # pragma: no cover -- defensive
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
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


# --------------------------------------------------------------------------
# Tests.
# --------------------------------------------------------------------------


def test_every_linux_active_api_function_has_python_port() -> None:
    """Every Linux-active C function in the scanned API files has a Python port."""
    c_funcs = _enumerate_all_c_functions()
    assert c_funcs, "expected to find at least one function definition across API files"
    py_syms = _enumerate_python_api_symbols()
    missing = c_funcs - py_syms - set(_DEFERRED.keys())
    assert not missing, (
        f"Missing Python ports for API-module C functions: "
        f"{sorted(missing)}. Either port them, or add to _DEFERRED with a reason."
    )


def test_deferred_api_symbols_actually_in_c_source() -> None:
    """_DEFERRED entries must correspond to real C functions (catches typos)."""
    combined = "\n".join(_read_c(p) for p in _C_FILES)
    for name in _DEFERRED:
        assert re.search(rf"\b{re.escape(name)}\s*\(", combined), (
            f"_DEFERRED has '{name}' but none of the scanned API C files mention it"
        )


def test_no_dead_deferred_entries() -> None:
    """If a deferred function gets ported, the _DEFERRED entry should be removed."""
    py_syms = _enumerate_python_api_symbols()
    redundant = set(_DEFERRED.keys()) & py_syms
    assert not redundant, (
        f"_DEFERRED entries that are actually ported (remove from _DEFERRED): {sorted(redundant)}"
    )


def test_enumerator_finds_known_public_api_entry_points() -> None:
    """Sanity check: well-known public API entry points are detected by the enumerator.

    If this test fails the regex / preprocessor walker has regressed and the
    inventory test above is unreliable. The chosen names span all three
    function-bearing scanned files (crypt2.c, init.c, ttsapi.c) so any
    walker regression -- a botched #ifdef, a comment-strip bug, an
    OP_THREAD_ROUTINE macro miss -- breaks at least one of them.
    """
    c_funcs = _enumerate_all_c_functions()
    expected = {
        # crypt2.c -- the FONIX cipher helpers.
        "encryptString",
        "decryptString",
        "trand",
        # init.c -- Linux shared-memory stubs.
        "__init_shared_mem",
        "__fini_shared_mem",
        # ttsapi.c -- the bulk of the public API.
        "TextToSpeechStartup",
        "TextToSpeechSpeak",
        "TextToSpeechSync",
        "TextToSpeechShutdown",
        "TextToSpeechSetSpeaker",
        "TextToSpeechSetRate",
        # ttsapi.c -- OP_THREAD_ROUTINE worker entry on Linux.
        "TextToSpeechThreadMain",
        # ttsapi.c -- patched onto Linux by 0001-expose-convert-to-phonemes-on-linux.patch.
        "TextToSpeechConvertToPhonemes",
    }
    missing = expected - c_funcs
    assert not missing, f"enumerator failed to find well-known API entry points: {sorted(missing)}"


def test_enumerator_skips_win32_only_libmain() -> None:
    """``LibMain`` is defined inside ``#ifdef WIN32`` and must be skipped on Linux."""
    c_funcs = _enumerate_c_functions_in(_C_DIR / "ttsapi.c")
    assert "LibMain" not in c_funcs, (
        "LibMain is defined under #ifdef WIN32 but the enumerator did not skip it"
    )


def test_enumerator_skips_licenses_only_all_digits() -> None:
    """``all_digits`` is defined inside ``#ifdef LICENSES`` and must be skipped on Linux.

    The Linux build doesn't pass ``-DLICENSES``, so ``all_digits`` is
    dead code in our compilation. Any leak through the walker would
    show up as a spurious "missing port" complaint.
    """
    c_funcs = _enumerate_c_functions_in(_C_DIR / "ttsapi.c")
    assert "all_digits" not in c_funcs, (
        "all_digits is defined under #ifdef LICENSES but the enumerator did not skip it"
    )


def test_enumerator_skips_win32_only_save_user_dictionary() -> None:
    """``TextToSpeechSaveUserDictionary`` lives inside the ``#ifdef WIN32`` block.

    The whole save-user-dictionary entry point sits between
    ``#ifdef WIN32`` (around line 11570) and ``#endif /* WIN32 */``
    (around line 11725), so it must NOT show up on Linux. (Contrast
    ``TextToSpeechConvertToPhonemes``, which our in-tree patch moves
    *out* of that same block.)
    """
    c_funcs = _enumerate_c_functions_in(_C_DIR / "ttsapi.c")
    assert "TextToSpeechSaveUserDictionary" not in c_funcs, (
        "TextToSpeechSaveUserDictionary is inside #ifdef WIN32 but the enumerator did not skip it"
    )


def test_enumerator_skips_epsonapi_c() -> None:
    """``epsonapi.c`` is not in ``API_SRC`` and must not be scanned.

    The Makefile's ``API_OBJ`` rule compiles only ``ttsapi_*.o``,
    ``decstd97.o``, ``init*.o`` and ``crypt2.o``. ``epsonapi.c`` is
    a stand-alone Epson-firmware front-end that the Linux build does
    not pull in -- its functions (``TextToSpeechInit`` /
    ``TextToSpeechStart`` / ``TextToSpeechReset``, all of which clash
    with names from ttsapi.c that we *do* care about) must not leak
    into the inventory.
    """
    scanned_names = {p.name for p in _C_FILES}
    assert "epsonapi.c" not in scanned_names, (
        "epsonapi.c is not built by the Linux Makefile; remove it from _C_FILES"
    )


def test_decstd97_defines_no_functions() -> None:
    """``decstd97.c`` is a string-literal-only file; no function definitions.

    DEC STD 97 Section 4.1 requires the copyright notice be carried
    verbatim in the shipped binary, and the C source carries it in a
    single ``volatile char standard_notices[2048]`` global. The walker
    must therefore find zero function definitions in that file -- a
    non-zero count would mean a runaway scan picked up text inside the
    quoted string literal.
    """
    c_funcs = _enumerate_c_functions_in(_C_DIR / "decstd97.c")
    assert c_funcs == set(), (
        f"decstd97.c should have no function definitions, walker returned: {sorted(c_funcs)}"
    )
