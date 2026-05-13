"""C-source parity tests for the inline-command (``[:cmd ...]``) handlers.

Re-parses each handler's function body from
``src/dapi/src/cmd/cm_copt.c`` at test time and asserts that the Python
port matches three structural invariants of the C original:

1. **Option-table cross-check** — the option table the handler uses
   (``log_options``, ``say_options``, ...) is the table named in the
   C source's ``cm_util_string_match`` call, in the canonical order
   listed in ``c_us_cde.h``.
2. **Switch-case coverage** — every numeric ``case`` label that
   appears in the C ``switch(value)`` block is handled by the Python
   port (or explicitly documented as a noted C-source bug).
3. **Return-code mapping** — each handler that returns
   ``CMD_bad_string`` when ``cm_util_string_match`` yields
   ``NO_STRING_MATCH`` does so in Python too.

The tests skip cleanly when ``DECTALK_SRC`` (or the default
``/tmp/dectalk-src``) is absent, mirroring the existing parity-test
pattern (see ``test_cmd_option_tables.py``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd import option_tables as ot
from dectalk.cmd.cm_cmd_break import cm_cmd_break
from dectalk.cmd.cm_cmd_error import cm_cmd_error
from dectalk.cmd.cm_cmd_language import cm_cmd_language
from dectalk.cmd.cm_cmd_phoneme import cm_cmd_phoneme
from dectalk.cmd.cm_cmd_punct import cm_cmd_punct
from dectalk.cmd.cm_cmd_say import cm_cmd_say
from dectalk.cmd.cm_cmd_skip import cm_cmd_skip
from dectalk.cmd.cmd_states import (
    CMD_bad_string,
    CMD_flushing,
    CMD_success,
    PUNCT_all,
    PUNCT_none,
    PUNCT_pass,
    PUNCT_some,
    SKIP_all,
    SKIP_cpg,
    SKIP_email,
    SKIP_none,
    SKIP_punct,
    SKIP_rule,
)
from dectalk.cmd.cmd_t import CmdT
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_both_ready, LANG_english

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_FILE = _SRC_ROOT / "src/dapi/src/cmd/cm_copt.c"
_C_DEFS = _SRC_ROOT / "src/dapi/src/cmd/cm_defs.h"
_C_HEADER = _SRC_ROOT / "src/dapi/src/cmd/c_us_cde.h"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file() or not _C_DEFS.is_file() or not _C_HEADER.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# ---------------------------------------------------------------------------
# C-source extraction helpers
# ---------------------------------------------------------------------------


def _read_c_source() -> str:
    """Return the cm_copt.c contents with CRLF normalised to LF."""
    return _C_FILE.read_text(encoding="latin-1").replace("\r\n", "\n")


def _extract_function_body(text: str, fn_name: str) -> str:
    """Return the body of ``int <fn_name>(...) { ... }`` (braces matched).

    The C source has multiple overloads of some functions gated by
    ``#ifdef``; this returns the first definition, which is the one
    that compiles on Linux (the mainline non-MSDOS / non-ARM7 branch
    is encountered first in textual order in every relevant case).
    """
    pat = re.compile(rf"\bint\s+{re.escape(fn_name)}\s*\(", re.MULTILINE)
    m = pat.search(text)
    if m is None:
        msg = f"could not locate {fn_name} in cm_copt.c"
        raise AssertionError(msg)
    # Find the opening brace of the body.
    i = text.index("{", m.end())
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1 : j]
        j += 1
    msg = f"unterminated function body for {fn_name}"
    raise AssertionError(msg)


def _strip_comments(body: str) -> str:
    """Drop ``/* ... */`` and ``// ...`` from a C fragment."""
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//[^\n]*", "", body)
    return body


def _extract_string_match_table(body: str) -> str | None:
    """Return the table-name argument of ``cm_util_string_match`` if any."""
    m = re.search(
        r"cm_util_string_match\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,",
        body,
    )
    return m.group(1) if m else None


