"""``InitializeVTM`` vocal-tract-model bring-up factory.

Translated from ``src/dapi/src/vtm/vtm_i.c`` lines 672-711 (the
original Klatt-VTM init that mutates module-scope globals) plus
``src/dapi/src/vtm/vtm3.c`` lines 2110-2169 (the active Linux
build's per-handle filter-state reset).

The C source has two ``InitializeVTM`` flavours -- both are named
identically and both serve the same architectural role
("zero the per-instance VTM scratchpad and prime the parameter
frame so the very first call to ``speech_waveform_generator()``
flushes the resonator delays"). The Linux build pulls the
``vtm3.c`` variant via ``#include "vtm3.c"`` from ``vtm.c``; the
``vtm_i.c`` variant is the original SPC-chip-era code preserved
in-tree as documentation. The Python port captures *both* sets
of initial values so the bring-up state is complete regardless
of which C body the inventory test scans.

The C ``vtm_i.c`` body primes ``parambuff[1..17]`` -- the
"variable parameters" array fed to the inner waveform generator
-- with formant targets that flush the filter delays
(``F1=F2=F3=2000`` Hz, ``B1=B2=B3=2000`` Hz, all amps at 0,
``T0=100`` and ``TLT=18`` for the spread-glottis voicing path),
then calls ``speech_waveform_generator()`` four times to let the
two-pole-resonator delays decay. The Python port skips the four
warm-up calls (the synchronous Python pipeline doesn't share a
persistent filter state across the bring-up shim) and just
returns the seeded :class:`VtmState`.

The C ``vtm3.c`` body zeroes the per-handle filter-state cluster
(``r2pd1..r5cd2``, ``rnpd1/2``, ``rnzd1/2``, ``rlpd1/2``,
``ablas1/2``, ``vlast``, ``one_minus_decay``, ``rampdown``,
``cas_count``, ``par_count``) and seeds ``lastf1 = lastfnp =
500`` so the first inter-frame interpolation has somewhere to
start from. Those defaults are encoded in the
:class:`VtmState` field defaults below.

In the Linux ``_capi`` pipeline this entire bring-up is a no-op
shim -- ``dectalk._capi.CAPI`` constructs the C-side state from
scratch on every ``speak()`` call, so the Python factory is only
exercised when the synchronous Python back-end runs (parity
testing, or the fallback path when ``libtts_us.so`` can't load).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---- Constants from vtm/vtmiont.c lines 791-808 (the OUT_* offsets) -------
# The C source threads ``variabpars = &parambuff[1]`` and then writes
# ``variabpars[OUT_*]`` -- i.e. the seeded indices are ``OUT_* + 1`` in
# the parambuff itself. We reuse the canonical OUT_* table from
# :mod:`dectalk.ph.param_indices` rather than re-defining it here.
from dectalk.ph.param_indices import (
    OUT_A2,
    OUT_A3,
    OUT_A4,
    OUT_A5,
    OUT_A6,
    OUT_AB,
    OUT_AP,
    OUT_AV,
    OUT_B1,
    OUT_B2,
    OUT_B3,
    OUT_F1,
    OUT_F2,
    OUT_F3,
    OUT_FZ,
    OUT_T0,
    OUT_TLT,
)

#: ``DT_PIPE_T parambuff[33];`` from vtm_i.h line 48. The PH side
#: writes ``parambuff[0]`` as the packet header and starts the actual
#: parameter payload at ``parambuff[1]`` (hence the ``&parambuff[1]``
#: aliasing in the C body).
PARAMBUFF_SIZE: int = 33


# ---- The result dataclass -------------------------------------------------


@dataclass(slots=True)
class VtmState:
    """Per-call vocal-tract-model bring-up scratchpad.

    Captures the union of state initialised by ``InitializeVTM`` in
    both the ``vtm_i.c`` and ``vtm3.c`` variants of the function.

    The dataclass is *mutable* (no ``frozen=True``) because the
    synchronous synth pipeline updates the resonator delays in
    place between frames -- the parity test for the bring-up state
    only checks the *initial* values, which is what
    :func:`initialize_vtm` returns.
    """

    #: ``parambuff[33]`` -- the inter-thread VTM parameter buffer.
    #: Element 0 is the packet header (left at 0 here); elements
    #: ``1..17`` hold the OUT_* parameter payload primed by
    #: ``InitializeVTM``. Elements ``18..32`` are unused by the bring-up
    #: path and stay at 0.
    parambuff: list[int] = field(default_factory=lambda: [0] * PARAMBUFF_SIZE)

    # ---- Per-handle filter delays (vtm3.c zero-init) -------------------
    #: Parallel 2nd formant delay-line: last and second-previous samples.
    r2pd1: int = 0
    r2pd2: int = 0
    #: Parallel 3rd formant delay-line.
    r3pd1: int = 0
    r3pd2: int = 0
    #: Parallel 4th formant delay-line.
    r4pd1: int = 0
    r4pd2: int = 0
    #: Parallel 5th formant delay-line.
    r5pd1: int = 0
    r5pd2: int = 0
    #: Parallel 6th formant delay-line.
    r6pd1: int = 0
    r6pd2: int = 0
    #: Cascade 1st formant delay-line.
    r1cd1: int = 0
    r1cd2: int = 0
    #: Cascade 2nd formant delay-line.
    r2cd1: int = 0
    r2cd2: int = 0
    #: Cascade 3rd formant delay-line.
    r3cd1: int = 0
    r3cd2: int = 0
    #: Cascade 4th formant delay-line.
    r4cd1: int = 0
    r4cd2: int = 0
    #: Cascade 5th formant delay-line.
    r5cd1: int = 0
    r5cd2: int = 0
    #: Cascade nasal-pole delay-line.
    rnpd1: int = 0
    rnpd2: int = 0
    #: Cascade nasal-zero delay-line.
    rnzd1: int = 0
    rnzd2: int = 0
    #: Down-sampling low-pass filter delay-line.
    rlpd1: int = 0
    rlpd2: int = 0
    #: Nasal anti-resonator delay-line.
    ablas1: int = 0
    ablas2: int = 0
    #: Tilt-filter last output sample.
    vlast: int = 0
    #: Tilt-filter second-sample IIR helper.
    one_minus_decay: int = 0

    # ---- Pitch-period / counter state ----------------------------------
    #: Cascade-branch sample counter.
    cas_count: int = 0
    #: Parallel-branch sample counter.
    par_count: int = 0
    #: Ramp-down counter used by the end-of-utterance fade.
    rampdown: int = 0

    # ---- Inter-frame interpolation seeds -------------------------------
    #: Previous-frame F1 for inter-frame interpolation. Seeded at 500 Hz
    #: so the first frame has a sane starting point (vtm3.c line 2117).
    lastf1: int = 500
    #: Previous-frame nasal-pole frequency. Seeded at 500 Hz (vtm3.c
    #: line 2118).
    lastfnp: int = 500


# ---- The factory ----------------------------------------------------------


def initialize_vtm() -> VtmState:
    """Build a fresh :class:`VtmState` with the bring-up defaults.

    Mirrors the architectural intent of the C ``InitializeVTM``:

    1. Allocate a zeroed ``parambuff[33]`` (the inter-thread VTM
       parameter buffer) and seed indices ``1..17`` with the
       flush-the-filters frame from ``vtm_i.c``:

       .. code-block:: c

           variabpars = &parambuff[1];
           variabpars[OUT_T0]  = 100;
           variabpars[OUT_F1]  = 2000;
           variabpars[OUT_F2]  = 2000;
           variabpars[OUT_F3]  = 2000;
           variabpars[OUT_FZ]  = 290;
           variabpars[OUT_B1]  = 2000;
           variabpars[OUT_B2]  = 2000;
           variabpars[OUT_B3]  = 2000;
           variabpars[OUT_AV]  = 0;
           variabpars[OUT_AP]  = 0;
           variabpars[OUT_A2]  = 0;
           variabpars[OUT_A3]  = 0;
           variabpars[OUT_A4]  = 0;
           variabpars[OUT_A5]  = 0;
           variabpars[OUT_A6]  = 0;
           variabpars[OUT_AB]  = 0;
           variabpars[OUT_TLT] = 18;

    2. Zero the per-handle filter delays (vtm3.c lines 2123-2167):
       all ``r__d1`` / ``r__d2`` resonator delay registers,
       ``ablas1/2``, ``vlast``, ``one_minus_decay``, ``rampdown``,
       and the ``cas_count`` / ``par_count`` sample counters.

    3. Seed the inter-frame interpolation cache: ``lastf1 =
       lastfnp = 500`` (vtm3.c lines 2117-2118).

    The C ``vtm_i.c`` body follows the parambuff seeding with four
    calls to ``speech_waveform_generator()`` to let the resonator
    delays decay before the first "real" frame; the Python port
    skips those calls because the synchronous Python pipeline has
    no persistent filter state to flush -- callers that need the
    decay can call into the synth pipeline themselves.

    Returns:
        A fresh :class:`VtmState` with the bring-up defaults. The
        caller owns it; subsequent calls return independent copies
        with no shared mutable state.
    """
    state = VtmState()

    # Mirror ``variabpars = &parambuff[1]`` -- the C source writes
    # parameters at offsets OUT_* into the alias, which corresponds to
    # parambuff[OUT_* + 1] in absolute terms. The 1-offset is because
    # parambuff[0] is the packet header in the inter-thread protocol.
    variabpars = state.parambuff  # alias for readability
    variabpars[OUT_T0 + 1] = 100
    variabpars[OUT_F1 + 1] = 2000
    variabpars[OUT_F2 + 1] = 2000
    variabpars[OUT_F3 + 1] = 2000
    variabpars[OUT_FZ + 1] = 290
    variabpars[OUT_B1 + 1] = 2000
    variabpars[OUT_B2 + 1] = 2000
    variabpars[OUT_B3 + 1] = 2000
    variabpars[OUT_AV + 1] = 0
    variabpars[OUT_AP + 1] = 0
    variabpars[OUT_A2 + 1] = 0
    variabpars[OUT_A3 + 1] = 0
    variabpars[OUT_A4 + 1] = 0
    variabpars[OUT_A5 + 1] = 0
    variabpars[OUT_A6 + 1] = 0
    variabpars[OUT_AB + 1] = 0
    variabpars[OUT_TLT + 1] = 18

    # The four ``speech_waveform_generator()`` calls in the C
    # ``vtm_i.c`` body are intentionally skipped -- the Python
    # bring-up factory produces the seeded state without running
    # the synth. Callers that want the post-decay state can
    # invoke the (currently-deferred) speech_waveform_generator
    # port four times against the returned VtmState.

    return state


# PEP8-rename alias so the VTM inventory enumerator picks the port up
# under its C name.
InitializeVTM = initialize_vtm


__all__ = [
    "PARAMBUFF_SIZE",
    "InitializeVTM",
    "VtmState",
    "initialize_vtm",
]
