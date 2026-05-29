"""Verify the PH ROM tables match the active C source ROM byte-for-byte.

The active voice ROM in the C build is selected by
``dectalkf_klsyn.h:296`` -- ``#define VOICE_ROM_DECTALK_1996M_43F``.
That gates ``ph_romi.c:69`` to ``#include "p_us_rom_dectalk_1996m_43f.c"``
rather than ``p_us_rom.c``.

The two ROM files differ in the per-allophone duration tables *and* in
the formant / bandwidth / locus *target* tables. Issue #229 re-ported
the target family from the active file:

- ``us_maltar`` / ``us_femtar`` -- F1-F3 + B1-B3 + AV targets, laid out
  in 57-phone blocks (the active ROM defines ``US_TOT_ALLOPHONES == 57``,
  not the BETA5 ``71``).
- ``us_maldip`` / ``us_femdip`` -- diphthong-transition values.
- ``us_maleloc`` / ``us_femloc`` -- formant-locus targets.
- ``us_plocu`` -- per-phone locus pointers (57-strided).

The active C source embeds in-table integer arithmetic (e.g. ``180+80``,
``300+100``); the parser below evaluates it so the comparison is on
final values.

Tables that are *not* yet re-ported (the amplitude tables and the
per-phone gesture/prosody tables) are still asserted against the legacy
``p_us_rom.c`` reference. Tables that are voice-independent
(``us_place``, ``us_begtyp``) match both files. Skips when
``DECTALK_SRC`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.include.phoneme_codes import US_TOT_ALLOPHONES
from dectalk.ph import phoneme_features as pf
from dectalk.ph import rom_tables as rt
from dectalk.ph.phoneme_features import FOBST

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
# Active ROM per dectalkf_klsyn.h:296 (#define VOICE_ROM_DECTALK_1996M_43F).
_C_FILE = _SRC_ROOT / "src/dapi/src/ph/p_us_rom_dectalk_1996m_43f.c"
# Reference/legacy ROM file -- used for the table set we haven't yet
# moved over to the 1996m_43f values (amplitudes, per-phone prosody).
_C_FILE_REF = _SRC_ROOT / "src/dapi/src/ph/p_us_rom.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file() or not _C_FILE_REF.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _eval_c_int_expr(token: str) -> int:
    """Evaluate one C integer expression (``180+80``, ``-2``, ``2005+300``).

    The active ROM keeps arithmetic in the table literals; we must
    evaluate it to compare against the Python (which stores final
    values). Only ``+ - * / ( )`` over decimal integers appear in the
    target / dip / locus tables (no octal -- those leading-zero literals
    only occur in the flag tables, which take a different code path).
    The expression is regex-validated to a safe integer-arithmetic
    grammar before evaluation.
    """
    if not re.fullmatch(r"[-+*/()\s0-9]+", token):
        raise AssertionError(f"unexpected token in C ROM table: {token!r}")
    # Input restricted to integer arithmetic by the regex guard above.
    return int(eval(token))


def _parse_rom_table(name: str, path: Path) -> tuple[int, ...]:
    """Parse a ``[const ]short NAME[]? = { ... };`` initialiser.

    Strips C comments, splits on commas, and evaluates any in-table
    integer arithmetic.
    """
    text = path.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    # Drop C preprocessor lines that sit inside an initialiser body
    # (the legacy ROM keeps an ``#endif`` right after ``= {``).
    text = re.sub(r"^[ \t]*#.*$", "", text, flags=re.MULTILINE)
    m = re.search(
        rf"(?:const\s+)?short\s+{re.escape(name)}\s*\[\d*\]\s*=\s*\{{(.+?)\}}\s*;",
        text,
        re.DOTALL,
    )
    assert m is not None, f"could not find {name} in {path.name}"
    tokens = [t.strip() for t in m.group(1).split(",")]
    return tuple(_eval_c_int_expr(t) for t in tokens if t != "")


# Formant / bandwidth / locus target tables re-ported from the active
# ROM (issue #229). These are asserted EXACTLY (native active-ROM
# layout), not just on a prefix.
_TABLES_TARGET_ACTIVE: tuple[str, ...] = (
    "us_maltar", "us_femtar",
    "us_maldip", "us_femdip",
    "us_maleloc", "us_femloc",
    "us_plocu",
)  # fmt: skip

# Per-allophone tables sourced from the active ROM (numeric literals).
# The Python literal pads these to 71 entries (sentinel tail); compare
# only the C-defined 57-entry prefix. ``us_begtyp`` is voice-independent
# (identical in both ROM files) but written numerically in the active
# file, so we read it there.
_TABLES_PERPHONE_ACTIVE: tuple[str, ...] = (
    "us_inhdr", "us_mindur", "us_begtyp",
)  # fmt: skip

# Tables still on the legacy ROM (amplitudes + per-phone gesture/prosody),
# plus the voice-independent ``us_place`` flag table (the active ROM
# writes it with ``F*`` flag macros rather than numeric literals, so we
# read its numeric form from the reference file -- it is identical in
# both ROMs). Re-porting the amplitude/prosody tables is tracked
# separately; the formant targets (#229) do not depend on them.
_TABLES_REF_ROM: tuple[str, ...] = (
    "us_burdr", "us_f0segtars", "us_endtyp",
    "us_ptram", "us_malamp", "us_femamp",
    "us_place",
    "us_f0glstp", "us_f0_phrase_position", "us_f0_stress_level",
)  # fmt: skip

_TABLES: tuple[str, ...] = (
    _TABLES_TARGET_ACTIVE + _TABLES_PERPHONE_ACTIVE + _TABLES_REF_ROM + ("us_featb",)
)


def _parse_featb_active() -> tuple[int, ...]:
    """Parse the active ROM ``us_featb`` (it uses ``F*`` flag macros).

    The active ``p_us_rom_dectalk_1996m_43f.c`` writes each entry as a
    sum of feature-flag macros (e.g. ``FSYLL+FVOICD+FVOWEL+FSON1+FSONOR``).
    Resolve the flag names from :mod:`dectalk.ph.phoneme_features` (those
    constants are parity-checked separately) and evaluate the sum.

    This table is voice-ROM-dependent: the active ROM sets ``us_featb[0]``
    (SIL) to ``FSONOR`` alone, whereas the BETA5 ``p_us_rom.c`` set the
    ``FOBST`` bit too -- which corrupted the F1 ``-1`` sentinel through the
    fricative-F1-raise rule in ``us_gettar`` (issue #229).
    """
    text = _C_FILE.read_text(encoding="latin-1")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    m = re.search(r"short\s+us_featb\s*\[[^\]]*\]\s*=\s*\{(.+?)\}\s*;", text, re.DOTALL)
    assert m is not None, "could not find us_featb in active ROM"
    out: list[int] = []
    for raw_tok in m.group(1).split(","):
        tok = raw_tok.strip()
        if not tok:
            continue
        total = 0
        for raw_term in tok.split("+"):
            term = raw_term.strip()
            if term.isdigit():
                total += int(term)
            else:
                flag = getattr(pf, term, None)
                assert flag is not None, f"unknown feature flag {term!r} in us_featb"
                total += flag
        out.append(total)
    return tuple(out)


def test_featb_matches_active_rom() -> None:
    """``us_featb`` mirrors the active ROM (resolving its ``F*`` macros).

    Must track the active ROM: ``us_featb[0]`` (SIL) is ``FSONOR`` (no
    ``FOBST``), so the F1 ``-1`` sentinel is not corrupted by the
    fricative-F1-raise rule.
    """
    expected = _parse_featb_active()
    assert rt.us_featb == expected, "us_featb mismatch vs active ROM"
    # Guard the specific bit that drove the #229 F1 end-of-utterance bug.
    assert (rt.us_featb[0] & FOBST) == 0, "SIL must not be flagged FOBST"


def test_us_tot_allophones_is_active_value() -> None:
    """The active ROM uses ``US_TOT_ALLOPHONES == 57`` (l_all_ph.h)."""
    text = (_SRC_ROOT / "src/dapi/src/include/l_all_ph.h").read_text(encoding="latin-1")
    # The 57 branch is gated on VOICE_ROM_DECTALK_43 / _1996M_43F.
    assert re.search(
        r"VOICE_ROM_DECTALK_1996M_43F.*?#define\s+US_TOT_ALLOPHONES\s+57",
        text,
        re.DOTALL,
    )
    assert US_TOT_ALLOPHONES == 57


@pytest.mark.parametrize("name", _TABLES_TARGET_ACTIVE)
def test_target_table_matches_active_rom(name: str) -> None:
    """Each re-ported target table matches the active ROM byte-for-byte.

    These are stored in the active ROM's native layout (57-phone
    parameter blocks for ``us_maltar`` / ``us_femtar``; flat for the
    dip / locus tables; 57-strided for ``us_plocu``), so the whole
    tuple must equal the C array exactly -- no sentinel padding.
    """
    expected = _parse_rom_table(name, _C_FILE)
    assert getattr(rt, name) == expected, f"{name} mismatch vs active ROM"


@pytest.mark.parametrize("name", _TABLES_PERPHONE_ACTIVE)
def test_active_perphone_table_matches_c(name: str) -> None:
    """Each per-phone table mirrors the active ROM in its 57-entry prefix.

    The trailing entries (indices 57..70) in the Python literal are
    sentinel padding -- the C array stops at ``DF`` (index 56); the
    Python port keeps 71 entries to match the per-allophone table family.
    """
    expected = _parse_rom_table(name, _C_FILE)
    pyvals = getattr(rt, name)
    assert pyvals[: len(expected)] == expected, f"{name} mismatch in active prefix"


@pytest.mark.parametrize("name", _TABLES_REF_ROM)
def test_reference_rom_table_matches_c(name: str) -> None:
    """Each ``us_*`` table still on the legacy ROM matches p_us_rom.c."""
    expected = _parse_rom_table(name, _C_FILE_REF)
    assert getattr(rt, name) == expected, f"{name} mismatch vs legacy ROM"


def test_divergent_phone_targets_use_active_values() -> None:
    """Spot-check the phones #229 flagged: LL B2/B3 and IY B3.

    Active ``VOICE_ROM_DECTALK_1996M_43F``: LL B2/B3 = 65/120, IY B3 =
    260 (the BETA5 ``p_us_rom.c`` had 160/180 and 160). Indices use the
    57-phone stride: ``block * 57 + phone_code``.
    """
    stride = 57
    b2_block, b3_block = 4, 5
    ll, iy = 27, 1  # USPhoneme.LL, USPhoneme.IY
    assert rt.us_maltar[b2_block * stride + ll] == 65
    assert rt.us_maltar[b3_block * stride + ll] == 120
    assert rt.us_maltar[b3_block * stride + iy] == 260


def test_target_table_negative_offsets_index_dip_in_bounds() -> None:
    """Negative sentinels in ``us_maltar`` index into ``us_maldip`` (internal
    consistency of the re-ported pair)."""
    for tar, dip in ((rt.us_maltar, rt.us_maldip), (rt.us_femtar, rt.us_femdip)):
        for v in tar:
            if v < -1:
                assert 0 <= -v < len(dip)


def test_target_block_layout_is_57_strided() -> None:
    """``us_maltar`` / ``us_femtar`` are 57 phones x 7 parameter blocks."""
    expected = US_TOT_ALLOPHONES * 7
    assert len(rt.us_maltar) == expected
    assert len(rt.us_femtar) == expected


def test_per_phoneme_tables_have_71_entries() -> None:
    """The simple per-allophone tables all have 71 entries (padded)."""
    expected = 71
    for name in ("us_inhdr", "us_mindur", "us_burdr", "us_f0segtars",
                 "us_begtyp", "us_endtyp", "us_place", "us_ptram"):  # fmt: skip
        assert len(getattr(rt, name)) == expected, name


def test_global_prosody_tables_size() -> None:
    """Global prosody tables have their published sizes."""
    glottal_step_count = 6
    phrase_positions = 8
    stress_levels = 8
    assert len(rt.us_f0glstp) == glottal_step_count
    assert len(rt.us_f0_phrase_position) == phrase_positions
    assert len(rt.us_f0_stress_level) == stress_levels


def test_rom_tables_contain_no_garbage() -> None:
    """All values fit in a signed short (-32768 .. 32767)."""
    int16_min = -32768
    int16_max = 32767
    for name in _TABLES:
        for i, v in enumerate(getattr(rt, name)):
            assert int16_min <= v <= int16_max, f"{name}[{i}]={v}"
