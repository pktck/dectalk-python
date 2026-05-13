"""C-source parity test for ``init_med_final`` against ph_sort2.c.

Re-parses the C function body from the original DECtalk source at test
time, verifies the structural invariants (the backward output-stream
walk, the forward input-stream walk, the ``FBOUNDARY`` early-exit, the
sylltype state transitions, the ``add_feature`` call), and asserts the
Python port behaves identically over a small representative set of
streams.

Skips cleanly when ``DECTALK_SRC`` env / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import EXCLAIM, WBOUND, USPhoneme
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import FFINALSYL, FFIRSTSYL, FMEDIALSYL, FWBNEXT
from dectalk.ph.init_med_final import init_med_final

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_sort2.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_ph_sort2_c() -> str:
    """Read ph_sort2.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_init_med_final_body() -> str:
    """Return the C ``init_med_final`` function body with comments stripped."""
    text = _read_ph_sort2_c()
    match = re.search(
        r"static\s+void\s+init_med_final\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "init_med_final() not found in ph_sort2.c"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


def test_init_med_final_signature_matches_c() -> None:
    """The C signature is ``static void init_med_final(LPTTS_HANDLE_T, short)``."""
    text = _read_ph_sort2_c()
    sig = re.search(
        r"static\s+void\s+init_med_final\s*\(\s*"
        r"LPTTS_HANDLE_T\s+\w+\s*,\s*short\s+\w+\s*\)",
        text,
    )
    assert sig is not None, "expected `static void init_med_final(LPTTS_HANDLE_T, short)`"


def test_init_med_final_initial_sylltype_is_fmonosyl() -> None:
    """The body initialises ``sylltype = FMONOSYL``."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"sylltype\s*=\s*FMONOSYL\s*;",
        body,
    ), "expected `sylltype = FMONOSYL;` initial assignment"


def test_init_med_final_backward_loop_starts_at_currphone_minus_one() -> None:
    """The backward loop runs ``for (m = CURRPHONE - 1; m > 0; m--)``."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"for\s*\(\s*m\s*=\s*CURRPHONE\s*-\s*1\s*;\s*"
        r"m\s*>\s*0\s*;\s*m--\s*\)",
        body,
    ), "expected `for (m = CURRPHONE - 1; m > 0; m--)` backward loop"


def test_init_med_final_boundary_predicate_uses_fwbnext() -> None:
    """The backward loop bails out when ``(sentstruc[m] & FBOUNDARY) >= FWBNEXT``."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"pDph_t->sentstruc\s*\[\s*m\s*\]\s*&\s*FBOUNDARY\s*\)\s*>=\s*FWBNEXT",
        body,
    ), "expected `(sentstruc[m] & FBOUNDARY) >= FWBNEXT` test"


def test_init_med_final_promotes_to_ffinalsyl_when_prior_syll() -> None:
    """Reading a prior FSYLL phone sets ``sylltype = FFINALSYL``."""
    body = _extract_init_med_final_body()
    # The C source: `sylltype = FFINALSYL;` inside the prior-syll branch.
    assert re.search(
        r"sylltype\s*=\s*FFINALSYL\s*;",
        body,
    ), "expected `sylltype = FFINALSYL;` in backward loop"


def test_init_med_final_forward_loop_starts_at_msym_plus_one() -> None:
    """The forward loop runs ``for (m = msym + 1; m < nsymbtot; m++)``."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"for\s*\(\s*m\s*=\s*msym\s*\+\s*1\s*;\s*"
        r"m\s*<\s*pDph_t->nsymbtot\s*;\s*m\+\+\s*\)",
        body,
    ), "expected `for (m = msym + 1; m < nsymbtot; m++)` forward loop"


def test_init_med_final_forward_boundary_range_is_wbound_to_exclaim() -> None:
    """The forward loop bails on ``symbols[m] >= WBOUND && symbols[m] <= EXCLAIM``."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"pDph_t->symbols\s*\[\s*m\s*\]\s*>=\s*WBOUND",
        body,
    ), "expected `symbols[m] >= WBOUND` lower bound"
    assert re.search(
        r"pDph_t->symbols\s*\[\s*m\s*\]\s*<=\s*EXCLAIM",
        body,
    ), "expected `symbols[m] <= EXCLAIM` upper bound"


def test_init_med_final_calls_add_feature_with_currphone() -> None:
    """On boundary, the body calls ``add_feature(pDph_t, sylltype, CURRPHONE)``."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"add_feature\s*\(\s*pDph_t\s*,\s*sylltype",
        body,
    ), "expected `add_feature(pDph_t, sylltype, ...)`"
    assert "CURRPHONE" in body, "expected the CURRPHONE macro"


def test_init_med_final_promotes_ffinalsyl_to_fmedialsyl() -> None:
    """When sylltype is FFINALSYL and forward syll seen, upgrades to FMEDIALSYL."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"sylltype\s*=\s*FMEDIALSYL\s*;",
        body,
    ), "expected `sylltype = FMEDIALSYL;` in forward loop"


def test_init_med_final_promotes_fmonosyl_to_ffirstsyl() -> None:
    """When sylltype is FMONOSYL and forward syll seen, upgrades to FFIRSTSYL."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"sylltype\s*=\s*FFIRSTSYL\s*;",
        body,
    ), "expected `sylltype = FFIRSTSYL;` in forward loop"


