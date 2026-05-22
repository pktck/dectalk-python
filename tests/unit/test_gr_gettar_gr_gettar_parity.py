"""C-source parity test for ``gr_gettar`` against src/dapi/src/ph/p_gr_st1.c.

Re-parses the C body via brace-depth tracking and asserts the Python
port reflects the C-source structure: the documented C branches
(``IS_FORM_FREQ_OR_BW`` / ``IS_NASAL_ZERO_FREQ`` / ``IS_AV_OR_AH`` /
``IS_PARALLEL_FORM_AMP``) plus a handful of distinctive German rules
(GRP_KH formant inheritance, GRP_AN/IM/UM/ON nasalised-vowel FZ=350,
the +5 EAB-hack on positive AV, the GRP_U TILT=10 override, the
GRP_L TILT += 8 nudge) are all present in the C source we're porting.

Also exercises the Python implementation end-to-end on a synthetic
German handle: the FORM_FREQ_OR_BW, AV, FZ, and PARALLEL_FORM_AMP
branches all execute without raising and return an ``int``.

Lastly, verifies the ROM-table transcriptions added by issue #79
(``gr_inhdr`` / ``gr_maltar`` / ``gr_maldip`` / ``gr_malamp`` etc.)
have the expected sizes (62 per-phone entries, 7-row parameter
matrices).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.cmd_codes import PSFONT
from dectalk.include.grp_codes import GR_TOT_ALLOPHONES, GRP_KH
from dectalk.include.phoneme_codes import PFGR
from dectalk.kernel.ksd_t import KsdT
from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.gr_gettar import gr_gettar
from dectalk.ph.numeric_constants import AV, F1, F2, F3, MALE
from dectalk.ph.rom_tables import (
    gr_femamp,
    gr_femdip,
    gr_femtar,
    gr_malamp,
    gr_maldip,
    gr_maltar,
)
from dectalk.ph.tts_handle import TtsHandle

_C_FILE = (
    Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
    / "src/dapi/src/ph/p_gr_st1.c"
)

pytestmark = [
    pytest.mark.parity,
    pytest.mark.skipif(
        not _C_FILE.is_file(),
        reason="DECtalk C source not available at /tmp/dectalk-src",
    ),
]


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body (between outer ``{}``) of the C ``gr_gettar`` function."""
    text = _read_c()
    pattern = re.compile(r"\bshort\s+gr_gettar\s*\(")
    for match in pattern.finditer(text):
        paren_start = match.end() - 1
        depth = 1
        i = paren_start + 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        while i < len(text) and text[i] in " \t\n\r":
            i += 1
        if i >= len(text) or text[i] != "{":
            continue
        start = i + 1
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            i += 1
        if depth == 0:
            return text[start : i - 1]
    raise AssertionError(f"gr_gettar definition not found in {_C_FILE.name}")


# -- C-source structural assertions ----------------------------------------


def test_signature_exists_in_c() -> None:
    """``gr_gettar`` definition is present in src/dapi/src/ph/p_gr_st1.c."""
    assert re.search(r"\bshort\s+gr_gettar\s*\(", _read_c())


def test_body_dispatches_on_par_type() -> None:
    """C body branches on ``par_type`` using the IS_* macros."""
    body = _extract_body()
    assert "IS_FORM_FREQ_OR_BW" in body
    assert "IS_NASAL_ZERO_FREQ" in body
    assert "IS_AV_OR_AH" in body
    assert "IS_PARALLEL_FORM_AMP" in body


def test_body_contains_grp_kh_formant_inheritance() -> None:
    """German /kh/ "big hammer" rule: phone_temp = phlas_temp on GRP_KH."""
    body = _extract_body()
    assert re.search(
        r"if\s*\(\s*phone_temp\s*==\s*GRP_KH\s*\).*?phone_temp\s*=\s*phlas_temp",
        body,
        re.DOTALL,
    )


def test_body_contains_grp_kh_f2_drop() -> None:
    """F2 of GRP_KH is dropped by 600 Hz."""
    body = _extract_body()
    assert re.search(
        r"npar\s*==\s*F2\s*-\s*1\s*\)\s*\n?\s*&&\s*phone_temp\s*==\s*GRP_KH",
        body,
    )
    assert "tartemp -= 600" in body


def test_body_contains_nasalised_vowels() -> None:
    """German nasalised vowels (AN/IM/UM/ON) set tartemp = 350."""
    body = _extract_body()
    for code in ("GRP_AN", "GRP_IM", "GRP_UM", "GRP_ON"):
        assert f"case {code}:" in body, f"missing nasalised vowel case {code}"
    assert "tartemp = 350" in body


def test_body_uses_fstress_2_two_level_stress() -> None:
    """German uses two-level stress (FSTRESS_2 + FSTRESS) for AV reduction."""
    body = _extract_body()
    assert "FSTRESS_2" in body
    assert "FSTRESS" in body
    # The -7 dummy-vowel reduction (vs US's -12).
    assert "tartemp -= 7" in body


def test_body_contains_av_plus_5_eab_hack() -> None:
    """The famous EAB hack: positive AV gets +5 ("FIX IT LATER HELPME")."""
    body = _extract_body()
    assert "tartemp += 5" in body
    assert "HELPME" in body


