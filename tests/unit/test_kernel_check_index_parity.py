"""C-source parity test for ``check_index`` against kernel/services.c.

Re-parses the ``check_index`` function body and extracts its
``switch (data[1])`` → ``buf[0]`` subtype mapping, plus its halt /
flush threshold (``data[5] > which_phone``). Asserts the Python port
preserves both.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.cmd_codes import (
    INDEX,
    INDEX_BOOKMARK,
    INDEX_NOISE,
    INDEX_REPLY,
    INDEX_SENTENCE,
    INDEX_START,
    INDEX_STOP,
    INDEX_VOLUME,
    INDEX_WORDPOS,
)
from dectalk.kernel.check_index import check_index
from dectalk.kernel.spc_codes import (
    SPC_subtype_bookmark,
    SPC_subtype_noise,
    SPC_subtype_sentence,
    SPC_subtype_start,
    SPC_subtype_stop,
    SPC_subtype_volume,
    SPC_subtype_wordpos,
    SPC_type_index,
)
from dectalk.kernel.spc_packet import SpcPacket

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/kernel/services.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_services_c() -> str:
    """Read services.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_check_index_body() -> str:
    """Return the contents of the C ``check_index`` *definition* body."""
    text = _read_services_c()
    # The forward declaration is `void check_index( ... );` (semicolon),
    # the definition has `{`. Match the definition only.
    match = re.search(
        r"void\s+check_index\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "check_index() definition not found"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


def _parse_switch_to_buf0(body: str) -> dict[str, list[str]]:
    """Parse the ``switch(data[1])`` cases to ``buf[0]`` token lists.

    Returns ``{case_label: [subtype_tokens]}`` — e.g. ``"INDEX_BOOKMARK"``
    maps to ``["SPC_type_index", "SPC_subtype_bookmark"]`` (the
    OR-list right of ``buf[0] =``).
    """
    out: dict[str, list[str]] = {}
    pending_cases: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        case_m = re.match(r"case\s+(\w+)\s*:\s*$", stripped)
        if case_m:
            pending_cases.append(case_m.group(1))
            continue
        buf_m = re.match(r"buf\[0\]\s*=\s*([^;]+);", stripped)
        if buf_m and pending_cases:
            tokens = re.findall(r"SPC_\w+", buf_m.group(1))
            for case in pending_cases:
                out[case] = tokens
            pending_cases = []
            continue
        if stripped.startswith("break"):
            pending_cases = []
    return out


def test_check_index_switch_covers_all_index_codes() -> None:
    """The C ``switch (data[1])`` has the documented 9 case labels."""
    body = _extract_check_index_body()
    cases = _parse_switch_to_buf0(body)
    expected = {
        "INDEX",
        "INDEX_REPLY",
        "INDEX_BOOKMARK",
        "INDEX_WORDPOS",
        "INDEX_START",
        "INDEX_STOP",
        "INDEX_SENTENCE",
        "INDEX_VOLUME",
        "INDEX_NOISE",
    }
    assert set(cases.keys()) == expected


def test_check_index_threshold_is_data5_strict_gt() -> None:
    """The break test is ``spc_pkt->data[5] > which_phone`` (strict)."""
    body = _extract_check_index_body()
    assert re.search(
        r"if\s*\(\s*spc_pkt->data\[\s*5\s*\]\s*>\s*which_phone\s*\)",
        body,
    ), "expected `if (spc_pkt->data[5] > which_phone)` halt-check"
    # And it's followed by `break;`
    halt = re.search(
        r"if\s*\(\s*spc_pkt->data\[\s*5\s*\]\s*>\s*which_phone\s*\)\s*break\s*;",
        body,
    )
    assert halt is not None


def test_check_index_buf1_is_data2_buf2_is_data3() -> None:
    """``buf[1] = data[2]; buf[2] = data[3];`` per the C source."""
    body = _extract_check_index_body()
    assert re.search(
        r"buf\[1\]\s*=\s*spc_pkt->data\[\s*2\s*\]\s*;",
        body,
    )
    assert re.search(
        r"buf\[2\]\s*=\s*spc_pkt->data\[\s*3\s*\]\s*;",
        body,
    )


def test_check_index_python_subtype_map_matches_c() -> None:
    """Every case label in the C switch produces the Python port's buf[0]."""
    body = _extract_check_index_body()
    cases = _parse_switch_to_buf0(body)

    py_label_to_code = {
        "INDEX": INDEX,
        "INDEX_REPLY": INDEX_REPLY,
        "INDEX_BOOKMARK": INDEX_BOOKMARK,
        "INDEX_WORDPOS": INDEX_WORDPOS,
        "INDEX_START": INDEX_START,
        "INDEX_STOP": INDEX_STOP,
        "INDEX_SENTENCE": INDEX_SENTENCE,
        "INDEX_VOLUME": INDEX_VOLUME,
        "INDEX_NOISE": INDEX_NOISE,
    }
    py_token_to_value = {
        "SPC_type_index": SPC_type_index,
        "SPC_subtype_bookmark": SPC_subtype_bookmark,
        "SPC_subtype_wordpos": SPC_subtype_wordpos,
        "SPC_subtype_start": SPC_subtype_start,
        "SPC_subtype_stop": SPC_subtype_stop,
        "SPC_subtype_sentence": SPC_subtype_sentence,
        "SPC_subtype_volume": SPC_subtype_volume,
        "SPC_subtype_noise": SPC_subtype_noise,
    }

    for case_label, tokens in cases.items():
        # Compute the OR of tokens to derive expected buf[0].
        expected_buf0 = 0
        for tok in tokens:
            expected_buf0 |= py_token_to_value[tok]

        # Build a single-packet chain triggering this case.
        pkt = SpcPacket()
        while len(pkt.data) < 6:
            pkt.data.append(0)
        pkt.data[1] = py_label_to_code[case_label]
        pkt.data[2] = 7  # sentinel
        pkt.data[3] = 9  # sentinel
        pkt.data[5] = 0  # ensure data[5] <= which_phone

        calls: list[tuple[int, int, int]] = []
        new_head = check_index(pkt, which_phone=10, emit=calls.append)
        assert new_head is None
        assert len(calls) == 1, f"case {case_label}: expected 1 emit, got {len(calls)}"
        got_buf0, got_buf1, got_buf2 = calls[0]
        assert got_buf0 == expected_buf0, (
            f"case {case_label}: buf[0]={got_buf0}, expected {expected_buf0}"
        )
        # buf[1]=data[2], buf[2]=data[3]
        assert got_buf1 == 7
        assert got_buf2 == 9


def test_check_index_python_threshold_matches_c() -> None:
    """A packet whose ``data[5] > which_phone`` stops the walk (C ``break``)."""
    pkt = SpcPacket()
    while len(pkt.data) < 6:
        pkt.data.append(0)
    pkt.data[1] = INDEX
    pkt.data[5] = 11  # > which_phone=10

    calls: list[tuple[int, int, int]] = []
    new_head = check_index(pkt, which_phone=10, emit=calls.append)
    assert new_head is pkt  # untouched
    assert calls == []


def test_check_index_python_data5_equal_threshold_flushes() -> None:
    """``data[5] == which_phone`` is NOT > so the packet IS flushed."""
    pkt = SpcPacket()
    while len(pkt.data) < 6:
        pkt.data.append(0)
    pkt.data[1] = INDEX
    pkt.data[5] = 10  # == which_phone=10

    calls: list[tuple[int, int, int]] = []
    new_head = check_index(pkt, which_phone=10, emit=calls.append)
    assert new_head is None
    assert len(calls) == 1


def test_check_index_python_signature_matches_c() -> None:
    """The C signature is ``check_index(LPTTS_HANDLE_T phTTS, unsigned int which_phone)``."""
    text = _read_services_c()
    sig = re.search(
        r"void\s+check_index\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*,\s*"
        r"unsigned\s+int\s+which_phone\s*\)\s*\{",
        text,
    )
    assert sig is not None
