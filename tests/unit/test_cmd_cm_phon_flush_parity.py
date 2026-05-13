"""C-source parity test for ``cm_phon_flush`` against ``cm_phon.c``.

Re-parses the C function body via brace-depth tracking and asserts:

- The four key shift / mask operations the Python port relies on
  (``temp <<= 10`` for the type field, ``temp <<= 2`` for the value
  field, ``temp <<= 6`` for the delay field, the syl_count
  ``& 0x003F`` mask).
- The percent-bias branches (``> 900`` / ``< -900``) that toggle
  ``pipe_values[1] |= 0x0001`` and adjust the magnitude by 900.
- The ``pKsd_t->lang_curr == LANG_english`` dispatch (and the other
  ``LANG_*`` arms) that route ``PFUSA`` / ``PFUK`` / ``PFGR`` / etc.
  into ``params[0]`` via ``<< PSFONT``.

Behavioural tests of the Python port cover the bit-packing for a
canonical input, the English-language font selection, and the
percent-bias rounding for delays exceeding +/-900.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from dectalk.cmd.cm_phon_flush import PhonFlushPacket, cm_phon_flush
from dectalk.include.cmd_codes import PSFONT, PSNEXTRA
from dectalk.include.phoneme_codes import PFGR, PFUSA
from dectalk.kernel.lang_codes import (
    LANG_english,
    LANG_german,
    LANG_italian,
    LANG_japanese,
    LANG_none,
)

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "src/dapi/src/cmd/cm_phon.c"

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


# --------------------------------------------------------------------------
# Helpers: extract the cm_phon_flush body from cm_phon.c.
# --------------------------------------------------------------------------


def _read_cm_phon_c() -> str:
    """Read cm_phon.c with CRLF endings normalised to LF."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Locate ``cm_phon_flush`` and return its body via brace-depth tracking."""
    text = _read_cm_phon_c()
    decl = re.search(r"void\s+cm_phon_flush\s*\(", text)
    assert decl is not None, "cm_phon_flush declaration not found"
    brace_start = text.index("{", decl.end())
    depth = 1
    i = brace_start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    assert depth == 0, "cm_phon_flush body braces never balance"
    return text[brace_start + 1 : i - 1]


# --------------------------------------------------------------------------
# Structural C-source assertions.
# --------------------------------------------------------------------------


def test_body_contains_type_shift_by_10() -> None:
    """The C body shifts the 4-bit type field by 10 positions."""
    body = _extract_body()
    assert re.search(r"temp\s*<<=\s*10\s*;", body), (
        "Expected `temp <<= 10` for the type field in pipe[1]"
    )


def test_body_contains_value_shift_by_2() -> None:
    """The C body shifts the 10-bit value field by 2 positions."""
    body = _extract_body()
    assert re.search(r"temp\s*<<=\s*2\s*;", body), (
        "Expected `temp <<= 2` for the value field in pipe[1]"
    )


def test_body_contains_delay_shift_by_6() -> None:
    """The C body shifts the 10-bit delay field by 6 positions."""
    body = _extract_body()
    assert re.search(r"temp\s*<<=\s*6\s*;", body), (
        "Expected `temp <<= 6` for the delay field in pipe[2]"
    )


def test_body_contains_syl_count_mask() -> None:
    """The C body masks the syl_count to 6 bits with ``0x003F``."""
    body = _extract_body()
    assert re.search(r"temp\s*&=\s*0x003F\s*;", body), (
        "Expected `temp &= 0x003F` for the syl_count field"
    )


def test_body_contains_value_mask_0x0ffc() -> None:
    """The C body masks the value to bits 2..11 with ``0x0FFC``."""
    body = _extract_body()
    assert re.search(r"&\s*0x0FFC", body), (
        "Expected the value-field mask `& 0x0FFC` in pipe[1] packing"
    )


