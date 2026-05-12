"""Verify :class:`LtsEmitter` state and helpers."""

from __future__ import annotations

from dectalk.lts.emitter import LtsEmitter


def test_emitter_default_state() -> None:
    """Default values match the C source's initialisation."""
    e = LtsEmitter()
    assert e.phones == []
    assert e.lphone == 0
    assert e.lbphone == 0
    assert e.rbphone == 0
    assert e.schar == ord(",")
    assert e.fchar == ord(".")


def test_send_phone_appends_and_updates_lphone() -> None:
    """``send_phone`` appends to ``phones`` and updates ``lphone``."""
    e = LtsEmitter()
    e.send_phone(42)
    assert e.phones == [42]
    assert e.lphone == 42
    e.send_phone(99)
    assert e.phones == [42, 99]
    assert e.lphone == 99


def test_send_phone_list_until_sil() -> None:
    """SIL (byte 0) terminates the emit, mirroring the C while-loop."""
    e = LtsEmitter()
    e.send_phone_list(bytes([1, 2, 3, 0, 99]))
    assert e.phones == [1, 2, 3]
    assert e.lphone == 3  # last non-SIL emission


def test_send_phone_list_no_sil_emits_all() -> None:
    """No SIL terminator → all bytes emitted."""
    e = LtsEmitter()
    e.send_phone_list(bytes([5, 6, 7]))
    assert e.phones == [5, 6, 7]
    assert e.lphone == 7


def test_send_phone_list_empty() -> None:
    """Empty input is a no-op."""
    e = LtsEmitter()
    e.send_phone_list(b"")
    assert e.phones == []
    assert e.lphone == 0


def test_send_phone_list_first_byte_sil() -> None:
    """A leading SIL skips everything; lphone stays at its prior value."""
    e = LtsEmitter()
    e.send_phone(11)  # set lphone to 11
    e.send_phone_list(bytes([0, 99]))  # SIL is first → no emit
    assert e.phones == [11]  # only the manual send_phone
    assert e.lphone == 11


def test_send_asky_phone_list_basic() -> None:
    """ASCKY 'i' glyph maps via usa_ascky_rev to the IY phoneme code."""
    from dectalk.include.usa_phon_tables import usa_ascky_rev  # noqa: PLC0415

    e = LtsEmitter()
    e.send_asky_phone_list(b"i")
    expected = usa_ascky_rev[ord("i")]
    assert e.phones == [expected]
    assert e.lphone == expected


def test_send_asky_phone_list_skips_null_ascky() -> None:
    """ASCKY bytes that map to NULL_ASCKY (no phoneme meaning) are skipped."""
    e = LtsEmitter()
    # Byte 0x00 maps to NULL_ASCKY → also stops the loop. Use 0x01 instead.
    e.send_asky_phone_list(bytes([0x01]))  # 0x01 maps to NULL_ASCKY
    assert e.phones == []


def test_send_asky_phone_list_stops_at_sil() -> None:
    """SIL terminator (byte 0) ends the walk."""
    e = LtsEmitter()
    e.send_asky_phone_list(b"i\x00x")
    # Only 'i' emitted; everything after the 0 byte is ignored.
    assert len(e.phones) == 1
