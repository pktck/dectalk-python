"""Pin behaviour on isolated-abbreviation tokens (`Dr.`, `i.e.`, `Inc.` etc.).

Issue #146 — policy decision for isolated-abbreviation handling.

**Background.** The kernel text-norm refresh audit
(`docs/c_audit/kernel_textnorm_refresh.md`, finding #8) initially
reported that the C oracle returns an empty phoneme stream for
isolated abbreviations like `Dr.`, `i.e.`, `Inc.`, `etc.` and
suggested this was a C-side quirk we may not want to mirror. The
issue asked us to decide between:

- **Option A (bug-for-bug parity)**: Verify Python also returns empty
  stream for these isolated tokens; add tests to pin behaviour.
- **Option B (improvement-over-C)**: Add abbreviation expansion so
  ``Dr.`` → "doctor", ``i.e.`` → "that is", ``Inc.`` → "incorporated".

**Finding from re-running the C oracle here.** The "empty stream"
claim was wrong. It came from C-library cross-call state pollution
in the bulk-oracle harness in
``tests/parity/test_python_phonemes_vs_c_parity.py``, which reuses
one ``CAPI()`` handle for ~1000 prompts before cycling. With a
**fresh** ``CAPI()`` instance per call, every isolated abbreviation
expands deterministically (``Dr.`` → "drive", ``i.e.`` → "this is",
``Inc.`` → "incorporated", ``etc.`` → "et cetera", and so on).

**Policy decided in issue #146.** Bug-for-bug parity is still the
goal — but "the bug" was a measurement artefact, not a C
behaviour. The real divergence is that the C path runs the
``abbrp_words`` / ``ls_task_Dr_St_process`` tables on isolated
abbreviations and Python doesn't. The proper fix is to port those
tables (tracked alongside the broader text-norm port via
``par_match_rule`` / ``par_process_input`` in ``docs/TASKS.md``);
until then this test pins **both** sides so any change to either
half is a deliberate, reviewed event:

- The :data:`_C_EXPECTED` map records what the C oracle actually
  emits today (with fresh ``CAPI()`` per call). If a future C
  oracle version changes any of these — or if the harness is
  later fixed and bulk-oracle output starts matching these —
  the test will surface the change.
- The :data:`_PY_EXPECTED` map records what
  ``dectalk.text_to_dectalk_phonemes`` emits today. Any future
  port of ``abbrp_words`` will need to update these entries
  (most likely to match the C column above) and is the
  intended path to closing the divergence.

The C side of the test is skipped unless the locally-built
``libtts_us.so`` is present (set up via ``scripts/setup_c_oracle.sh``).
The Python side runs unconditionally.

The corresponding ``Dr. Smith``-style cases (abbreviation followed
by a name) already match cleanly via ``title_abbrevs`` in
``src/dectalk/api/speak.py`` and are covered by
``tests/parity/test_python_phonemes_vs_c_parity.py``; this module
intentionally targets only the **isolated** form.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

import pytest

import dectalk
from dectalk._capi import CAPI

# ---------------------------------------------------------------------------
# Pinned Python output (current behaviour at issue-#146 time).
#
# These reflect what ``dectalk.text_to_dectalk_phonemes`` emits today
# with no abbreviation-expansion logic in the Python kernel: the
# abbreviation letters are read out (often via the lexicon's word-form
# entry for the merged spelling) and the trailing period leaks through
# as a clause-terminal marker.
# ---------------------------------------------------------------------------
_PY_EXPECTED: dict[str, bytes] = {
    "Dr.": b"d r . ",
    "i.e.": b"' ih. ",
    "Inc.": b"' ihnxk . ",
    "etc.": b"' eht k . ",
    "e.g.": b"' ehg . ",
    "vs.": b"v z . ",
    "Mr.": b"m r . ",
    "Mrs.": b"m r z . ",
    "Ms.": b"m z . ",
    "St.": b"s t . ",
    "Mt.": b"m t . ",
    "a.m.": b"' aem . ",
    "p.m.": b"p m . ",
}


# ---------------------------------------------------------------------------
# Pinned C oracle output (with a fresh ``CAPI()`` per call, no state
# pollution). These corrected the audit doc's claim that all of these
# return ``b''``.
# ---------------------------------------------------------------------------
_C_EXPECTED: dict[str, bytes] = {
    "Dr.": b"d r ' ayv ",  # "drive"
    "i.e.": b"dh` ihs   ihz ",  # "this is"
    "Inc.": b"ihn k ' owr p rreyt ixd ",  # "incorporated"
    "etc.": b"ixt s ' eht rrax",  # "et cetera"
    "e.g.": b"^ ( f rr  ixg z ' aem p el",  # "for example"
    "vs.": b"v rrs ixs ",  # "versus"
    "Mr.": b"m ihs t rr",  # "mister"
    "Mrs.": b"m ihs ixz ",  # "missus"
    "Ms.": b"m ihz ",  # "miz"
    "St.": b"s t r ` iyt ",  # "street" (isolated; cf. "saint" in "St. Louis")
    "Mt.": b"m awn t ",  # "mount"
    "a.m.": b") aem ",  # "AM"
    "p.m.": b"p ' iy  ' ehm ",  # "P M"
}


_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))


def _have_c_oracle() -> bool:
    """True iff a locally-built ``libtts_us.so`` exports the parity entry point."""
    candidates = sorted(_SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    if not candidates:
        return False
    try:
        lib = ctypes.CDLL(str(candidates[-1]))
        getattr(lib, "TextToSpeechConvertToPhonemes")  # noqa: B009
    except (OSError, AttributeError):
        return False
    return True


@pytest.mark.parametrize("prompt", list(_PY_EXPECTED), ids=list(_PY_EXPECTED))
def test_isolated_abbrev_python_pinned(prompt: str) -> None:
    """Pin Python's current output for isolated abbreviations.

    The Python pipeline does **not** expand isolated abbreviations
    today; it reads them out letter-by-letter / via the merged lexicon
    form and leaks the trailing period as a clause-terminal marker.
    This test asserts that current behaviour byte-for-byte so any
    change (e.g. a future port of the ``abbrp_words`` table) is a
    deliberate update of :data:`_PY_EXPECTED` with the new bytes,
    not an accidental regression.
    """
    actual = dectalk.text_to_dectalk_phonemes(prompt)
    expected = _PY_EXPECTED[prompt]
    assert actual == expected, (
        f"Python phoneme stream for isolated abbreviation {prompt!r} drifted:\n"
        f"  pinned (issue #146): {expected!r}\n"
        f"  actual:              {actual!r}\n"
        f"If the change is intentional (e.g. abbrp_words port landed),\n"
        f"update _PY_EXPECTED in this file and align _C_EXPECTED accordingly."
    )


@pytest.mark.c_oracle
@pytest.mark.skipif(
    not _have_c_oracle(),
    reason="C library with convert_to_phonemes patch is required for this oracle pin",
)
@pytest.mark.parametrize("prompt", list(_C_EXPECTED), ids=list(_C_EXPECTED))
def test_isolated_abbrev_c_oracle_pinned(prompt: str) -> None:
    """Pin the C oracle's actual (non-empty) output for isolated abbreviations.

    A fresh :class:`dectalk._capi.CAPI` instance is used per prompt to
    avoid the cross-call state pollution that produced the original
    audit doc's incorrect ``b''`` finding. If the bulk-oracle harness
    is ever refactored to also cycle handles per call, the parity
    corpus may grow to include these prompts directly — at which
    point this test still serves as a per-prompt regression gate.
    """
    capi = CAPI()
    actual = capi.convert_to_phonemes(prompt)
    expected = _C_EXPECTED[prompt]
    assert actual == expected, (
        f"C oracle phoneme stream for isolated abbreviation {prompt!r} drifted:\n"
        f"  pinned (issue #146, fresh CAPI per call): {expected!r}\n"
        f"  actual:                                   {actual!r}\n"
        f"If the C oracle binary changed, update _C_EXPECTED with the new bytes."
    )


def test_isolated_abbrev_python_and_c_intentionally_diverge() -> None:
    """Document the divergence: every pinned input differs between Python and C.

    This test is the policy decision crystallised as a single
    assertion: today, on every isolated-abbreviation token we
    track, Python and C produce different phoneme streams. The
    fix path is to port the ``abbrp_words`` /
    ``ls_task_Dr_St_process`` tables into the Python kernel; until
    that lands, the divergence is **expected** and **pinned**.

    When that port lands, this test will need to be updated (or
    removed) alongside :data:`_PY_EXPECTED`.
    """
    assert set(_PY_EXPECTED) == set(_C_EXPECTED), (
        "_PY_EXPECTED and _C_EXPECTED must cover the same prompt set"
    )
    matches: list[str] = [p for p in _PY_EXPECTED if _PY_EXPECTED[p] == _C_EXPECTED[p]]
    assert matches == [], (
        "Expected every isolated abbreviation to diverge between Python and C "
        "(per policy decision in issue #146). The following now match:\n"
        f"  {matches}\n"
        "If this is the result of a deliberate abbrp_words port, update or "
        "remove this regression-anchor test and the pinned dicts above."
    )
