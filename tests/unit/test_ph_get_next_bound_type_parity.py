"""C-source parity test for ``get_next_bound_type`` against ph_sort2.c.

Re-parses the C function body from the original DECtalk source at test
time, verifies the structural invariants (the forward loop bounds, the
``[SBOUND, EXCLAIM]`` boundary-range check, the ``bounftab`` lookup,
the ``FSYLL`` early-exit), and asserts the Python port behaves
identically over a small representative set of symbol streams.

Skips cleanly when ``DECTALK_SRC`` env / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import COMMA, EXCLAIM, SBOUND, WBOUND, USPhoneme
from dectalk.ph.boundary_table import bounftab
from dectalk.ph.dph_t import DphT
from dectalk.ph.get_next_bound_type import get_next_bound_type

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_sort2.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_ph_sort2_c() -> str:
    """Read ph_sort2.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_get_next_bound_type_body() -> str:
    """Return the C ``get_next_bound_type`` function body with comments stripped."""
    text = _read_ph_sort2_c()
    match = re.search(
        r"static\s+void\s+get_next_bound_type\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "get_next_bound_type() not found in ph_sort2.c"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


def test_get_next_bound_type_signature_matches_c() -> None:
    """The C signature is ``static void get_next_bound_type(LPTTS_HANDLE_T, short)``."""
    text = _read_ph_sort2_c()
    sig = re.search(
        r"static\s+void\s+get_next_bound_type\s*\(\s*"
        r"LPTTS_HANDLE_T\s+\w+\s*,\s*short\s+\w+\s*\)",
        text,
    )
    assert sig is not None, "expected `static void get_next_bound_type(LPTTS_HANDLE_T, short)`"


def test_get_next_bound_type_forward_loop_starts_at_msym_plus_one() -> None:
    """The forward loop is ``for (m = msym + 1; m < pDph_t->nsymbtot; m++)``."""
    body = _extract_get_next_bound_type_body()
    assert re.search(
        r"for\s*\(\s*m\s*=\s*msym\s*\+\s*1\s*;\s*"
        r"m\s*<\s*pDph_t->nsymbtot\s*;\s*m\+\+\s*\)",
        body,
    ), "expected `for (m = msym + 1; m < pDph_t->nsymbtot; m++)` loop"


def test_get_next_bound_type_uses_pvalue_range_check() -> None:
    """The boundary range check uses ``& PVALUE`` masked against ``[SBOUND, EXCLAIM]``."""
    body = _extract_get_next_bound_type_body()
    assert re.search(
        r"pDph_t->symbols\s*\[\s*m\s*\]\s*&\s*PVALUE\s*\)\s*>=\s*SBOUND",
        body,
    ), "expected `(symbols[m] & PVALUE) >= SBOUND` lower bound"
    assert re.search(
        r"pDph_t->symbols\s*\[\s*m\s*\]\s*&\s*PVALUE\s*\)\s*<=\s*EXCLAIM",
        body,
    ), "expected `(symbols[m] & PVALUE) <= EXCLAIM` upper bound"


def test_get_next_bound_type_calls_add_feature_with_bounftab() -> None:
    """The body calls ``add_feature(pDph_t, bounftab[symbols[m] - SBOUND], CURRPHONE)``."""
    body = _extract_get_next_bound_type_body()
    assert re.search(
        r"add_feature\s*\(\s*pDph_t\s*,\s*"
        r"bounftab\s*\[\s*pDph_t->symbols\s*\[\s*m\s*\]\s*-\s*SBOUND\s*\]\s*,",
        body,
    ), "expected `add_feature(pDph_t, bounftab[symbols[m] - SBOUND], ...)`"
    assert "CURRPHONE" in body, "expected the call to use the CURRPHONE macro"


def test_get_next_bound_type_aborts_on_fsyll_phone() -> None:
    """A vowel (``FSYLL``) before any boundary causes a silent ``return``."""
    body = _extract_get_next_bound_type_body()
    assert re.search(
        r"phone_feature\s*\(\s*pDph_t\s*,\s*pDph_t->symbols\s*\[\s*m\s*\]\s*\)\s*\)\s*"
        r"&\s*FSYLL\s*\)\s*IS_PLUS",
        body,
    ), "expected `(phone_feature(...) & FSYLL) IS_PLUS` syllable check"


# ---------------------------------------------------------------------------
# Behavioural parity tests.
# ---------------------------------------------------------------------------


def test_finds_immediate_word_boundary_writes_feature() -> None:
    """A boundary right after msym tags the current output phoneme."""
    state = DphT()
    # Input stream: [some consonant at 0, WBOUND at 1].
    state.symbols = [int(USPhoneme.T), WBOUND]
    state.nsymbtot = 2
    state.nphonetot = 1  # CURRPHONE = 0.
    state.sentstruc = [0]
    get_next_bound_type(state, 0)
    # WBOUND - SBOUND = 111 - 108 = 3 → bounftab[3] = FWBNEXT.
    assert state.sentstruc[0] == bounftab[WBOUND - SBOUND]


def test_finds_comma_writes_correct_flag() -> None:
    """A COMMA boundary writes the FCBNEXT flag via bounftab."""
    state = DphT()
    state.symbols = [int(USPhoneme.T), COMMA]
    state.nsymbtot = 2
    state.nphonetot = 1
    state.sentstruc = [0]
    get_next_bound_type(state, 0)
    # COMMA - SBOUND = 115 - 108 = 7 → FCBNEXT.
    assert state.sentstruc[0] == bounftab[COMMA - SBOUND]


def test_aborts_on_syllabic_vowel_before_boundary() -> None:
    """A syllabic vowel before a boundary silently aborts (no feature write)."""
    state = DphT()
    # T (consonant), IY (syllabic), WBOUND.
    state.symbols = [int(USPhoneme.T), int(USPhoneme.IY), WBOUND]
    state.nsymbtot = 3
    state.nphonetot = 1
    state.sentstruc = [0]
    get_next_bound_type(state, 0)
    # Should bail out at IY without writing.
    assert state.sentstruc[0] == 0


def test_skips_non_boundary_non_syllabic() -> None:
    """Non-syllabic consonants between msym and the boundary are skipped."""
    state = DphT()
    # T, K, R, EXCLAIM — all consonants, then EXCLAIM.
    state.symbols = [int(USPhoneme.T), int(USPhoneme.K), int(USPhoneme.R), EXCLAIM]
    state.nsymbtot = 4
    state.nphonetot = 1
    state.sentstruc = [0]
    get_next_bound_type(state, 0)
    # EXCLAIM - SBOUND = 118 - 108 = 10 → bounftab[10] = FEXCLNEXT.
    assert state.sentstruc[0] == bounftab[EXCLAIM - SBOUND]


def test_runs_off_end_no_op() -> None:
    """If no boundary or syllabic is found, nothing is written."""
    state = DphT()
    state.symbols = [int(USPhoneme.T), int(USPhoneme.K)]
    state.nsymbtot = 2
    state.nphonetot = 1
    state.sentstruc = [0]
    get_next_bound_type(state, 0)
    assert state.sentstruc[0] == 0


def test_msym_at_end_no_op() -> None:
    """An msym at or past the last index does nothing (empty loop)."""
    state = DphT()
    state.symbols = [int(USPhoneme.T), WBOUND]
    state.nsymbtot = 2
    state.nphonetot = 1
    state.sentstruc = [0]
    get_next_bound_type(state, 2)
    assert state.sentstruc[0] == 0


def test_or_accumulates_on_existing_sentstruc() -> None:
    """The feature OR's onto the current ``sentstruc[]`` value."""
    state = DphT()
    state.symbols = [int(USPhoneme.T), WBOUND]
    state.nsymbtot = 2
    state.nphonetot = 1
    state.sentstruc = [0o4]  # Some pre-existing flag.
    get_next_bound_type(state, 0)
    # OR'd, not overwritten.
    assert state.sentstruc[0] == 0o4 | bounftab[WBOUND - SBOUND]
