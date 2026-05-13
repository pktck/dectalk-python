"""``cm_util_say_string`` LTS-pipe injector from cm_util.c.

Translated from ``src/dapi/src/cmd/cm_util.c`` lines 328-345
(the Linux/non-MSDOS branch).

The C function pushes each byte of an input string onto the
inter-thread LTS pipe as a ``(PFASCII << PSFONT) | char`` packet,
either via ``cm_util_write_pipe`` (multi-threaded) or
``lts_loop`` (single-threaded). The Python pipeline runs the LTS
stage synchronously on the main thread, so there is no pipe
abstraction; this port exposes the per-character encoding as a
generator over the encoded packets and accepts an injectable
``lts_sink`` callable for callers that want to immediately feed
the packets into a Python LTS frontend.

Architectural shim — the C function returns void and writes via
side-effect; the Python port returns the list of encoded packets
while still calling ``lts_sink`` for each packet to mirror the
C side-effect semantics.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from dectalk.include.cmd_codes import PFASCII, PSFONT


def cm_util_say_string(
    instr: bytes | bytearray | str,
    lts_sink: Callable[[int], None] | None = None,
) -> list[int]:
    r"""Encode each byte of ``instr`` as a PFASCII-font LTS packet.

    Faithful translation of:

    .. code-block:: c

        void cm_util_say_string(PKSD_T pKsd_t, unsigned char _far *instr,
                                short mode) {
            unsigned short pipe_value[2] = { 0 };
            unsigned short i;
            for (i = 0; instr[i] != '\\0'; i++) {
                pipe_value[0] = (PFASCII << PSFONT) + instr[i];
        #ifndef SINGLE_THREADED
                cm_util_write_pipe(pKsd_t, pKsd_t->lts_pipe, &pipe_value, 1);
        #else
                lts_loop(pKsd_t->phTTS, pipe_value);
        #endif
            }
        }

    Args:
        instr: Input bytes (or string, which is encoded as UTF-8).
            The C source treats the trailing NUL as the end-of-
            string sentinel; the Python port stops at the first
            NUL byte to match.
        lts_sink: Optional per-packet callback (mirrors the C
            side-effect of feeding the LTS pipe or calling
            ``lts_loop``). If ``None``, only the return value is
            produced.

    Returns:
        List of ``(PFASCII << PSFONT) | byte`` packets, one per
        non-NUL input byte.
    """
    if isinstance(instr, str):
        instr = instr.encode("utf-8")
    packets: list[int] = []
    base = PFASCII << PSFONT
    for byte in instr:
        if byte == 0:
            break
        packet = base + byte
        packets.append(packet)
        if lts_sink is not None:
            lts_sink(packet)
    return packets


def cm_util_say_string_iter(instr: bytes | bytearray | str) -> Iterable[int]:
    """Lazy version of :func:`cm_util_say_string` (no sink, no list)."""
    if isinstance(instr, str):
        instr = instr.encode("utf-8")
    base = PFASCII << PSFONT
    for byte in instr:
        if byte == 0:
            return
        yield base + byte


__all__ = ["cm_util_say_string", "cm_util_say_string_iter"]
