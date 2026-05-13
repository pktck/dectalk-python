# ruff: noqa: N815 — preserve C-source mixedCase field names (phTTS, pSTphsettar)
"""PH-thread instance data struct (DPH_T) from ph_data.h.

Translated from ``src/dapi/src/ph/ph_data.h`` lines 431-716.

``DPH_T`` is the per-thread PH module instance state — the
aggregate that holds everything the PH pipeline reads and
mutates as it walks a clause's phoneme stream. Roughly 230
scalar fields plus 20 fixed-size arrays.

Notable arrays (sized by constants from
:mod:`dectalk.ph.numeric_constants`):

- ``param`` — per-parameter target state (one entry per
  Klatt voice param, sized by ``VOICE_PARS``).
- ``parstochip`` — output buffer to SPC chip.
- ``symbols`` / ``allophons`` / ``allofeats`` /
  ``alloopenq`` / ``allodurs`` — clause-scoped phoneme arrays
  sized by ``NPHON_MAX + SAFETY + 2``.
- ``curspdef`` / ``var_val`` — current speaker definition
  (sized ``SPDEF``).
- ``voidef`` / ``tunedef`` (and ``_8`` variants) — pointer
  arrays per loaded speaker, sized ``MAX_SPEAKERS``.
- ``dipspec`` — 40-entry diphthong-target scratch.
- ``f0basetypes`` — 5-by-17 F0 base-type lookup grid.

All scalar fields default to 0; arrays default to all-0;
pointer / object fields default to ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DphT:
    """PH-thread instance data (DPH_T in C). 230+ fields total."""

    param: object | None = None
    last_lang: int = 0
    PHSwapIn: object | None = None
    PHSwapOut: object | None = None
    PHSwapCnt: int = 0
    fvvtran: int = 0
    bvvtran: int = 0
    tvvbacktr: int = 0
    dfvvtran: int = 0
    dbvvtran: int = 0
    breathysw: int = 0
    spdefb1off: int = 0
    spdeflaxprcnt: int = 0
    spdeftltoff: int = 0
    f0_dep_tilt: int = 0
    f0flutter: int = 0
    f0s: int = 0
    f0: int = 0
    parstochip: list[int] = field(default_factory=list[int])
    lastf1: int = 0
    printdata: int = 0
    at_ending_sil: int = 0
    pressure: int = 0
    spressure: int = 0
    pressure_pause: int = 0
    delta_pressure: int = 0
    pressure_drop: int = 0
    pressure_gest: int = 0
    syl_pressure: int = 0
    press_offset: int = 0
    area_ap: int = 0
    target_ap: int = 0
    target_l: int = 0
    lastvot: int = 0
    target_ag: int = 0
    area_g: int = 0
    lastthing: int = 0
    last_area_g: int = 0
    delta_area_g: int = 0
    delta_a_forap: int = 0
    delta_area_gst: int = 0
    delta_area_gstop: int = 0
    agspeed: int = 0
    area_n: int = 0
    target_narea: int = 0
    area_l: int = 0
    last_area_l: int = 0
    area_flap: int = 0
    area_b: int = 0
    last_area_b: int = 0
    last_area_tb: int = 0
    target_b: int = 0
    target_tb: int = 0
    area_tb: int = 0
    dcstep: int = 0
    uestep: int = 0
    in_lclosure: int = 0
    in_lrelease: int = 0
    in_lfric: int = 0
    fnscale: int = 0
    in_tbrelease: int = 0
    in_bclosure: int = 0
    in_tbclosure: int = 0
    in_brelease: int = 0
    in_bfric: int = 0
    in_tbfric: int = 0
    lstep: int = 0
    bstep: int = 0
    tbstep: int = 0
    tstep: int = 0
    f1_velar: int = 0
    nasal_step: int = 0
    p_step: int = 0
    openquo: int = 0
    oqtarget: int = 0
    oqleadtime: int = 0
    tcum: int = 0
    stress_pulse: int = 0
    avglstop: int = 0
    avcreek: int = 0
    DelayCnt: int = 0
    timeref: int = 0
    Speaker_Rhythm: int = 0
    tarbas: int = 0
    clausetype: int = 0
    addjit: int = 0
    sprate: int = 0
    allophons: list[int] = field(default_factory=list[int])
    allofeats: list[int] = field(default_factory=list[int])
    alloopenq: list[int] = field(default_factory=list[int])
    allodurs: list[int] = field(default_factory=list[int])
    last_real_phon: int = 0
    promote_helper_verb: int = 0
    prevtargf0: int = 0
    done: int = 0
    prevnphon: int = 0
    clausenumber: int = 0
    clausepos: int = 0
    commacnt: int = 0
    dcommacnt: int = 0
    hatstate: int = 0
    hatstatel: int = 0
    hatpos: int = 0
    sinstart: int = 0
    spdefglspeed: int = 0
    phTTS: object | None = None
    durfon: int = 0
    nallotot: int = 0
    malfem: int = 0
    del_av: int = 0
    p_locus: int = 0
    p_diph: int = 0
    p_tar: int = 0
    p_amp: int = 0
    arg1: int = 0
    arg2: int = 0
    arg3: int = 0
    symbols: list[int] = field(default_factory=list[int])
    nsymbtot: int = 0
    user_durs: int = 0
    user_f0: int = 0
    user_offset: int = 0
    phonemes: int = 0
    sentstruc: int = 0
    nphonetot: int = 0
    newparagsw: int = 0
    f0mode: int = 0
    cbsymbol: int = 0
    nfperiod: int = 0
    nfcomma: int = 0
    oddeven: int = 0
    curspdef: list[int] = field(default_factory=list[int])
    voidef: list[int] = field(default_factory=list[int])
    voidef_8: list[int] = field(default_factory=list[int])
    tunedef: list[int] = field(default_factory=list[int])
    tunedef_8: list[int] = field(default_factory=list[int])
    var_val: list[int] = field(default_factory=list[int])
    loadspdef: int = 0
    assertiveness: int = 0
    f0_lp_filter: int = 0
    size_hat_rise: int = 0
    scale_str_rise: int = 0
    f0basefall: int = 0
    f0minimum: int = 0
    f0scalefac: int = 0
    f0segscalefac: int = 0
    compause: int = 0
    perpause: int = 0
    f0tar: list[int] = field(default_factory=list[int])
    f0type: list[int] = field(default_factory=list[int])
    f0length: list[int] = field(default_factory=list[int])
    Cntfromlast: int = 0
    keepallo: int = 0
    lastallo: int = 0
    keepdur: int = 0
    number_words: int = 0
    number_verbs: int = 0
    number_fsyls: int = 0
    f0baseline: int = 0
    f0basetypes: list[int] = field(default_factory=list[int])
    f0tim: list[int] = field(default_factory=list[int])
    cumdur: int = 0
    tcumdur: int = 0
    nf0ev: int = 0
    nf0tot: int = 0
    f0prime: int = 0
    f0last: int = 0
    temp: int = 0
    avtemp: int = 0
    f0primelast: int = 0
    enddrop: int = 0
    tot_enddrop: int = 0
    scaled_enddrop: int = 0
    glotalize: int = 0
    delayed_pulse: int = 0
    creek: int = 0
    ph_init: int = 0
    longcumdur: int = 0
    dipspec: list[int] = field(default_factory=list[int])
    Cibles_Defaut: int = 0
    NbSyllabes: int = 0
    fconsfeats: list[int] = field(default_factory=list[int])
    asperation: int = 0
    reset_pitch: int = 0
    bound: int = 0
    nphone: int = 0
    nphonelast: int = 0
    phonestep: int = 0
    fric_count: int = 0
    frequency_shift: int = 0
    lastoffs: int = 0
    default_pitch: int = 0
    initpardelay: int = 0
    shrink: int = 0
    shrif: int = 0
    shrib: int = 0
    had_hatbegin: int = 0
    had_hatend: int = 0
    had_in_phrase_final: int = 0
    docitation: int = 0
    modulcount: int = 0
    smodulcount: int = 0
    gettar_count: int = 0
    delta_special: int = 0
    special_phrase: int = 0
    new_sentence: int = 0
    nstep: int = 0
    gain: int = 0
    tarold: int = 0
    dur1: int = 0
    oldval: int = 0
    th_to_s: int = 0
    lastf0: int = 0
    evryoth: int = 0
    emphasisflag: int = 0
    pbvalue: int = 0
    p_bvalue: int = 0
    impulse_width: int = 0
    vowel_portion: int = 0
    test_targf0: int = 0
    targf0_increment: int = 0
    diff_targf0: int = 0
    impulse_width_increment: int = 0
    diff_impulse_width: int = 0
    ramp_targf0: int = 0
    ramp_impulse_width: int = 0
    ramp_delayf0: int = 0
    last_preamble_command: int = 0
    Word_has_stress: int = 0
    pSTphsettar: object | None = None


__all__ = ["DphT"]