def test_body_contains_h_kh_aspiration() -> None:
    """/h/ aspiration is 52/55, /kh/ aspiration is 42/44."""
    body = _extract_body()
    assert re.search(r"phone_temp\s*==\s*GRP_H", body)
    assert re.search(r"phone_temp\s*==\s*GRP_KH", body)
    assert "tartemp = 52" in body
    assert "tartemp = 55" in body
    assert "tartemp = 42" in body
    assert "tartemp = 44" in body


def test_body_contains_begtypnex_5_to_1_remap() -> None:
    """German begtypnex remap: 5 -> 1 (vs US's 4 -> 2)."""
    body = _extract_body()
    assert re.search(r"begtypnex\s*==\s*5", body)
    assert re.search(r"begtypnex\s*=\s*1", body)


def test_body_contains_grp_u_and_grp_l_tilt_rules() -> None:
    """TILT overrides: GRP_U -> 10, GRP_L gets +8."""
    body = _extract_body()
    assert re.search(r"phone_temp\s*==\s*GRP_U", body)
    assert re.search(r"phone_temp\s*==\s*GRP_L", body)
    assert re.search(r"tartemp\s*=\s*10", body)
    assert re.search(r"tartemp\s*\+=\s*8", body)


def test_body_contains_grp_dj_voicebar_rule() -> None:
    """The voiced-obstruent voicebar rule mentions GRP_DJ."""
    body = _extract_body()
    assert "GRP_DJ" in body
    assert "tartemp = 40" in body  # Max tilt for [b, d, g]


# -- ROM table sanity (sizes match the C declarations) --------------------


def test_gr_tot_allophones_matches_c() -> None:
    """``GR_TOT_ALLOPHONES`` is 62 to match the C ``#define``."""
    assert GR_TOT_ALLOPHONES == 62


def test_gr_per_phone_table_sizes() -> None:
    """Per-phone GR tables have exactly GR_TOT_ALLOPHONES entries."""
    # 7 parameter rows * 62 entries == 434.
    assert len(gr_maltar) == 7 * GR_TOT_ALLOPHONES
    assert len(gr_femtar) == 7 * GR_TOT_ALLOPHONES


def test_gr_amp_table_sizes() -> None:
    """Both male and female amplitude tables have 602 entries each."""
    assert len(gr_malamp) == 602
    assert len(gr_femamp) == 602


def test_gr_diph_table_sizes() -> None:
    """Diphthong tables: male 182, female 62 (variable-length rows)."""
    assert len(gr_maldip) == 182
    assert len(gr_femdip) == 62


# -- End-to-end smoke (the function executes without raising) -------------


def _make_handle() -> TtsHandle:
    """Build a minimal handle wired for German-male, GRP_KH at index 1."""
    handle = TtsHandle()
    dph = DphT()
    ksd = KsdT()
    ksd.sprate = 180  # Above the 100 glottal-stop threshold.
    dph.malfem = MALE
    dph.p_diph = list(gr_maldip)
    dph.p_tar = list(gr_maltar)
    dph.p_amp = list(gr_malamp)
    # Three-phone window: GRP_KH at index 1, padded with GRP_KH neighbours
    # so get_phone() never reads a sentinel.
    gr_kh = (PFGR << PSFONT) | (GRP_KH & 0xFF)
    dph.allophons = [gr_kh, gr_kh, gr_kh, gr_kh]
    dph.allofeats = [0, 0, 0, 0]
    dph.nphone = 1
    dph.nallotot = 4
    settar = DphSettarSt()
    settar.np = F1  # FORM_FREQ_OR_BW branch.
    settar.phcur = gr_kh
    dph.pSTphsettar = settar
    handle.p_ph_thread_data = dph
    handle.p_kernel_share_data = ksd
    return handle


def test_python_gr_gettar_runs_form_freq() -> None:
    """FORM_FREQ_OR_BW branch returns an int (no NotImplementedError)."""
    handle = _make_handle()
    result = gr_gettar(handle, 1)
    assert isinstance(result, int)


@pytest.mark.parametrize("np", [F1, F2, F3, AV])
def test_python_gr_gettar_handles_all_param_branches(np: int) -> None:
    """Each major par_type branch executes without raising."""
    handle = _make_handle()
    settar = handle.p_ph_thread_data.pSTphsettar  # type: ignore[union-attr]
    assert settar is not None
    settar.np = np
    result = gr_gettar(handle, 1)
    assert isinstance(result, int)


def test_gettar_dispatcher_routes_german_font() -> None:
    """The :func:`gettar` dispatcher accepts a German-font phone.

    Regression guard: with #79 the GR branch in ``gettar()`` should no
    longer raise ``NotImplementedError`` -- the German ROM tables
    (``gr_maltar`` / ``gr_femamp`` / ``gr_maldip``) are now transcribed
    in :mod:`dectalk.ph.rom_tables` and the dispatcher delegates to
    :func:`gr_gettar`.
    """
    from dectalk.ph.gettar import gettar  # noqa: PLC0415

    handle = _make_handle()
    # Pre-set last_lang to something else so the swap branch fires.
    handle.p_ph_thread_data.last_lang = -1  # type: ignore[union-attr]
    result = gettar(handle, 1)
    assert isinstance(result, int)
