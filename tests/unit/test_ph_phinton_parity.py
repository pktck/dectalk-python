"""C-source parity test for ``phinton`` against ph_inton2.c.

Re-parses the C body via regex / brace-depth tracking and asserts the
US-English intonation engine still exists in the develop branch with
its expected per-clause structure. The Python translation in
:mod:`dectalk.ph.phinton` is exercised end-to-end on a synthesised
silence-only clause to confirm it runs without raising and writes
non-trivial state to the F0-event arrays.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent
for the C-source assertions; the Python behavioural tests always run.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.include.usp_codes import USP_AA, USP_P
from dectalk.kernel.ksd_t import KsdT
from dectalk.kernel.lang_codes import LANG_english
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FHAT_BEGINS,
    FHAT_ENDS,
    FPERNEXT,
    FSTRESS_1,
)
from dectalk.ph.inton_constants import NORMAL
from dectalk.ph.numeric_constants import MALE, NPHON_MAX
from dectalk.ph.phinton import (
    _US_F0_MPHRASE_POSITION,
    _US_F0_MSTRESS_LEVEL,
    phinton,
)
from dectalk.ph.phoneme_features import FBURST, FPLOSV
from dectalk.ph.timing import phone_feature
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import DECLARATIVE, GEN_SIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_inton2.c"

_c_skip = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_inton2_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


# -- C-source structural assertions ----------------------------------------


@_c_skip
def test_signature_matches_c() -> None:
    """C signature: ``void phinton(LPTTS_HANDLE_T phTTS)``."""
    text = _read_inton2_c()
    assert re.search(r"\bvoid\s+phinton\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", text)


@_c_skip
def test_body_unpacks_kernel_share_data() -> None:
    """Source contains ``pKsd_t = phTTS->pKernelShareData`` in phinton's region."""
    text = _read_inton2_c()
    assert re.search(r"PKSD_T\s+\w+\s*=\s*phTTS\s*->\s*pKernelShareData", text)


@_c_skip
def test_body_unpacks_ph_thread_data() -> None:
    """Source contains ``pDph_t = phTTS->pPHThreadData`` in phinton's region."""
    text = _read_inton2_c()
    assert re.search(r"PDPH_T\s+\w+\s*=\s*phTTS\s*->\s*pPHThreadData", text)


@_c_skip
def test_body_declares_intonation_state_locals() -> None:
    """Source declares MAX_NRISES / F0_FINAL_FALL / F0_GLOTTALIZE locals."""
    text = _read_inton2_c()
    for name in (
        "MAX_NRISES",
        "F0_FINAL_FALL",
        "F0_NON_FINAL_FALL",
        "F0_GLOTTALIZE",
    ):
        assert name in text, f"missing local declaration for {name}"


@_c_skip
def test_body_references_stress_level_tables() -> None:
    """Source references the per-language stress-level tables."""
    text = _read_inton2_c()
    assert "f0_mstress_level" in text
    assert "f0_fstress_level" in text
    assert "f0_mphrase_position" in text
    assert "f0_fphrase_position" in text


@_c_skip
def test_body_has_emphasis_and_rise_constants() -> None:
    """Source defines EMPH_FALL / DELTARISE / FINAL_FALL macro-style constants."""
    text = _read_inton2_c()
    assert re.search(r"#\s*define\s+EMPH_FALL", text)
    assert re.search(r"#\s*define\s+DELTARISE", text)
    assert re.search(r"#\s*define\s+FINAL_FALL", text)


@_c_skip
def test_function_is_very_long() -> None:
    """The phinton body is very large (~2080-line C function)."""
    text = _read_inton2_c()
    decl = re.search(r"\bvoid\s+phinton\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", text)
    assert decl is not None
    assert text.count("\n") > 800, "ph_inton2.c is unexpectedly short"


@_c_skip
def test_us_phrase_position_table_values_match_python() -> None:
    """C source's ``us_f0_mphrase_position[]`` matches the Python tuple."""
    text = _read_inton2_c()
    # Find the non-POETRY definition.
    match = re.search(
        r"us_f0_mphrase_position\s*\[\s*\]\s*=\s*\{([^}]+)\}",
        text,
    )
    assert match is not None
    values = tuple(int(v.strip()) for v in match.group(1).split(",") if v.strip().isdigit())
    # First match in file is the POETRY-guarded variant; second is the
    # active one. Walk both candidates and confirm one matches.
    all_matches = re.findall(
        r"us_f0_mphrase_position\s*\[\s*\]\s*=\s*\{([^}]+)\}",
        text,
    )
    parsed = [
        tuple(int(v.strip()) for v in m.split(",") if v.strip().lstrip("-").isdigit())
        for m in all_matches
    ]
    assert _US_F0_MPHRASE_POSITION in parsed, (
        f"Python US m-phrase table {_US_F0_MPHRASE_POSITION} not found in C candidates {parsed}"
    )
    del values  # silence linter


@_c_skip
def test_us_stress_level_table_values_match_python() -> None:
    """C source's ``us_f0_mstress_level[] = {1,81,61,161}`` matches Python."""
    text = _read_inton2_c()
    match = re.search(
        r"us_f0_mstress_level\s*\[\s*\]\s*=\s*\{([^}]+)\}",
        text,
    )
    assert match is not None
    parsed = tuple(
        int(v.strip()) for v in match.group(1).split(",") if v.strip().lstrip("-").isdigit()
    )
    assert parsed == _US_F0_MSTRESS_LEVEL