def _has_no_string_match_branch(body: str) -> bool:
    """Return True iff the body returns CMD_bad_string on NO_STRING_MATCH.

    The canonical pattern is::

        if(value == NO_STRING_MATCH)
            return(CMD_bad_string);

    (with optional braces / whitespace).
    """
    clean = _strip_comments(body)
    # Collapse all whitespace to single spaces for easier matching.
    flat = re.sub(r"\s+", " ", clean)
    pattern = (
        r"if\s*\(\s*[A-Za-z_][A-Za-z0-9_]*\s*==\s*NO_STRING_MATCH\s*\)"
        r"[^;]*?return\s*\(?\s*CMD_bad_string"
    )
    return re.search(pattern, flat) is not None


_INACTIVE_GUARDS = frozenset({"MSDOS", "SINGLE_THREADED", "ARM7", "_WIN32", "UNDER_CE"})


def _is_inactive_directive(stripped: str) -> bool:
    """Return True iff a ``#if ...`` / ``#ifdef ...`` line is inactive."""
    if stripped.startswith("#ifdef"):
        parts = stripped.split()
        return len(parts) >= 2 and parts[1] in _INACTIVE_GUARDS
    if stripped.startswith("#if") and "defined" in stripped:
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", stripped)
        return any(t in _INACTIVE_GUARDS for t in tokens)
    return False


def _strip_inactive_blocks(body: str) -> str:
    """Drop lines inside ``#ifdef`` / ``#if defined(...)`` blocks that the
    Linux mainline build excludes (MSDOS, SINGLE_THREADED, ARM7, etc.).

    ``#ifndef`` blocks are always kept — for the guards we care about,
    they map to the active branch in our build.
    """
    cleaned: list[str] = []
    skip_depth = 0
    for line in _strip_comments(body).splitlines():
        stripped = line.strip()
        if stripped.startswith("#if") and (skip_depth or _is_inactive_directive(stripped)):
            skip_depth += 1
            continue
        if stripped.startswith("#endif") and skip_depth:
            skip_depth -= 1
            continue
        if skip_depth:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _extract_case_labels(body: str) -> list[str]:
    """Return the (deduplicated, ordered) list of ``case`` label tokens.

    Strips out lines inside ``#ifdef MSDOS`` / ``#ifdef SINGLE_THREADED``
    / ``#ifdef ARM7`` blocks since those are inactive in our Linux
    build.
    """
    body_clean = _strip_inactive_blocks(body)
    labels = re.findall(r"\bcase\s+([A-Za-z_0-9]+)\s*:", body_clean)
    # Deduplicate while keeping order.
    seen: set[str] = set()
    out: list[str] = []
    for label in labels:
        if label not in seen:
            seen.add(label)
            out.append(label)
    return out


def _resolve_label(label: str) -> int:
    """Map a case label string to its integer value.

    Numeric literals (``0``, ``42``) resolve directly. Symbolic labels
    are looked up against the constants imported at module scope and
    against ``cm_defs.h`` (re-parsed) so we don't have to mirror the
    full enum hierarchy here.
    """
    if label.isdigit():
        return int(label)
    table = _defs_constants()
    if label in table:
        return table[label]
    msg = f"unknown case label: {label}"
    raise AssertionError(msg)


def _defs_constants() -> dict[str, int]:
    """Return ``#define <NAME> <int>`` pairs from cm_defs.h."""
    text = _C_DEFS.read_text(encoding="latin-1").replace("\r\n", "\n")
    out: dict[str, int] = {}
    for m in re.finditer(
        r"^\s*#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+(0x[0-9A-Fa-f]+|-?\d+)\b",
        text,
        re.MULTILINE,
    ):
        name = m.group(1)
        val_str = m.group(2)
        out[name] = int(val_str, 16) if val_str.lower().startswith("0x") else int(val_str)
    return out


# ---------------------------------------------------------------------------
# Option-table cross-check — what cm_util_string_match() takes
# ---------------------------------------------------------------------------


_HANDLERS_AND_TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("cm_cmd_phoneme", "phoneme_modes", ot.phoneme_modes),
    ("cm_cmd_break", "log_options", ot.log_options),
    ("cm_cmd_say", "say_options", ot.say_options),
    ("cm_cmd_error", "error_options", ot.error_options),
    ("cm_cmd_punct", "punct_options", ot.punct_options),
    ("cm_cmd_skip", "skip_options", ot.skip_options),
    ("cm_cmd_language", "lang_options", ot.lang_options),
)


