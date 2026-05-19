"""Per-phoneme PH static target state from ph_data.h.

Translated from ``src/dapi/src/ph/ph_data.h`` lines 315-428.

``DPHSETTAR_ST`` holds the accumulator + scratch state for
one pass through the PH pipeline files:

- ``PH_SETAR.C`` populates ``bouval``..``delay_cnt``
  (current parameter state).
- ``PH_SORT.C`` reads/writes ``did_del``.
- ``PH_TIMNG.C`` populates ``sprlast``..``durxx`` (duration / timing).
- ``PH_DRWT0.C`` populates ``basecntr``..``f0sa1`` (F0 contour drawing).
- ``PH_DRAW.C`` populates ``drawinitsw``..``breathytilt`` (frame drawing).
- ``PH_INTON.C`` populates ``nrises_sofar``..``tarstop`` (intonation).

All fields default to 0 (``np`` to ``None``); the engine
populates them per-phoneme as it walks the phoneme stream.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DphSettarSt:
    """Per-phoneme PH static target state (DPHSETTAR_ST in C)."""

    bouval: int = 0
    vot: int = 0
    vvbouval: int = 0
    durtran: int = 0
    vvdurtran: int = 0
    phonex: int = 0
    gencoartic: int = 0
    initsw: int = 0
    np: int = 0
    par_type: int = 0  # char in C
    nasvowel: int = 0
    phcur: int = 0
    delay_cnt: int = 0
    did_del: int = 0
    sprlast: int = 0
    sprat1: int = 0
    sprat2: int = 0
    strucstressprev: int = 0
    phonex_timing: int = 0
    strucnex: int = 0
    feanex: int = 0
    sprat0: int = 0
    durxx: int = 0
    basecntr: int = 0
    basestep: int = 0
    basetime: int = 0
    f0command: int = 0
    glide_step: int = 0
    glide_inc: int = 0
    glide_tot: int = 0
    place: int = 0
    type: int = 0
    length: int = 0
    phocur: int = 0
    nfram: int = 0
    nframb: int = 0
    nframs: int = 0
    nframg: int = 0
    diplo: int = 0
    extrad: int = 0
    tglstp: int = 0
    tglstn: int = 0
    segdur: int = 0
    segdrg: int = 0
    f0las1: int = 0
    f0las2: int = 0
    tarhat: int = 0
    tarimp: int = 0
    f0a2: int = 0
    f0b: int = 0
    f0a1: int = 0
    dtimf0: int = 0
    phonex_drawt0: int = 0
    tarseg: int = 0
    tarseg1: int = 0
    beginfall: int = 0
    lastone: int = 0
    lastbase: int = 0
    np_drawt0: int = 0
    npg: int = 0
    nimp: int = 0
    nimpcnt: int = 0
    endfall: int = 0
    timecos3: int = 0
    timecos5: int = 0
    timecos10: int = 0
    timecos15: int = 0
    timecosvib: int = 0
    f0basestart: int = 0
    f0beginfall: int = 0
    f0endfall: int = 0
    vibsw: int = 0
    newnote: int = 0
    delnote: int = 0
    delcum: int = 0
    f0start: int = 0
    tarbas: int = 0
    f0slas1: int = 0
    f0slas2: int = 0
    f0delta: int = 0
    delimp: int = 0
    f0sa2: int = 0
    f0sb: int = 0
    f0sa1: int = 0
    drawinitsw: int = 0
    breathyah: int = 0
    breathytilt: int = 0
    nrises_sofar: int = 0
    hatsize: int = 0
    hat_loc_re_baseline: int = 0
    lastbound: int = 0
    delayed_pulse: int = 0
    numstresses: int = 0
    creek: int = 0
    numsylsofar: int = 0
    checkedphone: int = 0
    numsyllables: int = 0
    tarstop: int = 0


__all__ = ["DphSettarSt"]
