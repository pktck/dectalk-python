"""C-source parity test for ``cm_util_say_string`` against cm_util.c.

Re-parses the Linux/non-MSDOS branch of ``cm_util_say_string``
and asserts:

- Signature matches ``void cm_util_say_string(PKSD_T, unsigned char *, short)``.
- The per-character loop reads ``instr[i] != '\\0'``.
- The encoded packet is ``(PFASCII << PSFONT) + instr[i]``.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_util_say_string import cm_util_say_string, cm_util_say_string_iter
from dectalk.include.cmd_codes import PFASCII, PSFONT

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_util.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_cm_util_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_linux_body() -> str:
    """Return the Linux/non-MSDOS branch of cm_util_say_string."""
    text = _read_cm_util_c()
    # The Linux branch sits inside an ``#else`` of an outer
    # ``#ifdef MSDOS``. Anchor on the signature that appears after the
    # ``#else``.
    match = re.search(
        r"#else\s*\n"
        r"void\s+cm_util_say_string\s*\(\s*PKSD_T\s+\w+\s*,\s*unsigned\s+char\s+"
        r"_far\s*\*\s*\w+\s*,\s*short\s+\w+\s*\)\s*\n\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "cm_util_say_string Linux body not found in cm_util.c"
    return match.group(1)


def test_per_char_loop_uses_null_sentinel() -> None:
    """The C loop terminates on the trailing NUL byte."""
    body = _extract_linux_body()
    assert re.search(r"for\s*\(\s*i\s*=\s*0\s*;\s*instr\[\s*i\s*\]\s*!=\s*'\\0'", body)


def test_packet_encoding_is_pfascii_psfont() -> None:
    """The packet is ``(PFASCII << PSFONT) + instr[i]``."""
    body = _extract_linux_body()
    assert re.search(
        r"pipe_value\[\s*0\s*\]\s*=\s*\(\s*PFASCII\s*<<\s*PSFONT\s*\)\s*\+\s*instr\[\s*i\s*\]",
        body,
    )


def test_python_encodes_each_byte_independently() -> None:
    """The Python port returns one packet per input byte."""
    packets = cm_util_say_string(b"abc")
    base = PFASCII << PSFONT
    assert packets == [base + ord("a"), base + ord("b"), base + ord("c")]


def test_python_stops_at_null_sentinel() -> None:
    """A NUL byte inside the input terminates encoding."""
    packets = cm_util_say_string(b"hi\x00there")
    base = PFASCII << PSFONT
    assert packets == [base + ord("h"), base + ord("i")]


def test_python_invokes_sink_per_packet() -> None:
    """``lts_sink`` is called once per encoded packet, in order."""
    captured: list[int] = []
    packets = cm_util_say_string(b"ABC", lts_sink=captured.append)
    base = PFASCII << PSFONT
    assert captured == packets == [base + ord("A"), base + ord("B"), base + ord("C")]


def test_python_handles_str_input() -> None:
    """``str`` inputs are UTF-8 encoded for parity with C's bytes input."""
    packets = cm_util_say_string("abc")
    base = PFASCII << PSFONT
    assert packets == [base + ord("a"), base + ord("b"), base + ord("c")]


def test_python_empty_input_returns_empty_list() -> None:
    """No characters in -> no packets out."""
    assert cm_util_say_string(b"") == []
    assert cm_util_say_string(b"\x00") == []


def test_python_iter_matches_eager_form() -> None:
    """The lazy ``_iter`` variant produces the same packets."""
    eager = cm_util_say_string(b"hello")
    lazy = list(cm_util_say_string_iter(b"hello"))
    assert eager == lazy