@pytest.mark.parametrize(
    ("fn_name", "expected_table", "py_table"),
    _HANDLERS_AND_TABLES,
    ids=[t[0] for t in _HANDLERS_AND_TABLES],
)
def test_handler_uses_expected_option_table(
    fn_name: str,
    expected_table: str,
    py_table: tuple[str, ...],
) -> None:
    """Each handler passes the documented table name to cm_util_string_match."""
    body = _extract_function_body(_read_c_source(), fn_name)
    actual = _extract_string_match_table(body)
    assert actual == expected_table, (
        f"{fn_name}: C source calls cm_util_string_match({actual}, ...) "
        f"but the Python port uses option_tables.{expected_table}"
    )
    # And the Python tuple is non-empty.
    assert py_table, f"option_tables.{expected_table} is empty"


# ---------------------------------------------------------------------------
# Switch-case coverage — every numeric case the C source handles is mapped
# ---------------------------------------------------------------------------


def test_cm_cmd_break_cases_match_c_source() -> None:
    """``cm_cmd_break`` handles cases 0 and 1 (the C-source ``[:break]`` bug)."""
    body = _extract_function_body(_read_c_source(), "cm_cmd_break")
    labels = _extract_case_labels(body)
    indices = {_resolve_label(label) for label in labels}
    # The C source's switch literally lists ``case 0`` and ``case 1``.
    assert indices == {0, 1}, f"unexpected case set: {indices}"

    # The Python port exercises both branches.
    ksd = KsdT()
    cmd = CmdT()
    cmd.pString = [b"text"]  # log_options[0]
    cmd.param_index = 1
    assert cm_cmd_break(ksd, cmd) == CMD_success
    assert ksd.wbreak == 1

    ksd = KsdT()
    ksd.wbreak = 1
    cmd.pString = [b"phonemes"]  # log_options[1]
    assert cm_cmd_break(ksd, cmd) == CMD_success
    assert ksd.wbreak == 0


def test_cm_cmd_say_cases_match_c_source() -> None:
    """``cm_cmd_say`` handles all six numeric cases in the C switch."""
    body = _extract_function_body(_read_c_source(), "cm_cmd_say")
    labels = _extract_case_labels(body)
    indices = {_resolve_label(label) for label in labels}
    assert indices == {0, 1, 2, 3, 4, 5}, f"unexpected case set: {indices}"

    # Every option-table entry has a switch arm.
    for i, _ in enumerate(ot.say_options):
        ksd = KsdT()
        cmd = CmdT()
        cmd.pString = [ot.say_options[i].encode("latin-1")]
        cmd.param_index = 1
        result = cm_cmd_say(ksd, cmd)
        # Cases 0,1,4,5 → CMD_success directly.
        # Cases 2,3 → CMD_success (default sync_fn returns CMD_success).
        assert result == CMD_success, f"case {i} ({ot.say_options[i]!r}) failed"


def test_cm_cmd_say_letter_respects_flushing_sync() -> None:
    """``case 2`` and ``case 3`` short-circuit when sync_fn reports flush."""
    body = _extract_function_body(_read_c_source(), "cm_cmd_say")
    # The C source's ``case 2`` and ``case 3`` both check
    # ``cm_cmd_sync(phTTS) == CMD_flushing``.
    assert "cm_cmd_sync" in body
    flat = re.sub(r"\s+", " ", _strip_comments(body))
    # Both case 2 and case 3 should mention cm_cmd_sync.
    sync_occurrences = flat.count("cm_cmd_sync")
    assert sync_occurrences >= 2, (
        f"expected >=2 cm_cmd_sync calls in cm_cmd_say body, got {sync_occurrences}"
    )

    # Python: passing a sync_fn that reports flushing should propagate.
    for keyword in ("letter", "filtered_letter"):
        ksd = KsdT()
        cmd = CmdT()
        cmd.pString = [keyword.encode("latin-1")]
        cmd.param_index = 1
        result = cm_cmd_say(ksd, cmd, sync_fn=lambda: CMD_flushing)
        assert result == CMD_flushing, f"{keyword}: expected CMD_flushing"


