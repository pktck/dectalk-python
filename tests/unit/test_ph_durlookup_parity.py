"""C-source parity test for ``durlookup`` against ph_sort.c.

Re-parses the C function body, extracts:

- the outer table-walking loop ``while ((len = *tp++) != 0)``,
- the ``GEN_SIL`` early-termination predicate,
- the ``EOS`` success predicate and the post-EOS ``return (++cp)``
  pointer arithmetic,
- the ``tp += len`` advance to the next entry,

and asserts the Python port behaves identically over a small
representative set of tables.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.dectalk import EOS
from dectalk.ph.durlookup import durlookup
from dectalk.ph.utterance_constants import GEN_SIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / ("src/dapi/src/ph/ph_sort.c")

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_ph_sort_c() -> str:
    """Read ph_sort.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_durlookup_body() -> str:
    """Return the C ``durlookup`` function body with comments stripped."""
    text = _read_ph_sort_c()
    match = re.search(
        r"short\s*\*\s*durlookup\s*\([^)]*\)\s*\{(.+?)^\}",
        text,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "durlookup() not found in ph_sort.c"
    body = match.group(1)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.DOTALL)
    body = re.sub(r"//.*", "", body)
    return body


def test_durlookup_signature_matches_c() -> None:
    """The C signature is ``short *durlookup(PDPH_T, short *, short[])``."""
    text = _read_ph_sort_c()
    sig = re.search(
        r"short\s*\*\s*durlookup\s*\(\s*PDPH_T\s+\w+\s*,\s*"
        r"short\s*\*\s*\w+\s*,\s*"
        r"short\s+\w+\s*\[\s*\]\s*\)",
        text,
    )
    assert sig is not None, "expected `short *durlookup(PDPH_T, short *, short [])`"


def test_durlookup_outer_loop_is_len_eq_post_inc_tp() -> None:
    """Outer loop is ``while ((len = *tp++) != 0)``."""
    body = _extract_durlookup_body()
    assert re.search(
        r"while\s*\(\s*\(\s*len\s*=\s*\*\s*tp\s*\+\+\s*\)\s*!=\s*0\s*\)",
        body,
    ), "expected `while ((len = *tp++) != 0)` outer loop"


def test_durlookup_gen_sil_early_termination() -> None:
    """The body bails out of the inner loop when ``*lp == GEN_SIL``."""
    body = _extract_durlookup_body()
    assert re.search(
        r"if\s*\(\s*\*\s*lp\s*==\s*GEN_SIL\s*\)\s*break\s*;",
        body,
    ), "expected `if (*lp == GEN_SIL) break;` inner-loop termination"


def test_durlookup_eos_success_returns_post_increment_cp() -> None:
    """``*cp == EOS`` triggers ``return (++cp)`` (pointer just past EOS)."""
    body = _extract_durlookup_body()
    assert re.search(
        r"if\s*\(\s*\*\s*cp\s*==\s*EOS\s*\)",
        body,
    ), "expected `if (*cp == EOS)` success predicate"
    assert re.search(
        r"return\s*\(\s*\+\+\s*cp\s*\)\s*;",
        body,
    ), "expected `return (++cp);` to return the post-EOS pointer"


def test_durlookup_advances_via_tp_plus_eq_len() -> None:
    """Each failed inner-loop iteration advances ``tp += len`` to next entry."""
    body = _extract_durlookup_body()
    assert re.search(
        r"tp\s*\+=\s*len\s*;",
        body,
    ), "expected `tp += len;` advance"


def test_durlookup_returns_null_at_end_of_table() -> None:
    """Fallthrough returns ``NULL`` (the table-exhausted case)."""
    body = _extract_durlookup_body()
    assert re.search(
        r"return\s*\(\s*NULL\s*\)\s*;",
        body,
    ), "expected `return (NULL);` after the table walk"


def test_durlookup_inner_loop_compares_lp_neq_post_inc_cp() -> None:
    """Inner-loop mismatch predicate is ``*lp != *cp++``."""
    body = _extract_durlookup_body()
    assert re.search(
        r"if\s*\(\s*\*\s*lp\s*!=\s*\*\s*cp\s*\+\+\s*\)",
        body,
    ), "expected `if (*lp != *cp++)` mismatch test"


# -- Behavioural tests ------------------------------------------------------


def test_empty_table_returns_none() -> None:
    """A bare end-of-table sentinel returns ``None``."""
    assert durlookup(None, [GEN_SIL], [0]) is None


