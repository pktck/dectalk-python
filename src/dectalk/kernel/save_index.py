"""SPC chain index-append helper from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 198-277.

:func:`save_index` appends a new index-packet to the tail of the
SPC packet save chain. The packet's data[] layout follows the
C source:

- data[0] = sym  (the phoneme position)
- data[1] = type (the INDEX_* code)
- data[2] = value (caller-supplied marker value)
- data[3] = how  (TEXT_OUTPUT / ESCAPE_OUTPUT / SPC_INDEX_PAUSE)
- data[4] = sym  (running allophone offset starts at sym)
- data[5] = sym  (target phoneme position)
- data[6] = 0    (allophone delta initially zero)

The C source uses malloc + a tail-walk; Python allocates a fresh
:class:`SpcPacket`, appends it, and returns the new chain head.
"""

from __future__ import annotations

from dectalk.kernel.spc_codes import SPC_type_index
from dectalk.kernel.spc_packet import SpcPacket

_SPC_INDEX_DATA_SLOTS = 7  # data[0..6] used by save_index/check_index.


def save_index(
    spc_pkt_save: SpcPacket | None,
    sym: int,
    type_code: int,
    value: int,
    how: int,
) -> SpcPacket:
    """Append a new index packet to the chain and return the new head.

    Faithful translation of:

    .. code-block:: c

        void save_index(PKSD_T pKsd_t, unsigned int sym,
                        unsigned int type, unsigned int value,
                        unsigned int how) {
            struct spc_packet *spc_pkt = pKsd_t->spc_pkt_save;
            struct spc_packet *last_pkt;
            if (spc_pkt == NULL_SPC_PACKET) {
                spc_pkt = malloc(sizeof(struct spc_packet));
                spc_pkt->link = NULL_SPC_PACKET;
                pKsd_t->spc_pkt_save = spc_pkt;
            } else {
                last_pkt = spc_pkt;
                spc_pkt = spc_pkt->link;
                while (spc_pkt != NULL_SPC_PACKET) {
                    last_pkt = spc_pkt;
                    spc_pkt = spc_pkt->link;
                }
                spc_pkt = malloc(sizeof(struct spc_packet));
                spc_pkt->link = NULL_SPC_PACKET;
                last_pkt->link = spc_pkt;
            }
            spc_pkt->type    = SPC_type_index;
            spc_pkt->data[0] = sym;
            spc_pkt->data[1] = type;
            spc_pkt->data[2] = value;
            spc_pkt->data[3] = how;
            spc_pkt->data[4] = sym;
            spc_pkt->data[5] = sym;
            spc_pkt->data[6] = 0;
        }

    Args:
        spc_pkt_save: Current chain head, or None for an empty chain.
        sym: Phoneme position the marker is anchored to.
        type_code: INDEX_* type code (``data[1]``).
        value: Caller-supplied marker value (``data[2]``).
        how: ``TEXT_OUTPUT`` / ``ESCAPE_OUTPUT`` / ``SPC_INDEX_PAUSE``
            dispatch code.

    Returns:
        The (unchanged) chain head if it was non-None, or the
        newly-allocated packet if the chain was empty.
    """
    new_pkt = SpcPacket()
    new_pkt.type = SPC_type_index
    # Ensure data[] is at least 7 slots.
    while len(new_pkt.data) < _SPC_INDEX_DATA_SLOTS:
        new_pkt.data.append(0)
    new_pkt.data[0] = sym
    new_pkt.data[1] = type_code
    new_pkt.data[2] = value
    new_pkt.data[3] = how
    new_pkt.data[4] = sym
    new_pkt.data[5] = sym
    new_pkt.data[6] = 0  # Explicit; matches C BATS #1114 fix.
    new_pkt.link = None

    if spc_pkt_save is None:
        return new_pkt

    # Walk to the tail and append.
    tail = spc_pkt_save
    while tail.link is not None:
        tail = tail.link
    tail.link = new_pkt
    return spc_pkt_save


__all__ = ["save_index"]
