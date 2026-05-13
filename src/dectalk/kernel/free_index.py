"""SPC-chain free helper from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 493-531.

:func:`free_index` walks the SPC packet save chain, frees each
packet, and resets the chain head to ``None``. Returns the
new (empty) chain head so callers can update their KSD slot.

In Python the GC handles the freeing automatically; we just walk
the chain to break the link references (helping GC reach the
packets faster) and return ``None`` as the new head.
"""

from __future__ import annotations

from dectalk.kernel.spc_packet import SpcPacket


def free_index(spc_pkt_save: SpcPacket | None) -> None:
    """Free every packet in the chain rooted at ``spc_pkt_save``.

    Faithful translation of:

    .. code-block:: c

        void free_index(PKSD_T pKsd_t) {
            struct spc_packet *spc_pkt = pKsd_t->spc_pkt_save;
            struct spc_packet *free_pkt;
            while (spc_pkt != NULL_SPC_PACKET) {
                free_pkt = spc_pkt;
                spc_pkt = spc_pkt->link;
                free(free_pkt);
            }
            pKsd_t->spc_pkt_save = NULL_SPC_PACKET;
        }

    The C source assigns ``NULL`` back to ``pKsd_t->spc_pkt_save``
    after walking; Python can't easily do that from inside a
    function with only the head reference. Callers must explicitly
    reset their head reference to ``None`` after this returns.

    Walks the chain and clears each ``link`` field so the GC reaches
    the released packets quickly.

    Args:
        spc_pkt_save: Head of the SPC save chain (or None for empty).
    """
    spc_pkt = spc_pkt_save
    while spc_pkt is not None:
        next_pkt = spc_pkt.link
        spc_pkt.link = None  # Break the chain link for the GC.
        spc_pkt = next_pkt


__all__ = ["free_index"]
