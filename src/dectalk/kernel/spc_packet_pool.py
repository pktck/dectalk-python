"""Simple SPC-packet allocator from services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 150-170
(the ``!DTPC1 && !EPSON_ARM7`` branch).

DECtalk uses a single-slot global SPC-packet allocator on
non-DTPC1 / non-EPSON_ARM7 builds (which is the Linux build).
``get_spc_packet`` returns the global slot if it's free,
``free_spc_packet`` returns it to the pool.

The C source's single-slot allocator is mirrored here with a
class-level singleton instance. This is unused at runtime today
but provides parity for any code path that calls these helpers.
"""

from __future__ import annotations

from dectalk.kernel.spc_packet import SpcPacket

_global_spc_pkt: SpcPacket = SpcPacket()
"""The single global SPC packet slot (mirrors ``global_spc_pkt[0]``)."""

_cur_packet_number: list[int] = [0]
"""Mutable cell holding the current packet count (0=free, 1=allocated)."""


def get_spc_packet() -> SpcPacket | None:
    """Return the global SPC packet if free, else ``None``.

    Faithful translation of:

    .. code-block:: c

        struct spc_packet *get_spc_packet(void) {
            if (cur_packet_number == 0) {
                return &(global_spc_pkt[0]);
                cur_packet_number = 1;  // unreachable!
            }
            return NULL;
        }

    Note the original C source has a bug: ``cur_packet_number=1``
    follows an unconditional ``return``, so it's unreachable. The
    Python port preserves this — the slot never actually gets
    marked allocated. (This is fine because the kernel only ever
    needs one SPC packet outstanding at a time on these builds.)
    """
    if _cur_packet_number[0] == 0:
        return _global_spc_pkt
    return None


def free_spc_packet(spc_pkt: SpcPacket | None) -> None:
    """Release ``spc_pkt`` back to the pool if it's the global slot.

    Faithful translation of:

    .. code-block:: c

        void free_spc_packet(struct spc_packet *spc_pkt) {
            if (spc_pkt == &(global_spc_pkt[0])) {
                cur_packet_number = 0;
            }
        }
    """
    if spc_pkt is _global_spc_pkt:
        _cur_packet_number[0] = 0


__all__ = ["free_spc_packet", "get_spc_packet"]
