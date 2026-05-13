"""SPC-index adjustment helper from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 376-407.

:func:`adjust_index` walks the linked list of pending SPC packets
(``pKsd_t->spc_pkt_save``) and adjusts the allophone-offset
fields on every packet whose data[5] (target phoneme position)
is at or past ``which + data[6]``.

The SPC-packet ``data`` layout for index packets is:

- ``data[4]`` — running allophone offset
- ``data[5]`` — target phoneme position
- ``data[6]`` — allophone delta

The C source uses ``EnterCriticalSection``/``LeaveCriticalSection``
around the walk; in Python the GIL serialises us so we don't need
explicit locks for parity. Subscribers must still serialise their
own callers if they share the list across threads.
"""

from __future__ import annotations

from dectalk.kernel.spc_packet import SpcPacket

# Highest data[] index this function reads from index packets is 6
# (data[4] / data[5] / data[6]). Need len(data) > 6 to access all three.
_MAX_INDEX_FIELD = 6


def adjust_index(
    spc_pkt_save: SpcPacket | None,
    which: int,
    direction: int,
    delete: int,
) -> None:
    """Adjust SPC packet allophone offsets for the chain at ``spc_pkt_save``.

    Faithful translation of:

    .. code-block:: c

        void adjust_index(PKSD_T pKsd_t, unsigned int which,
                          int direction, int del) {
            struct spc_packet *spc_pkt;
            EnterCriticalSection(pKsd_t->pcsSpcPktSave);
            if ((spc_pkt = pKsd_t->spc_pkt_save) != NULL_SPC_PACKET) {
                while (spc_pkt != NULL_SPC_PACKET) {
                    if (spc_pkt->data[5] >= which + (int)spc_pkt->data[6]) {
                        spc_pkt->data[4] = (int)(spc_pkt->data[4]) + direction;
                        spc_pkt->data[6] = (int)(spc_pkt->data[6]) + del;
                    }
                    spc_pkt = spc_pkt->link;
                }
            }
            LeaveCriticalSection(pKsd_t->pcsSpcPktSave);
        }

    Args:
        spc_pkt_save: Head of the SPC-packet save chain
            (typically ``pKsd_t->spc_pkt_save``). May be ``None`` for
            an empty chain.
        which: Threshold phoneme position. Only packets whose
            ``data[5] >= which + data[6]`` are adjusted.
        direction: Signed delta added to each matching packet's
            ``data[4]`` (running allophone offset).
        delete: Signed delta added to each matching packet's
            ``data[6]`` (allophone delta).

    Notes:
        The C source's signed/unsigned arithmetic via
        ``(unsigned int)((int)(value) + delta)`` is preserved by
        keeping Python ints (which don't wrap, so the arithmetic is
        always safe at full precision).
    """
    spc_pkt = spc_pkt_save
    while spc_pkt is not None:
        # data[] should be at least 7 entries long for index packets;
        # guard against shorter buffers to avoid IndexError.
        if len(spc_pkt.data) > _MAX_INDEX_FIELD and spc_pkt.data[5] >= which + spc_pkt.data[6]:
            spc_pkt.data[4] = spc_pkt.data[4] + direction
            spc_pkt.data[6] = spc_pkt.data[6] + delete
        spc_pkt = spc_pkt.link


__all__ = ["adjust_index"]