def test_single_entry_exact_match_returns_payload_index() -> None:
    """A one-entry table whose key matches returns the payload index."""
    # Layout: [len=3, key='A'=1, EOS, payload=99, end_sentinel=0]
    table = [3, 1, EOS, 99, 0]
    # Key length = 1 word + EOS + 1 payload = 3 words, matches len.
    # Trace: tp=0, len=table[0]=3, tp=1. lp=0, cp=1.
    # iter1: cp_val=table[1]=1, cp=2. symbol[0]=1 == 1. symbol[0]!=GEN_SIL.
    #        table[cp]=table[2]=EOS → match. Return cp+1 = 3.
    assert durlookup(None, [1, GEN_SIL], table) == 3
    # And table[3] is the payload.
    assert table[3] == 99


def test_mismatched_symbol_returns_none() -> None:
    """A symbol that does not match any key returns ``None``."""
    table = [3, 1, EOS, 99, 0]
    assert durlookup(None, [2, GEN_SIL], table) is None


def test_gen_sil_input_before_eos_no_match() -> None:
    """``GEN_SIL`` in the input pattern before the table EOS aborts the match."""
    # Key is two words long: 'A','B' — input is just 'A' followed by GEN_SIL.
    # When we hit GEN_SIL on the input side, we break without a match.
    table = [4, 1, 2, EOS, 99, 0]
    # Trace: tp=0, len=4, tp=1. lp=0, cp=1.
    # iter1: cp_val=table[1]=1, cp=2. symbol[0]=1 == 1. symbol[0]!=GEN_SIL.
    #        table[2]=2 != EOS. lp=1.
    # iter2: cp_val=table[2]=2, cp=3. symbol[1]=GEN_SIL != 2 → break.
    # tp += 4 → tp=5, len=table[5]=0 → return None.
    assert durlookup(None, [1, GEN_SIL], table) is None


def test_second_entry_matches_after_first_fails() -> None:
    """The table walker advances past the first entry to find a later match."""
    # Two entries:
    #   entry 0: key='A'=1 → payload 99    (len=3: key + EOS + payload)
    #   entry 1: key='B'=2 → payload 88    (len=3)
    # then 0 sentinel.
    table = [3, 1, EOS, 99, 3, 2, EOS, 88, 0]
    # symbol='B' should match the second entry — its payload index is 7.
    assert durlookup(None, [2, GEN_SIL], table) == 7
    assert table[7] == 88


def test_two_word_key_match() -> None:
    """A two-word key matches a two-symbol input."""
    # Layout: [len=4, key=[5,6], EOS, payload=77, end_sentinel=0]
    table = [4, 5, 6, EOS, 77, 0]
    # Trace: tp=0, len=4, tp=1. lp=0, cp=1.
    # iter1: cp_val=table[1]=5, cp=2. symbol[0]=5 == 5. !=GEN_SIL.
    #        table[2]=6 != EOS. lp=1.
    # iter2: cp_val=table[2]=6, cp=3. symbol[1]=6 == 6. !=GEN_SIL.
    #        table[3]=EOS → match. Return cp+1 = 4.
    assert durlookup(None, [5, 6, GEN_SIL], table) == 4
    assert table[4] == 77


def test_prefix_match_without_eos_is_rejected() -> None:
    """A prefix-only match (key longer than input) does not return."""
    # Key=[5,6] but symbol=[5, GEN_SIL]: lp hits GEN_SIL before table EOS.
    # Trace: lp=0, cp=1. cp_val=5, cp=2. 5==5. !=GEN_SIL.
    #        table[2]=6 != EOS. lp=1.
    #        cp_val=table[2]=6, cp=3. symbol[1]=GEN_SIL != 6 → break.
    table = [4, 5, 6, EOS, 77, 0]
    assert durlookup(None, [5, GEN_SIL], table) is None


def test_payload_index_points_just_past_eos() -> None:
    """The returned index is the C-equivalent of ``++cp`` past the EOS."""
    # Construct a table where the EOS is at a known offset.
    # entry 0: len=2, key=[42], EOS, (no payload)
    # then 0.
    table = [2, 42, EOS, 0]
    # Trace: tp=0, len=2, tp=1. lp=0, cp=1.
    # iter1: cp_val=42, cp=2. symbol[0]=42 == 42. !=GEN_SIL.
    #        table[2]=EOS → match. Return cp+1 = 3.
    result = durlookup(None, [42, GEN_SIL], table)
    assert result == 3
    # And table[3] = 0 (the end-of-table sentinel) — payload starts here.


def test_does_not_mutate_inputs() -> None:
    """``durlookup`` does not mutate its inputs."""
    symbol = [1, GEN_SIL]
    table = [3, 1, EOS, 99, 0]
    symbol_copy = list(symbol)
    table_copy = list(table)
    durlookup(None, symbol, table)
    assert symbol == symbol_copy
    assert table == table_copy
