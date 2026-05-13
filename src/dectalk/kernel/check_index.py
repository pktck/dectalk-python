"""SPC chain index-flush helper from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 285-369.

:func:`check_index` walks the SPC packet save chain and flushes
every packet whose ``data[5]`` (target phoneme position) is at
or before ``which_phone``. For each flushed packet it builds a
3-element notification buffer ``(spc_type | subtype, data[2],
data[3])`` and dispatches it to the VTM via the caller-provided
``emit`` callback.

The C source's ``write_pipe`` / ``vtm_loop`` dispatch becomes a
Python callable so callers can route the buf to whatever VTM
implementation they have available. Returns the new chain head
after removing the flushed packets — caller must update its
KSD slot.
"""

from __future__ import annotations

from collections.abc import Callable

from dectalk.include.cmd_codes import (
    INDEX,
    INDEX_BOOKMARK,
    INDEX_NOISE,
    INDEX_REPLY,
    INDEX_SENTENCE,
    INDEX_START,
    INDEX_STOP,
    INDEX_VOLUME,
    INDEX_WORDPOS,
)
from dectalk.kernel.spc_codes import (
    SPC_subtype_bookmark,
    SPC_subtype_noise,
    SPC_subtype_sentence,
    SPC_subtype_start,
    SPC_subtype_stop,
    SPC_subtype_volume,
    SPC_subtype_wordpos,
    SPC_type_index,
)
from dectalk.kernel.spc_packet import SpcPacket

# data[5] threshold: only fields up to index 5 are read from each packet.
_MAX_FIELD = 5

# Map from the C-level INDEX_* code (in data[1]) to the SPC subtype OR.
_INDEX_TO_SUBTYPE: dict[int, int] = {
    INDEX: 0,
    INDEX_REPLY: 0,
    INDEX_BOOKMARK: SPC_subtype_bookmark,
    INDEX_WORDPOS: SPC_subtype_wordpos,
    INDEX_START: SPC_subtype_start,
    INDEX_STOP: SPC_subtype_stop,
    INDEX_SENTENCE: SPC_subtype_sentence,
    INDEX_VOLUME: SPC_subtype_volume,
    INDEX_NOISE: SPC_subtype_noise,
}


def check_index(
    spc_pkt_save: SpcPacket | None,
    which_phone: int,
    emit: Callable[[tuple[int, int, int]], None],
) -> SpcPacket | None:
    """Flush packets at-or-before ``which_phone`` from the chain via ``emit``.

    Faithful translation of:

    .. code-block:: c

        void check_index(LPTTS_HANDLE_T phTTS, unsigned int which_phone) {
            struct spc_packet *spc_pkt, *last_pkt;
            DT_PIPE_T buf[3];
            while ((spc_pkt = pKsd_t->spc_pkt_save) != NULL_SPC_PACKET) {
                if (spc_pkt->data[5] > which_phone) break;
                switch (spc_pkt->data[1]) {
                    case INDEX:           buf[0] = SPC_type_index; break;
                    case INDEX_BOOKMARK:  buf[0] = SPC_type_index | SPC_subtype_bookmark; break;
                    // ... (see _INDEX_TO_SUBTYPE)
                }
                buf[1] = spc_pkt->data[2];
                buf[2] = spc_pkt->data[3];
                last_pkt = spc_pkt;
                spc_pkt = spc_pkt->link;
                pKsd_t->spc_pkt_save = spc_pkt;
                free(last_pkt);
                write_pipe(pKsd_t->vtm_pipe, buf, 3);
            }
        }

    Args:
        spc_pkt_save: Head of the SPC save chain.
        which_phone: Threshold phoneme position - packets at or
            before this are flushed.
        emit: Callback receiving each flushed packet's 3-element
            (spc_type_with_subtype, data[2], data[3]) tuple.

    Returns:
        New chain head (after removing the flushed prefix).
    """
    cur = spc_pkt_save
    while cur is not None:
        if len(cur.data) <= _MAX_FIELD:
            break
        if cur.data[5] > which_phone:
            break
        # Determine subtype OR based on data[1].
        subtype = _INDEX_TO_SUBTYPE.get(cur.data[1], 0)
        buf = (SPC_type_index | subtype, cur.data[2], cur.data[3])
        # Advance to next packet first, then emit (matches C ordering).
        next_pkt = cur.link
        cur.link = None  # break link so freed packet doesn't dangle
        emit(buf)
        cur = next_pkt
    return cur


__all__ = ["check_index"]