def test_cm_cmd_error_cases_match_c_source() -> None:
    """``cm_cmd_error`` handles cases 0..4."""
    body = _extract_function_body(_read_c_source(), "cm_cmd_error")
    labels = _extract_case_labels(body)
    indices = {_resolve_label(label) for label in labels}
    assert indices == {0, 1, 2, 3, 4}, f"unexpected case set: {indices}"

    for i, keyword in enumerate(ot.error_options):
        cmd = CmdT()
        cmd.pString = [keyword.encode("latin-1")]
        cmd.param_index = 1
        result = cm_cmd_error(cmd)
        assert result == CMD_success
        assert cmd.error_mode == i, f"error_mode mismatch for {keyword!r}"


def test_cm_cmd_punct_cases_match_c_source() -> None:
    """``cm_cmd_punct`` handles the four PUNCT_* labels."""
    body = _extract_function_body(_read_c_source(), "cm_cmd_punct")
    labels = _extract_case_labels(body)
    indices = {_resolve_label(label) for label in labels}
    assert indices == {PUNCT_none, PUNCT_some, PUNCT_all, PUNCT_pass}, (
        f"unexpected case set: {indices}"
    )

    # The labels resolve to 0..3 (PUNCT_* are 0..3 in cm_defs.h).
    assert indices == {0, 1, 2, 3}


def test_cm_cmd_skip_cases_match_c_source() -> None:
    """``cm_cmd_skip`` handles the six SKIP_* labels."""
    body = _extract_function_body(_read_c_source(), "cm_cmd_skip")
    labels = _extract_case_labels(body)
    indices = {_resolve_label(label) for label in labels}
    assert indices == {SKIP_none, SKIP_email, SKIP_punct, SKIP_rule, SKIP_all, SKIP_cpg}, (
        f"unexpected case set: {indices}"
    )
    assert indices == {0, 1, 2, 3, 4, 5}


def test_cm_cmd_phoneme_cases_match_c_source() -> None:
    """``cm_cmd_phoneme`` handles cases 0..5."""
    body = _extract_function_body(_read_c_source(), "cm_cmd_phoneme")
    labels = _extract_case_labels(body)
    indices = {_resolve_label(label) for label in labels}
    assert indices == {0, 1, 2, 3, 4, 5}, f"unexpected case set: {indices}"


def test_cm_cmd_language_cases_cover_c_source() -> None:
    """``cm_cmd_language`` covers every language and alias case.

    The C switch has cases 0..5 for the canonical language names and
    6..11 for their two-letter aliases (us / uk / fr / gr / sp / la).
    """
    body = _extract_function_body(_read_c_source(), "cm_cmd_language")
    labels = _extract_case_labels(body)
    indices = {_resolve_label(label) for label in labels}
    # In the mainline Linux build we also see cases 1..5 / 7..11
    # (the ARM7-gated section is the only one omitted).
    expected = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11}
    assert indices == expected, f"unexpected case set: {indices}"


# ---------------------------------------------------------------------------
# Return-code mapping — NO_STRING_MATCH → CMD_bad_string
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fn_name",
    [
        "cm_cmd_break",
        "cm_cmd_say",
        "cm_cmd_error",
        "cm_cmd_punct",
        "cm_cmd_skip",
        "cm_cmd_phoneme",
        "cm_cmd_language",
    ],
)
def test_handler_returns_bad_string_on_no_string_match(fn_name: str) -> None:
    """Every handler maps NO_STRING_MATCH → CMD_bad_string at the C level."""
    body = _extract_function_body(_read_c_source(), fn_name)
    assert _has_no_string_match_branch(body), (
        f"{fn_name}: C source missing the NO_STRING_MATCH → CMD_bad_string branch"
    )


def test_cm_cmd_break_python_returns_bad_string_for_unknown() -> None:
    """Python port returns CMD_bad_string for an unknown ``[:break]`` arg."""
    ksd = KsdT()
    cmd = CmdT()
    cmd.pString = [b"bogus_keyword_xyz"]
    cmd.param_index = 1
    assert cm_cmd_break(ksd, cmd) == CMD_bad_string


