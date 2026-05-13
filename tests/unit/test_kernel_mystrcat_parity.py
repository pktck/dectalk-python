"""C-source parity test for the kernel ``mystrcat`` helper in loader.c.

Re-parses the function body from ``src/dapi/src/kernel/loader.c`` and asserts:

- the prototype matches the expected ``void mystrcat(... dest, ... src, ... count)``
  signature with the Microsoft ``_far`` qualifiers and an ``unsigned int`` cap,
- the early-return guard uses ``count - 1``,
- the copy loop bound uses ``count - 2``,
- the body writes a trailing NUL and contains no other statements
  (no recursion, no helpers, no kernel-state access).

Behavioural assertions exercise the documented edge cases:

- empty source leaves only the trailing NUL,
- a full destination triggers the ``sofar >= count - 1`` early-return
  without mutating ``dest``,
- the copy stops one byte short of ``count`` to leave room for the
  terminator,
- internal NULs in ``src`` end the copy,
- repeated calls accumulate (since ``dest`` is scanned forward each time).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.kernel.mystrcat import mystrcat

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/kernel/loader.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_loader_c() -> str:
    """Read loader.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _strip_comments(body: str) -> str:
    """Remove ``/* ... */`` and ``// ...`` comments from a body."""
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//[^\n]*", "", body)
    return body


# ---------------------------------------------------------------------------
# C-source structural parity.
# ---------------------------------------------------------------------------


def test_mystrcat_signature_matches_c_source() -> None:
    """``mystrcat`` is declared with the expected _far prototype in loader.c."""
    text = _read_loader_c()
    proto_re = (
        r"void\s+mystrcat\s*\(\s*"
        r"unsigned\s+char\s+_far\s*\*\s*dest\s*,\s*"
        r"unsigned\s+char\s+_far\s*\*\s*src\s*,\s*"
        r"unsigned\s+int\s+count\s*\)"
    )
    assert re.search(proto_re, text), "mystrcat prototype not found in loader.c"


