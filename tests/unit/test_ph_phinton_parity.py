"""C-source parity test for ``phinton`` against ph_inton0.c.

The production ``ENGLISH_US`` + ``OLD_INTONATION_AND_TIMING`` build uses
``ph_inton0.c``, which defines ``phinton`` twice. The first (line ~154)
is the ``NWSNOAA`` / ``ENGLISH_UK`` variant; the **second** (line ~1325)
is the active US English one. We extract the second definition for the
structural assertions and exercise the Python port end-to-end.

The active engine is value-encoded: ``make_f0_command`` stores only
``f0tim`` + ``f0tar`` (no ``f0type``), and the command type lives in the
``tar`` value (0 = reset, even = STEP, odd = IMPULSE, >= 2000 = user).

Skips the C-source assertions when ``DECTALK_SRC`` / ``/tmp/dectalk-src``
is absent; the Python behavioural tests always run.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import cast

import pytest

from dectalk.include.usp_codes import USP_AA, USP_P
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.feature_bits import (
    FHAT_BEGINS,
    FPERNEXT,
    FSTRESS_1,
)
from dectalk.ph.inton_constants import NORMAL, PHONE_TARGETS_SPECIFIED, SINGING
from dectalk.ph.numeric_constants import NPHON_MAX
from dectalk.ph.phinton import (
    _US_F0_PHRASE_POSITION,
    _US_F0_STRESS_LEVEL,
    phinton,
)
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.utterance_constants import GEN_SIL

_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_C_FILE = _SRC / "src/dapi/src/ph/ph_inton0.c"
_ROM_FILE = _SRC / "src/dapi/src/ph/p_us_rom_dectalk_1996m_43f.c"

_c_skip = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read(path: Path) -> str:
    return path.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_active_phinton() -> str:
    """Return the body of the *second* (active US English) phinton."""
    text = _read(_C_FILE)
    headers = list(re.finditer(r"void\s+phinton\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)\s*\{", text))
    assert len(headers) >= 2, f"expected two phinton definitions, found {len(headers)}"
    start = headers[-1].end() - 1  # the '{'
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    raise AssertionError("unterminated phinton body")


# -- C-source structural assertions ----------------------------------------


@_c_skip
def test_signature_matches_c() -> None:
    """C signature: ``void phinton(LPTTS_HANDLE_T phTTS)``."""
    assert re.search(r"\bvoid\s+phinton\s*\(\s*LPTTS_HANDLE_T\s+\w+\s*\)", _read(_C_FILE))


@_c_skip
def test_active_body_uses_single_stress_and_phrase_tables() -> None:
    """Rule 2 indexes ``us_f0_stress_level`` + ``us_f0_phrase_position``."""
    body = _extract_active_phinton()
    assert "us_f0_stress_level[stresscur]" in body.replace(" ", "")
    assert "us_f0_phrase_position[" in body
    # The HLSYN per-gender tables are NOT referenced in the active engine.
    assert "f0_mstress_level" not in body
    assert "f0_fstress_level" not in body


@_c_skip
def test_active_body_hardcodes_q_and_comma_gestures() -> None:
    """Q-gestures 181/251 and comma gestures 71/101 are literals in the body."""
    body = _extract_active_phinton()
    assert re.search(r"make_f0_command\s*\(\s*pDph_t\s*,\s*4\s*,\s*181\b", body)
    assert re.search(r"make_f0_command\s*\(\s*pDph_t\s*,\s*4\s*,\s*251\b", body)
    assert re.search(r"make_f0_command\s*\(\s*pDph_t\s*,\s*6\s*,\s*181\b", body)
    assert re.search(r"make_f0_command\s*\(\s*pDph_t\s*,\s*4\s*,\s*71\b", body)


@_c_skip
def test_active_body_calls_make_f0_command_without_type() -> None:
    """make_f0_command is called in the 6-arg (no-``type``) form.

    The active calls pass ``(pDph_t, rulenumber, tar, delay, length,
    &cumdur)``; the second positional arg is a small rule number, not a
    ``type`` enum.
    """
    body = _extract_active_phinton()
    calls = re.findall(r"make_f0_command\s*\(\s*pDph_t\s*,\s*([A-Za-z0-9_+\- ]+?)\s*,", body)
    assert calls, "no make_f0_command calls found"
    # Every second-arg is a rule number (0..8) or a bare integer — never a
    # STEP/IMPULSE/GLIDE/USER type token.
    for second in calls:
        assert not re.search(r"STEP|IMPULSE|GLIDE|GLOTTAL|USER|F0_RESET", second), (
            f"unexpected type token in make_f0_command call: {second!r}"
        )


@_c_skip
def test_active_body_has_schwa_insertion() -> None:
    """Rule 9 inserts a USP_AX/USP_IX schwa with an NF25MS duration."""
    body = _extract_active_phinton()
    assert "USP_AX" in body
    assert "USP_IX" in body
    assert re.search(r"allodurs\s*\[\s*nphon\s*\+\s*1\s*\]\s*=\s*NF25MS", body)


@pytest.mark.skipif(not _ROM_FILE.is_file(), reason="active voice ROM not available")
def test_table_values_match_active_rom() -> None:
    """The Python F0 tables match p_us_rom_dectalk_1996m_43f.c."""
    text = _read(_ROM_FILE)

    def _parse(name: str) -> tuple[int, ...]:
        m = re.search(rf"{name}\s*\[\s*\]\s*=\s*\{{([^}}]+)\}}", text)
        assert m is not None, f"{name} not found in active ROM"
        return tuple(
            int(v.strip()) for v in m.group(1).split(",") if v.strip().lstrip("-").isdigit()
        )

    assert _parse("us_f0_stress_level") == _US_F0_STRESS_LEVEL
    assert _parse("us_f0_phrase_position") == _US_F0_PHRASE_POSITION


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
    dph = DphT()
    dph.pSTphsettar = DphSettarSt()

    n = len(allophons)
    pad = NPHON_MAX + 8 - n
    dph.allophons = list(allophons) + [GEN_SIL] * pad
    dph.allofeats = list(allofeats) if allofeats is not None else [0] * n
    dph.allofeats += [0] * (NPHON_MAX + 8 - len(dph.allofeats))
    dph.allodurs = list(allodurs) + [0] * pad
    dph.user_f0 = list(user_f0) if user_f0 is not None else [0] * (NPHON_MAX + 8)
    dph.user_offset = [0] * (NPHON_MAX + 8)
    dph.f0tar = [0] * NPHON_MAX
    dph.f0tim = [0] * NPHON_MAX

    dph.nallotot = n
    dph.f0mode = NORMAL
    dph.assertiveness = 4096  # frac4mul(x, 4096) == x (Q12 unity).
    dph.scale_str_rise = 32  # muldv(32, x, 32) == x.
    dph.size_hat_rise = 100
    dph.cbsymbol = 0

    handle = TtsHandle()
    handle.p_kernel_share_data = ksd
    handle.p_ph_thread_data = dph
    return handle


def test_phinton_runs_on_silence_only_clause() -> None:
    """A silence-only clause runs end-to-end and queues no F0 events."""
    handle = _make_handle(allophons=[GEN_SIL, GEN_SIL], allodurs=[5, 5])
    phinton(handle)
    dph = cast(DphT, handle.p_ph_thread_data)
    assert dph.nf0tot == 0
    assert dph.tcumdur >= 5


def test_phinton_emits_stress_impulse_value_encoded() -> None:
    """A stressed vowel queues the value-encoded stress IMPULSE (odd tar)."""
    allophons = [GEN_SIL, USP_P, USP_AA, GEN_SIL]
    allodurs = [10, 8, 20, 10]
    allofeats = [0, 0, FSTRESS_1 | FPERNEXT, FPERNEXT]
    handle = _make_handle(allophons=allophons, allodurs=allodurs, allofeats=allofeats)
    phinton(handle)
    dph = cast(DphT, handle.p_ph_thread_data)

    assert dph.nf0tot > 0
    queued = dph.f0tar[: dph.nf0tot]
    # Rule 2: tar = us_f0_stress_level[1] + us_f0_phrase_position[0] = 71 + 210
    # = 281 (scale_str_rise == 32 is identity), forced odd -> IMPULSE.
    expected = _US_F0_STRESS_LEVEL[1] + _US_F0_PHRASE_POSITION[0]
    assert expected == 281
    assert expected in queued, f"stress impulse {expected} not queued: {queued}"
    assert expected & 0o1, "stress impulse must be odd (IMPULSE-encoded)"
    # All f0tim deltas are non-negative.
    for i in range(dph.nf0tot):
        assert dph.f0tim[i] >= 0


def test_phinton_resets_state_at_clause_start() -> None:
    """``nf0tot`` / hat counters reset per clause."""
    handle = _make_handle(allophons=[GEN_SIL], allodurs=[5])
    dph = cast(DphT, handle.p_ph_thread_data)
    settar = cast(DphSettarSt, dph.pSTphsettar)

    dph.nf0tot = 99
    dph.had_hatbegin = 1
    dph.had_hatend = 1
    settar.hatsize = 999

    phinton(handle)

    assert dph.nf0tot == 0
    assert dph.had_hatbegin == 0
    assert dph.had_hatend == 0
    assert settar.hatsize == 0


def test_phinton_inserts_dummy_schwa_after_clause_final_plosive() -> None:
    """A final plosive followed by silence triggers dummy-vowel insertion."""
    handle = _make_handle(allophons=[GEN_SIL, USP_P, GEN_SIL], allodurs=[5, 8, 5])
    phinton(handle)
    dph = cast(DphT, handle.p_ph_thread_data)
    # A schwa got inserted: nallotot grew by 1.
    assert dph.nallotot == 4


def test_phinton_hat_rise_is_even_step_encoded() -> None:
    """Rule 1 hat-rise queues an even (STEP-encoded) tar."""
    allophons = [GEN_SIL, USP_AA, GEN_SIL]
    allodurs = [10, 20, 10]
    # +FHAT_BEGINS on the syllabic vowel arms the hat rise.
    allofeats = [0, FHAT_BEGINS, 0]
    handle = _make_handle(allophons=allophons, allodurs=allodurs, allofeats=allofeats)
    phinton(handle)
    dph = cast(DphT, handle.p_ph_thread_data)
    assert dph.nf0tot > 0
    # The hat-rise step is size_hat_rise (100) made even+nonzero: 100 & 0o37776
    # | 0o2 == 102. Even -> STEP-encoded.
    queued = dph.f0tar[: dph.nf0tot]
    assert 102 in queued, f"hat-rise STEP 102 not queued: {queued}"
    assert 102 % 2 == 0


def test_phinton_runs_rule9_in_phone_targets_mode() -> None:
    """Rule 0 ``goto skiprules`` still runs Rule 9 (schwa) in user-F0 modes."""
    for mode in (PHONE_TARGETS_SPECIFIED, SINGING):
        handle = _make_handle(allophons=[GEN_SIL, USP_P, GEN_SIL], allodurs=[5, 8, 5])
        dph = cast(DphT, handle.p_ph_thread_data)
        dph.f0mode = mode
        phinton(handle)
        assert dph.nallotot == 4, f"mode {mode} dropped Rule 9: nallotot={dph.nallotot}"