def test_init_med_final_skip_write_when_still_fmonosyl() -> None:
    """When sylltype is still FMONOSYL at boundary, no ``add_feature`` is called."""
    body = _extract_init_med_final_body()
    assert re.search(
        r"if\s*\(\s*sylltype\s*!=\s*FMONOSYL\s*\)",
        body,
    ), "expected `if (sylltype != FMONOSYL)` write guard"


# ---------------------------------------------------------------------------
# Behavioural parity tests.
# ---------------------------------------------------------------------------


def test_monosyllabic_no_feature_written() -> None:
    """Pure monosyllable: no syllable before or after → no add_feature."""
    state = DphT()
    # Output stream: just one consonant phoneme at index 0 (no FSYLL before).
    state.phonemes = [int(USPhoneme.T)]
    state.nphonetot = 1  # CURRPHONE = 0; backward loop body never runs.
    state.sentstruc = [0]
    # Input stream: ahead is WBOUND immediately, no FSYLL.
    state.symbols = [int(USPhoneme.T), WBOUND]
    state.nsymbtot = 2
    init_med_final(state, 0)
    # sylltype stays FMONOSYL → no add_feature → sentstruc[0] unchanged.
    assert state.sentstruc[0] == 0


def test_final_syll_when_prior_syll_no_follow() -> None:
    """One vowel in prior phonemes, WBOUND right ahead → FFINALSYL."""
    state = DphT()
    # phonemes[1] = IY (FSYLL), phonemes[2] = current consonant.
    state.phonemes = [int(USPhoneme.T), int(USPhoneme.IY), int(USPhoneme.K)]
    state.nphonetot = 3  # CURRPHONE = 2.
    state.sentstruc = [0, 0, 0]
    # Input: just a word boundary ahead.
    state.symbols = [int(USPhoneme.K), WBOUND]
    state.nsymbtot = 2
    init_med_final(state, 0)
    assert state.sentstruc[2] == FFINALSYL


def test_first_syll_when_no_prior_but_following_syll() -> None:
    """No prior syllable, but a syllable follows before the boundary → FFIRSTSYL."""
    state = DphT()
    # phonemes[1] is a consonant (no FSYLL).
    state.phonemes = [int(USPhoneme.T), int(USPhoneme.P)]
    state.nphonetot = 2  # CURRPHONE = 1.
    state.sentstruc = [0, 0]
    # Input: consonant at 0 (msym), then IY (syllabic), then WBOUND.
    state.symbols = [int(USPhoneme.K), int(USPhoneme.IY), WBOUND]
    state.nsymbtot = 3
    init_med_final(state, 0)
    assert state.sentstruc[1] == FFIRSTSYL


def test_medial_syll_when_prior_and_following() -> None:
    """A syll before and a syll after → FMEDIALSYL."""
    state = DphT()
    # phonemes[1] = IY (prior syll); phonemes[2] = current consonant.
    state.phonemes = [int(USPhoneme.T), int(USPhoneme.IY), int(USPhoneme.K)]
    state.nphonetot = 3  # CURRPHONE = 2.
    state.sentstruc = [0, 0, 0]
    # Input: IY (syllabic) before WBOUND.
    state.symbols = [int(USPhoneme.K), int(USPhoneme.IY), WBOUND]
    state.nsymbtot = 3
    init_med_final(state, 0)
    assert state.sentstruc[2] == FMEDIALSYL


def test_word_boundary_in_output_breaks_backward_walk() -> None:
    """A FWBNEXT marker in ``sentstruc`` halts the backward scan."""
    state = DphT()
    # phonemes[1] is a vowel from a prior word; sentstruc[2] has FWBNEXT,
    # which should stop the backward walk before it sees the prior syll.
    state.phonemes = [int(USPhoneme.T), int(USPhoneme.IY), int(USPhoneme.K), int(USPhoneme.AE)]
    state.nphonetot = 4  # CURRPHONE = 3.
    state.sentstruc = [0, 0, FWBNEXT, 0]
    # Input: just a WBOUND ahead.
    state.symbols = [int(USPhoneme.AE), WBOUND]
    state.nsymbtot = 2
    init_med_final(state, 0)
    # Because the word boundary at sentstruc[2] cuts off the backward
    # walk before reaching the IY at index 1, sylltype stays FMONOSYL
    # and no add_feature happens.
    assert state.sentstruc[3] == 0


def test_uses_exclaim_boundary() -> None:
    """An EXCLAIM symbol in the forward stream also terminates the walk."""
    state = DphT()
    state.phonemes = [int(USPhoneme.T), int(USPhoneme.IY), int(USPhoneme.K)]
    state.nphonetot = 3
    state.sentstruc = [0, 0, 0]
    state.symbols = [int(USPhoneme.K), EXCLAIM]
    state.nsymbtot = 2
    init_med_final(state, 0)
    # Prior syll exists, no following syll → FFINALSYL.
    assert state.sentstruc[2] == FFINALSYL


def test_no_op_if_no_boundary_in_forward_stream() -> None:
    """If forward walk runs off the end without seeing a boundary, no write."""
    state = DphT()
    state.phonemes = [int(USPhoneme.T), int(USPhoneme.IY), int(USPhoneme.K)]
    state.nphonetot = 3
    state.sentstruc = [0, 0, 0]
    # No boundary in input stream.
    state.symbols = [int(USPhoneme.K), int(USPhoneme.T)]
    state.nsymbtot = 2
    init_med_final(state, 0)
    # Loop runs to the end without a boundary → no add_feature call.
    assert state.sentstruc[2] == 0