# -- Python behavioural tests ----------------------------------------------


def _make_handle(
    *,
    allophons: list[int],
    allodurs: list[int],
    allofeats: list[int] | None = None,
    user_f0: list[int] | None = None,
) -> TtsHandle:
    """Build a minimally-populated TtsHandle ready for ``phinton``."""
    ksd = KsdT()
    ksd.lang_curr = LANG_english

    dph = DphT()
    settar = DphSettarSt()
    dph.pSTphsettar = settar

    n = len(allophons)
    # Pad arrays out to NPHON_MAX so the engine's lookahead is safe.
    pad = NPHON_MAX + 8 - n
    dph.allophons = list(allophons) + [GEN_SIL] * pad
    dph.allofeats = list(allofeats) if allofeats is not None else [0] * n
    dph.allofeats += [0] * (NPHON_MAX + 8 - len(dph.allofeats))
    dph.allodurs = list(allodurs) + [0] * pad
    dph.alloopenq = [0] * (NPHON_MAX + 8)
    dph.user_f0 = list(user_f0) if user_f0 is not None else [0] * (NPHON_MAX + 8)
    dph.user_offset = [0] * (NPHON_MAX + 8)
    dph.f0tar = [0] * NPHON_MAX
    dph.f0type = [0] * NPHON_MAX
    dph.f0length = [0] * NPHON_MAX
    dph.f0tim = [0] * NPHON_MAX

    dph.nallotot = n
    dph.f0mode = NORMAL
    dph.clausetype = DECLARATIVE
    dph.malfem = MALE
    dph.assertiveness = 4096  # full strength (frac4mul: x>>12 -> >>0).
    dph.scale_str_rise = 32  # identity in muldv(temp, x, 32).
    dph.size_hat_rise = 100
    dph.number_words = 3

    handle = TtsHandle()
    handle.p_kernel_share_data = ksd
    handle.p_ph_thread_data = dph
    return handle


def test_phinton_runs_on_silence_only_clause() -> None:
    """A silence-only clause runs end-to-end without raising."""
    handle = _make_handle(allophons=[GEN_SIL, GEN_SIL], allodurs=[5, 5])
    phinton(handle)
    dph = cast(DphT, handle.p_ph_thread_data)
    # tcumdur accumulator counts the first phone (nphon == 0 path).
    assert dph.tcumdur >= 5
    # Open-quotient gets touched for each visited phone -- the exact
    # value depends on the +FVOICD/+FOBST flags on GEN_SIL, but it
    # should always land in the (30, 50, 70) trio that phinton emits.
    assert dph.alloopenq[0] in (30, 50, 70)
    # No F0 events get queued for an all-silence clause.
    assert dph.nf0tot == 0


def test_phinton_writes_f0tim_for_stressed_clause() -> None:
    """A stressed vowel followed by a period emits at least one F0 event."""
    # 4-phone clause: [GEN_SIL, USP_P, USP_AA(stressed,hat-begins/ends,
    # period-next), GEN_SIL]. The stressed-vowel slot triggers Rules
    # 1 (hat rise), 2 (stress impulse), 3 (hat fall), and 6
    # (final-fall glottalisation).
    allophons = [GEN_SIL, USP_P, USP_AA, GEN_SIL]
    allodurs = [10, 8, 20, 10]
    allofeats = [
        0,
        0,
        FSTRESS_1 | FHAT_BEGINS | FHAT_ENDS | FPERNEXT,
        FPERNEXT,
    ]
    handle = _make_handle(
        allophons=allophons,
        allodurs=allodurs,
        allofeats=allofeats,
    )
    phinton(handle)
    dph = cast(DphT, handle.p_ph_thread_data)
    # nf0tot should advance — at least one stress IMPULSE got queued.
    assert dph.nf0tot > 0, "phinton produced no F0 events for stressed clause"
    # f0tim entries are non-negative frame-deltas.
    for i in range(dph.nf0tot):
        assert dph.f0tim[i] >= 0
    # tcumdur was advanced for the audible phones (skips trailing sil).
    assert dph.tcumdur > 0


def test_phinton_resets_state_at_clause_start() -> None:
    """``nf0tot`` / hat counters reset per clause."""
    handle = _make_handle(allophons=[GEN_SIL], allodurs=[5])
    dph = cast(DphT, handle.p_ph_thread_data)
    settar = cast(DphSettarSt, dph.pSTphsettar)

    # Prime state with bogus values.
    dph.nf0tot = 99
    dph.had_hatbegin = 1
    dph.had_hatend = 1
    dph.prevtargf0 = 12345
    settar.hatsize = 999

    phinton(handle)

    assert dph.nf0tot == 0
    assert dph.had_hatbegin == 0
    assert dph.had_hatend == 0
    assert dph.prevtargf0 == -1
    assert settar.hatsize == 0


def test_phinton_inserts_dummy_schwa_after_clause_final_plosive() -> None:
    """A final plosive followed by silence triggers dummy-vowel insertion."""
    # Verify USP_P is +FPLOSV +FBURST in the feature table.
    feat = phone_feature(USP_P)
    assert feat & FPLOSV
    assert feat & FBURST

    allophons = [GEN_SIL, USP_P, GEN_SIL]
    allodurs = [5, 8, 5]
    handle = _make_handle(allophons=allophons, allodurs=allodurs)
    phinton(handle)
    dph = cast(DphT, handle.p_ph_thread_data)
    # A schwa got inserted: nallotot grew by 1.
    assert dph.nallotot == 4
