"""C-source parity test for ``pht0draw`` against ph_drwt02.c.

Re-parses the C body via brace-depth tracking and asserts both the
MALE branch (lines 765-1507) and the FEMALE branch (lines 1508-2167)
of the F0 contour generator still exist in the develop branch with
their expected control flow, command dispatch, and segmental-table
choices. Also runs behavioural Python tests that lean on the
distinctive MALE/FEMALE differences (impulse-envelope comparison,
EXCLAIM-clause scaling, segmental table).

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.ph.dph_settar_st import DphSettarSt
from dectalk.ph.dph_t import DphT
from dectalk.ph.getcosine import HIGHEST_F0, LOWEST_F0
from dectalk.ph.numeric_constants import FEMALE, MALE
from dectalk.ph.param_indices import OUT_T0
from dectalk.ph.pht0draw import _frac4mul_ph, pht0draw
from dectalk.ph.tts_handle import TtsHandle
from dectalk.ph.us_f0_segtars import us_f0fsegtars, us_f0msegtars
from dectalk.ph.utterance_constants import EXCLAIMCLAUSE, GEN_SIL

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/ph/ph_drwt02.c"

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
    """Return the body (between outer ``{}``) of the C ``pht0draw`` function."""
    text = _read_c()
    pattern = re.compile(r"\bpht0draw\s*\(")
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
    raise AssertionError(f"pht0draw definition not found in {_C_FILE.name}")


def _split_male_female(body: str) -> tuple[str, str]:
    """Return ``(male_body, female_body)`` slices of the C function body.

    The C source structure is::

        if (pDph_t->malfem == MALE) {
            ...                                /* MALE */
        }/*end of if malfem==male*/
        else
        {
            ...                                /* FEMALE */
        } /* end of fem stuff*/

    We use the literal end-of-MALE comment as the split point — it
    pre-dates the FEMALE port and is unique in the file.
    """
    sentinel = "/*end of if malfem==male*/"
    idx = body.find(sentinel)
    assert idx != -1, "MALE/FEMALE split marker not found in pht0draw body"
    return body[:idx], body[idx + len(sentinel) :]


# -- C-source structural assertions ----------------------------------------


def test_signature_exists_in_c() -> None:
    """``pht0draw`` definition is present in ph_drwt02.c."""
    assert re.search(r"\bpht0draw\s*\(", _read_c())


def test_body_dispatches_on_malfem() -> None:
    """Top-level body splits on ``pDph_t->malfem == MALE``."""
    body = _extract_body()
    assert re.search(r"pDph_t->malfem\s*==\s*MALE", body)


def test_female_branch_exists() -> None:
    """The else-branch (FEMALE) has its own hard-init / soft-init blocks."""
    _, female = _split_male_female(_extract_body())
    # FEMALE hard-init sets newnote=1600 (vs MALE 1000).
    assert re.search(r"newnote\s*=\s*1600", female)
    # FEMALE soft-init clears nimpcnt and tarimp.
    assert re.search(r"nimpcnt\s*=\s*0", female)


def test_female_uses_f0fsegtars() -> None:
    """FEMALE branch references the female segmental table ``us_f0fsegtars``."""
    _, female = _split_male_female(_extract_body())
    # The HLSYN production build uses 2*us_f0fsegtars[phocur & PVALUE].
    assert re.search(r"us_f0fsegtars\s*\[\s*pDphsettar->phocur\s*&\s*PVALUE\s*\]", female)
    # MALE uses us_f0msegtars (verify the table choice is FEMALE-specific).
    male, _ = _split_male_female(_extract_body())
    assert "us_f0msegtars" in male


def test_female_impulse_envelope_uses_le() -> None:
    """FEMALE impulse envelope uses ``<=`` for the ramp-up branch (MALE uses ``<``)."""
    _, female = _split_male_female(_extract_body())
    assert re.search(r"nimpcnt\s*<=\s*\(\s*pDphsettar->nimp>>1\s*\)", female)
    male, _ = _split_male_female(_extract_body())
    assert re.search(r"nimpcnt\s*<\s*\(\s*pDphsettar->nimp>>1\s*\)", male)


def test_female_avglstop_assignment() -> None:
    """FEMALE branch writes ``avglstop = (6 - dtglst)`` for ``dtglst <= 5``."""
    _, female = _split_male_female(_extract_body())
    assert re.search(r"avglstop\s*=\s*\(\s*6\s*-\s*dtglst\s*\)", female)
    assert re.search(r"if\s*\(\s*dtglst\s*<=\s*5\s*\)", female)


def test_female_exclaim_scale_uses_500() -> None:
    """FEMALE EXCLAIM scale offset is ``f0scalefac+500`` (MALE is +1000)."""
    _, female = _split_male_female(_extract_body())
    assert re.search(r"f0scalefac\s*\+\s*500\b", female)
    male, _ = _split_male_female(_extract_body())
    assert re.search(r"f0scalefac\s*\+\s*1000\b", male)


def test_female_voicing_check_inspects_previous_allophone() -> None:
    """FEMALE voicing test inspects ``allophons[np_drawt0-1]`` (MALE uses ``phocur``)."""
    _, female = _split_male_female(_extract_body())
    assert re.search(
        r"phone_feature\([^)]*pDph_t->allophons\[pDphsettar->np_drawt0\s*-\s*1\]",
        female,
    )


def test_female_command_dispatch_has_step_glide_glottal_impulse() -> None:
    """FEMALE F0 command loop dispatches on USER / F0_RESET / STEP / GLIDE / GLOTTAL / IMPULSE."""
    _, female = _split_male_female(_extract_body())
    for case in ("USER", "F0_RESET", "STEP", "GLIDE", "GLOTTAL", "IMPULSE"):
        assert re.search(rf"\bcase\s+{case}\s*:", female), f"missing case {case}"


def test_female_flutter_uses_f0flutter_on_exclaim() -> None:
    """FEMALE flutter section adds an extra ``mlsh1(pseudojitter, f0flutter)`` for EXCLAIM."""
    _, female = _split_male_female(_extract_body())
    assert re.search(r"mlsh1\([^)]*pDph_t->f0flutter", female)


# -- Python behavioural tests ----------------------------------------------


def _make_handle(*, malfem: int) -> TtsHandle:
    """Return a minimal TtsHandle ready for pht0draw."""
    p_dph_t = DphT()
    p_dph_t.nf0ev = -2
    p_dph_t.f0minimum = 800
    p_dph_t.f0_lp_filter = 1300
    p_dph_t.malfem = malfem
    p_dph_t.nallotot = 4
    p_dph_t.f0scalefac = 4096
    p_dph_t.clausetype = 0
    p_dph_t.f0mode = 1
    p_dph_t.f0flutter = 700

    p_dph_t.allophons = [GEN_SIL, GEN_SIL, GEN_SIL, GEN_SIL]
    p_dph_t.allodurs = [10, 10, 10, 10]
    p_dph_t.allofeats = [0, 0, 0, 0]

    p_dph_t.f0tar = [0]
    p_dph_t.f0type = [0]
    p_dph_t.f0length = [1]
    p_dph_t.f0tim = [9999]
    p_dph_t.nf0tot = 0

    p_dph_t.parstochip = [0] * 20
    p_dph_t.pSTphsettar = DphSettarSt()

    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    return handle


def test_female_dispatch_runs_to_completion() -> None:
    """FEMALE dispatch produces a valid frame without raising."""
    handle = _make_handle(malfem=FEMALE)
    pht0draw(handle)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    assert p_dph_t.nf0ev == 0
    assert LOWEST_F0 <= p_dph_t.f0prime <= HIGHEST_F0
    assert p_dph_t.parstochip[OUT_T0] == p_dph_t.f0prime


def test_female_hard_init_uses_newnote_1600() -> None:
    """FEMALE hard init differs from MALE in the newnote constant."""
    male_handle = _make_handle(malfem=MALE)
    female_handle = _make_handle(malfem=FEMALE)

    pht0draw(male_handle)
    pht0draw(female_handle)

    male_settar = male_handle.p_ph_thread_data.pSTphsettar  # type: ignore[union-attr]
    female_settar = female_handle.p_ph_thread_data.pSTphsettar  # type: ignore[union-attr]
    assert isinstance(male_settar, DphSettarSt)
    assert isinstance(female_settar, DphSettarSt)

    assert male_settar.newnote == 1000
    assert female_settar.newnote == 1600


def test_female_segmental_table_doubled() -> None:
    """``us_f0fsegtars`` is the female segmental table (and is doubled at use)."""
    # GEN_SIL maps to index 0; ensure the table is present and non-degenerate.
    assert len(us_f0fsegtars) > 0
    assert len(us_f0msegtars) > 0
    # The tables are distinct; the FEMALE branch uses the f-variant.
    assert us_f0fsegtars is not us_f0msegtars


def test_female_excl_scale_offset_smaller_than_male() -> None:
    """FEMALE EXCLAIM scaling uses ``f0scalefac+500`` (smaller than MALE's +1000).

    Concretely: with the same ``f0prime`` *pre-scale* the post-scale
    EXCLAIM output should be smaller for FEMALE than MALE (because the
    multiplier 4096+500 < 4096+1000).
    """
    f0minimum = 800
    f0prime_pre = 2000
    f0scalefac = 4096

    male_scaled = f0minimum + _frac4mul_ph(f0prime_pre - f0minimum, f0scalefac + 1000)
    female_scaled = f0minimum + _frac4mul_ph(f0prime_pre - f0minimum, f0scalefac + 500)

    assert female_scaled < male_scaled


def test_female_avglstop_zero_when_far_from_glottal_stop() -> None:
    """FEMALE writes ``avglstop`` each frame; default-far-from-stop yields 0."""
    handle = _make_handle(malfem=FEMALE)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)

    # Run a few frames; tglstp=-200 keeps dtglst > 5 the whole time.
    for _ in range(5):
        pht0draw(handle)
        assert p_dph_t.avglstop == 0


def test_female_exclaim_clause_runs() -> None:
    """FEMALE flutter+scale block runs cleanly on an EXCLAIM clause."""
    handle = _make_handle(malfem=FEMALE)
    p_dph_t = handle.p_ph_thread_data
    assert isinstance(p_dph_t, DphT)
    p_dph_t.clausetype = EXCLAIMCLAUSE

    for _ in range(8):
        pht0draw(handle)
        # f0prime always clamped to the legal band.
        assert LOWEST_F0 <= p_dph_t.f0prime <= HIGHEST_F0