def test_body_handles_percent_above_900() -> None:
    """``temp > 900`` sets the percent bit and subtracts 900."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*temp\s*>\s*900\s*\)", body)
    assert re.search(r"temp\s*-=\s*900\s*;", body)


def test_body_handles_percent_below_minus_900() -> None:
    """``temp < -900`` sets the percent bit and adds 900."""
    body = _extract_body()
    assert re.search(r"if\s*\(\s*temp\s*<\s*-?\s*900\s*\)", body)
    assert re.search(r"temp\s*\+=\s*900\s*;", body)


def test_body_sets_percent_bit_via_or_0x0001() -> None:
    """The percent bit lands in bit 0 of pipe[1] via ``|= 0x0001``."""
    body = _extract_body()
    assert re.search(r"pipe_values\[1\]\s*\|=\s*0x0001", body), (
        "Expected percent-bit OR into pipe[1]"
    )


def test_body_dispatches_on_lang_curr_english() -> None:
    """The C body has a ``LANG_english`` arm in the language switch."""
    body = _extract_body()
    assert re.search(r"pKsd_t\s*->\s*lang_curr", body), (
        "Expected `pKsd_t->lang_curr` access in the language dispatch"
    )
    assert re.search(r"case\s+LANG_english", body), (
        "Expected `case LANG_english` in the language switch"
    )


def test_body_has_all_six_language_arms() -> None:
    """Every Linux-active language gets its own switch arm with a font code."""
    body = _extract_body()
    expected = {
        "LANG_english": "PFUSA",
        "LANG_british": "PFUK",
        "LANG_german": "PFGR",
        "LANG_spanish": "PFSP",
        "LANG_latin_american": "PFLA",
        "LANG_french": "PFFR",
    }
    for lang, font in expected.items():
        assert re.search(rf"case\s+{lang}", body), f"missing `case {lang}`"
        assert re.search(rf"{font}\s*<<\s*PSFONT", body), (
            f"missing `{font} << PSFONT` font OR for {lang}"
        )


def test_body_uses_psnextra_for_extra_count() -> None:
    """The C body merges ``(param_index - 1) << PSNEXTRA`` into params[0]."""
    body = _extract_body()
    assert re.search(r"param_index\s*-\s*1\s*\)\s*<<\s*PSNEXTRA", body), (
        "Expected `(param_index - 1) << PSNEXTRA` extra-slot merge"
    )


def test_body_skips_font_when_params0_high_byte_set() -> None:
    """The ``params[0] & 0xff00`` shortcut bypasses the font dispatch."""
    body = _extract_body()
    assert re.search(r"params\[0\]\s*&\s*0xff00", body), (
        "Expected `params[0] & 0xff00` shortcut check"
    )


def test_body_gated_by_phoneme_speak() -> None:
    """The packing is gated by ``pKsd_t->phoneme_mode & PHONEME_SPEAK``."""
    body = _extract_body()
    assert re.search(r"phoneme_mode\s*&\s*PHONEME_SPEAK", body), (
        "Expected `phoneme_mode & PHONEME_SPEAK` gate"
    )


def test_body_resets_state_at_end() -> None:
    """The C body trails with ``param_index = 0; cmd_p_flag = 0; p_count = 0``."""
    body = _extract_body()
    assert re.search(r"param_index\s*=\s*0\s*;", body)
    assert re.search(r"cmd_p_flag\s*=\s*0\s*;", body)
    assert re.search(r"p_count\s*=\s*0\s*;", body)


# --------------------------------------------------------------------------
# Behavioural tests of the Python port.
# --------------------------------------------------------------------------


def test_packs_canonical_input_into_pipe_layout() -> None:
    """Pack ``params = [0, 0x0F, 0x3FF, 100, 50, 0x1F]`` and verify the layout.

    Expected packing (no percent bias, English language):

    * ``params[0] = 0`` -> high byte clear -> font dispatch kicks in.
      English -> ``PFUSA << PSFONT | (4 - 1) << PSNEXTRA``.
    * Type field: ``0x0F << 10 = 0x3C00``.
    * Value field: ``(0x3FF << 2) & 0x0FFC = 0x0FFC``.
    * Delay field: ``100 << 6 = 0x1900`` in pipe[2].
    * Syl_count field: ``0x1F & 0x003F = 0x1F`` in pipe[2].
    * Length field: ``50`` straight into pipe[3].
    """
    packet = cm_phon_flush(
        [0, 0x0F, 0x3FF, 100, 50, 0x1F],
        language=LANG_english,
    )
    assert isinstance(packet, PhonFlushPacket)
    assert packet.param_index == 4

    # pipe[0]: PFUSA<<PSFONT | (4-1)<<PSNEXTRA
    expected_p0 = (PFUSA << PSFONT) | (3 << PSNEXTRA)
    assert packet.params[0] == expected_p0
    assert packet.language_font == PFUSA

    # pipe[1]: type (4 bits << 10) | value-shifted-masked
    expected_p1 = (0x0F << 10) | ((0x3FF << 2) & 0x0FFC)
    assert packet.params[1] == expected_p1

    # pipe[2]: delay (100 << 6) | syl_count (0x1F)
    expected_p2 = ((100 << 6) & 0xFFFF) | (0x1F & 0x003F)
    assert packet.params[2] == expected_p2

    # pipe[3]: length 50 passed through.
    assert packet.params[3] == 50

    # No params past slot 3.
    assert len(packet.params) == 4


def test_english_language_selects_pfusa_font() -> None:
    """``language = LANG_english`` -> ``PFUSA << PSFONT`` merged into params[0]."""
    packet = cm_phon_flush([0, 0, 0, 0, 0, 0], language=LANG_english)
    assert packet.params[0] & 0xFF00 == (PFUSA << PSFONT) | (3 << PSNEXTRA) & 0xFF00
    assert packet.params[0] & (0xFFFF << PSNEXTRA) == (3 << PSNEXTRA)
    assert packet.language_font == PFUSA


def test_german_language_selects_pfgr_font() -> None:
    """``language = LANG_german`` -> ``PFGR << PSFONT`` merged into params[0]."""
    packet = cm_phon_flush([0, 0, 0, 0, 0, 0], language=LANG_german)
    assert packet.language_font == PFGR
    # The font field sits at PSFONT (=8). Mask off the PSNEXTRA region
    # and the phoneme code byte to isolate it.
    font_bits = (packet.params[0] >> PSFONT) & 0x1F
    assert font_bits == PFGR


def test_unmapped_language_leaves_font_zero() -> None:
    """Languages with no font mapping (Japanese / Italian / none) skip the font."""
    for lang in (LANG_japanese, LANG_italian, LANG_none):
        packet = cm_phon_flush([0, 0, 0, 0, 0, 0], language=lang)
        # No font OR'd in -- params[0] keeps just the extra-count bits.
        assert packet.language_font == 0
        font_bits = (packet.params[0] >> PSFONT) & 0x1F
        assert font_bits == 0, f"language {lang:#x} should not pick a font"


def test_high_byte_in_params0_skips_font_dispatch() -> None:
    """``params[0] & 0xff00`` short-circuits the language switch."""
    # Pre-assembled font in the high byte: the function should NOT
    # overwrite it nor consult `language`.
    pre = 0x1234
    packet = cm_phon_flush([pre, 0, 0, 0, 0, 0], language=LANG_english)
    # The high byte is preserved; only the PSNEXTRA bits (3 << 13) are OR'd in.
    expected = pre | ((4 - 1) << PSNEXTRA)
    assert packet.params[0] == expected & 0xFFFF
    assert packet.language_font == 0


def test_delay_above_900_sets_percent_bit_and_subtracts_900() -> None:
    """``delay = 1000`` -> percent bit set, delay reduced to 100."""
    packet = cm_phon_flush(
        [0, 0, 0, 1000, 0, 0],
        language=LANG_english,
    )
    # pipe[1] bit 0 must be set.
    assert packet.params[1] & 0x0001 == 0x0001
    # pipe[2] delay = (1000 - 900) << 6 = 100 << 6 = 6400.
    expected_delay = (100 << 6) & 0xFFFF
    assert packet.params[2] == expected_delay


def test_delay_below_minus_900_sets_percent_bit_and_adds_900() -> None:
    """``delay = -1000`` -> percent bit set, delay raised to -100."""
    packet = cm_phon_flush(
        [0, 0, 0, -1000, 0, 0],
        language=LANG_english,
    )
    assert packet.params[1] & 0x0001 == 0x0001
    # pipe[2] = (-100 << 6) masked to 16 bits = (-6400) & 0xFFFF = 0xE700.
    expected_delay = (-100 << 6) & 0xFFFF
    assert packet.params[2] & 0xFFC0 == expected_delay & 0xFFC0


def test_delay_within_900_does_not_set_percent_bit() -> None:
    """``delay = 500`` keeps the percent bit clear."""
    packet = cm_phon_flush(
        [0, 0, 0, 500, 0, 0],
        language=LANG_english,
    )
    assert packet.params[1] & 0x0001 == 0


def test_param_index_below_4_skips_packing() -> None:
    """``len(params) <= 3`` keeps the slots unpacked (only font merge applies)."""
    # Only 3 params: params[0..2] -- the C ``param_index > 3`` gate
    # fails so slots 1..2 fall through verbatim.
    packet = cm_phon_flush([0x10, 0x20, 0x30], language=LANG_english)
    assert packet.param_index == 3
    # params[1] / params[2] are forwarded unchanged (masked to 16 bits).
    assert packet.params[1] == 0x20
    assert packet.params[2] == 0x30
    # params[0] gets PFUSA font + (3-1) << PSNEXTRA merged in.
    expected_p0 = 0x10 | (PFUSA << PSFONT) | (2 << PSNEXTRA)
    assert packet.params[0] == expected_p0 & 0xFFFF


def test_empty_params_returns_zeroed_packet() -> None:
    """An empty params list returns a zero-filled packet with index 0."""
    packet = cm_phon_flush([], language=LANG_english)
    assert packet.param_index == 0
    assert packet.params == [0, 0, 0, 0]
    assert packet.language_font == 0


def test_returns_phon_flush_packet_dataclass() -> None:
    """The return is a :class:`PhonFlushPacket` with the documented fields."""
    packet = cm_phon_flush([0, 0, 0, 0, 0, 0], language=LANG_english)
    assert isinstance(packet, PhonFlushPacket)
    assert hasattr(packet, "params")
    assert hasattr(packet, "param_index")
    assert hasattr(packet, "language_font")
