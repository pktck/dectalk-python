"""SPC-allophone adjustment helpers from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 415-486:

- :func:`adjust_allo` — walk the SPC packet chain and adjust
  ``data[5]`` on every packet at or past ``which``.
- :func:`set_index_allo` — walk the chain and set ``data[5]`` on
  every packet whose ``data[4]`` matches ``nphone``.

Both functions take the head of the SPC packet save chain as an
explicit argument (the C source reads ``pKsd_t->spc_pkt_save``).
The C source's EnterCriticalSection / LeaveCriticalSection is
skipped — the GIL serialises us; callers should still serialise
themselves if sharing the list across threads.
"""

from __future__ import annotations

from dectalk.kernel.spc_packet import SpcPacket

# Highest data[] index any helper reads is 5; need len(data) > 5 to access it.
_MAX_FIELD = 5


def adjust_allo(
    spc_pkt_save: SpcPacket | None,
    which: int,
    direction: int,
) -> None:
    """Adjust ``data[5]`` on every packet with ``data[5] >= which``.

    Faithful translation of:

    .. code-block:: c

        void adjust_allo(PKSD_T pKsd_t, unsigned int which, int direction) {
            struct spc_packet *spc_pkt = pKsd_t->spc_pkt_save;
            while (spc_pkt != NULL_SPC_PACKET) {
                if (spc_pkt->data[5] >= which) {
                    spc_pkt->data[5] = (int)(spc_pkt->data[5]) + direction;
                }
                spc_pkt = spc_pkt->link;
            }
        }

    Args:
        spc_pkt_save: Head of the SPC save chain (or None).
        which: Threshold position.
        direction: Signed delta added to each matching packet's
            ``data[5]``.
    """
    spc_pkt = spc_pkt_save
    while spc_pkt is not None:
        if len(spc_pkt.data) > _MAX_FIELD and spc_pkt.data[5] >= which:
            spc_pkt.data[5] = spc_pkt.data[5] + direction
        spc_pkt = spc_pkt.link


def set_index_allo(
    spc_pkt_save: SpcPacket | None,
    nphone: int,
    nallo: int,
) -> None:
    """Set ``data[5] = nallo`` on every packet with ``data[4] == nphone``.

    Faithful translation of:

    .. code-block:: c

        void set_index_allo(PKSD_T pKsd_t, unsigned int nphone,
                            unsigned int nallo) {
            struct spc_packet *spc_pkt = pKsd_t->spc_pkt_save;
            while (spc_pkt != NULL_SPC_PACKET) {
                if (spc_pkt->data[4] == nphone) {
                    spc_pkt->data[5] = nallo;
                }
                spc_pkt = spc_pkt->link;
            }
        }

    Args:
        spc_pkt_save: Head of the SPC save chain (or None).
        nphone: Phoneme position to match against ``data[4]``.
        nallo: New allo offset to write to ``data[5]``.
    """
    spc_pkt = spc_pkt_save
    while spc_pkt is not None:
        if len(spc_pkt.data) > _MAX_FIELD and spc_pkt.data[4] == nphone:
            spc_pkt.data[5] = nallo
        spc_pkt = spc_pkt.link


__all__ = ["adjust_allo", "set_index_allo"]
