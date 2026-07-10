"""Kernel shared-data struct (KSD_T) from kernel.h.

Translated from ``src/dapi/src/include/kernel.h`` lines 551-877
(``struct share_data``). The full struct has well over a hundred
fields covering dictionary handles, pipe handles, interrupt
semaphores, async-change flags, voice / volume state, code-page
translation tables, language-specific tables, debug switches, and
more.

This file currently models the **minimal subset** required by the
``kernel/services.c`` helpers we have already ported. Fields are
added one-at-a-time as the next porting target needs them, so the
dataclass stays grounded in what's actually used.

Currently modelled (with the helper that consumes each):

- ``lang_curr`` (``default_lang``)
- ``lang_ready`` (``default_lang``)
- ``lang_lts`` / ``lang_ph`` (``default_lang`` non-SINGLE_THREADED)
- ``lts_pipe`` / ``ph_pipe`` (``default_lang`` non-SINGLE_THREADED)
- ``cmd_flush`` (``flush_done``)
- ``spc_sync`` (``flush_done``)
- ``loaded_languages`` (``default_lang``)
- ``ascky`` / ``ascky_size`` / ``reverse_ascky`` /
  ``arpabet`` / ``arpa_size`` / ``arpa_case`` / ``typing_table`` /
  ``error_table`` (``default_lang``)
- ``spc_pkt_save`` (the SPC index-chain helpers
  ``save_index`` / ``check_index`` / ``adjust_index`` /
  ``adjust_allo`` / ``set_index_allo`` / ``free_index``)
- ``sprate`` / ``halting`` / ``modeflag`` (synthesis pipeline)
- ``pitch_delta`` (``cmd_init`` engine-wide pitch offset)

Field defaults mirror C zero-initialisation of the malloc'd
``share_data`` struct, with three intentional exceptions:

1. ``lang_curr`` defaults to :data:`LANG_none` (``0xFFFF``) — the
   "no language selected yet" sentinel that
   :func:`dectalk.kernel.default_lang.default_lang` checks for.
   In C this is set explicitly during kernel start-up before any
   subsystem reports in.
2. ``spc_sync`` uses :class:`DtSemaphore`, which initialises the
   counter to 0 internally (matching the C ``DT_SEMAPHORE``
   zero-init).
3. ``modeflag`` defaults to :data:`MODE_CITATION` — kernel start-up
   sets ``KS.modeflag = MODE_CITATION`` (``kernel/main.c:188``), and
   ``TextToSpeechStartup`` does the same (``api/ttsapi.c:2039``;
   ``| MODE_LATIN`` only for Spanish builds). The bit is *read* only
   by ``phalloph``, where its being set permanently disables the
   "flap the initial /t/ of 'to'" allophone rule
   (``ph_aloph1.c:902-912``, guard ``(modeflag & MODE_CITATION) ==
   0``) — issue #307.

See :func:`test_kernel_ksd_t_defaults` for the invariant tests
that lock these defaults in.

The pipe-handle fields use ``object | None`` because pipe internals
aren't part of the bit-parity oracle — what matters is that the
correct handle gets aliased into ``lts_pipe`` / ``ph_pipe`` when
``default_lang`` runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dectalk.kernel.lang_codes import LANG_none
from dectalk.kernel.language_tables import DtpcLanguageTables
from dectalk.kernel.misc_constants import MAX_languages
from dectalk.kernel.mode_flags import MODE_CITATION
from dectalk.kernel.spc_packet import SpcPacket
from dectalk.kernel.sync_primitives import DtSemaphore


@dataclass(slots=True)
class KsdT:
    """Kernel shared-data instance (KSD_T in C).

    All scalar fields default to 0; pointer fields default to
    None; the ``lang_*`` arrays default to ``MAX_languages``-long
    lists of zeros / Nones.
    """

    # SPC index chain (used by save_index / check_index / ...).
    spc_pkt_save: SpcPacket | None = None

    # Process-flush flags.
    cmd_flush: int = 0

    # Mode flags read by cm_cmd_break / cm_cmd_say.
    wbreak: int = 0  # word-boundary pause toggle ([:break on/off]).
    sayflag: int = 0  # SAY_CLAUSE / SAY_WORD / SAY_LETTER / SAY_LINE / SAY_SYLLABLE.
    input_timeout: int = 0  # mirror of pCmd_t->timeout ([:timeout <n>]).
    phoneme_mode: int = 0  # PHONEME_ASCKY / PHONEME_SPEAK / PHONEME_OFF bitfield.

    # Sync semaphore (read .value in flush_done).
    spc_sync: DtSemaphore = field(default_factory=DtSemaphore)

    # Language ready/curr state.
    lang_curr: int = LANG_none
    lang_ready: list[int] = field(
        default_factory=lambda: [0] * MAX_languages,
    )
    lang_lts: list[object | None] = field(
        default_factory=lambda: [None] * MAX_languages,
    )
    lang_ph: list[object | None] = field(
        default_factory=lambda: [None] * MAX_languages,
    )

    # Current-language interprocess pipes (non-SINGLE_THREADED).
    lts_pipe: object | None = None
    ph_pipe: object | None = None

    # Language-specific user-interface tables.
    loaded_languages: DtpcLanguageTables | None = None
    ascky: bytes | None = None
    ascky_size: int = 0
    reverse_ascky: list[int] | None = None
    arpabet: bytes | None = None
    arpa_size: int = 0
    arpa_case: int = 0
    typing_table: list[bytes] | None = None
    error_table: list[bytes] | None = None

    # Per-clause speech rate (volatile short in C). Read by us_gettar
    # to fork a quieter glottal-stop target at slow rates.
    sprate: int = 0
    # Halt flag (volatile short in C). Inner loops poll this to bail
    # out of the synthesis pipeline mid-clause.
    halting: int = 0
    # Mode flag (MODE_CITATION / MODE_LATIN / ... bits from esc.h).
    # Read by phalloph to decide rule-firing. The C engine never runs
    # with this zeroed: kernel/main.c:188 and api/ttsapi.c:2039 both
    # start it as MODE_CITATION, which keeps phalloph's 'to'-flap rule
    # (ph_aloph1.c:902) permanently disabled (#307).
    modeflag: int = MODE_CITATION
    # Pitch delta in semitone units (volatile int in C). Set to 35 by
    # ``cmd_init`` on every full reset and adjusted by ``[:dv]`` /
    # ``[:tonecharact]`` commands.  Cited from
    # ``src/dapi/src/cmd/cmd_init.c`` line 92:
    # ``pKsd_t->pitch_delta = 35;``
    pitch_delta: int = 0
    # Volume attenuation index in [0, 140] (volatile int in C — declared
    # in ``include/kernel.h`` line 717 as ``int vol_att``). The C kernel
    # initialises it to ``100`` (``ttsapi.c`` lines 2050 / 6609) and the
    # ``[:volume set sp N]`` / ``[:vol set sp N]`` directive routes
    # through ``cm_copt.c`` line 1657 to mutate it. ``vtm3.c`` line 514
    # copies it into ``pKsd_t->vol_att``, clamps to ``[0, 141]`` and
    # uses ``int_volume_table[vol_att]`` as the Q15 post-scale on every
    # synthesised sample (line 1642: ``out = frac1mul(out, vol_att)``).
    # In Python, ``_pump_frames_to_samples`` reads this field to apply
    # the same post-scale (per ``docs/vtm-divergence-audit.md`` §5).
    vol_att: int = 100


__all__ = ["KsdT"]