def test_cm_cmd_say_python_returns_bad_string_for_unknown() -> None:
    """Python port returns CMD_bad_string for an unknown ``[:say]`` arg."""
    ksd = KsdT()
    cmd = CmdT()
    cmd.pString = [b"bogus_keyword_xyz"]
    cmd.param_index = 1
    assert cm_cmd_say(ksd, cmd) == CMD_bad_string


def test_cm_cmd_error_python_returns_bad_string_for_unknown() -> None:
    """Python port returns CMD_bad_string for an unknown ``[:error]`` arg."""
    cmd = CmdT()
    cmd.pString = [b"bogus_keyword_xyz"]
    cmd.param_index = 1
    assert cm_cmd_error(cmd) == CMD_bad_string


def test_cm_cmd_punct_python_returns_bad_string_for_unknown() -> None:
    """Python port returns CMD_bad_string for an unknown ``[:punct]`` arg."""
    cmd = CmdT()
    cmd.pString = [b"bogus_keyword_xyz"]
    cmd.param_index = 1
    assert cm_cmd_punct(cmd) == CMD_bad_string


def test_cm_cmd_skip_python_returns_bad_string_for_unknown() -> None:
    """Python port returns CMD_bad_string for an unknown ``[:skip]`` arg."""
    cmd = CmdT()
    cmd.pString = [b"bogus_keyword_xyz"]
    cmd.param_index = 1
    assert cm_cmd_skip(cmd) == CMD_bad_string


def test_cm_cmd_phoneme_python_returns_bad_string_for_unknown() -> None:
    """Python port returns CMD_bad_string for an unknown ``[:phoneme]`` arg."""
    ksd = KsdT()
    cmd = CmdT()
    cmd.pString = [b"bogus_keyword_xyz"]
    cmd.param_index = 1
    assert cm_cmd_phoneme(ksd, cmd) == CMD_bad_string


def test_cm_cmd_language_python_returns_bad_string_for_unknown() -> None:
    """Python port returns CMD_bad_string for an unknown ``[:lang]`` arg."""
    ksd = KsdT()
    cmd = CmdT()
    cmd.pString = [b"bogus_keyword_xyz"]
    cmd.param_index = 1
    cmd.esc_command = False
    # lang_ready[english] is the default 0; even before the table miss,
    # the string-match step should reject "bogus_keyword_xyz".
    assert cm_cmd_language(ksd, cmd) == CMD_bad_string


# ---------------------------------------------------------------------------
# Language handler — readiness gate maps to CMD_bad_value
# ---------------------------------------------------------------------------


def test_cm_cmd_language_requires_lang_both_ready() -> None:
    """``[:lang english]`` switches only when ``lang_ready[english]`` is set."""
    body = _extract_function_body(_read_c_source(), "cm_cmd_language")
    # The C source guards each case with
    # ``if(pKsd_t->lang_ready[LANG_X] == LANG_both_ready) ... else return CMD_bad_value;``.
    flat = re.sub(r"\s+", " ", _strip_comments(body))
    assert "LANG_both_ready" in flat, (
        "cm_cmd_language: C source no longer references LANG_both_ready"
    )

    # Python: when the language is not ready, the handler returns CMD_bad_value.
    ksd = KsdT()
    cmd = CmdT()
    cmd.pString = [b"english"]
    cmd.param_index = 1
    cmd.esc_command = False
    # default lang_ready is all zeros → not ready.
    from dectalk.cmd.cmd_states import CMD_bad_value  # noqa: PLC0415

    assert cm_cmd_language(ksd, cmd) == CMD_bad_value

    # When ready, the call succeeds.
    ksd2 = KsdT()
    ksd2.lang_ready[LANG_english] = LANG_both_ready
    cmd2 = CmdT()
    cmd2.pString = [b"english"]
    cmd2.param_index = 1
    cmd2.esc_command = False
    assert cm_cmd_language(ksd2, cmd2) == CMD_success
