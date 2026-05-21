"""C-source parity test for :func:`ph_setallofeats` against the C reference.

There is no dedicated ``ph_setallofeats.c`` in the DECtalk source --
``allofeats[]`` is populated as a side-effect of ``phalloph2`` /
``ph_aloph2.c``'s ``make_out_phonol`` helper. The Python pipeline
currently skips the full ``phalloph`` chain (still routed through
``dectalk._capi`` for the audio path) and instead derives the
minimum feature bits ``phinton`` needs from the ARPABET front-end
output. This test pins those derivations to the C-source contract:

* The feature-bit values in :mod:`dectalk.ph.feature_bits` match
  ``ph_defs.h`` exactly. Drift here would silently miscompute every
  feature word.
* ``ph_aloph2.c`` does in fact write ``curr_outstruc`` into
  ``allofeats[nallotot]`` and zero-init the trailing-SIL slot --
  proving the Python derivation models the right contract.
* ``ph_inton2.c``'s ``phinton`` reads ``allofeats[]`` and gates F0
  events on ``FSTRESS`` / ``FBOUNDARY`` / ``FPERNEXT`` masks --
  the bits :func:`ph_setallofeats` writes.

Plus behavioural checks on the Python helper:

* Unstressed / stressed / sentence-final ARPABET inputs produce the
  expected ``FSTRESS`` / ``FWBNEXT`` / ``FPERNEXT`` patterns.
* ``nf0tot > 0`` after a full ``hello world`` run -- the issue's
  headline acceptance criterion.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.

Tracks issue #63.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import PFUSA, USPhoneme
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FBOUNDARY,
    FNOSTRESS,
    FPERNEXT,
    FSENTENDS,
    FSTRESS,
    FSTRESS_1,
    FSTRESS_2,
    FWBNEXT,
)
from dectalk.ph.ph_setallofeats import ph_setallofeats
from dectalk.ph.utterance_constants import GEN_SIL

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_ALOPH2 = _SRC_ROOT / "src/dapi/src/ph/ph_aloph2.c"
_C_INTON2 = _SRC_ROOT / "src/dapi/src/ph/ph_inton2.c"
_C_DEFS = _SRC_ROOT / "src/dapi/src/ph/ph_defs.h"

pytestmark = pytest.mark.skipif(
    not _C_ALOPH2.is_file() or not _C_INTON2.is_file() or not _C_DEFS.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read(path: Path) -> str:
    """Read a CRLF / latin-1 C source file as a normalised string."""
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


# ---------------------------------------------------------------------------
# Constant-parity checks: every feature bit we set must match ph_defs.h.
# ---------------------------------------------------------------------------


def _parse_octal_define(c_text: str, name: str) -> int:
    """Extract a numeric #define from ph_defs.h text.

    ph_defs.h uses K&R-style octal (a leading ``0`` -- e.g. ``03``,
    ``040``, ``0400``), hex (``0x...``), or decimal. We parse them as
    Python ints to compare against ``feature_bits.py``. Python's
    ``int("03", 0)`` rejects K&R octal (needs ``0o3``), so detect the
    leading-zero case manually.
    """
    match = re.search(rf"#define\s+{name}\s+(0[xX][0-9a-fA-F]+|\d+)\b", c_text)
    assert match is not None, f"{name!r} not defined in ph_defs.h"
    raw = match.group(1)
    if raw.startswith(("0x", "0X")):
        return int(raw, 16)
    if raw.startswith("0") and raw != "0":
        return int(raw, 8)
    return int(raw, 10)


def test_feature_bit_constants_match_c_source() -> None:
    """The feature-bit values we OR into allofeats match ph_defs.h."""
    defs = _read(_C_DEFS)

    assert _parse_octal_define(defs, "FSTRESS") == FSTRESS
    assert _parse_octal_define(defs, "FNOSTRESS") == FNOSTRESS
    assert _parse_octal_define(defs, "FSTRESS_1") == FSTRESS_1
    assert _parse_octal_define(defs, "FSTRESS_2") == FSTRESS_2
    assert _parse_octal_define(defs, "FBOUNDARY") == FBOUNDARY
    assert _parse_octal_define(defs, "FWBNEXT") == FWBNEXT
    assert _parse_octal_define(defs, "FPERNEXT") == FPERNEXT
    assert _parse_octal_define(defs, "FSENTENDS") == FSENTENDS


# ---------------------------------------------------------------------------
# C-source contract: ph_aloph2.c writes curr_outstruc into allofeats[].
# ---------------------------------------------------------------------------


def test_make_out_phonol_writes_allofeats() -> None:
    """``ph_aloph2.c::make_out_phonol`` does write ``pDph_t->allofeats[]``.

    Pinning this guards the contract we're modelling: the C source
    sets ``allofeats[nallotot] = curr_outstruc`` for every emitted
    allophone, and the trailing-SIL slot is explicitly zeroed.
    Drift here (e.g. an upstream refactor moves the write) would
    invalidate the rationale for :func:`ph_setallofeats`.
    """
    text = _read(_C_ALOPH2)
    # 1. ``allofeats[nallotot] = curr_outstruc`` -- the per-allophone write.
    assert re.search(
        r"pDph_t->allofeats\[\s*pDph_t->nallotot\s*\]\s*=\s*curr_outstruc\s*;",
        text,
    ), "make_out_phonol must write curr_outstruc into allofeats[nallotot]"

    # 2. ``allofeats[nallotot] = 0`` -- trailing-SIL zero init.
    assert re.search(
        r"pDph_t->allofeats\[\s*pDph_t->nallotot\s*\]\s*=\s*0\s*;",
        text,
    ), "ph_aloph2.c must zero-init the trailing GEN_SIL allofeats slot"


# ---------------------------------------------------------------------------
# C-source contract: phinton reads the bits we set.
# ---------------------------------------------------------------------------


def test_phinton_reads_stress_and_boundary_bits() -> None:
    """``ph_inton2.c::phinton`` reads ``FSTRESS`` and ``FBOUNDARY`` from allofeats.

    Verifies the consumer side of the contract: the bits
    :func:`ph_setallofeats` sets are the bits ``phinton`` checks.
    """
    text = _read(_C_INTON2)
    # struccur is initialised from allofeats[nphon] (line ~754).
    assert re.search(r"struccur\s*=\s*pDph_t->allofeats\[\s*nphon\s*\]\s*;", text)
    # stresscur masks FSTRESS off struccur (line ~779).
    assert re.search(r"stresscur\s*=\s*struccur\s*&\s*FSTRESS\b", text)
    # nextsylbou masks FBOUNDARY off allofeats lookahead (line ~849).
    assert re.search(
        r"nextsylbou\s*=\s*pDph_t->allofeats\[\s*nphonx\s*\]\s*&\s*FBOUNDARY\b",
        text,
    )
    # Final fall (Rule 4) checks FPERNEXT against struccur.
    assert re.search(r"struccur\s*&\s*FPERNEXT\b", text)


# ---------------------------------------------------------------------------
# Behavioural tests on the Python helper.
# ---------------------------------------------------------------------------


def _make_dph_t_with_allophons(allophons: list[int]) -> DphT:
    """Build a DphT pre-seeded for a ph_setallofeats call.

    Minimal scaffolding: ``allophons`` populated, ``allofeats`` sized
    and zero-initialised, ``nallotot`` set. Mirrors what
    ``init_phclause`` + the caller's allophone copy would produce.
    """
    p_dph_t = DphT()
    p_dph_t.allophons = list(allophons) + [0] * 32
    p_dph_t.allofeats = [0] * (len(allophons) + 32)
    p_dph_t.nallotot = len(allophons)
    return p_dph_t


def test_sentence_final_word_gets_pernext_sentends() -> None:
    """Last syllabic phone of the final word gets ``FPERNEXT | FSENTENDS``.

    The C source's phinton Rule 4 (final fall) fires on this bit
    combination -- the canonical "you hit the end of a sentence"
    marker.
    """
    # "buy" -> [SIL, B, AY1, SIL]. B and AY both have direct
    # USPhoneme entries (unlike HH/L/NG -- issue #61's alias gap).
    B = (PFUSA << 8) | int(USPhoneme.B)  # noqa: N806
    AY = (PFUSA << 8) | int(USPhoneme.AY)  # noqa: N806
    allophons = [GEN_SIL, B, AY, GEN_SIL]
    p_dph_t = _make_dph_t_with_allophons(allophons)

    ph_setallofeats(p_dph_t, [["B", "AY1"]], is_sentence_final=True)

    # Leading SIL untouched.
    assert p_dph_t.allofeats[0] == 0
    # B (consonant): FNOSTRESS, no boundary bits.
    assert (p_dph_t.allofeats[1] & FSTRESS) == FNOSTRESS
    assert (p_dph_t.allofeats[1] & FBOUNDARY) == 0
    # AY1 (vowel, last-syllabic in only word, sentence-final):
    # FSTRESS_1 + FPERNEXT + FSENTENDS.
    assert (p_dph_t.allofeats[2] & FSTRESS) == FSTRESS_1
    assert (p_dph_t.allofeats[2] & FBOUNDARY) == FPERNEXT
    assert p_dph_t.allofeats[2] & FSENTENDS
    # Trailing SIL untouched.
    assert p_dph_t.allofeats[3] == 0


def test_mid_clause_word_gets_fwbnext() -> None:
    """Non-final words get ``FWBNEXT`` on the last syllabic phone."""
    # "go now" -> [SIL, G, OW1, N, AW1, SIL].
    G = (PFUSA << 8) | int(USPhoneme.G)  # noqa: N806
    OW = (PFUSA << 8) | int(USPhoneme.OW)  # noqa: N806
    N = (PFUSA << 8) | int(USPhoneme.N)  # noqa: N806
    AW = (PFUSA << 8) | int(USPhoneme.AW)  # noqa: N806
    allophons = [GEN_SIL, G, OW, N, AW, GEN_SIL]
    p_dph_t = _make_dph_t_with_allophons(allophons)

    ph_setallofeats(p_dph_t, [["G", "OW1"], ["N", "AW1"]], is_sentence_final=True)

    # G: consonant, no stress, no boundary.
    assert (p_dph_t.allofeats[1] & FBOUNDARY) == 0
    # OW1: vowel, primary stress, end of word 1 (non-final word) -> FWBNEXT.
    assert (p_dph_t.allofeats[2] & FSTRESS) == FSTRESS_1
    assert (p_dph_t.allofeats[2] & FBOUNDARY) == FWBNEXT
    # N: consonant, no stress, no boundary.
    assert (p_dph_t.allofeats[3] & FBOUNDARY) == 0
    # AW1: vowel, primary stress, end of word 2 (final word, sentence-final)
    # -> FPERNEXT|FSENTENDS.
    assert (p_dph_t.allofeats[4] & FSTRESS) == FSTRESS_1
    assert (p_dph_t.allofeats[4] & FBOUNDARY) == FPERNEXT


def test_unstressed_arpabet_decodes_to_fnostress() -> None:
    """Unstressed vowels (``AH0``) decode to ``FNOSTRESS``."""
    AH = (PFUSA << 8) | int(USPhoneme.AH)  # noqa: N806
    allophons = [GEN_SIL, AH, GEN_SIL]
    p_dph_t = _make_dph_t_with_allophons(allophons)

    ph_setallofeats(p_dph_t, [["AH0"]], is_sentence_final=True)

    # AH0: unstressed vowel. FSTRESS == 0 means no stress contribution.
    assert (p_dph_t.allofeats[1] & FSTRESS) == FNOSTRESS
    # Still gets the sentence-final boundary marker.
    assert (p_dph_t.allofeats[1] & FBOUNDARY) == FPERNEXT


def test_secondary_stress_decodes_to_fstress_2() -> None:
    """``AH2`` decodes to ``FSTRESS_2``."""
    AH = (PFUSA << 8) | int(USPhoneme.AH)  # noqa: N806
    allophons = [GEN_SIL, AH, GEN_SIL]
    p_dph_t = _make_dph_t_with_allophons(allophons)

    ph_setallofeats(p_dph_t, [["AH2"]], is_sentence_final=False)

    assert (p_dph_t.allofeats[1] & FSTRESS) == FSTRESS_2
    # Not sentence-final -> no FPERNEXT.
    assert (p_dph_t.allofeats[1] & FBOUNDARY) == 0


def test_phinton_produces_nf0tot_gt_zero_on_hello_world() -> None:
    """End-to-end acceptance: ``phinton`` emits at least one F0 event.

    The issue's headline criterion: after running the full pipeline
    on "hello world", ``nf0tot`` is non-zero (phinton is no longer
    monotone). Without :func:`ph_setallofeats` populating
    ``allofeats[]``, ``phinton`` saw all-zero feature words and
    emitted nothing.
    """
    # Run via the actual speak() entry point with the full pipeline
    # gated on. Snapshot nf0tot by monkey-patching phinton.
    _saved_disable = os.environ.get("DECTALK_DISABLE_CAPI")
    _saved_full = os.environ.get("DECTALK_FULL_PIPELINE")
    os.environ["DECTALK_DISABLE_CAPI"] = "1"
    os.environ["DECTALK_FULL_PIPELINE"] = "1"

    # Force a fresh import so the env vars take effect.
    for mod in [m for m in list(sys.modules) if m.startswith("dectalk")]:
        del sys.modules[mod]

    try:
        # Late imports intentional: env vars above must take effect on
        # a fresh dectalk import (sys.modules was just cleared).
        import dectalk  # noqa: PLC0415
        import dectalk.api.speak as speak_mod  # noqa: PLC0415
        import dectalk.ph.phinton as phinton_mod  # noqa: PLC0415

        captured: dict[str, int] = {"nf0tot": -1}
        _orig = phinton_mod.phinton

        def _capture(handle: object) -> object:
            ret = _orig(handle)
            assert hasattr(handle, "p_ph_thread_data")
            p = handle.p_ph_thread_data  # type: ignore[attr-defined]
            assert p is not None
            captured["nf0tot"] = p.nf0tot
            return ret

        phinton_mod.phinton = _capture  # type: ignore[assignment]
        speak_mod.phinton = _capture  # type: ignore[attr-defined]

        dectalk.speak("hello world")
        assert captured["nf0tot"] > 0, (
            f"phinton produced no F0 events even with allofeats populated; "
            f"nf0tot={captured['nf0tot']}"
        )
    finally:
        # Restore env vars so other tests aren't affected.
        if _saved_disable is None:
            os.environ.pop("DECTALK_DISABLE_CAPI", None)
        else:
            os.environ["DECTALK_DISABLE_CAPI"] = _saved_disable
        if _saved_full is None:
            os.environ.pop("DECTALK_FULL_PIPELINE", None)
        else:
            os.environ["DECTALK_FULL_PIPELINE"] = _saved_full