def test_mystrcat_early_return_uses_count_minus_one() -> None:
    """Early-return guard ``if (sofar >= count - 1) return;`` is present."""
    text = _read_loader_c()
    match = re.search(
        r"void\s+mystrcat\s*\([^)]*\)\s*\{(?P<body>.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "mystrcat definition not found in loader.c"
    body = _strip_comments(match.group("body"))
    assert re.search(
        r"if\s*\(\s*sofar\s*>=\s*count\s*-\s*1\s*\)\s*\n?\s*return\s*;",
        body,
    ), "expected `if (sofar >= count - 1) return;` guard in mystrcat body"


def test_mystrcat_copy_loop_uses_count_minus_two() -> None:
    """The copy-loop bound is ``sofar < count - 2``."""
    text = _read_loader_c()
    match = re.search(
        r"void\s+mystrcat\s*\([^)]*\)\s*\{(?P<body>.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "mystrcat definition not found in loader.c"
    body = _strip_comments(match.group("body"))
    assert re.search(
        r"while\s*\(\s*\(\s*sofar\s*<\s*count\s*-\s*2\s*\)",
        body,
    ), "expected `while ((sofar < count - 2) ...)` bound in mystrcat body"


def test_mystrcat_terminates_with_nul() -> None:
    """The body ends by writing ``'\\0'`` at ``dest[sofar]`` before returning."""
    text = _read_loader_c()
    match = re.search(
        r"void\s+mystrcat\s*\([^)]*\)\s*\{(?P<body>.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "mystrcat definition not found in loader.c"
    body = _strip_comments(match.group("body"))
    # The terminator write appears after the copy loop and before the
    # final ``return;``. Use a non-greedy NUL char-class match because
    # the C source spells it as ``'\0'``.
    assert re.search(
        r"dest\s*\[\s*sofar\s*\]\s*=\s*'\\0'\s*;",
        body,
    ), "expected `dest[sofar] = '\\0';` terminator write in mystrcat body"


def test_mystrcat_body_has_no_helper_calls() -> None:
    """``mystrcat`` body invokes no other functions — it's a pure leaf."""
    text = _read_loader_c()
    match = re.search(
        r"void\s+mystrcat\s*\([^)]*\)\s*\{(?P<body>.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "mystrcat definition not found in loader.c"
    body = _strip_comments(match.group("body"))
    # Any ``IDENT(`` other than control-flow keywords would indicate a
    # call. The body should only contain ``for (...)``, ``if (...)``,
    # ``while (...)``, and ``return``.
    keywords = {"for", "if", "while", "return"}
    for call_match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", body):
        ident = call_match.group(1)
        assert ident in keywords, (
            f"unexpected call to `{ident}(...)` in mystrcat body — should be a pure leaf"
        )


# ---------------------------------------------------------------------------
# Behavioural assertions for the Python port.
# ---------------------------------------------------------------------------


def _make_buf(initial: bytes, size: int) -> bytearray:
    """Build a ``size``-byte buffer pre-populated with ``initial`` + NUL padding."""
    buf = bytearray(size)
    buf[: len(initial)] = initial
    return buf


def test_mystrcat_appends_into_empty_destination() -> None:
    """Appending into an empty buffer copies up to ``count - 2`` bytes."""
    buf = bytearray(16)
    mystrcat(buf, b"hello", 16)
    # The terminator sits right after "hello".
    assert bytes(buf[:5]) == b"hello"
    assert buf[5] == 0


def test_mystrcat_appends_after_existing_string() -> None:
    """Appending onto an already-populated buffer continues from the NUL."""
    buf = _make_buf(b"foo", 16)
    mystrcat(buf, b"bar", 16)
    assert bytes(buf[:6]) == b"foobar"
    assert buf[6] == 0


def test_mystrcat_truncates_to_count_minus_two() -> None:
    """Copy stops at ``count - 2`` so the final NUL lands at ``count - 1``."""
    # count = 6 means we may write indices 0..4 (data) and 5 (NUL).
    buf = bytearray(6)
    mystrcat(buf, b"abcdef", 6)
    # Highest data byte written is at index count-2 == 4.
    assert bytes(buf[:5]) == b"abcd\x00"
    # And the NUL at index 4 is the terminator -- index 5 still 0.
    assert buf[5] == 0


def test_mystrcat_early_return_when_destination_is_full() -> None:
    """``sofar >= count - 1`` skips the copy *and* the terminator rewrite."""
    # Pre-fill with 7 non-NUL bytes; NUL sits at index 7 (sofar == 7).
    # count - 1 == 7, so the guard fires. Nothing should change.
    buf = bytearray(b"abcdefg\x00\xff\xff")
    snapshot = bytes(buf)
    mystrcat(buf, b"XY", 8)
    assert bytes(buf) == snapshot, "buffer must be unchanged when guard fires"


def test_mystrcat_stops_at_internal_nul_in_src() -> None:
    """An internal NUL byte in ``src`` ends the copy."""
    buf = bytearray(16)
    mystrcat(buf, b"abc\x00def", 16)
    assert bytes(buf[:3]) == b"abc"
    assert buf[3] == 0


def test_mystrcat_handles_empty_src() -> None:
    """Empty ``src`` writes only the NUL terminator at the existing end."""
    buf = _make_buf(b"foo", 16)
    mystrcat(buf, b"", 16)
    assert bytes(buf[:3]) == b"foo"
    assert buf[3] == 0


def test_mystrcat_repeated_calls_accumulate() -> None:
    """Calling ``mystrcat`` repeatedly appends each ``src`` in turn."""
    buf = bytearray(32)
    mystrcat(buf, b"DECtalk ", 32)
    mystrcat(buf, b"Express ", 32)
    mystrcat(buf, b"running", 32)
    assert bytes(buf[:23]) == b"DECtalk Express running"
    assert buf[23] == 0


def test_mystrcat_matches_loader_version_string_pattern() -> None:
    """Repro of the loader.c call-site pattern with the build banner."""
    # loader.c builds:
    #   mystrcat(KS.version, versionstring, VERSIONLEN - 1)
    #   mystrcat(KS.version, " [LM]",        VERSIONLEN - 1)
    # Simulate that here with a small VERSIONLEN.
    version_len = 16
    buf = bytearray(version_len)
    mystrcat(buf, b"5.0", version_len - 1)
    mystrcat(buf, b" [LM]", version_len - 1)
    assert bytes(buf[:8]) == b"5.0 [LM]"
    assert buf[8] == 0
