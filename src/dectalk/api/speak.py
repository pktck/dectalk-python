"""High-level text → audio entry points.

The audio path (``speak`` / ``to_wav``) routes through :mod:`dectalk._capi`
when the locally-built DECtalk C library is available — output is then
byte-identical to the DECtalk binary. When ``_capi`` cannot be loaded
(no C library on the host, e.g. CI runners, end-user installs without
the source tree, ``lang`` other than ``"us"``), the audio path falls
back to the approximate Python pipeline (``kernel``/``cmd``/``lts``/
``dic``/``ph``).

The phoneme-list path (``text_to_phonemes``) and the direct-phoneme
path (``synthesize_phonemes``) always use the approximate Python front
end; they will be replaced as their corresponding C modules are
translated in Phases C-E of the C-to-Python port plan.

Words missing from the bundled lexicon are reported via
:exc:`UnknownWordError` from the phoneme path. The audio path never
raises that — both the C library and the approximate Python LTS have
their own letter-to-sound rules.
"""

from __future__ import annotations

import io
import os
import wave
from collections import deque
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np
from numpy.typing import NDArray

from dectalk._capi import CAPI, CAPIError

if TYPE_CHECKING:
    from dectalk.include.phoneme_codes import USPhoneme
from dectalk.cmd import SpeechState, parse
from dectalk.data.voices import PRESETS, VoicePreset, get_preset
from dectalk.dic import lookup
from dectalk.dic.form_class_bits import FC_ADJ, FC_NOUN
from dectalk.dic.markers import (
    emits_vpstart,
    load_formclass_lexicon,
    load_marker_lexicon,
    load_vpstart_words,
)
from dectalk.kernel.normalize import try_url
from dectalk.kernel.text import Token, TokenKind, tokenize
from dectalk.lts import lts
from dectalk.lts.homo_disambig import (
    BATS705_DEFAULT_FC,
    resolved_form_class,
    select_homograph_entry,
)
from dectalk.lts.suffix_formclass import suffix_form_class
from dectalk.nt.audio import write_wav
from dectalk.ph.prosody import split_sentences
from dectalk.ph.sequencer import synthesize_phonemes

# Escape-hatch env var for the no-``_capi`` dispatch. Unset (or any
# value other than "0") routes US-English audio through the full
# translated PH pipeline; "0" selects the legacy approximate path.
# See :func:`_use_full_pipeline`.
#
# The full pipeline's render stage has no escape hatch of its own:
# the ``vtm1.c``-ported synthesiser is the only FULL-path render. The
# former ``DECTALK_USE_VTM1=0`` legacy hlsyn render was retired by
# issue #279 after the full 133,641-prompt corpus went byte-exact on
# the vtm1 path (#274 made vtm1 the default; #311/#312 made FULL the
# no-``_capi`` default) — the env var is ignored if set.
_FULL_PIPELINE_ENV: str = "DECTALK_FULL_PIPELINE"


def _use_full_pipeline(lang: str) -> bool:
    """Whether the no-``_capi`` audio path uses the full PH pipeline.

    Defaults to True for US English (issue #311): when ``_capi`` is
    unavailable (or ``DECTALK_DISABLE_CAPI=1``), ``speak``/``to_wav``
    route through the translated PH orchestration chain
    (:func:`_speak_via_python_full`) + the ``vtm1.c``-ported
    synthesiser — the byte-exact parity path measured at 100% on the
    500-prompt stratified sample and the full-corpus WAV gate. Set
    ``DECTALK_FULL_PIPELINE=0`` to select the legacy approximate
    pipeline (parse -> tokenize -> LTS -> sequencer) instead; that
    path is retained as a diagnostic escape hatch (the #272/#274
    pattern one level up) and for languages other than US English,
    which the full pipeline does not yet wire.
    """
    return lang == "us" and os.environ.get(_FULL_PIPELINE_ENV) != "0"


# Symbol characters the DECtalk C kernel splits out of a chunk and
# speaks via their own runtime-dictionary rows (issue #244). Each maps
# to a ``__SYM_*__`` sentinel resolved in ``word_phoneme_overrides``
# with the exact Dic_us.txt phonemes (lines 70-236: ``&,N,'@nd`` /
# ``+,N,pl'^s`` / ``=,N,'ikwLz`` / ``@,N,'@t`` / ``^,N,k'Erxt`` / ...).
# ``#`` is handled separately (its row is the two-word ``n'^mbR sAn``).
# Deliberately absent: ``$`` (currency formats), ``-`` (hyphen
# compounds + dash/number ranges), ``.``/``,``/``:``/``;`` (pause and
# decimal syntax) — those belong to other front-end paths.
_SYMBOL_SENTINELS: Final[dict[str, str]] = {
    "&": "__SYM_AMPERSAND__",
    "%": "__SYM_PERCENT__",
    "@": "__SYM_AT__",
    "+": "__SYM_PLUS__",
    "=": "__SYM_EQUALS__",
    "*": "__SYM_ASTERISK__",
    "/": "__SYM_SLASH__",
    "^": "__SYM_CARET__",
}

# Title abbreviations that are plain runtime-dictionary entries keyed
# WITH the trailing period (issue #246; Dic_us.txt: ``mr.,N,mIstR`` /
# ``mrs.,N,mIs|z`` / ``Ms.,N,mIz`` / ``Prof.,N,prxf'EsR`` /
# ``vs.,N,vRs|s``). They hit case-insensitively in every context —
# including end of input — and consume the period (no sentence break).
# ``dr.``/``st.`` are NOT here: they go through the
# ``ls_task_Dr_St_process`` context rule (see the chunk-loop pre-pass
# in ``text_to_dectalk_phonemes``). ``no.`` is NOT an entry either —
# the C reads ``No. 5`` as "no" + period, already matched.
_TITLE_DICT_SENTINELS: Final[dict[str, str]] = {
    "mr": "__TITLE_MR__",
    "mrs": "__TITLE_MRS__",
    "ms": "__TITLE_MS__",
    "prof": "__TITLE_PROF__",
    "vs": "__TITLE_VS__",
}

# Nominal speaking rate that maps to ``rate=1.0`` in the public API.
# DECtalk's TextToSpeechSetRate accepts words-per-minute in [75, 600];
# 180 wpm is the binary's default (per
# ``${DECTALK_SRC}/src/docsosf/html/idh_ref_2_speaking_rate.htm``: "The
# default speaking rate is 180 words per minute (WPM)"). Empirically
# verified: ``say -a 'testing one two three'`` and
# ``say -a '[:rate 180] testing one two three'`` produce identical
# sample counts (19099) — i.e. 180 WPM is the no-command baseline.
# Keep in sync with :data:`dectalk.cmd.commands._DEFAULT_WPM`.
_DEFAULT_WPM: int = 180

# Expected WAV format from _capi: 16-bit signed mono.
_INT16_SAMPLE_WIDTH: int = 2
_MONO_CHANNELS: int = 1

# Per-utterance leading / trailing silence pads matching the DECtalk
# binary's envelope. The C kernel emits a short leading silence (~20 ms)
# before any audible audio and a longer trailing silence (~380 ms) after
# the final sentence (the ``nfperiod`` end-of-utterance pad in
# ``ph_phram`` -- empirically 4170-4571 samples / 380-415 ms across the
# parity corpus). The approximate Python pipeline (used when ``_capi``
# is unavailable) renders only the phoneme contents and produces nearly
# zero leading / trailing silence, leaving every prompt under-running by
# ~4 K samples vs the C reference. Padding here closes that gap on the
# under-running prompts (e.g. ``DECtalk version 6.2.0``, ``hello!``)
# from -4060 samples down to within ±400 (issue #201). The pad sizes
# are tuned to the median of the C reference rather than per-prompt --
# the leading number is consistent across the corpus, and the trailing
# number is uniform for any utterance ending in a sentence-final
# punctuation mark or at end-of-text (which DECtalk treats as implicit
# sentence end).
_LEADING_SILENCE_SAMPLES: int = 213
"""Samples of silence prepended to every approximate-pipeline utterance.

Mirrors the ~19 ms onset pad the C kernel emits before any phoneme audio
(observed via first-nonzero sample analysis on the 15-prompt parity
corpus -- 213 samples is the floor / most common value)."""

_TRAILING_SILENCE_SAMPLES_SENTENCE: int = 4200
"""Samples appended after a sentence-final approximate utterance.

Mirrors the ~380 ms end-of-utterance pad the C kernel emits after the
last phoneme of any utterance that ends in ``.``, ``!``, ``?``, or at
end-of-text (which DECtalk treats as an implicit period). Empirically
the C trailing pad ranges 4170-4571 samples; 4200 is in the middle of
that band."""

_TRAILING_SILENCE_SAMPLES_CLAUSE: int = 100
"""Samples appended after a non-sentence-final approximate utterance.

When the text ends with a clause mark (``,``, ``;``, ``:``) rather than
a sentence terminator, the C kernel emits only a token (~100-sample)
trailing pad."""

_SENTENCE_FINAL_PUNCT: frozenset[str] = frozenset({".", "?", "!"})
"""Punctuation marks that trigger the long end-of-utterance silence."""

# Lazily-constructed CAPI singleton; created on first audio call so
# imports of this module don't require the C library to be present.
# ``_capi_unavailable`` is set to True after a failed attempt so we
# don't keep retrying (and re-emitting the same import error).
_capi_instance: CAPI | None = None
_capi_unavailable: bool = False


class UnknownWordError(KeyError):
    """Raised when a word is not in the bundled lexicon (phoneme path only)."""


def _try_get_capi() -> CAPI | None:
    """Return the CAPI singleton, or None if the C library can't be loaded.

    Honours ``DECTALK_DISABLE_CAPI=1`` -- when set, the function returns
    None unconditionally so the caller takes the pure-Python path. Used
    by the stop-hook verifier to assert that the Python pipeline produces
    byte-identical output without any C-library wrapper.
    """
    global _capi_instance, _capi_unavailable  # noqa: PLW0603
    if os.environ.get("DECTALK_DISABLE_CAPI") == "1":
        return None
    if _capi_unavailable:
        return None
    if _capi_instance is None:
        try:
            _capi_instance = CAPI()
        except (CAPIError, OSError):
            _capi_unavailable = True
            return None
    return _capi_instance


def _voice_to_speaker_id(voice: str | VoicePreset | None) -> int | None:
    """Map a public-API ``voice`` argument to a DECtalk speaker ID.

    Returns None when no speaker change is needed (default = Perfect Paul).
    """
    if voice is None:
        return None
    preset = voice if isinstance(voice, VoicePreset) else get_preset(voice)
    return int(preset.voice)


def _rate_multiplier_to_wpm(rate: float) -> int:
    """Convert a multiplier (1.0 = normal, 2.0 = slower) to WPM."""
    return max(75, min(600, round(_DEFAULT_WPM / rate)))


def _wav_bytes_to_int16(wav_bytes: bytes) -> NDArray[np.int16]:
    """Decode a 16-bit mono WAV byte string into an ``int16`` NumPy array."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as fh:
        if fh.getsampwidth() != _INT16_SAMPLE_WIDTH or fh.getnchannels() != _MONO_CHANNELS:
            raise CAPIError(
                f"_capi returned non-int16-mono WAV "
                f"(sampwidth={fh.getsampwidth()}, channels={fh.getnchannels()})"
            )
        raw = fh.readframes(fh.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _resolve_voice(voice: str | VoicePreset | None) -> VoicePreset | None:
    """Coerce a voice argument (None | name | preset) to a preset or None."""
    if voice is None:
        return None
    if isinstance(voice, VoicePreset):
        return voice
    return get_preset(voice)


def _voice_name_for_spdefs(voice: str | VoicePreset | None) -> str | None:
    """Extract a canonical voice name from the public-API voice argument.

    Used by :func:`_render_clause_full` to look up the right row in the
    C voice-definition table (:mod:`dectalk.ph.voice_definitions`). The
    table is keyed by the same lower-case strings as
    :data:`dectalk.data.voices.PRESETS`; a :class:`VoicePreset`'s
    :class:`~dectalk.include.dectalk.Voice` enum lets us recover that
    string by reverse-lookup. Returns ``None`` when no name is supplied
    so :func:`~dectalk.ph.voice_definitions.spdefs_for_voice` picks the
    Paul default.
    """
    if voice is None:
        return None
    if isinstance(voice, str):
        return voice.lower()
    # ``VoicePreset``: reverse-lookup the canonical name via the global
    # PRESETS registry (each preset's ``voice`` enum is unique within
    # the table). Falling back to ``None`` (== Paul) is safe -- the
    # value still feeds the LL synthesizer's per-voice speaker/F0.
    for name, preset in PRESETS.items():
        if preset is voice or preset.voice == voice.voice:
            return name
    return None


def _speak_via_capi(
    text: str,
    rate: float,
    voice: str | VoicePreset | None,
) -> bytes | None:
    """Render ``text`` through the C library, or return None if unavailable.

    Used by both :func:`speak` (decodes the WAV bytes) and :func:`to_wav`
    (writes them directly).
    """
    capi = _try_get_capi()
    if capi is None:
        return None
    speaker_id = _voice_to_speaker_id(voice)
    wpm = _rate_multiplier_to_wpm(rate) if rate != 1.0 else None
    try:
        return capi.speak(text, speaker=speaker_id or 0, rate=wpm)
    except CAPIError:
        return None


def _arpabet_to_us_allophone(name: str) -> int | None:  # pyright: ignore[reportUnusedFunction]
    """Map an ARPABET phoneme symbol (e.g. ``"AH"``, ``"HH1"``) to a USP code.

    Retained after issue #69 wired the full ``phsort + us_phalloph`` chain
    in :mod:`dectalk.ph.us_phalloph2` (which moved the active alias
    handling to that module). The reference implementation here remains
    so that tests under ``tests/unit/test_arpabet_us_alias.py`` and any
    diagnostic / debug paths still resolve.


    Strips a trailing stress digit, upper-cases, and looks up the name in
    the :class:`~dectalk.include.phoneme_codes.USPhoneme` enum. Several
    CMU-ARPABET symbols don't share their name with the FONIX/DECtalk
    allophone enum (e.g. ARPABET ``HH`` is named ``HX`` in the DECtalk
    table); :data:`_ARPABET_ALIAS` covers those before falling back to a
    bare-name lookup. Returns ``None`` when the symbol isn't a recognised
    US allophone.

    The alias table follows the audit in
    ``docs/parity-divergence-audit.md`` (issue #58); see also
    ``${DECTALK_SRC}/src/dapi/src/include/l_us_ph.h`` for the
    authoritative DECtalk allophone names.
    """
    from dectalk.include.phoneme_codes import PFUSA, USPhoneme  # noqa: PLC0415

    # Unstressed CMU vowels (``AH0`` / ``IH0``) map to DECtalk's
    # explicit schwa allophones (AX / IX) — the C source US dictionary
    # uses ``x`` / ``|`` for these slots rather than the unreduced
    # ``^`` / ``I`` forms. Issue #156 / parity re-audit §2. Mirrored in
    # ``dectalk.ph.us_phalloph2._ARPABET_UNSTRESSED_ALIAS_OFFSET``.
    upper_name = name.upper()
    _unstressed = {"AH0": USPhoneme.AX, "IH0": USPhoneme.IX}
    if upper_name in _unstressed:
        return (PFUSA << 8) | int(_unstressed[upper_name])

    bare = name.rstrip("0123456789").upper()
    member = _ARPABET_ALIAS.get(bare)
    if member is None:
        try:
            member = USPhoneme[bare]
        except KeyError:
            return None
    return (PFUSA << 8) | int(member)


def _build_arpabet_alias() -> dict[str, USPhoneme]:
    """Build the ARPABET→USPhoneme alias table.

    Consulted by :func:`_arpabet_to_us_allophone`.

    The keys are CMU-ARPABET symbols (already stress-stripped, upper-
    cased) that do *not* share their name with the DECtalk
    :class:`~dectalk.include.phoneme_codes.USPhoneme` enum. The values
    point at the DECtalk allophone the front-end should emit for that
    ARPABET input.

    Sources:

    * ``docs/parity-divergence-audit.md`` (issue #58) — names the
      three high-impact aliases ``HH→HX``, ``L→LL``, ``NG→NX`` whose
      absence drops 38% of phones on ``"hello world"``.
    * ``${DECTALK_SRC}/src/dapi/src/include/l_us_ph.h`` — authoritative
      DECtalk allophone names (FONIX scheme).

    The remaining CMU-39 ARPABET symbols share names with their
    DECtalk counterparts and resolve via the bare-name fallback in
    :func:`_arpabet_to_us_allophone`.
    """
    from dectalk.include.phoneme_codes import USPhoneme  # noqa: PLC0415

    return {
        # CMU ARPABET → DECtalk FONIX allophone.
        "HH": USPhoneme.HX,  # /h/ allophone
        "L": USPhoneme.LL,  # light L (DECtalk's default L allophone)
        "NG": USPhoneme.NX,  # 'sing'
        # CMU ARPABET ``ER`` is the rhotacized vowel "bird"; the C
        # source US dictionary represents it with ``R`` (= US_RR /
        # syllabic R), never with ``K`` (= US_ER). The bare-name
        # USPhoneme.ER fallback yields the wrong allophone for every
        # "bird" / "world" / "her" / "for" / "father" entry.
        # (issue #156 / parity re-audit §2). Mirrored in
        # ``dectalk.ph.us_phalloph2._ARPABET_ALIAS_OFFSET``.
        "ER": USPhoneme.RR,  # /ɝ/ "bird" → syllabic R
    }


# Module-level cache. Initialised lazily on first lookup so an import-time
# circular reference into ``dectalk.include.phoneme_codes`` is avoided
# (the include module already imports cleanly today but keeping the
# closure local matches the rest of this file's style).
_ARPABET_ALIAS: dict[str, USPhoneme] = _build_arpabet_alias()


def _speak_via_python_full(
    text: str,
    rate: float,
    voice: str | VoicePreset | None,
    lang: str,
    lts_fallback: bool,
) -> NDArray[np.int16]:
    """Real PH-stage pipeline -- walks the translated C call chain.

    The default no-``_capi`` path for US English (issue #311);
    ``DECTALK_FULL_PIPELINE=0`` opts out. Routes the input through
    :func:`dectalk.cmd.parse` so inline ``[:cmd value]`` directives
    (rate, voice, phoneme-mode) mutate per-segment state instead of
    leaking into the phone stream, then synthesises each segment via
    the ported C call chain (``ph_claus.c``-style):

      1. tokenize + LTS to build an ARPABET phoneme sequence (uses
         the existing dict + ``lts`` fallback path).
      2. ARPABET symbols -> US allophone codes via the USPhoneme enum.
      3. Populate ``DphT.allophons`` / ``allofeats`` / ``allodurs`` /
         ``nallotot`` from the allophone sequence.
      4. :func:`init_phclause` + :func:`init_timing` + :func:`us_phtiming`
         for per-clause array setup and per-phone duration assignment.
      5. :func:`phinton` for F0 contour generation.
      6. Per-frame driver loop walking ``phsettar`` / ``pht0draw`` /
         ``phdraw`` and emitting one post-``send_pars`` ``delaypars``
         voice packet per 6.4 ms tick.
      7. :func:`~dectalk.vtm.pump_frames.pump_frames_via_vtm1` pumps
         the per-frame post-``send_pars`` ``delaypars`` packets (built
         by :func:`~dectalk.ph.parstochip_to_frames.send_pars_delaypars`,
         issue #275) to int16 PCM through the ``vtm1.c``-ported
         ``speech_waveform_generator`` — the synthesiser the shipped
         ``libtts_us.so`` uses and the byte-exact parity path (issues
         #272 / #311). The former ``DECTALK_USE_VTM1=0`` legacy hlsyn
         render was retired by issue #279 (the hlsyn back-end itself
         remains for :func:`synthesize_phonemes` and the
         ``DECTALK_FULL_PIPELINE=0`` approximate pipeline).

    Args:
        text: Speech input string. May contain ``[:cmd value]``
            directives that mutate per-segment voice / rate / phoneme
            mode.
        rate: Multiplicative speaking-rate factor; ``1.0`` is nominal.
            Combined multiplicatively with any per-segment ``[:rate N]``.
        voice: Initial voice preset (string name, ``VoicePreset``, or
            ``None``). Overridden per-segment by ``[:dv NAME]``.
        lang: Language code; only ``"us"`` is wired for the full path.
        lts_fallback: Allow ``lts()`` for words not in the dictionary.

    Returns:
        16-bit PCM samples at the synthesiser's native sample rate.
    """
    if lang != "us":
        raise NotImplementedError(
            f"DECTALK_FULL_PIPELINE: lang={lang!r} not yet wired; only 'us' is."
        )

    # Route through the inline-command parser so ``[:rate N]`` / ``[:dv]``
    # / ``[:phoneme on]`` directives become per-segment state mutations
    # instead of leaking into the phone stream (issue #64).
    initial_voice = voice if isinstance(voice, str) else None
    initial_state = SpeechState(voice=initial_voice, rate=rate)
    segments = parse(text, initial_state=initial_state)
    if not segments:
        return np.zeros(0, dtype=np.int16)

    chunks: list[NDArray[np.int16]] = []
    for seg in segments:
        # Per-segment voice: a ``[:dv NAME]`` directive overrides the
        # caller's voice; otherwise we fall back to whatever the caller
        # passed (which may be a VoicePreset object rather than a name).
        seg_voice: str | VoicePreset | None = (
            seg.state.voice if seg.state.voice is not None else voice
        )

        # A ``[:phoneme on/off/...]`` directive only selects how ``[...]``
        # bracket blocks are read; it never turns a plain segment body into
        # a raw phoneme stream. The C front-end always LTS-renders text
        # outside brackets, so ``[:phoneme on] hello`` speaks the word
        # "hello" (issue #248). Route every body through the normal path.

        # Render the whole segment body through ONE ``_render_clause_full``
        # call. Its internal ``split_dectalk_stream_clauses`` loop hands
        # the phoneme stream to the per-clause chain one COMMA / PERIOD /
        # QUEST / EXCLAIM-terminated run at a time — the C ``kltask`` /
        # ``speak_now`` shape — while keeping ONE ``DphT``, ONE
        # ``send_pars`` delay pipeline, and ONE vtm1 synthesiser state
        # across the utterance, exactly like the C engine's single PH
        # thread + single VTM stream. The pre-#270 shape here (issue
        # #218) text-split the body per *sentence* and rendered each as
        # its own chunk: every chunk re-hard-init'd F0 (C soft-inits via
        # ``init_clause``'s ``nf0ev = -1``, keeping the declination
        # baseline falling across sentences), dropped one delay-buffer
        # fill frame per sentence (C's ``send_pars`` ``initpardelay``
        # fill happens ONCE per handle), and reset the vtm1 filter
        # memories — diverging every multi-sentence utterance from the
        # binary's continuous stream (issue #307).
        chunk = _render_clause_full(
            seg.body,
            rate=seg.state.rate,
            voice=seg_voice,
            lang=lang,
            lts_fallback=lts_fallback,
            comma_pause=seg.state.comma_pause,
            period_pause=seg.state.period_pause,
            dv_overrides=seg.state.dv_overrides,
            sw_volume=seg.state.sw_volume,
            phoneme_prefix=seg.phoneme_prefix,
        )
        if chunk.size:
            chunks.append(chunk)

    if not chunks:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(chunks)


def _render_clause_full(  # noqa: PLR0915, PLR0912 — orchestration is intrinsically long
    text: str,
    *,
    rate: float,
    voice: str | VoicePreset | None,
    lang: str,
    lts_fallback: bool,
    comma_pause: int | None = None,
    period_pause: int | None = None,
    dv_overrides: tuple[tuple[int, int], ...] = (),
    sw_volume: int = 0,
    phoneme_prefix: bytes = b"",
) -> NDArray[np.int16]:
    """Render a single parser segment's body through the full PH pipeline.

    Pure ``[:cmd]``-free text. Called by :func:`_speak_via_python_full`
    once per :class:`~dectalk.cmd.Segment`.

    Args:
        text: Segment body (no ``[:cmd]`` directives).
        rate: Speaking-rate multiplier for this segment.
        voice: Voice preset for this segment.
        lang: Language code (only ``"us"`` is wired).
        lts_fallback: Allow LTS for out-of-lexicon words.
        comma_pause: ``[:comma N]`` milliseconds from the segment
            state, or None when unset (issue #249).
        period_pause: ``[:period N]`` milliseconds from the segment
            state, or None when unset.
        dv_overrides: ``[:dv <field> <value>]`` design-voice writes as
            ordered ``(spd_index, raw_value)`` pairs; overlaid (tunedef +
            ``limit[]`` clamp) onto the voice's ``SPDEF`` row before the
            speaker reload (issue #331). Empty tuple = no overrides.
        sw_volume: ``[:volume set N]`` dB gain offset (issue #331), folded
            into the speaker chip's voicing / frication / aspiration gains
            by :func:`~dectalk.ph.setspdef.spd_chip_from_row`. ``0`` is
            unity (byte-exact default path).
    """
    from dectalk.kernel.ksd_t import KsdT  # noqa: PLC0415
    from dectalk.kernel.lang_codes import LANG_english  # noqa: PLC0415
    from dectalk.ph.dph_settar_st import DphSettarSt  # noqa: PLC0415
    from dectalk.ph.dph_t import DphT  # noqa: PLC0415
    from dectalk.ph.init_phclause import init_phclause  # noqa: PLC0415
    from dectalk.ph.init_timing import init_timing  # noqa: PLC0415
    from dectalk.ph.phsettar import phsettar  # noqa: PLC0415
    from dectalk.ph.setspdef import (  # noqa: PLC0415
        C_SPEAKER_INDEX,
        apply_dv_overrides,
        seed_dph_scalars,
        spd_chip_from_row,
    )
    from dectalk.ph.tts_handle import TtsHandle  # noqa: PLC0415
    from dectalk.ph.us_phtiming import us_phtiming  # noqa: PLC0415
    from dectalk.ph.voice_definitions import VOICES_BY_NAME, voice_paul  # noqa: PLC0415

    voice_preset = _resolve_voice(voice)
    # Per-voice ``SPDEF`` row from the active DECtalk 4.3 voice table
    # (``p_us_vdf_dectalk43.c``; issue #164 / #302). The ``usevoice``
    # tune-table addition is a no-op on this build (the active
    # ``p_us_vdf_oldtune.c`` rows are all-zero at 11025 Hz — see
    # ``dectalk.ph.setspdef``), so the raw row IS ``curspdef``.
    voice_name = _voice_name_for_spdefs(voice) or "paul"
    voice_row: Sequence[int] = VOICES_BY_NAME.get(voice_name, voice_paul)
    # ``[:dv <field> <value>]`` design-voice writes (issue #331): clamp each
    # to its ``limit[]`` range and overlay onto ``curspdef`` before the
    # speaker reload, exactly as the C ``NEW_PARAM`` path mutates the row
    # ahead of ``setspdef``. The tunedef add is a no-op on this build.
    if dv_overrides:
        voice_row = apply_dv_overrides(voice_row, dv_overrides)

    # 1. Text -> the byte-exact DECtalk phoneme stream. This is the same
    # ASCII stream the LTS+dic oracle path emits — byte-identical to the C
    # library's ``convert_to_phonemes`` across the parity corpus. Routing
    # the synth path through it (instead of the approximate per-word
    # ``_tokens_to_phoneme_words`` -> ``lts()`` lookup it used before)
    # means the audio inherits the *faithful* phoneme stream: spelled-out
    # acronyms (``BBC`` -> ``b' iy b' iy s' iy``, #217), digit-expansion
    # prosody (the ``) eh n d`` "and" + comma pauses, #225 / #238), the
    # correct vowel reductions (IH -> IX / AH -> AX) and syllabic
    # EL/EN/IR, and no spurious cross-word sibilant insertions (#237). The
    # stream's embedded punctuation / phrase markers (``COMMA`` / ``PERIOD``
    # / ``VPSTART`` / ``MBOUND`` / …) flow straight into ``phsort`` exactly
    # as the C kernel's ``symbols[]`` stream does, so ``all_phsort``
    # generates the internal ``GEN_SIL`` phones and clause-boundary
    # features natively — superseding the hand-rolled boundary-feature
    # fix-ups this function used to need (#218).
    # A ``phoneme_prefix`` carries a pre-computed DECtalk phoneme stream that
    # is prepended to the segment body's phonemes and rendered as ONE
    # utterance (issue #330). It is used for the malformed-command error
    # strings ("Command error in command." etc.), whose fixed pronunciations
    # are injected char-by-char into the C LTS pipe (``cm_cmd.c:878``) rather
    # than looked up per-word — so the exact C phoneme bytes are embedded
    # verbatim, bypassing the Python LTS (which mispronounces "error" /
    # "parameter"). Prepending keeps the error + following text one
    # continuous stream, matching the C engine's single PH thread.
    raw_phonemes = phoneme_prefix + text_to_dectalk_phonemes(
        text, lang=lang, lts_fallback=lts_fallback
    )
    if not raw_phonemes:
        return np.zeros(0, dtype=np.int16)

    # 3. Build engine state.
    # Map rate (multiplier; 1.0 == _DEFAULT_WPM nominal, 2.0 == half-
    # speed, 0.5 == double-speed) to DECtalk's words-per-minute sprate
    # field. The conversion mirrors the inverse formula in
    # :func:`_rate_multiplier_to_wpm` so both the C-routed and pure-
    # Python paths derive the same WPM from the same multiplier — and
    # so an inline ``[:rate N]`` directive (which
    # :func:`dectalk.cmd.commands._cmd_rate` encodes as
    # ``rate = _DEFAULT_WPM / N``) round-trips back to ``wpm = N``
    # here (issue #70). init_timing inspects sprate to derive
    # timeref / sprat0 / sprat1 / sprat2 etc.
    wpm = _rate_multiplier_to_wpm(rate)

    p_dph_t = DphT()
    p_dph_t.dipspec = [0] * 256
    p_dph_t.parstochip = [0] * 64
    p_dph_t.sprate = wpm
    # Per-voice speaker seeding — the full ``setspdef`` scalar reload
    # (``ph_vset.c`` lines 541-831) ported in ``dectalk.ph.setspdef``
    # (issue #302). Seeds malfem (male/female target-table select in
    # ``gettar``), fnscale (Q12 head-size formant scaler), the F0
    # scalars (f0_lp_filter / f0minimum / f0scalefac / size_hat_rise /
    # scale_str_rise / f0basefall / assertiveness — the #259/#261
    # wrong-variant and missing-scale defects live in the derivations,
    # documented at the port), the ``phdraw`` tilt/bandwidth scalars
    # (f0_dep_tilt=FT, spdeftltoff=(SM*25)/100, spdefb1off=(BR²>>1)+4096
    # — #226/#289), the breathy-AH scalar (spdeflaxprcnt=LX*41, #148),
    # and last_lang=0 (forces gettar table reload on first call).
    # Replaces the Paul-only literals that used to live here: non-Paul
    # voices (rita FT=0 BR=46 SM=24, wendy LX=80 BR=55 SM=100, kit
    # HS=80 SEX=0, ...) now derive every scalar from their own row.
    seed_dph_scalars(p_dph_t, voice_row)
    # Matching per-voice SPD_CHIP block (same setspdef pass, chip side):
    # feeds phdraw's llframe conversion (F4/B4/F5/B5) and the vtm1
    # speaker seed (gains / nopen / aturb / t0jit / fnscale). For Paul
    # this equals the oracle-packet-verified ``default_us_paul_spd()``
    # block (issue #284).
    # ``sw_volume`` folds the ``[:volume set N]`` dB offset into the chip's
    # voicing / frication / aspiration gains (issue #331); 0 = unity.
    _spd_chip = spd_chip_from_row(
        voice_row, speaker=C_SPEAKER_INDEX.get(voice_name, 0), sw_volume=sw_volume
    )
    # Seed F0 to the speaker's f0minimum so the very first ``pht0draw``
    # frame's ``f0prime = f0 + f0s`` reflects the voice's baseline rather
    # than the calloc'd zero (which scales below LOWEST_F0 = 500 deciHz
    # and gets clamped, leaving every frame-0 T0 stuck at the synth
    # safety floor). Mirrors the soft-init ``pDph_t->f0 = f0basestart``
    # assignment in ``ph_drwt01.c`` line 440 — the HLSYN ph_drwt02 path
    # drops that line but expects the field to be primed by the speaker
    # activation chain (un-ported here; see issue #148).
    p_dph_t.f0 = p_dph_t.f0minimum
    settar = DphSettarSt()
    # initsw stays at the default 0 so the very-first-call
    # ``getbegtar(phTTS, 0)`` seeding loop in ``init_variables`` fires
    # (ph_setar.c lines 1782-1791). The C source uses initsw as a
    # "very first init since engine startup" gate -- it must run once
    # per process to seed ``param[F1..TILT].tarend`` from the first
    # phone's begin-target. Pre-seeding initsw=1 (the previous Python
    # behaviour) skipped that seeding, leaving tarend at the
    # uninitialised zero values when ``us_back_smooth_rules`` evaluates
    # its "onset" condition on the leading GEN_SIL frame. Letting
    # initsw=0 makes the Python state match what a freshly-started
    # C engine would have on its first ``phsettar`` call (issue #157).
    p_dph_t.pSTphsettar = settar
    handle = TtsHandle()
    handle.p_ph_thread_data = p_dph_t
    p_ksd_t = KsdT()
    p_ksd_t.sprate = wpm
    p_ksd_t.lang_curr = LANG_english
    handle.p_kernel_share_data = p_ksd_t

    # 4. Split the stream into clauses. The C engine's ``ph_task.c``
    # ``kltask`` loop hands symbols to ``phclause`` once per clause
    # delimiter (``isdelim`` = COMMA..EXCLAIM) — NOT once per
    # utterance — and resets the buffer to a fresh leading GEN_SIL
    # after each. Every ``phclause`` pass therefore sees a
    # clause-local ``nallotot``, which drives ``us_phtiming``'s
    # short-phrase rules (Rule 2's ``nallotot < 10`` vowel bonus,
    # Rule 17's ``prcnt += 30``) and the rhythm-pass segmentation.
    # Rendering a multi-clause utterance through one merged clause
    # walk left every content phone in comma-separated prompts
    # systematically short (the ``multi_clause`` |Δ|med=1633 bucket of
    # the 500-prompt FULL+VTM1 sample, issue #270). The per-frame
    # driver below runs once per clause, appending to the same frame
    # stream — exactly as C's per-clause ``phclause`` frame loops feed
    # the single VTM stream.
    from dectalk.ph.us_phalloph2 import (  # noqa: PLC0415
        phalloph2_from_symbols,
        split_dectalk_stream_clauses,
    )

    clause_runs = split_dectalk_stream_clauses(raw_phonemes)

    # 4a-bis. Per-clause pause-length defaults from ``phclause()``
    # lines 247-255 of ``ph_claus.c`` (English branch). These are
    # consulted by ``us_phtiming``'s Rule 1 when computing the
    # GEN_SIL ``dpause`` value (``nfperiod + perpause + asperation``
    # for sentence-end, ``nfcomma + compause + asperation`` for
    # comma-end). Without them the trailing SIL gets the default
    # 15-frame minimum and the Python output is ~360 ms shorter than
    # the C reference (issue #72 trailing-silence pad gap). C re-runs
    # the assignment at every ``phclause`` entry with the same
    # constants, so setting them once before the clause loop is
    # equivalent.
    #
    # The English ``nfperiod`` value is gated by
    # ``#if defined(HLSYN) || defined(CHANGES_AFTER_V43)``:
    # 94 with HLSYN, **75** without. The shipped Linux
    # ``libtts_us.so`` builds with neither macro defined (see
    # ``dectalkf_klsyn.h`` line 116-118: ``HLSYN`` is gated behind
    # ``EPSON_ARM7``), so the active default is 75 (issue #155).
    p_dph_t.nfperiod = 75
    p_dph_t.nfcomma = 16

    # 4a-bis-2. User pause overrides from ``[:comma N]`` /
    # ``[:period N]`` (issue #249). The C command handlers send the
    # CPAUSE / PPAUSE control words down the LTS pipe (``cm_copt.c``
    # lines 2486-2541) and ``ph_task.c`` lines 784-788 consume them:
    #
    #     case CPAUSE: compause = mstofr(deadstop(N, -280, 30000));
    #     case PPAUSE: perpause = mstofr(deadstop(N, -420, 30000));
    #
    # The pipe itself is 16-bit (``DT_PIPE_T`` = unsigned short,
    # port.h line 73), so the value wraps to S16 in transit. The
    # period command clamps to [-420, 30000] at the cmd layer BEFORE
    # the pipe (cm_copt.c lines 2526-2530 — the BTS#10100 fix), which
    # makes its wrap a no-op; the comma command sends the raw value,
    # so e.g. ``[:comma 45000]`` arrives as -20536 and deadstops to
    # -280 (verified byte-identical vs the oracle).
    #
    # ``us_phtiming``'s Rule 1 then adds the fields to the GEN_SIL
    # dpause (``nfcomma + compause + asperation`` / ``nfperiod +
    # perpause + asperation``, p_us_tim.c lines 290-305) — already
    # ported, so seeding the two fields completes the chain.
    if comma_pause is not None or period_pause is not None:
        from dectalk.ph.task_helpers import deadstop, mstofr  # noqa: PLC0415

        def _s16_pipe(value: int) -> int:
            return ((value + 0x8000) & 0xFFFF) - 0x8000

        if comma_pause is not None:
            p_dph_t.compause = mstofr(deadstop(_s16_pipe(comma_pause), -280, 30000))
        if period_pause is not None:
            p_dph_t.perpause = mstofr(deadstop(_s16_pipe(period_pause), -420, 30000))

    # 4a-ter. Zero / size the per-clause scratch arrays ONCE per
    # utterance -- C's ``kltask`` calls ``init_phclause`` at task
    # entry (ph_task.c line 422), NOT per ``phclause``; the per-clause
    # scratch beyond ``nallotot`` intentionally keeps stale data.
    init_phclause(p_dph_t)

    from dectalk.ph.init_clause import init_clause  # noqa: PLC0415
    from dectalk.ph.param_indices import OUT_DU, OUT_PH, OUT_PH2  # noqa: PLC0415
    from dectalk.ph.parstochip_to_frames import send_pars_delaypars  # noqa: PLC0415
    from dectalk.ph.phdraw import phdraw  # noqa: PLC0415
    from dectalk.ph.phinton import phinton  # noqa: PLC0415
    from dectalk.ph.pht0draw import pht0draw  # noqa: PLC0415

    # Accumulate the post-``send_pars`` ``delaypars[]`` packets so the
    # vtm1 synth path (issues #158 / #272 / #275) can pump them through
    # ``speech_waveform_generator`` without re-running the PH stage.
    # Each packet mixes two driver frames exactly as
    # ``ph_claus.c::send_pars`` (lines 694-846) does before its
    # ``spcwrite``: formant-side slots one frame delayed, AV/T0 current,
    # TLT current via the ``lineartilt[]`` LUT — see
    # :func:`~dectalk.ph.parstochip_to_frames.send_pars_delaypars`.
    # That per-frame call is also the dedicated capture seam for the
    # F0 / frame-metadata diagnostics (``tests/parity/test_per_frame_f0
    # .py``, ``tests/unit/test_full_pipeline_frame0_voice_init.py``,
    # ``tests/unit/test_full_pipeline_parstochip_metadata.py``,
    # ``scripts/verify_out_t0_parity.py``), which monkey-patch it to
    # snapshot the *raw* current/previous parstochip pair it receives
    # (issue #279: the seam replaced the retired per-frame LLFrame
    # conversion the legacy hlsyn render used). Keep its call shape
    # (raw pair in, packet out) stable.
    delaypars_frames: list[list[int]] = []
    # Cap each clause's frame loop to keep buggy state from running
    # away during the multi-month port. 8000 frames is ~51 s of audio
    # -- well past any reasonable clause.
    max_frames = 8000
    # One-frame-delay buffer mirroring ph_claus.c's ``delaypars[]``
    # (lines 706-846). Holds the previous frame's parstochip so the
    # F1/B1/F2/B2/F3/B3/FZ/A2..A6/AB/AP slots of the *emitted*
    # packet come from one frame ago, while AV / TLT / T0
    # come from the current frame. The delay buffer lives in
    # ``send_pars``'s per-handle static state, so it spans clause
    # boundaries: only the very FIRST frame of the whole utterance is
    # the fill frame.
    #
    # ``None`` doubles as the utterance-first-iteration marker:
    # ``ph_claus.c::send_pars`` implements the one-frame delay by
    # allocating ``delaypars[]`` on its first call and ONLY seeding
    # it — it does NOT spcwrite that first frame. The synthesizer
    # only receives the delayed buffer on the SECOND call onwards.
    # The Python loop therefore also discards the first iteration's
    # frame: it represents the synth-side delay-buffer fill, not an
    # emitted PCM frame (issue #157 leading-frame bleed -- removes 1
    # frame of leading silence per utterance; #266 leading-silence
    # accounting).
    previous_parstochip: list[int] | None = None

    # 4b..6. Per-clause chain -- one ``phclause()`` equivalent per
    # delimiter-closed symbol run (C: ``speak_now`` -> ``phclause``):
    #
    #   - ``all_phsort`` (``ph_sort.c`` lines 428-1712) -- walks the
    #     clause's symbol stream emitting ``phonemes[]`` /
    #     ``sentstruc[]`` with the full per-phone feature word.
    #   - ``us_phalloph`` (``ph_aloph1.c`` lines 444-1546) -- applies
    #     the US-English allophonic-substitution rules and writes
    #     through to ``allophons[]`` / ``allofeats[]`` (setting the
    #     clause-local ``nallotot``).
    #   - ``init_timing`` + ``us_phtiming`` -- the ~22 named duration
    #     rules; Rule 2's short-phrase bonus and Rule 17's
    #     ``nallotot < 10`` lengthening see the clause-local phone
    #     count exactly as C does.
    #   - ``init_clause`` + ``phinton`` -- F0 contour events. Clause 0
    #     hard-inits pht0draw (``nf0ev = -2`` via ``loadspdef``);
    #     later clauses soft-init (``nf0ev = -1``) because the
    #     ``loadspdef`` consumption below clears the flag -- matching
    #     ``phclause``'s ``if (loadspdef) { loadspdef = FALSE;
    #     setspdef(...); }`` (ph_claus.c lines 259-262), which gives
    #     the C engine its cross-comma F0 declination continuity.
    #   - per-frame driver loop (``pht0draw`` / ``phdraw`` /
    #     ``phsettar``) appending to the utterance-wide frame stream.
    #
    # Because ``raw_phonemes`` carries the C kernel's punctuation /
    # phrase / boundary markers, ``all_phsort`` emits the internal +
    # trailing ``GEN_SIL`` phones and clause-boundary features
    # natively per clause. A clause-final ``!`` arrives as an
    # ``EXCLAIM`` marker, still driving ``raise_last_stress``
    # (issue #212); a yes/no ``?`` arrives as a ``QUEST`` marker,
    # still setting the question clausetype ``phinton`` reads.
    for clause_symbols, clause_nsymbtot in clause_runs:
        # C phclause step 0: init_clause + loadspdef consumption.
        init_clause(p_dph_t)
        if p_dph_t.loadspdef == 1:
            # ``setspdef``'s speaker-scalar seeding equivalent happened
            # at DphT construction above; just consume the flag so the
            # NEXT clause weak-inits F0 (ph_claus.c lines 259-262).
            p_dph_t.loadspdef = 0

        phalloph2_from_symbols(handle, clause_symbols, clause_nsymbtot)

        init_timing(
            p_dph_t,
            settar,
            sprate_ref=[wpm],
            lang_curr=LANG_english,
        )

        # Per-allophone duration rules (us_phtiming). Must run AFTER
        # init_timing (which seeds sprat0/sprat1/sprat2) and BEFORE
        # the per-frame loop (which needs durfon = allodurs[nphone]).
        us_phtiming(handle)

        # phinton: F0 contour generation, once per clause. Writes
        # f0tar / f0type / f0length / f0tim on DphT.
        phinton(handle)

        # Per-frame driver loop -- mirrors ph_claus.c's phclause
        # while-loop (lines 367-505). For each 6.4 ms frame:
        #
        #   * Increment tcum. If it has passed the current allophone's
        #     duration, advance ``nphone`` (breaking when allophones
        #     run out), reset ``tcum``, set ``durfon`` from
        #     ``allodurs``, and re-run phsettar for the new allophone.
        #   * Call pht0draw to generate the F0 contour for this frame,
        #     writing ``parstochip[OUT_T0]``.
        #   * Call phdraw to update ``parstochip[]`` for this frame.
        #   * Mix ``parstochip[]`` with the previous frame's via
        #     ``send_pars_delaypars`` and append the emitted packet.
        #
        # The first iteration enters the "advance" branch (tcum starts
        # at -1, durfon at 0 -- C's init_pars()), so phsettar gets
        # called for nphone=0 inside the loop. ``phinton`` may insert
        # a dummy schwa which increments ``p_dph_t.nallotot``; reading
        # it live keeps the trailing GEN_SIL in the walk (#72).
        p_dph_t.tcum = -1
        p_dph_t.nphone = -1
        p_dph_t.durfon = 0
        for _ in range(max_frames):
            p_dph_t.tcum += 1
            if p_dph_t.tcum >= p_dph_t.durfon:
                p_dph_t.nphone += 1
                if p_dph_t.nphone >= p_dph_t.nallotot:
                    break
                p_dph_t.tcum -= p_dph_t.durfon
                p_dph_t.durfon = (
                    p_dph_t.allodurs[p_dph_t.nphone] if p_dph_t.allodurs[p_dph_t.nphone] > 0 else 40
                )
                # Phoneme-code / duration metadata writes from
                # ph_claus.c lines 465-472 (BATS 887, eab 5/3/99).
                # Consumed by debug / instrumentation readers (frame
                # dumps), not the Klatt synthesiser; keeps frame-dump
                # parity with the C binary.
                p_dph_t.parstochip[OUT_PH] = p_dph_t.allophons[p_dph_t.nphone]
                p_dph_t.parstochip[OUT_DU] = p_dph_t.allodurs[p_dph_t.nphone]
                if p_dph_t.nphone + 1 > p_dph_t.nallotot:
                    p_dph_t.parstochip[OUT_PH2] = 0
                else:
                    p_dph_t.parstochip[OUT_PH2] = p_dph_t.allophons[p_dph_t.nphone + 1]
                phsettar(handle)
            pht0draw(handle)
            phdraw(handle)
            if previous_parstochip is not None:
                delaypars_frames.append(
                    send_pars_delaypars(p_dph_t.parstochip, previous_parstochip)
                )
            # else: first iteration of the utterance — matches C's
            # send_pars initpardelay==0 branch, which only seeds
            # delaypars and skips the spcwrite. The synthesizer never
            # sees this frame directly; its formant side re-surfaces
            # as the delayed half of the first emitted packet.
            previous_parstochip = list(p_dph_t.parstochip)

    # 7. Pump the collected voice packets through the synthesizer for
    # int16 PCM output: the post-send_pars ``delaypars`` packets go
    # through ``speech_waveform_generator`` (vtm1.c) -- the same
    # synthesiser the shipped ``libtts_us.so`` uses (issue #158)
    # consuming the same packet stream the C driver's spcwrite ships
    # (issue #275) -- the byte-exact parity path (issues #272 / #311).
    # ``KsdT.vol_att`` (always the default 100 until the ``[:volume
    # N]`` port lands) threads through to the pump's Q15 post-scale.
    # The former ``DECTALK_USE_VTM1=0`` legacy hlsyn render of this
    # step was retired by issue #279.
    from dectalk.vtm.pump_frames import pump_frames_via_vtm1  # noqa: PLC0415

    return pump_frames_via_vtm1(
        list(delaypars_frames),
        voice_preset,
        spd_chip=_spd_chip,
        vol_att=p_ksd_t.vol_att,
    )


def _utterance_trailing_silence_samples(text: str) -> int:
    """Return the trailing-silence pad length for an approximate-path utterance.

    DECtalk's C kernel appends a long (~380 ms) silence after any
    utterance that ends in a sentence terminator (``.``, ``!``, ``?``)
    or at end-of-text (which the kernel treats as an implicit period).
    Utterances that end at a clause boundary (``,``, ``;``, ``:``) get
    only a short (~10 ms) pad. The approximate Python pipeline doesn't
    model these pads natively, so this helper picks the right length
    based on the raw text's trailing punctuation. Used by
    :func:`_speak_via_python` to close the front-end under-run gap on
    short sentence-final prompts (issue #201).
    """
    stripped = text.rstrip()
    if not stripped:
        return _TRAILING_SILENCE_SAMPLES_CLAUSE
    last = stripped[-1]
    # End-of-text without an explicit terminator is treated as an
    # implicit sentence end by the C kernel -- matches the empirical
    # ~4200-sample trailing pad on prompts like "DECtalk version 6.2.0"
    # (no terminator) and "hello!" (explicit ``!``).
    if last in _SENTENCE_FINAL_PUNCT or last.isalnum():
        return _TRAILING_SILENCE_SAMPLES_SENTENCE
    return _TRAILING_SILENCE_SAMPLES_CLAUSE


def _speak_via_python(
    text: str,
    rate: float,
    voice: str | VoicePreset | None,
    lang: str,
    lts_fallback: bool,
) -> NDArray[np.int16]:
    """Pure-Python audio pipeline dispatch (no ``_capi``).

    For US English this routes through :func:`_speak_via_python_full`
    — the translated PH orchestration chain + ``vtm1.c``-ported
    synthesiser, byte-identical to the DECtalk binary across the
    parity corpus (issue #311; the no-``_capi`` default since the
    full-corpus WAV burn-down). ``DECTALK_FULL_PIPELINE=0`` opts out
    to the legacy approximate path below (parse -> tokenize -> LTS ->
    sequencer), which also serves languages other than US English.
    The approximate output is intelligible but not byte-identical.

    The approximate path's output is wrapped with leading + trailing
    silence pads matching the C reference's per-utterance envelope
    (issue #201). The approximate phoneme sequencer renders only the
    audible phoneme contents, so without these pads every prompt
    under-ran the C reference by ~4000 samples (the missing trailing
    pause). The pad sizes mirror the C kernel's ``nfperiod`` /
    leading-onset behaviour on the 15-prompt parity corpus.
    """
    if _use_full_pipeline(lang):
        return _speak_via_python_full(text, rate, voice, lang, lts_fallback)
    initial_voice = voice if isinstance(voice, str) else None
    initial_state = SpeechState(voice=initial_voice, rate=rate)
    segments = parse(text, initial_state=initial_state)
    if not segments:
        return np.zeros(0, dtype=np.int16)

    chunks: list[NDArray[np.int16]] = []
    for seg in segments:
        preset = _resolve_voice(seg.state.voice)
        if preset is None and isinstance(voice, VoicePreset):
            preset = voice

        # ``[:phoneme ...]`` never re-interprets a plain body as phonemes
        # (issue #248); the body is always LTS-rendered as normal text.
        for sentence_text, is_question in split_sentences(seg.body):
            phones = _tokens_to_phonemes(
                tokenize(sentence_text),
                lang=lang,
                lts_fallback=lts_fallback,
                spell_out=_acronym_spell_out_words(sentence_text),
            )
            if not phones:
                continue
            chunks.append(
                synthesize_phonemes(
                    phones,
                    rate=seg.state.rate,
                    preset=preset,
                    question=is_question,
                )
            )

    if not chunks:
        return np.zeros(0, dtype=np.int16)
    # Wrap the synthesised content with the C-kernel-equivalent
    # leading + trailing silence pads (issue #201). The leading pad is
    # uniform; the trailing pad's length depends on whether the text
    # ends at a sentence terminator (long pad) or a clause mark (short
    # pad). Both are no-op silence -- they only shift the output
    # envelope to match the binary's, closing the front-end under-run
    # observed on prompts like ``DECtalk version 6.2.0`` and ``hello!``.
    leading = np.zeros(_LEADING_SILENCE_SAMPLES, dtype=np.int16)
    trailing = np.zeros(_utterance_trailing_silence_samples(text), dtype=np.int16)
    return np.concatenate([leading, *chunks, trailing])


def text_to_phonemes(text: str, *, lang: str = "us", lts_fallback: bool = True) -> list[str]:
    """Convert text to a flat ARPABET phoneme stream with pause markers.

    Currently uses the approximate Python front end (kernel/dic/lts); will
    be replaced by the translated C front end in Phase D of the port plan.
    """
    return _tokens_to_phonemes(
        tokenize(text),
        lang=lang,
        lts_fallback=lts_fallback,
        spell_out=_acronym_spell_out_words(text),
    )


def _isolated_punct_tokens(  # noqa: PLR0911 — one return per C dispatch arm
    chunk: str, *, clause_has_word: bool
) -> list[Token] | None:
    """Token expansion for a whole-chunk punctuation mark, or ``None``.

    Mirrors the C treatment of punctuation that arrives as its own
    whitespace-delimited token (issue #315). In the C front end the
    ``cm_pars_proc_char`` / ``cm_text_getclause`` pair either folds the
    mark onto the previous word or forwards it as its own one-char word,
    which ``ls_spel`` then spells via the language typing table
    (``usa_type.tab``) -- the binary demonstrably SPEAKS punctuation-only
    input ("period" for ``...``). Empirical rules, each pinned against
    ``convert_to_phonemes`` on the flushed stream (the speak path always
    appends an 8-space flush, resolving the parser's pending-dot state):

    - A single ``.,;:!?`` directly after a word in the open clause
      attaches to it as the ordinary clause/sentence marker
      (``cm_text.c`` rev 074 removes the space before clause
      punctuation): ``'hello .'`` -> ``hxaxll' ow.``.
    - With no word in the open clause the mark is spoken by name:
      ``'.'`` -> "period", ``','`` -> "comma", ``':'`` -> "colon",
      ``';'`` -> "semi#colon", ``'!'`` -> "exclamation point",
      ``'?'`` -> "question mark". A name CLOSES the clause for the
      attach rule (its mark is MARK_clause in the C parser), so marks
      following a name are spoken by name too, even when a real word
      opened the clause (``'... !'`` -> "period exclamation point",
      ``'hello ... !'`` -> "hello period exclamation point").
    - Dot runs never attach. ``..`` becomes "period" + an attached
      ``.`` terminator (the LTS splits the 2-dot word into the ``.``
      word plus ``.`` right-punct) while ``...`` / ``....`` collapse
      to the bare "period" word with NO terminator even after a word
      (``'hello ...'`` -> "hello period"; the utterance-final PERIOD
      then comes from the PH task's flush, ``ph_task.c`` line 738).
      Runs of 5+ dots hit a C-side parser bug (the ``cm_pars`` dot
      buffer degenerates to a lone ``t`` word) and stay on the legacy
      pause path here.

    Returns ``None`` for anything that is not a whole-chunk mark this
    port models -- the caller falls through to the regular tokenizer.
    """
    if not chunk or any(c not in ".,;:!?" for c in chunk):
        return None
    if all(c == "." for c in chunk):
        n_dots = len(chunk)
        if n_dots == 1:
            if clause_has_word:
                return [Token(TokenKind.PAUSE_LONG, ".")]
            return [Token(TokenKind.WORD, "__PUNCT_NAME_PERIOD__")]
        if n_dots == 2:  # noqa: PLR2004 — the C parser's 2-dot word
            return [
                Token(TokenKind.WORD, "__PUNCT_NAME_PERIOD__"),
                Token(TokenKind.PAUSE_LONG, "."),
            ]
        if n_dots <= 4:  # noqa: PLR2004 — 3-4 dots collapse to one
            return [Token(TokenKind.WORD, "__PUNCT_NAME_PERIOD__")]
        return None
    if len(chunk) != 1:
        return None  # mixed punctuation run: keep the legacy path.
    if clause_has_word:
        kind = TokenKind.PAUSE_LONG if chunk in "!?" else TokenKind.PAUSE_SHORT
        return [Token(kind, chunk)]
    if chunk == ",":
        return [Token(TokenKind.WORD, "__PUNCT_NAME_COMMA__")]
    if chunk == ":":
        return [Token(TokenKind.WORD, "__PUNCT_NAME_COLON__")]
    if chunk == ";":
        return [
            Token(TokenKind.WORD, "__PUNCT_NAME_SEMI__"),
            Token(TokenKind.PAUSE_SHORT, "#"),
            Token(TokenKind.WORD, "__PUNCT_NAME_SEMI_COLON_TAIL__"),
        ]
    if chunk == "!":
        return [
            Token(TokenKind.WORD, "__PUNCT_NAME_EXCLAMATION__"),
            Token(TokenKind.WORD, "__PUNCT_NAME_POINT__"),
        ]
    # ``?`` is the only remaining member of the mark set.
    return [
        Token(TokenKind.WORD, "__PUNCT_NAME_QUESTION__"),
        Token(TokenKind.WORD, "__PUNCT_NAME_MARK__"),
    ]


def _open_clause_has_word(tokens: list[Token]) -> bool:
    """True when the still-open clause already carries a real word.

    Walks ``tokens`` backwards: a WORD closes the search as a hit, any
    pause/punctuation token closes it as a miss (the clause was
    terminated). A spoken-punctuation-name word (``__PUNCT_NAME_*__``)
    also closes it as a miss: the mark it stands for is MARK_clause in
    the C parser, so the clause dispatches right after it and a
    following mark is spoken by name too (``'. .'`` -> "period period",
    ``'hello ... !'`` -> "hello period exclamation point"). The ``#``
    syllable-break marker is transparent (intra-word, e.g. the hyphen-
    compound path).
    """
    for tok in reversed(tokens):
        if tok.kind is TokenKind.WORD:
            return not tok.text.startswith("__PUNCT_NAME_")
        if tok.text == "#":
            continue
        return False
    return False


def text_to_dectalk_phonemes(  # noqa: PLR0912, PLR0915 — many branches mirror C's per-token dispatch
    text: str, *, lang: str = "us", lts_fallback: bool = True
) -> bytes:
    """Convert text to DECtalk's native ASCII phoneme format (Phase-D oracle target).

    Walks tokens individually so word boundaries become ``"_"`` markers
    consumed by :func:`dectalk.dic.dectalk_phonemes.encode_to_dectalk`.
    The encoder maps those markers to the C source's ``  `` two-space
    word separator. The result can be byte-compared against
    :func:`dectalk._capi.CAPI.convert_to_phonemes` -- the LTS+dic
    stage-boundary oracle on the path to pure-Python bit parity.
    """
    from dectalk.dic.dectalk_phonemes import (  # noqa: PLC0415
        DECTALK_PRIMARY_STRESS,
        DECTALK_SECONDARY_STRESS,
        encode_to_dectalk,
    )

    # DECtalk's punctuation markers come from src/dapi/src/include/
    # usa_phon.tab (the PERIOD/QUEST/EXCLAIM/COMMA/RELSTART entries near
    # the bottom of usa_arpa[]). Each marker is encoded by the encoder
    # as the literal punctuation character + trailing space. The Python
    # tokenizer preserves the actual punct char in ``Token.text`` for
    # pause-kind tokens; we wrap it in a ``__PUNCT__<char>`` marker
    # the encoder recognises.
    punct_prefix = "__PUNCT__"

    # Words that DECtalk's C LTS prefixes with the ``)`` (VPSTART)
    # phrase marker when the convert_to_phonemes path emits them.
    # The Python LTS doesn't model phrase structure yet, so we
    # hardcode the words the parity corpus needs. ``SELLS`` is the
    # verb in "she sells sea shells"; ``SPEAKING`` is the corpus's
    # "betty speaking" / "harry speaking" pattern.
    # Curated list of "pure verbs" that always get the VPSTART ``)``
    # marker in C output. Based on the agent's investigation of
    # ``Dic_us_2002.txt`` form-class flags (bit 18 set, bit 12 clear)
    # plus per-utterance verification. The full dictionary has hundreds
    # of such entries; this curated subset covers the high-frequency
    # cases the corpus exercises. New entries should be added only when
    # they pass the lexical verification.
    vpstart_words: frozenset[str] = frozenset(
        {
            # Curated set of pure verb entries; each verified against
            # the C oracle as producing the ``)`` marker in isolation.
            # Past tenses / past participles that don't get the marker
            # (gone, ate, eaten, spoke, spoken, thought, known, took,
            # wrote, written, sold) are deliberately omitted -- their
            # dictionary form-class differs.
            "SEE",
            "SEES",
            "SEEING",
            "SAW",
            "SEEN",
            "GO",
            "GOES",
            "GOING",
            "WENT",
            "COME",
            "COMES",
            "COMING",
            "CAME",
            "EAT",
            "EATS",
            "EATING",
            "SAY",
            "SAYS",
            "SAYING",
            "SAID",
            "TELL",
            "TELLS",
            "TELLING",
            "TOLD",
            "SPEAK",
            "SPEAKS",
            "SPEAKING",
            "THINK",
            "THINKS",
            "THINKING",
            "KNOW",
            "KNOWS",
            "KNOWING",
            "KNEW",
            "WANT",
            "WANTS",
            "WANTED",
            "WANTING",
            "ASK",
            "ASKS",
            "ASKED",
            "ASKING",
            "MAKE",
            "MAKES",
            "MAKING",
            "TAKE",
            "TAKES",
            "TAKING",
            "TAKEN",
            "READ",
            "READS",
            "READING",
            "WRITE",
            "WRITES",
            "WRITING",
            "SELL",
            "SELLS",
            "SELLING",
            "BAKE",
            "BAKES",
            "BAKED",
            "BAKING",
            "HAPPEN",
            "HAPPENS",
            "HAPPENED",
            "HAPPENING",
            "THANK",
            "THANKS",
            "THANKED",
            "THANKING",
            "LOSE",
            "LOSES",
            "LOSING",
            "SING",
            "SINGS",
            "SINGING",
            "PUT",
            # "PUTS" is deliberately NOT here: its own runtime
            # dictionary row (``puts,N,p`Uts``) carries a noun+verb
            # mask, so the C emitter sends no ``)`` for it — unlike
            # bare PUT and PUTTING whose rows are pure-verb (issue
            # #310 batch verification).
            "PUTTING",
            "HEAR",
            "HEARS",
            "HEARD",
            "HEARING",
            "USE",
            "USES",
            "USING",
            "LIVE",
            "LIVES",
            "LIVED",
            "MADE",
            "AM",
            # Verified VPSTART verbs from -ate / -ize / -ish suffix
            # families plus other high-frequency single-syllable
            # transitive verbs. Each form is verified in isolation as
            # producing the ``)`` marker in C output.
            "RECOGNIZE",
            "RECOGNIZED",
            "RECOGNIZING",
            "ADVERTISE",
            "ADVERTISED",
            "ADVERTISING",
            "VERIFY",
            "VERIFIED",
            "VERIFIES",
            "CREATE",
            "CREATES",
            "CREATED",
            "CREATING",
            "OPERATE",
            "OPERATES",
            "OPERATED",
            "OPERATING",
            "DEMONSTRATE",
            "DEMONSTRATES",
            "DEMONSTRATED",
            "DEMONSTRATING",
            "APPRECIATE",
            "APPRECIATES",
            "APPRECIATED",
            "APPRECIATING",
            "PUNISH",
            "PUNISHED",
            "PUNISHES",
            "PUNISHING",
            "CONSIDER",
            "FOLLOW",
            "OBTAIN",
            "OCCUR",
            "PERFORM",
            "PREVENT",
            "PROVIDE",
            "SEEK",
            "SETTLE",
            "SOLVE",
            "SPEND",
            "STEAL",
            "SUCCEED",
            "SUFFER",
            "SUGGEST",
            "SUPPOSE",
            "SURVIVE",
            "TEACH",
            "TRANSLATE",
            "UNDERSTAND",
            "WEAR",
            # ``-IFY`` verbs (notify / satisfy / justify -- form-classed
            # as verbs in the C main dic).
            "NOTIFY",
            "NOTIFIED",
            "NOTIFIES",
            "NOTIFYING",
            "SATISFY",
            "SATISFIED",
            "SATISFIES",
            "SATISFYING",
            "JUSTIFY",
            "JUSTIFIED",
            "JUSTIFIES",
            "JUSTIFYING",
            # More high-frequency verbs verified to take ``)``.
            "LISTEN",
            "LISTENED",
            "LISTENING",
            "LISTENS",
            # Bulk VPSTART verb additions (verified each emits the
            # ``)`` marker in C output as the only diff vs Python).
            "ARRIVE",
            "ATTEND",
            "BELONG",
            "BORROW",
            "BREATHE",
            "BRING",
            "CARRY",
            "CHOOSE",
            "CLIMB",
            "COLLECT",
            "CONTAIN",
            "DEVOUR",
            "DIE",
            "DIVIDE",
            "DRAW",
            "EDIT",
            "ELECT",
            "ENGAGE",
            "ENTER",
            "ENTERTAIN",
            "FAIL",
            "FORBID",
            "FORGET",
            "FORGIVE",
            "GATHER",
            "GROW",
            "INCLUDE",
            "INJURE",
            "JOIN",
            "KEEP",
            "LEARN",
            "LET",
            "MAINTAIN",
            "MARRY",
            "OBEY",
            "OBSERVE",
            "OCCUPY",
            "OWE",
            "PERSUADE",
            "PLEAD",
            "POUR",
            "PROVE",
            "PURSUE",
            "REACT",
            "RECOMMEND",
            "REPRESENT",
            "SAVE",
            "SEEM",
            "SEIZE",
            "SEND",
            "SERVE",
            "SORT",
            "SUBMIT",
            "SURROUND",
            "SWEAR",
            "THREATEN",
            "UNDERTAKE",
            "UNDO",
            "UNITE",
            "VANISH",
            "WEAKEN",
            "ACCEPT",
            "ADD",
            "ADMIT",
            "ADOPT",
            "ADVISE",
            "AGREE",
            "ALLOW",
            "APOLOGIZE",
            "APPEAR",
            "APPLAUD",
            "APPLY",
            "APPROVE",
            "ATTRACT",
            "AVOID",
            "BATHE",
            "BEGIN",
            "BURY",
            "CHEW",
            "TIGHTEN",
            "TOLERATE",
            "UNTIE",
            # Dictionary-marked function words that also carry the
            # form-class flag in C's main dic (verified in isolation).
            "SO",
        }
    )

    # Sidecar-derived VPSTART set: every ``Dic_us.txt`` entry whose
    # form-class mask satisfies the C rule from ``ls_dict.c`` lines
    # 759-763 (``(fc & (FC_VERB|FC_CHARACTER)) == (FC_VERB|FC_CHARACTER)
    # || fc == FC_VERB``). Generated by ``scripts/build_dic_sidecars.py``
    # and bundled as ``src/dectalk/data/vpstart_us.txt``. Union with the
    # hand-curated set above so we keep inflected forms the C suffix
    # engine derives at runtime (``SELLS`` from ``SELL`` etc.) while
    # picking up the ~1400 verb infinitives the manual list omits.
    # Note: we deliberately do NOT also mirror the C suffix engine by
    # stem-stripping inflected forms and re-checking the sidecar. The
    # sidecar is derived from ``Dic_us_2002.txt`` which is a superset
    # of the runtime ``Dic_us.txt`` -- words in the sidecar but not the
    # runtime dictionary (e.g. ``CARRY``, ``USE``) never get the
    # form-class flag consulted at runtime, so their inflected forms
    # (``CARRIES``, ``USED``) must not emit ``)``. Direct membership
    # in the union set is both necessary and sufficient.
    vpstart_words = vpstart_words | load_vpstart_words(lang=lang)

    # Sidecar-derived compound-marker lexicon. Each entry's phoneme list
    # carries one or more ``"__PUNCT__*"`` tokens at the compound
    # boundaries the C source's main dictionary marks with ``*``
    # (MBOUND). Generated by ``scripts/build_dic_sidecars.py`` and
    # bundled as ``src/dectalk/data/lexicon_us_markers.txt``. Used to
    # expand compound-``*`` parity from the ~30 hand-curated entries
    # in ``word_phoneme_overrides`` below to the full ~1100 closed
    # compounds in ``Dic_us.txt``. Hand-curated overrides win for
    # entries that appear in both -- their phoneme sequences are tuned
    # against the C oracle, in particular for compound-internal vowel
    # reductions that the bundled lexicon strips.
    compound_marker_lex = load_marker_lexicon(lang=lang)

    # Sidecar-derived form-class masks (issue #295): the runtime
    # dictionary's built fc value per entry, keyed ``WORD`` /
    # ``WORD|P`` / ``WORD|S``. Drives (a) faithful homograph entry
    # selection via :func:`select_homograph_entry` (the C
    # ``ls_homo_homo`` port), (b) the context-dependent ``)`` VPSTART
    # emission for homographs via :func:`emits_vpstart`, and (c) the
    # per-word context tracking that mirrors the C ``fc_struct``
    # array.
    formclass_lex = load_formclass_lexicon(lang=lang)
    homograph_pair_words = frozenset(
        key[:-2] for key in formclass_lex if key.endswith("|P") and f"{key[:-2]}|S" in formclass_lex
    )
    formclass_words = frozenset(key.split("|", 1)[0] for key in formclass_lex)
    # Mirror of the C ``fc_struct[]``: one mask per WORD token of the
    # current sentence, in order. Cleared at sentence-final punctuation
    # (the C resets ``fc_index`` when ``wstate`` returns to ``UNK_WH``).
    word_fcs: list[int] = []

    # Spell-out: known acronyms that DECtalk reads letter-by-letter
    # (each letter as its own word). When set, we split into separate
    # letter pronunciations using the ``letter_names`` table below.
    # Dynamic spell-out set: starts empty; the chunk pre-pass adds any
    # all-uppercase 2-4 letter chunk where ``ls_spel_say_it`` decides
    # to spell rather than speak (e.g. ``FBI``, ``DNA``, ``BBQ``).
    spell_out_words: set[str] = set()

    # Word-level phoneme overrides for words where the Python LTS
    # diverges from DECtalk's transcription. Keyed by the upper-cased
    # token text. Each value is the ARPABET phoneme list to emit
    # instead of running the dict/LTS path. Used for closing
    # parity-corpus prompts whose Python LTS rules are wrong.
    word_phoneme_overrides: dict[str, list[str]] = {
        # "rhythms" -- Python LTS spuriously emits HH for the silent h
        # in "rh" and TH instead of DH. DECtalk has it as R IH DH AX
        # M (plural Z added by the voicing rule).
        "RHYTHMS": ["R", "IH1", "DH", "AX0", "M", "S"],
        # "just" -- Python's lookup transcribes it as JH AH0 S T
        # (unstressed schwa). DECtalk treats it as a stressed
        # adverb: JH AH1 S T.
        "JUST": ["JH", "AH1", "S", "T"],
        # "happened" -- Python's LTS doubles the P and emits EH twice
        # ("hx' aep p ehn ehd"). DECtalk has HH AE1 P AX0 N D.
        "HAPPENED": ["HH", "AE1", "P", "AX0", "N", "D"],
        # "dalmatians" -- Python's LTS spuriously emits T+IH+AE+N+S
        # for "-tians". DECtalk has SH+IX+N (with -s -> Z plural).
        "DALMATIANS": ["D", "AH0", "L", "M", "AE1", "SH", "IX", "N", "S"],
        # Doubled-consonant -ed/-ing/-er forms (issue #310) whose stems
        # are outside both dictionaries and whose C rendering leans on
        # compiled LTS rules the Python heuristic engine lacks: the
        # ``wa`` -> AO letter rule (swap/swat/swab/wad families) and
        # the second-syllable stress assignment (commit/regret
        # families). Each entry is verified byte-exact against the C
        # oracle; the matching bare stems carry aligned rows in
        # ``lexicon_us_full.txt``.
        "SWAPPED": ["S", "W", "AO1", "P", "T"],
        "SWAPPING": ["S", "W", "AO1", "P", "IX", "NG"],
        "SWAPPER": ["S", "W", "AO1", "P", "ER0"],
        "SWATTED": ["S", "W", "AO1", "T", "IX", "D"],
        "SWATTING": ["S", "W", "AO1", "T", "IX", "NG"],
        "SWABBED": ["S", "W", "AO1", "B", "D"],
        "SWABBING": ["S", "W", "AO1", "B", "IX", "NG"],
        "WADDED": ["W", "AO1", "D", "IX", "D"],
        "WADDING": ["W", "AO1", "D", "IX", "NG"],
        "COMMITTED": ["K", "AH0", "M", "IH1", "T", "IX", "D"],
        "COMMITTING": ["K", "AH0", "M", "IH1", "T", "IX", "NG"],
        "REGRETTED": ["R", "IX0", "G", "R", "EH1", "T", "IX", "D"],
        "REGRETTING": ["R", "IX0", "G", "R", "EH1", "T", "IX", "NG"],
        # Literal "forty" reads via the lexicon as ``f ' aor t iy``
        # (AO + R). Digit-expanded ``40`` / ``42`` uses the OR
        # r-coloured single vowel and so gets its own sentinel.
        "__NUM_FORTY__": ["F", "OR1", "T", "IY0"],
        # Teen-word overrides: DECtalk inserts the ``*`` MBOUND marker
        # before the ``T IY N`` second-half of these compound numbers.
        # Literal forms keep the lexicon's stress pattern (secondary on
        # IY); digit-expanded forms (``__NUM_FOURTEEN__`` and friends)
        # use primary stress on IY plus the OR r-coloured vowel where
        # relevant (handled in ``_digit_expand`` below).
        "FOURTEEN": ["F", "OW1", "R", "__PUNCT__*", "T", "IY2", "N"],
        "FIFTEEN": ["F", "IH1", "F", "__PUNCT__*", "T", "IY2", "N"],
        "SIXTEEN": ["S", "IH1", "K", "S", "__PUNCT__*", "T", "IY2", "N"],
        "SEVENTEEN": ["S", "EH1", "V", "AH0", "N", "__PUNCT__*", "T", "IY2", "N"],
        "EIGHTEEN": ["EY1", "__PUNCT__*", "T", "IY2", "N"],
        "NINETEEN": ["N", "AY1", "N", "__PUNCT__*", "T", "IY2", "N"],
        # Digit-expanded teen sentinels: ``*`` MBOUND + primary stress
        # on both syllables (``f ' or* t ' iyn``).
        "__NUM_FOURTEEN__": ["F", "OR1", "__PUNCT__*", "T", "IY1", "N"],
        "__NUM_FIFTEEN__": ["F", "IH1", "F", "__PUNCT__*", "T", "IY1", "N"],
        "__NUM_SIXTEEN__": ["S", "IH1", "K", "S", "__PUNCT__*", "T", "IY1", "N"],
        "__NUM_SEVENTEEN__": [
            "S",
            "EH1",
            "V",
            "AH0",
            "N",
            "__PUNCT__*",
            "T",
            "IY1",
            "N",
        ],
        "__NUM_EIGHTEEN__": ["EY1", "__PUNCT__*", "T", "IY1", "N"],
        "__NUM_NINETEEN__": ["N", "AY1", "N", "__PUNCT__*", "T", "IY1", "N"],
        # Spoken-punctuation-name sentinels (issue #315). A whole-chunk
        # punctuation mark with no word before it in the open clause is
        # spoken by name: the C ``cm_pars``/``cm_text`` stage routes the
        # char through as its own word and ``ls_spel`` spells it via the
        # language typing table (``usa_type.tab`` -> ``typing_table[c]``
        # in ``ls_spel.c`` line 164). The table's phonemic strings carry
        # DIFFERENT stress/vowel patterns than the dictionary words
        # ("Eksklxm'eSxn pOnt" has an unstressed "point" and the AX
        # schwa where the dictionary's "exclamation point" uses
        # ``p ' oyn t`` and IX), so every name is hard-coded here from
        # the typing-table rendering (each verified byte-identical to
        # ``convert_to_phonemes`` on the isolated mark).
        # "p'irixd" -> ``p ' iyr iyaxd``.
        "__PUNCT_NAME_PERIOD__": ["P", "IY1", "R", "IY0", "AX0", "D"],
        # "k'amx" -> ``k ' aam ax``.
        "__PUNCT_NAME_COMMA__": ["K", "AA1", "M", "AX0"],
        # "k'olxn" -> ``k ' owllaxn``.
        "__PUNCT_NAME_COLON__": ["K", "OW1", "L", "AX0", "N"],
        # "s'Emi" -> ``s ' ehm iy`` (first half of "s'Emi#kolxn").
        "__PUNCT_NAME_SEMI__": ["S", "EH1", "M", "IY0"],
        # "kolxn" unstressed second half of "s'Emi#kolxn" ->
        # ``k owllaxn`` (the ``:`` name above is stressed).
        "__PUNCT_NAME_SEMI_COLON_TAIL__": ["K", "OW0", "L", "AX0", "N"],
        # "Eksklxm'eSxn" -> ``ehk s k llaxm ' eyshaxn``.
        "__PUNCT_NAME_EXCLAMATION__": [
            "EH0",
            "K",
            "S",
            "K",
            "L",
            "AX0",
            "M",
            "EY1",
            "SH",
            "AX0",
            "N",
        ],
        # "pOnt" (unstressed) -> ``p oyn t``.
        "__PUNCT_NAME_POINT__": ["P", "OY0", "N", "T"],
        # "kw'EsCxn" -> ``k w ' ehs chaxn``.
        "__PUNCT_NAME_QUESTION__": ["K", "W", "EH1", "S", "CH", "AX0", "N"],
        # "mark" (unstressed) -> ``m aar k``.
        "__PUNCT_NAME_MARK__": ["M", "AA0", "R", "K"],
        # Title-abbreviation sentinels (issue #246; emitted by the
        # chunk-loop title pre-pass). The C forms are the verbatim
        # runtime-dictionary / ls_task phoneme strings, all subtly
        # different from the spelled-out words:
        # - ``mr. / mrs. / ms. / vs.`` rows carry NO stress mark
        #   (``mIstR`` -> ``m ihs t rr``; the word "mister" is
        #   ``m ' ihs t rr``),
        # - ``dr. / st.`` resolve context-sensitively to the
        #   ``pdoctor`` / ``pdrive`` / ``psaint`` / ``pstreet`` tables
        #   in l_us_con.c lines 607-631 (doctor/saint unstressed,
        #   drive S1-stressed, street S2-stressed),
        # - ``Prof.`` = ``prxf'EsR`` -> ``p r axf ' ehs rr``.
        "__TITLE_DR__": ["D", "AA0", "K", "T", "ER0"],
        "__TITLE_DR_DRIVE__": ["D", "R", "AY1", "V"],
        "__TITLE_ST__": ["S", "EY0", "N", "T"],
        "__TITLE_ST_STREET__": ["S", "T", "R", "IY2", "T"],
        "__TITLE_MR__": ["M", "IH0", "S", "T", "ER0"],
        "__TITLE_MRS__": ["M", "IH0", "S", "IX", "Z"],
        "__TITLE_MS__": ["M", "IH0", "Z"],
        "__TITLE_PROF__": ["P", "R", "AX", "F", "EH1", "S", "ER0"],
        "__TITLE_VS__": ["V", "ER0", "S", "IX", "S"],
        # Words the #246 evidence prompts exercise, re-aligned to the
        # runtime-dictionary rows: ``today,N,t|d'e`` has the IX first
        # vowel (the bundled lexicon's AH0 read ``t axd ' ey``);
        # "versus" and "professor" are outside the runtime dictionary
        # and the Python LTS diverged from the C LTS (voiced final S /
        # scrambled vowels) -- pin the C readings.
        "TODAY": ["T", "IX", "D", "EY1"],
        "VERSUS": ["V", "ER1", "S", "IX", "S"],
        "PROFESSOR": ["P", "R", "AX", "F", "EH1", "S", "ER0"],
        # --- Symbol sentinels (issue #244) --------------------------
        # Emitted by the chunk-loop symbol splitter; phonemes are the
        # verbatim Dic_us.txt symbol rows (lines 70-236), NOT the
        # spelled-out words -- the two differ: ``^`` reads
        # ``k ' ehr axt`` (dic ``k'Erxt``) while the word "caret" is
        # ``k ' aer ixt``; ``@`` reads stressed ``' aet`` (dic ``'@t``)
        # while the word "at" destresses to ``eht``; ``&`` reads
        # ``' aen d`` (dic ``'@nd``) without the ``^ (`` function-word
        # markers plain "and" gets.
        "__SYM_AMPERSAND__": ["AE1", "N", "D"],
        "__SYM_PERCENT__": ["P", "ER0", "S", "EH1", "N", "T"],
        "__SYM_AT__": ["AE1", "T"],
        "__SYM_PLUS__": ["P", "L", "AH1", "S"],
        "__SYM_EQUALS__": ["IY1", "K", "W", "EL", "Z"],
        "__SYM_ASTERISK__": ["AE1", "S", "T", "ER0", "IX", "S", "K"],
        "__SYM_SLASH__": ["S", "L", "AE1", "SH"],
        "__SYM_CARET__": ["K", "EH1", "R", "AX", "T"],
        # ``#`` = ``n'^mbR sAn`` ("number sign") -- two words, so the
        # splitter emits two sentinel tokens.
        "__SYM_NUMBER__": ["N", "AH1", "M", "B", "ER0"],
        "__SYM_SIGN__": ["S", "AY0", "N"],
        # The words the ``+`` / ``=`` symbols expand to, fixed to the
        # C reading (issue #244): the Python LTS voiced the final S of
        # "plus" (``p ll' ahz``; C LTS keeps ``p ll' ahs``) and read
        # "equals" with a plain L (``' iyk w llz``; the C dic row
        # ``equal,N,'ikwL`` carries the syllabic EL -> ``' iyk w elz``).
        "PLUS": ["P", "L", "AH1", "S"],
        "EQUALS": ["IY1", "K", "W", "EL", "Z"],
        # --- Single-letter words (issue #244) -----------------------
        # A standalone letter reads as its letter name with PRIMARY
        # stress in the C front end, in every position (``a = b`` ->
        # ``b ' iy``, ``vitamin C`` -> ``s ' iy``, ``x / y`` ->
        # ``' ehk s   w ' ay``; all verified against the oracle). The
        # bundled lexicon carried unstressed forms (``B`` -> ``b iy``)
        # and the LTS mangled the rest (``x`` -> ``k s``, ``q`` ->
        # ``k``). ``A`` and ``I`` are NOT letters here -- they keep
        # their article / pronoun word paths, which already match C.
        # ``Q`` and ``W`` differ from the acronym spell-out table
        # (``_LETTER_NAMES``): standalone Q reads the ``yu`` diphthong
        # (``k ' yu``) and W reads the syllabic-EL + MBOUND compound
        # form ``d ' ahb el* yxuw`` (both oracle-verified).
        "B": ["B", "IY1"],
        "C": ["S", "IY1"],
        "D": ["D", "IY1"],
        "E": ["IY1"],
        "F": ["EH1", "F"],
        "G": ["JH", "IY1"],
        "H": ["EY1", "CH"],
        "J": ["JH", "EY1"],
        "K": ["K", "EY1"],
        "L": ["EH1", "L"],
        "M": ["EH1", "M"],
        "N": ["EH1", "N"],
        "O": ["OW1"],
        "P": ["P", "IY1"],
        "Q": ["K", "YU1"],
        "R": ["AA1", "R"],
        "S": ["EH1", "S"],
        "T": ["T", "IY1"],
        "U": ["Y", "UW1"],
        "V": ["V", "IY1"],
        "W": ["D", "AH1", "B", "EL", "__PUNCT__*", "Y", "UW0"],
        "X": ["EH1", "K", "S"],
        "Y": ["W", "AY1"],
        "Z": ["Z", "IY1"],
        # "DECtalk" -- the C source's kernel marks the SYL_BREAK between
        # "DEC" and "talk" so the encoder emits the ``#`` syllable-
        # boundary token. The Python lexicon stores ``D EH1 K T AO0 K``
        # which would emit ``d ' ehk t aok`` (no ``#``). Insert the
        # marker explicitly. (The lexicon's ``V ER1 ZH N`` entry for
        # "version" reads correctly as ``v ' rrzhen`` once the
        # encoder's word-final-sonorant-after-consonant rule converts
        # the final N to ``en`` -- no override needed.)
        "DECTALK": ["D", "EH1", "K", "__PUNCT__#", "T", "AO0", "K"],
        # "supercalifragilisticexpialidocious" -- the Python LTS
        # mis-stresses "su-" (emits stressed AH instead of unstressed
        # UW), reads "-gil-" with a hard G instead of JH (soft G), and
        # botches "-cious" as S+IH+AW+Z instead of SH+IX+S. The C
        # output is the Mary Poppins pronunciation; hardcode it since
        # we don't have the LTS context for it.
        "SUPERCALIFRAGILISTICEXPIALIDOCIOUS": [
            "S",
            "UW0",
            "P",
            "ER0",
            "K",
            "AE0",
            "L",
            "IH0",
            "F",
            "R",
            "AE0",
            "JH",
            "IH0",
            "L",
            "IH0",
            "S",
            "T",
            "IH0",
            "S",
            "EH0",
            "K",
            "S",
            "P",
            "IH0",
            "AE0",
            "L",
            "IH0",
            "D",
            "AA0",
            "SH",
            "IX",
            "S",
        ],
        # "billion" -- not in the bundled lexicon. C output is
        # ``b ' ihllyxaxn`` = B IH L Y AX N (with primary stress on IH).
        "BILLION": ["B", "IH1", "L", "Y", "AX", "N"],
        # "live" has two C-dic pronunciations: verb (L IH1 V) and
        # adjective (L AY1 V). The bundled lexicon only carries the
        # adjective form; the verb form is selected by the form-class
        # flag in the C main dic. Since the VPSTART verb list above
        # already form-classes LIVE/LIVES as verbs, force the verb
        # pronunciation here too. ``LIVED`` already has the right lex
        # entry (L IH1 V D).
        "LIVE": ["L", "IH1", "V"],
        "LIVES": ["L", "IH1", "V", "Z"],
        # Words whose C dictionary entry carries the ``*`` MBOUND
        # prefix marker. These come from ``Dic_us_2002.txt`` and aren't
        # part of the bundled lexicon. A future dictionary port could
        # subsume these into a separate marker table; for now we list
        # the common ones the corpus exercises.
        "HOUSE": ["__PUNCT__*", "HH", "AW1", "S"],
        "BIRTHDAY": ["B", "ER1", "TH", "__PUNCT__*", "D", "EY2"],
        "NOTEBOOK": ["N", "OW1", "T", "__PUNCT__*", "B", "UH2", "K"],
        "LIGHTHOUSE": ["L", "AY1", "T", "__PUNCT__*", "HH", "AW2", "S"],
        # Compound words whose C dic carries an internal ``*`` MBOUND
        # marker between the two parts. The bundled lexicon stores
        # them as flat phoneme sequences; insert the marker and use
        # the C-emitted unreduced vowels for the second component
        # (compound-internal post-stress IH0 stays as IH, not IX --
        # the MBOUND breaks the "same-word" context that the
        # syllable-internal reduction rule needs).
        # ``IH`` (no stress digit) bypasses the IH0+NG -> IX reduction
        # rule and matches the C emit's unmarked-IH after MBOUND.
        "EVERYTHING": ["EH1", "V", "R", "IY0", "__PUNCT__*", "TH", "IH", "NG"],
        "EVERYONE": ["EH1", "V", "R", "IY0", "__PUNCT__*", "W", "AH0", "N"],
        "ANYWHERE": ["EH1", "N", "IY0", "__PUNCT__*", "W", "EY0", "R"],
        "SOMETIMES": ["S", "AH1", "M", "__PUNCT__*", "T", "AY0", "M", "Z"],
        # Additional MBOUND compounds derived by replaying the C
        # dictionary's ``*`` marker output. Each second component carries
        # secondary stress (``2``) where the C emit shows `` ` `` and
        # primary (``1``) where it shows ``'``; the first-component
        # vowel keeps its lexicon stress.
        "WEEKEND": ["W", "IY1", "K", "__PUNCT__*", "EH0", "N", "D"],
        "RAINCOAT": ["R", "EY1", "N", "__PUNCT__*", "K", "OW2", "T"],
        "SNOWFLAKE": ["S", "N", "OW1", "__PUNCT__*", "F", "L", "EY0", "K"],
        "SNOWMAN": ["S", "N", "OW1", "__PUNCT__*", "M", "AE0", "N"],
        "SUNSET": ["S", "AH1", "N", "__PUNCT__*", "S", "EH2", "T"],
        "DAYDREAM": ["D", "EY1", "__PUNCT__*", "D", "R", "IY0", "M"],
        "NIGHTMARE": ["N", "AY1", "T", "__PUNCT__*", "M", "EY0", "R"],
        "HIGHWAY": ["HH", "AY1", "__PUNCT__*", "W", "EY2"],
        "HEADPHONE": ["HH", "EH1", "D", "__PUNCT__*", "F", "OW2", "N"],
        "OUTSIDE": ["AW0", "T", "__PUNCT__*", "S", "AY1", "D"],
        "OUTDOOR": ["AW0", "T", "__PUNCT__*", "D", "OW1", "R"],
        "OUTDOORS": ["AW0", "T", "__PUNCT__*", "D", "OW1", "R", "Z"],
        "MYSELF": ["M", "AY0", "__PUNCT__*", "S", "EH1", "L", "F"],
        "YOURSELF": ["Y", "ER0", "__PUNCT__*", "S", "EH2", "L", "F"],
        "HIMSELF": ["HH", "IH0", "M", "__PUNCT__*", "S", "EH2", "L", "F"],
        "HERSELF": ["HH", "ER0", "__PUNCT__*", "S", "EH1", "L", "F"],
        "OURSELVES": ["AA0", "R", "__PUNCT__*", "S", "EH1", "L", "V", "Z"],
        "THEMSELVES": ["DH", "EH0", "M", "__PUNCT__*", "S", "EH1", "L", "V", "Z"],
        "NEWSPAPER": ["N", "UW1", "Z", "__PUNCT__*", "P", "EY2", "P", "ER0"],
        "BEDROOM": ["B", "EH1", "D", "__PUNCT__*", "R", "UW2", "M"],
        "FOOTBALL": ["F", "UH1", "T", "__PUNCT__*", "B", "AO2", "L"],
        "AIRPORT": ["EY1", "R", "__PUNCT__*", "P", "OW2", "R", "T"],
        "AIRPLANE": ["EY1", "R", "__PUNCT__*", "P", "L", "EY2", "N"],
        "SCHOOLHOUSE": ["S", "K", "UW1", "L", "__PUNCT__*", "HH", "AW2", "S"],
        # ``eleven`` lex stores AH0 L EH1 V AH0 N; C reads the
        # post-stress AH0 (between V and final N) as IX.
        "ELEVEN": ["AH0", "L", "EH1", "V", "IX", "N"],
        # ``thirteen`` -- the *one* teen word missing from the C
        # MBOUND-marker pattern in the lexicon (lex stores just TH
        # ER1 T IY2 N). C emits ``th' rr* t ` iyn``.
        "THIRTEEN": ["TH", "ER1", "__PUNCT__*", "T", "IY2", "N"],
        # Digit-expanded ``13`` -- primary stress on second syllable.
        "__NUM_THIRTEEN__": ["TH", "ER1", "__PUNCT__*", "T", "IY1", "N"],
        # Digit-expansion-only sentinels. The C kernel reads digit
        # strings ("4", "40", "1234") with subtly different pronunciations
        # than the literal words ("four", "forty") -- specifically the
        # OR r-coloured vowel for "4" and an AX schwa instead of EN
        # syllabic-N inside "thousand". Generated by ``_digit_expand``
        # below.
        "__NUM_FOUR__": ["F", "OR1"],
        "__NUM_THOUSAND__": ["TH", "AW1", "Z", "AX", "N", "D"],
        # The "and" inserted between hundreds and units in a digit
        # expansion ("two hundred [AND] thirty four") uses the VPSTART
        # `)` marker + unstressed EH + N + D, distinct from the literal
        # "and" which uses SBOUND ``^`` + PPSTART ``(`` + AE + N + D.
        "__NUM_AND__": ["__PUNCT__)", "EH0", "N", "D"],
        # Initial-cluster silent-letter words. ``rules_us.py`` strips the
        # silent leading consonant of gn- / pn- / ps- / mn- words, but
        # the remaining vowel+stress pattern still drifts from the C
        # oracle in a handful of multi-syllable borrowings. Pin the four
        # canonical acceptance-criteria prompts (issue #127) and a few
        # close relatives whose Python LTS otherwise mis-stresses the
        # post-cluster nucleus (psalm's silent L, pseudo's UW+OW split).
        # The simpler one-syllable cases (gnaw, gnat, gnome, gnash,
        # psyche) already match by rule and need no override.
        "PNEUMONIA": ["N", "UW0", "M", "AA1", "N", "IY0", "AX0"],
        "PNEUMATIC": ["N", "UW0", "M", "AE1", "T", "IX", "K"],
        "PSYCHIC": ["S", "AY1", "K", "IX", "K"],
        # The L in "psalm" is silent in the C oracle output (s ' aam),
        # following the same /m/-after-/a/ pattern as "calm" / "palm".
        "PSALM": ["S", "AA1", "M"],
        "PSEUDO": ["S", "UW1", "D", "OW0"],
        "MNEMONIC": ["N", "IX0", "M", "AA1", "N", "IX", "K"],
        # Single-syllable "gnu" — the rule path lands on AH (default U
        # short vowel) instead of long UW. Pin to the C oracle reading.
        "GNU": ["N", "UW1"],
    }

    # DECtalk's first-verbs hack (``ls_task.c`` verbs_table) overrides
    # these six auxiliary / linking verbs with a fixed phoneme sequence
    # carrying secondary stress (S2) -- but ONLY when the verb appears
    # at the start of a sentence. Mid-sentence occurrences fall back to
    # the lexicon's unstressed pronunciation.
    first_verb_phones: dict[str, list[str]] = {
        "ARE": ["AA2", "R"],
        "HAD": ["HH", "EH2", "D"],
        "IS": ["IH2", "Z"],
        "WAS": ["W", "AX2", "Z"],
        "WERE": ["W", "ER2"],
        "WILL": ["W", "IH2", "LX"],
    }

    # Function words DECtalk destresses in mid-utterance position.
    # When the word appears NOT at the start AND NOT at the end of
    # a sentence (i.e. another word follows), the C source emits
    # the ``^`` (SBOUND) phrase marker + the unstressed schwa form
    # instead of the dictionary's stressed pronunciation. Pairs of
    # ``(name, prefix_markers, phonemes)`` -- ``prefix_markers`` is
    # a list of punctuation-style markers ('^' / '(' / ')') prepended
    # before the phonemes.
    function_word_destress: dict[str, tuple[list[str], list[str]]] = {
        # ``a`` -> ``^ ax`` mid-sentence.
        "A": (["^"], ["AH0"]),
        # ``and`` -> ``^ ( aen d`` everywhere (the C source preserves
        # the AE+N+D phonemes but adds the SBOUND + PPSTART markers).
        "AND": (["^", "("], ["AE0", "N", "D"]),
        # ``to`` -> ``^ ( t uh`` everywhere (SBOUND + PPSTART + T + UH
        # unstressed -- the destressed-preposition reading C emits even
        # at the very start of an utterance ("to bed" -> ``^ ( t uh
        # b ' ehd``)).
        "TO": (["^", "("], ["T", "UH0"]),
        # ``for`` -> ``^ ( f rr`` (SBOUND + PPSTART + F + ER unstressed).
        "FOR": (["^", "("], ["F", "ER0"]),
    }

    # ARPABET pronunciation of each English letter name (the same
    # phoneme sequences DECtalk's spell-out path emits). Aliased to the
    # module-level constant so the oracle path and the synth path's
    # acronym spell-out share one source of truth (issue #217).
    letter_names: dict[str, list[str]] = _LETTER_NAMES

    def _dedupe_consecutive_phonemes(phones: list[str]) -> list[str]:
        """Collapse consecutive identical phonemes (LTS ``-LL`` artifact)."""
        out: list[str] = []
        for p in phones:
            if out and out[-1] == p:
                continue
            out.append(p)
        return out

    # Stops that trigger the syllabic-L/N conversion when followed by
    # an unstressed L / N at the stem end. (Subset of "true" voiced /
    # voiceless stops -- the same set the C source's allophone rule
    # consults in ``ph_aloph*.c``.)
    syllabic_trigger_stops: frozenset[str] = frozenset(
        {"P", "B", "T", "D", "K", "G", "F", "V", "S", "Z", "TH", "DH", "SH", "ZH"}
    )

    def _apply_pre_inflection_syllabic(stem_phones: list[str]) -> list[str]:
        """Substitute N/L -> EN/EL inside the stem where the syllabic rule fires.

        Mirrors the encoder's word-final syllabic-sonorant rule but
        applies it to the *stem* before an inflectional suffix is
        appended. Two patterns:

        - ``<stop> N`` at stem end -> ``<stop> EN`` (``REASON`` ->
          ``R IY Z EN``).
        - ``<stop> N <stop>`` where the trailing stop is the last
          phoneme of the stem -> ``<stop> EN <stop>`` (``SECOND`` ->
          ``S EH K EN D``; the trailing D is the silent past-tense
          consonant that lives between the syllabic N and the
          inflectional -s).
        """
        if len(stem_phones) < 2:  # noqa: PLR2004
            return list(stem_phones)
        out = list(stem_phones)
        last = len(out) - 1

        def _maybe_convert(idx: int) -> bool:
            base = out[idx].rstrip("0123456789")
            if base not in {"L", "N"}:
                return False
            if out[idx][-1:].isdigit():
                # Stressed L/N never collapses to a syllabic form.
                return False
            prev_base = out[idx - 1].rstrip("0123456789")
            if prev_base not in syllabic_trigger_stops:
                return False
            out[idx] = "EN" if base == "N" else "EL"
            return True

        # Case 1: stem ends with N/L directly.
        if not _maybe_convert(last) and last >= 2:  # noqa: PLR2004
            # Case 2: stem ends with stop and the phoneme before it is N/L.
            tail_base = out[last].rstrip("0123456789")
            if tail_base in {"D", "T"}:
                _maybe_convert(last - 1)
        return out

    arp_vowel_bases: frozenset[str] = frozenset(
        {"AA", "AE", "AH", "AO", "AX", "AY", "AW", "EH", "ER", "EY",
         "IH", "IX", "IY", "OW", "OY", "UH", "UW"}
    )  # fmt: skip
    # DECtalk vowel codes emitted by ``encode_to_dectalk`` (the values of
    # the arpabet vowels in its ARPABET_TO_DECTALK table) plus the ``yu``
    # collapse, used to pick vowel tokens out of a re-encoded stem. Kept
    # local rather than importing the module-private ``_VOWEL_DECTALK_CODES``.
    dt_vowel_codes: frozenset[str] = frozenset(
        {"iy", "ih", "ey", "eh", "ae", "aa", "ay", "aw", "ah", "ao", "ow",
         "oy", "uh", "uw", "ax", "rr", "ix", "ir", "er", "ar", "or", "ur", "yu"}
    )  # fmt: skip

    def _freeze_stem_weak_vowels(stem_phones: list[str], *, silent_e: bool = False) -> list[str]:
        """Lock the stem's reducible weak vowels to their bare-word value (issue #322).

        The encoder's ``AH0``/``IH0`` -> ``IX``/``AX`` reductions
        (``ah_before_final_t`` / ``_s`` / ``_st`` / ``_sh`` ... in
        :func:`encode_to_dectalk`) all gate on the vowel being
        **word-final**. When an inflectional suffix is appended the
        stem's final weak vowel is no longer word-final, so the reduction
        fires in the *assembled* context instead of the stem's own:
        ``edits`` loses ``edit``'s IX (``ehd axt`` vs C ``ehd ixt``) and
        ``focused`` gains a spurious IX because the appended ``S T`` looks
        like the ``-est`` superlative pattern (``owk ixs t`` vs C
        ``owk axs t``). The C engine renders the stem as its own word and
        concatenates the suffix afterwards, so the stem keeps its *bare*
        weak vowel regardless of what follows.

        Mirror that: encode the stem alone, read back each weak vowel's
        realisation (:func:`encode_to_dectalk` emits exactly two bytes per
        unit, so a plain stem tokenises cleanly), and rewrite ``AH0`` /
        ``IH0`` to the concrete ``IX`` / ``AX`` the bare stem produced.
        ``IX`` / ``AX`` are inert under re-encoding, so the appended suffix
        can no longer shift them. Weak vowels that stay full (``ah`` /
        ``ih``) are left untouched.

        ``silent_e`` marks a stem recovered from a ``base + "E"`` lexicon
        lookup -- the silent-e sibilant class (``promise`` / ``practice`` /
        ``notice`` / ``service``). C reduces those to IX from orthography
        the phoneme-level encoder can't see, so Python's *bare* reduction
        is unreliable (it under-reduces to AX) and freezing it would demote
        ``promised`` from the correct IX to AX. For that class we skip the
        freeze and let the assembled context stand (its ``AH0 S T`` -> IX
        path happens to match C). ``focus`` is *not* silent-e (no
        ``FOCUSE`` entry), so ``focused`` still freezes to its bare AX.
        """
        if silent_e:
            return list(stem_phones)
        weak_idxs = {i for i, p in enumerate(stem_phones) if p in ("AH0", "IH0")}
        if not weak_idxs:
            return list(stem_phones)
        raw = encode_to_dectalk(stem_phones)
        if len(raw) % 2:  # a __RAW__ payload broke the 2-byte invariant
            return list(stem_phones)
        codes = [raw[j : j + 2].decode("ascii", "replace") for j in range(0, len(raw), 2)]
        stress_marks = (f"{DECTALK_PRIMARY_STRESS} ", f"{DECTALK_SECONDARY_STRESS} ")
        emitted = [
            c.rstrip(" ")
            for c in codes
            if c not in stress_marks and c.rstrip(" ") in dt_vowel_codes
        ]
        in_vpos = [
            i for i, p in enumerate(stem_phones) if p.rstrip("0123456789") in arp_vowel_bases
        ]
        if len(in_vpos) != len(emitted):
            # Alignment uncertain (e.g. an unexpected collapse) -- leave
            # the stem untouched rather than mis-assign a vowel.
            return list(stem_phones)
        out = list(stem_phones)
        for k, i in enumerate(in_vpos):
            if i in weak_idxs:
                if emitted[k] == "ix":
                    out[i] = "IX"
                elif emitted[k] == "ax":
                    out[i] = "AX"
        return out

    def _lts_inflection_stem(stem: str, *, attach_e: bool) -> list[str] | None:
        """LTS phonemes for an inflectional-suffix stem (issues #310, #320).

        Mirrors how the C LTS rule engine renders the stem letters of
        an unknown ``-ed`` / ``-ing`` / ``-es`` / ``-er`` / ``-est``
        word (oracle-verified black-box; the C tables in ``l_us_rta.c``
        are compiled and opaque):

        - Doubled final consonant collapses to one before the rules run
          (``vrabbed`` -> VRAB, ``fittest`` -> FIT; C emits a single
          consonant and the short stem vowel). A doubled ``S`` is the
          exception: it is a root cluster the C engine keeps
          (``stress`` / ``bless`` / ``mass``) -- collapsing ``ss`` to a
          lone ``s`` would voice it to Z (``stres`` -> S T R EH Z), so
          keep the pair and let the dedupe fold it to a single
          voiceless S (issue #320's root-S voicing misfire).
        - Otherwise the vowel-initial suffix puts the stem's final
          consonant into a silent-e / open-syllable context, so the C
          rules lengthen the stem vowel exactly as a re-attached silent
          ``e`` would: magic-e (``vraked`` / ``poking`` -> ...OW K,
          ``braver`` -> ...EY V) and c/g softening (``vaged`` ->
          V EY JH). Re-attach an ``E`` so the Python rules see the same
          context -- except after ``X``, where the C rules keep the
          short vowel (``faxed`` -> F AE K S T).

        The ``-ed``-only ``attach_e`` distinction the original #310 port
        drew (``voning`` keeps its short vowel while ``vroking``
        lengthens) turned out to matter only for nonsense letter-pairs
        outside the corpus; every real inflected form the #316 census
        exercises lengthens, so magic-e now fires for all the
        vowel-initial suffixes. ``attach_e`` is retained as a hook for a
        future consonant-suffix caller that must suppress it.

        Args:
            stem: Upper-cased orthographic stem (suffix stripped).
            attach_e: Whether the suffix opens a silent-e / open-syllable
                context (true for every vowel-initial inflection).

        Returns:
            De-duplicated LTS phonemes for the massaged stem, or
            ``None`` when the stem shape is out of the rule's domain
            (vowel-final, vowel-less, non-alphabetic, too short).
        """
        min_stem = 2
        if len(stem) < min_stem or not stem.isalpha():
            return None
        vowels = "AEIOU"
        # Vowel-final stems (``agreed`` -> AGRE, ``screeed``) and
        # vowel-less stems (``vryed`` -> VRY; C's ``str_vowel`` guard
        # keeps the suffix match off the word's only vowel) stay on
        # the whole-word LTS path.
        if stem[-1] in vowels or not any(v in stem for v in vowels):
            return None
        if stem[-1] == stem[-2]:
            base = stem if stem[-1] == "S" else stem[:-1]
        elif not attach_e:
            return None
        elif stem[-1] == "X":
            base = stem
        else:
            base = stem + "E"
        return _dedupe_consecutive_phonemes(lts(base))

    # Inflectional -s (plural / 3rd-person sg) voices to Z when the
    # preceding phoneme is voiced (any vowel, or a voiced consonant).
    # The rule only fires when the word's *spelling* ends with an
    # inflectional ``-s``; root-internal S like ``COURSE`` / ``HORSE``
    # stays as S even though it's preceded by R (a voiced consonant).
    # Syllabic variants of L / N / M (``EL`` / ``EN`` / ``EM``) are
    # voiced too, so they belong in this set alongside the regular
    # voiced consonants.
    voiced_cons_for_z: frozenset[str] = frozenset(
        {"B", "D", "G", "JH", "L", "M", "N", "NG", "R", "V", "Z", "ZH", "DH",
         "EL", "EN", "EM"}
    )  # fmt: skip
    vowel_arpabet: frozenset[str] = frozenset(
        {"IY", "IH", "EY", "EH", "AE", "AA", "AY", "AW", "AH", "AO",
         "OW", "OY", "UH", "UW", "ER", "AX", "IX"}
    )  # fmt: skip

    def _voice_final_s_after_consonant(
        phones: list[str], word: str, *, from_stem_strip: bool = False
    ) -> list[str]:
        """``...C S`` -> ``...C Z`` when ``word`` looks like inflectional -s.

        Args:
            phones: phoneme list ending with a final ``S`` token.
            word: original orthographic form (used for the ``-s`` ending check).
            from_stem_strip: True iff ``phones`` was assembled by appending S to
                a separately-looked-up stem. In that case the S is provably the
                inflectional ending and the voicing fires after both voiced
                consonants and vowels (``days`` -> Z, ``seconds`` -> Z). If the
                whole word was in the lexicon, we only voice after voiced
                consonants so words like ``yes`` / ``this`` (where the root S
                is preceded by a vowel) stay voiceless.
        """
        if len(phones) < 2 or phones[-1] != "S":  # noqa: PLR2004 — len() < 2 means no preceding context
            return phones
        # Only voice when the spelling suggests a true ``-s`` ending.
        # Heuristic: word ends with 's' but not 'ss' / 'us' / 'is' etc.
        # where the orthographic 's' is part of the root.
        word_lower = word.lower()
        if not word_lower.endswith("s") or word_lower.endswith(("ss", "us", "is")):
            return phones
        prev_base = phones[-2].rstrip("0123456789")
        if prev_base in voiced_cons_for_z:
            return [*phones[:-1], "Z"]
        if from_stem_strip and prev_base in vowel_arpabet:
            return [*phones[:-1], "Z"]
        return phones

    # DECtalk maps a trailing ``?`` to ``.`` when the sentence contains a
    # ``wh-`` question word (information question, falling intonation);
    # yes/no questions ("is it raining?") keep the ``?`` token (rising
    # intonation). The set below covers the ``wh-`` family the C kernel
    # treats specially.
    wh_question_words: frozenset[str] = frozenset(
        {
            "HOW",
            "WHAT",
            "WHEN",
            "WHERE",
            "WHICH",
            "WHO",
            "WHOM",
            "WHOSE",
            "WHY",
        }
    )

    def _punct_marker(ch: str, *, sentence_has_wh: bool) -> str:
        # Collapse rules observed in the C source's output:
        # - ``;`` and ``:`` -> ``,`` (RELSTART folds into COMMA emit)
        # - ``?`` -> ``.`` ONLY when the sentence has a ``wh-`` question
        #   word; otherwise ``?`` passes through (DECtalk's rising-
        #   intonation yes/no-question marker).
        # - ``!`` and ``.`` pass through unchanged
        if ch in (";", ":"):
            ch = ","
        elif ch == "?" and sentence_has_wh:
            ch = "."
        return f"{punct_prefix}{ch}"

    flat: list[str] = []
    # Strip inline ``[:cmd value]`` blocks via cmd.parse so commands
    # like ``[:nb]`` (voice change) and ``[:rate 200]`` don't leak
    # into the phoneme stream as faux words.
    for seg in parse(text):
        # ``[:phoneme ...]`` never re-interprets a plain body as phonemes
        # (issue #248); fall through and LTS-render the segment body.
        import re as _re  # noqa: PLC0415 — local import keeps the helper file-private

        from dectalk.kernel.numbers import number_to_words  # noqa: PLC0415

        # C-faithful kernel-level digit-string expansion. Replaces the
        # words that read differently when generated from a numeral
        # (``FOUR`` -> ``__NUM_FOUR__`` for the OR-vowel form,
        # ``THOUSAND`` -> ``__NUM_THOUSAND__`` for the schwa-N form),
        # inserts comma pauses between scale groups, and inserts
        # ``__NUM_AND__`` after a HUNDRED followed by tens/units. The
        # ``__NUM_*__`` sentinels resolve via ``word_phoneme_overrides``
        # to the exact phoneme stream the DECtalk C kernel emits for
        # digit-expansion contexts.
        def _digit_expand(value: int) -> list[Token]:
            teens = {
                "THIRTEEN": "__NUM_THIRTEEN__",
                "FOURTEEN": "__NUM_FOURTEEN__",
                "FIFTEEN": "__NUM_FIFTEEN__",
                "SIXTEEN": "__NUM_SIXTEEN__",
                "SEVENTEEN": "__NUM_SEVENTEEN__",
                "EIGHTEEN": "__NUM_EIGHTEEN__",
                "NINETEEN": "__NUM_NINETEEN__",
            }
            words = number_to_words(value)
            out: list[Token] = []
            for i_w, w in enumerate(words):
                next_w = words[i_w + 1] if i_w + 1 < len(words) else None
                if w == "FOUR":
                    out.append(Token(TokenKind.WORD, "__NUM_FOUR__"))
                elif w == "FORTY":
                    out.append(Token(TokenKind.WORD, "__NUM_FORTY__"))
                elif w in teens:
                    out.append(Token(TokenKind.WORD, teens[w]))
                elif w == "THOUSAND":
                    out.append(Token(TokenKind.WORD, "__NUM_THOUSAND__"))
                    if next_w is not None:
                        out.append(Token(TokenKind.PAUSE_SHORT, ","))
                elif w in ("MILLION", "BILLION"):
                    out.append(Token(TokenKind.WORD, w))
                    if next_w is not None:
                        out.append(Token(TokenKind.PAUSE_SHORT, ","))
                elif w == "HUNDRED":
                    out.append(Token(TokenKind.WORD, w))
                    if next_w is not None and next_w not in (
                        "THOUSAND",
                        "MILLION",
                        "BILLION",
                    ):
                        out.append(Token(TokenKind.WORD, "__NUM_AND__"))
                else:
                    out.append(Token(TokenKind.WORD, w))
            return out

        _dotted = _re.compile(r"^[\d,]+(?:\.\d+)+$")
        _digits_strict = _re.compile(r"^\d[\d,]*$")
        _title_chunk = _re.compile(r"^([A-Za-z]+)\.$")
        _leading_alpha = _re.compile(r"^[A-Za-z]+")

        def _clause_initial(toks: list[Token]) -> bool:
            """True when no WORD has been emitted since the last pause.

            Mirrors the C ``fc_index == 1`` test in
            ``ls_task_Dr_St_process`` (ls_task.c line 3042): the
            form-class index resets at every clause delimiter, so
            "first word of the sentence" means first word of the
            current *clause* — a comma resets it too (verified:
            ``Hello, St. paul`` reads "saint").
            """
            for back_tok in reversed(toks):
                if back_tok.kind is TokenKind.WORD:
                    return False
                if back_tok.kind in (TokenKind.PAUSE_LONG, TokenKind.PAUSE_SHORT):
                    return True
            return True

        from dectalk.lts.numeric_formats import (  # noqa: PLC0415 — local like the helpers above
            am_pm_phonemes,
            numeric_chunk_phonemes,
        )
        from dectalk.lts.token_shapes import (  # noqa: PLC0415 — local like the helpers above
            is_clean_cap_word,
            is_mixed_alnum,
            roman_ordinal_text,
            spell_form,
            split_alnum_runs,
        )
        from dectalk.lts.util_helpers import (  # noqa: PLC0415 — local like the helpers above
            ls_util_is_year,
        )

        raw_prefix = "__RAW__"
        # Tokenize with C-faithful digit-string handling: for each
        # whitespace-delimited chunk, if (after stripping surrounding
        # punctuation) it's a pure digit-string or dotted decimal,
        # route through ``_digit_expand``; if it's one of the C front
        # end's numeric formats (ordinal / currency / clock time /
        # fraction / dd-mon date / signed integer / digit-dash part
        # number — issue #225), splice the pre-rendered oracle-exact
        # phoneme stream from ``lts.numeric_formats``; otherwise let
        # ``kernel.text.tokenize`` handle it. The chunk queue lets the
        # symbol-splitting pre-pass below re-inject the split parts of
        # a chunk (``one+`` -> ``one`` + ``__SYM_PLUS__``) so each part
        # runs through this same dispatch.
        tokens: list[Token] = []
        chunk_queue: deque[str] = deque(seg.body.split())
        prev_chunk: str | None = None
        while chunk_queue:
            chunk = chunk_queue.popleft()
            # Preceding whitespace-delimited chunk (for the roman-numeral
            # R387 capitalised-word prefix test, issue #324). Snapshot
            # before overwriting so the current iteration still sees it.
            prev_chunk_for_roman = prev_chunk
            prev_chunk = chunk
            # Sentinel re-injected by the symbol split below: emit the
            # WORD token directly (its phonemes live in
            # ``word_phoneme_overrides``). Checked FIRST -- the
            # sentinel names contain the very symbol characters the
            # splitter looks for.
            if chunk in _SYMBOL_SENTINELS.values():
                tokens.append(Token(TokenKind.WORD, chunk))
                continue
            if chunk == "__SYM_NUMBER_SIGN__":
                # ``#`` speaks as the two-word dictionary entry
                # ``n'^mbR sAn`` ("number sign", Dic_us.txt line 70).
                tokens.append(Token(TokenKind.WORD, "__SYM_NUMBER__"))
                tokens.append(Token(TokenKind.WORD, "__SYM_SIGN__"))
                continue
            # Whole-chunk punctuation (issue #315): attach to the open
            # clause's word or speak the mark by name, exactly as the
            # C ``cm_pars``/``ls_spel`` pair does. ``None`` means the
            # chunk is not an isolated mark -- fall through. This lane
            # owns the ``.,;:!?`` mark set; the symbol splitter below
            # owns the disjoint ``& % @ + = * / # ^`` set, and the
            # numeric dispatch (issue #225) owns digit-bearing chunks
            # (the boundary #244's digit-guard already coordinates
            # toward), so the three never contend for the same chunk.
            punct_tokens = _isolated_punct_tokens(
                chunk, clause_has_word=_open_clause_has_word(tokens)
            )
            if punct_tokens is not None:
                tokens.extend(punct_tokens)
                continue
            # --- Title abbreviations (issue #246) -------------------
            # A chunk of the exact shape ``<letters>.`` may be a title
            # abbreviation. Two C mechanisms apply (case-insensitive):
            #
            # - ``mr. / mrs. / ms. / prof. / vs.`` are plain runtime-
            #   dictionary entries keyed WITH the trailing period
            #   (Dic_us.txt lines 177/191/9623/9624/14809), so they hit
            #   unconditionally -- any following context, including end
            #   of input -- and the period is consumed (no sentence
            #   break, no ``.`` marker in the stream).
            # - ``dr. / st.`` go through ``ls_task_Dr_St_process``
            #   (ls_task.c lines 2988-3057): next word capitalised ->
            #   doctor/saint, UNLESS that word is exactly ``Dr``/``St``
            #   (back-to-back guard) -> drive/street; next word lower-
            #   case -> doctor/saint only when the abbreviation is the
            #   first word of the clause, else drive/street; no next
            #   word at all -> drive/street.
            title_m = _title_chunk.match(chunk)
            if title_m:
                title_low = title_m.group(1).lower()
                if title_low in _TITLE_DICT_SENTINELS:
                    tokens.append(Token(TokenKind.WORD, _TITLE_DICT_SENTINELS[title_low]))
                    continue
                if title_low in ("dr", "st"):
                    nxt = chunk_queue[0] if chunk_queue else None
                    if nxt is None:
                        person = False  # FINISHED_WORD branch: street/drive
                    elif nxt[0].isupper():
                        nxt_alpha_m = _leading_alpha.match(nxt)
                        nxt_alpha = nxt_alpha_m.group(0) if nxt_alpha_m else ""
                        # "St. Dr." back-to-back reads street/drive.
                        person = nxt_alpha not in ("Dr", "St")
                    else:
                        person = _clause_initial(tokens)
                    if title_low == "dr":
                        sentinel = "__TITLE_DR__" if person else "__TITLE_DR_DRIVE__"
                    else:
                        sentinel = "__TITLE_ST__" if person else "__TITLE_ST_STREET__"
                    tokens.append(Token(TokenKind.WORD, sentinel))
                    continue
            # --- Symbol splitting (issue #244) ----------------------
            # The C kernel treats ``& % @ + = * / # ^`` as word
            # delimiters that speak via their own runtime-dictionary
            # rows (Dic_us.txt lines 70-236), wherever they sit in the
            # chunk: ``one+ two`` / ``+one`` / ``a+b`` all read "plus".
            # Guards mirror the C order of operations:
            # - whole-token dictionary entries win over splitting
            #   (``and/or`` is a Dic_us.txt row -> spoken via its own
            #   entry, never split),
            # - digit-bearing chunks stay with the numeric formats
            #   (``10/20`` fraction, ``100%``, ``$0.01`` -- issue #225
            #   territory),
            # - URLs keep their ``/`` syntax.
            if (
                any(c in _SYMBOL_SENTINELS or c == "#" for c in chunk)
                and not any(c.isdigit() for c in chunk)
                and "$" not in chunk
                and lookup(chunk.rstrip(".,;:!?").upper(), lang=lang) is None
                and try_url(chunk) is None
            ):
                parts: list[str] = []
                buf: list[str] = []
                for c in chunk:
                    if c in _SYMBOL_SENTINELS or c == "#":
                        if buf:
                            parts.append("".join(buf))
                            buf.clear()
                        parts.append("__SYM_NUMBER_SIGN__" if c == "#" else _SYMBOL_SENTINELS[c])
                    else:
                        buf.append(c)
                if buf:
                    parts.append("".join(buf))
                chunk_queue.extendleft(reversed(parts))
                continue
            # Mimic tokenize's punctuation stripping so we can spot a
            # digit-only payload like ``5.``, ``(123)`` or ``"42"``.
            inner = chunk
            leading: list[str] = []
            trailing: list[str] = []
            while inner and not inner[0].isalnum() and inner[0] != "$":
                leading.append(inner[0])
                inner = inner[1:]
            while inner and not inner[-1].isalnum():
                trailing.insert(0, inner[-1])
                inner = inner[:-1]
            # --- Roman numeral contextual ordinal (issue #324) ------
            # NWS rule R387 (par_rule.par:417) rewrites a roman numeral to
            # its ordinal value ("the Nth") when — and only when — it
            # directly follows a capitalised word: ``Chapter IV`` ->
            # ``Chapter the 4th`` -> "chapter the fourth". The capitalised
            # prefix (``U<1>A<+>W<+>``) is the whole guard: bare ``IV``,
            # lowercase ``iv``, ``chapter IV`` and ``Chapter, IV`` (punct,
            # not whitespace) all fail R387 and read as ordinary words.
            # The ``roman_num`` table is exact strings for 2..20 only, so
            # words like ``MIX``/``DID`` never match. Reinject ``the`` +
            # ``Nth`` so the pipeline reads the ordinal (mirrors the C
            # ``r/$7/$9/`` replacement).
            if inner and not leading and inner.isupper():
                roman_txt = roman_ordinal_text(inner)
                if roman_txt is not None and is_clean_cap_word(prev_chunk_for_roman):
                    roman_parts = roman_txt.split()  # ["the", "4th"]
                    roman_parts[-1] = roman_parts[-1] + "".join(trailing)
                    chunk_queue.extendleft(reversed(roman_parts))
                    continue
            # C keeps sign characters through its punctuation strip
            # (``ls_task_strip_left_punctuation`` LS class excludes
            # them; ``ls_task_set_sign_flag`` consumes them later) —
            # recover a stripped sign for the numeric dispatch. Pure
            # unsigned digit strings return None from the dispatcher
            # (the corpus-proven ``_digit_expand`` path owns them);
            # signed ones are C's do_sign + do_number ("minus five").
            # --- Numeric formats (issue #225) -----------------------
            # After the symbol splitter (which skips digit/``$`` chunks),
            # route the C front end's numeric shapes through the ported
            # LTS dispatch. Lookahead uses the chunk queue: ``$5
            # million`` peeks/consumes the nwdtab scale word and a clock
            # time peeks/consumes a following am/pm word — both mirror
            # the C ``ls_task_readword`` consumption.
            numeric_expansion = None
            if inner:
                sign_prefix = leading[-1] if leading and leading[-1] in "-+" else ""
                is_plain_digits = bool(_digits_strict.match(inner) or _dotted.match(inner))
                # Bare all-digit tokens normally skip the numeric
                # dispatch (the corpus-proven ``_digit_expand`` path owns
                # them), but a sign-free 4-digit YEAR must reach it so it
                # reads "nineteen eighty four" via ls_proc_do_4_digits
                # (issue #335) rather than the cardinal "one thousand
                # nine hundred...". ``ls_util_is_year`` mirrors the C
                # recognizer exactly, so only true years route here
                # (2000 / 2001 / other non-year 4-digit tokens stay on
                # the cardinal path).
                is_bare_year = not sign_prefix and ls_util_is_year(inner)
                if sign_prefix or not is_plain_digits or is_bare_year:
                    next_chunk = chunk_queue[0] if (not trailing and chunk_queue) else None
                    numeric_expansion = numeric_chunk_phonemes(
                        inner,
                        sign_prefix=sign_prefix,
                        next_word=next_chunk,
                        had_leading_punct=len(leading) > (1 if sign_prefix else 0),
                    )
            if numeric_expansion is None and inner and _digits_strict.match(inner):
                tokens.extend(_digit_expand(int(inner.replace(",", ""))))
            elif numeric_expansion is not None:
                tokens.append(
                    Token(
                        TokenKind.WORD,
                        raw_prefix + numeric_expansion.phonemes.decode("latin-1"),
                    )
                )
                if numeric_expansion.consumed_next:
                    # "$5 million" folded the scale word in.
                    chunk_queue.popleft()
                elif numeric_expansion.is_time and not trailing and chunk_queue:
                    # C's after-time lookahead spells a following
                    # am/pm word (``ls_task.c:3616-3646``). Only when
                    # the time chunk carried no trailing punctuation —
                    # the pause token must stay between the two words.
                    ampm_chunk = chunk_queue[0]
                    ampm_inner = ampm_chunk
                    ampm_trailing: list[str] = []
                    has_leading = False
                    while ampm_inner and not ampm_inner[0].isalnum():
                        has_leading = True
                        ampm_inner = ampm_inner[1:]
                    while ampm_inner and not ampm_inner[-1].isalnum():
                        ampm_trailing.insert(0, ampm_inner[-1])
                        ampm_inner = ampm_inner[:-1]
                    spelled = None if has_leading else am_pm_phonemes(ampm_inner)
                    if spelled is not None:
                        chunk_queue.popleft()
                        tokens.append(Token(TokenKind.WORD, raw_prefix + spelled.decode("latin-1")))
                        trailing = ampm_trailing
            elif inner and _dotted.match(inner):
                # Dotted decimal (``3.14`` / ``1,234.56`` / ``6.2.0``).
                # The C kernel speaks the integer part as a whole number
                # through the same digit-expansion path as a bare
                # digit-string (schwa-N THOUSAND, comma pauses, __NUM_AND__
                # after HUNDRED, or-vowel FOUR/FORTY) and then reads every
                # ``.``-separated fraction group digit by digit with
                # leading zeros preserved: ``3.14`` -> "three point one
                # four" (not "fourteen"), ``10.01`` -> "ten point zero
                # one". Verified against CAPI.convert_to_phonemes (#281).
                parts = inner.split(".")
                tokens.extend(_digit_expand(int(parts[0].replace(",", ""))))
                for part in parts[1:]:
                    tokens.append(Token(TokenKind.WORD, "POINT"))
                    for digit in part:
                        tokens.extend(_digit_expand(int(digit)))
            elif inner and is_mixed_alnum(inner):
                # --- Mixed alphanumeric split (issue #323) ----------
                # NWS rules R390/R391 (par_rule.par:430-432) insert a
                # space at every digit/letter boundary; re-process each
                # run as its own word. Digit runs read as numbers, letter
                # runs pronounce via LTS or (for unpronounceable all-caps
                # clusters like ``kg`` -> "kay gee") spell. Reached only
                # when the numeric dispatch declined, which is exactly the
                # R389 ordinal/plural guard (``1st`` / ``1990s`` / ``70s``
                # stay with numeric_formats). ``spell_form`` upper-cases
                # the runs the say-it predicate spells so the all-caps
                # path below renders them; ``.`` binds to its digit run so
                # ``6.02e23`` keeps its decimal.
                runs = [spell_form(r) for r in split_alnum_runs(inner)]
                runs[0] = "".join(leading) + runs[0]
                runs[-1] = runs[-1] + "".join(trailing)
                chunk_queue.extendleft(reversed(runs))
                continue
            elif (
                inner and inner.isalpha() and inner.isupper() and 2 <= len(inner) <= 4  # noqa: PLR2004
            ):
                # All-uppercase 2-4 letter token: run the
                # ``ls_spel_say_it`` decision. If ``say_it`` returns
                # False (spell it), record the upper-cased token in
                # ``spell_out_words`` so the main loop's letter-by-letter
                # path renders it. Otherwise let ``tokenize`` handle it
                # as a normal word.
                from dectalk.lts.spell_or_say import say_it  # noqa: PLC0415

                if not say_it(inner):
                    spell_out_words.add(inner)
                tokens.extend(tokenize(chunk))
                continue
            elif inner and "-" in inner and not inner.startswith("-"):
                # Hyphenated compound (``forty-two``, ``self-taught``):
                # tokenise each part separately so we can insert the
                # ``#`` syllable-break marker the C source emits in
                # place of the regular word break.
                parts = inner.split("-")
                for i_part, part in enumerate(parts):
                    if i_part > 0:
                        tokens.append(Token(TokenKind.PAUSE_SHORT, "#"))
                    if part:
                        tokens.extend(tokenize(part))
            else:
                tokens.extend(tokenize(chunk))
                continue
            # If the chunk had trailing sentence/clause punct (e.g.
            # ``101.``), preserve the pause token after the digit
            # expansion -- this matches tokenize's behaviour.
            if trailing:
                last = trailing[-1]
                if last in (".", "!", "?"):
                    tokens.append(Token(TokenKind.PAUSE_LONG, last))
                elif last in (",", ";", ":"):
                    tokens.append(Token(TokenKind.PAUSE_SHORT, last))
        # Pre-pass B: legacy title expansion (PAUSE_LONG '.' + WORD
        # pattern). The chunk-loop title pre-pass above (issue #246)
        # now intercepts every clean ``<Title>.`` chunk with the
        # C-faithful context rules, so this only sees the leftover
        # punctuation-adjacent shapes it can still reach (``"Dr.,"`` /
        # quoted forms) where tokenize separated the title from its
        # period. Kept as a better-than-spelling fallback -- the C
        # spells such shapes letter-by-letter with a spoken "period",
        # machinery we don't model.
        title_abbrevs = {
            "DR": "__TITLE_DR__",
            "MR": "__TITLE_MR__",
            "MRS": "__TITLE_MRS__",
            "MS": "__TITLE_MS__",
        }
        rewritten: list[Token] = []
        i_tok = 0
        while i_tok < len(tokens):
            tok = tokens[i_tok]
            if (
                tok.kind is TokenKind.WORD
                and tok.text in title_abbrevs
                and i_tok + 2 < len(tokens)
                and tokens[i_tok + 1].kind is TokenKind.PAUSE_LONG
                and tokens[i_tok + 1].text == "."
                and tokens[i_tok + 2].kind is TokenKind.WORD
            ):
                rewritten.append(Token(TokenKind.WORD, title_abbrevs[tok.text]))
                i_tok += 2  # skip the period; next iter consumes the name
                continue
            rewritten.append(tok)
            i_tok += 1
        tokens = rewritten
        # Pre-scan for ``wh-`` question words so the ``?`` punct mapping
        # knows which intonation contour the C kernel would pick.
        sentence_has_wh = any(
            t.kind is TokenKind.WORD and t.text in wh_question_words for t in tokens
        )

        def _select_pair(word: str, cur_fc: int) -> tuple[str, int, int]:
            """Resolve a homograph pair's reading from tracked context.

            Applies the C ``ls_homo_homo`` selection against the
            running ``word_fcs`` mirror of ``fc_struct``: the first
            word of a sentence takes the primary entry, an unknown
            previous word noun-defaults (BATS#705 — persisted into
            ``word_fcs``, matching the C's in-place mutation), and the
            27-rule table decides the rest.

            Args:
                word: Upper-cased homograph with ``|P``/``|S`` rows in
                    the form-class sidecar.
                cur_fc: The word's pre-hit mask (0 for a direct hit;
                    the suffix rule's mask for a stripped derivation).

            Returns:
                ``(reading, selected_fc, exposed_fc)`` — the ``"P"`` /
                ``"S"`` reading, the selected entry's built mask (for
                the VPSTART decision), and the mask this word exposes
                to later context checks.
            """
            p_fc = formclass_lex[f"{word}|P"]
            s_fc = formclass_lex[f"{word}|S"]
            prev_fc = 0
            if word_fcs:
                if word_fcs[-1] == 0:
                    word_fcs[-1] = BATS705_DEFAULT_FC
                prev_fc = word_fcs[-1]
            reading, homo_rule = select_homograph_entry(
                p_fc,
                s_fc,
                cur_fc=cur_fc,
                prev_fc=prev_fc,
                prev_prev_fc=word_fcs[-2] if len(word_fcs) >= 2 else None,  # noqa: PLR2004
                first_word=not word_fcs,
            )
            selected_fc = p_fc if reading == "P" else s_fc
            exposed_fc = resolved_form_class(selected_fc, cur_fc=cur_fc, rule=homo_rule)
            return reading, selected_fc, exposed_fc

        for tok_idx, token in enumerate(tokens):
            if token.kind is TokenKind.WORD:
                # Only insert an inter-word break if there's no
                # punctuation marker just before -- the C source's
                # punctuation emit (``, `` / ``. `` / ``! `` /
                # ``? ``) already carries its own trailing space.
                if flat and not flat[-1].startswith(punct_prefix):
                    flat.append("_")
                # Numeric-format splice (issue #225): the chunk loop
                # pre-rendered ordinals / currency / times / fractions
                # / dates / ranges to the oracle's exact ASCII stream
                # via ``lts.numeric_formats``. Pass the payload through
                # untouched and expose the C number form class
                # (``ls_task.c:3773`` marks numbers FC_ADJ).
                if token.text.startswith(raw_prefix):
                    flat.append(token.text)
                    word_fcs.append(FC_ADJ)
                    continue
                # --- Homograph resolution + form-class tracking -----
                # (issue #295). For P/S homograph pairs — whether the
                # token itself (``close``) or its suffix-stripped root
                # (``tears`` → ``tear``) — pick the reading from
                # context and emit the ``)`` VPSTART marker per the
                # *selected* entry's mask, exactly as
                # ``ls_dict_find_word`` does. Every other word emits
                # ``)`` from the static sidecar/curated set as before.
                homo_reading: str | None = None
                homo_stem_reading: tuple[str, str] | None = None
                # Runtime-dictionary root + rule suffix from the ACTIVE
                # ``l_us_suf.c`` strip-rule walk (issue #310). Set when
                # the word itself is outside the runtime dictionary but
                # a suffix rule re-derives a root inside it (``stopped``
                # -> STOP via the ``pp`` -> ``p`` un-doubling variant).
                # The stem-strip branches below use the root as the
                # C-faithful stem source and emit the ``)`` VPSTART
                # marker per the *root* entry's mask -- in C the marker
                # comes from ``ls_dict_find_word`` when the suffix
                # engine looks the stripped root up (``ls_suff.c`` line
                # 266 -> ``ls_dict.c`` lines 759-763).
                suffix_root: str | None = None
                suffix_rule_suffix: str | None = None
                vpstart_emitted = False
                if token.text in spell_out_words:
                    # ``ls_task_spell_word`` tags spelled words FC_NOUN.
                    this_word_fc = FC_NOUN
                elif token.text in homograph_pair_words:
                    homo_fc_reading, selected_fc, this_word_fc = _select_pair(token.text, 0)
                    homo_reading = homo_fc_reading
                    if emits_vpstart(selected_fc):
                        flat.append(f"{punct_prefix})")
                        vpstart_emitted = True
                elif token.text in formclass_lex:
                    this_word_fc = formclass_lex[token.text]
                else:
                    suffix_fc, stem_root, rule_suffix = suffix_form_class(
                        token.text, formclass_words
                    )
                    if stem_root is not None and stem_root in homograph_pair_words:
                        homo_fc_reading, selected_fc, this_word_fc = _select_pair(
                            stem_root, suffix_fc
                        )
                        homo_stem_reading = (stem_root, homo_fc_reading)
                        if emits_vpstart(selected_fc):
                            flat.append(f"{punct_prefix})")
                            vpstart_emitted = True
                    else:
                        this_word_fc = suffix_fc
                        suffix_root = stem_root
                        suffix_rule_suffix = rule_suffix
                word_fcs.append(this_word_fc)
                if (
                    homo_reading is None
                    and homo_stem_reading is None
                    and token.text in vpstart_words
                ):
                    flat.append(f"{punct_prefix})")
                    vpstart_emitted = True
                # Function-word destressing / phrase-marker injection.
                # For "A": apply only when followed by another WORD
                # (mid-sentence). For "AND": apply unconditionally
                # (C emits the ``^ (`` markers in every position).
                rule = function_word_destress.get(token.text)
                has_following_word = any(t.kind is TokenKind.WORD for t in tokens[tok_idx + 1 :])
                if rule is not None and (token.text != "A" or has_following_word):
                    markers, custom_phones = rule
                    for marker in markers:
                        flat.append(f"{punct_prefix}{marker}")
                    flat.extend(custom_phones)
                    continue
                if token.text in spell_out_words:
                    # Spell out letter-by-letter. The default C path
                    # keeps every letter primary-stressed; the only
                    # exception is the small set of acronyms whose
                    # main-dic entry hard-codes a destressed middle
                    # letter (FBI is the canonical example -- C dic
                    # has ``Ef bi 'A`` with no stress mark on ``bi``).
                    # The ``destress_middle_letter_acronyms`` set
                    # opts those into the legacy "first and last
                    # only" pattern.
                    destress_middle_letter_acronyms: frozenset[str] = frozenset({"FBI"})
                    letters = list(token.text)
                    for i_letter, letter in enumerate(letters):
                        if i_letter > 0:
                            flat.append("_")
                        group = list(letter_names.get(letter, [letter]))
                        if (
                            0 < i_letter < len(letters) - 1
                            and token.text in destress_middle_letter_acronyms
                        ):
                            group = [p[:-1] + "0" if p and p[-1].isdigit() else p for p in group]
                        flat.extend(group)
                    continue
                # First-verbs hack: at the start of a sentence, six
                # auxiliary / linking verbs (are/had/is/was/were/will) get
                # secondary stress applied through a fixed phoneme
                # sequence. C ref: ``ls_task.c`` -- ``ls_task_set_what_state``
                # runs ``ls_task_lookup_first_verbs`` (the ``verbs[6]``
                # table) only while ``wstate == UNK_WH``, and
                # ``ls_task_do_right_punct`` resets ``wstate = UNK_WH``
                # after ``.`` / ``?`` / ``!`` only -- ``,`` / ``;`` / ``:``
                # do NOT reset it. The Python tokenizer maps exactly that
                # sentence-terminator set to ``PAUSE_LONG`` (and the
                # clause set to ``PAUSE_SHORT``), so "sentence-initial"
                # means: no WORD token since the last ``PAUSE_LONG``
                # (or since the start of the utterance).
                is_sentence_initial = True
                for back_tok in reversed(tokens[:tok_idx]):
                    if back_tok.kind is TokenKind.WORD:
                        is_sentence_initial = False
                        break
                    if back_tok.kind is TokenKind.PAUSE_LONG:
                        break
                stem_stripped = False
                if is_sentence_initial and token.text in first_verb_phones:
                    phones = list(first_verb_phones[token.text])
                elif token.text in word_phoneme_overrides:
                    phones = list(word_phoneme_overrides[token.text])
                elif token.text in compound_marker_lex:
                    # Sidecar compound: phoneme list already carries the
                    # ``__PUNCT__*`` MBOUND markers at the C dictionary's
                    # compound boundaries. Use as-is rather than the
                    # bundled lexicon's stripped form.
                    phones = list(compound_marker_lex[token.text])
                else:
                    # Form-class homograph disambiguation (issue #144 /
                    # #295). Runtime P/S homograph pairs were resolved
                    # against the C ``ls_homo_homo`` rules at the top
                    # of the loop; fetch the selected reading's
                    # phonemes (``CLOSE|P`` vs ``CLOSE|S``).
                    if homo_reading is not None:
                        phones = lookup(token.text, lang=lang, form_class=homo_reading)
                        # Fall back to the default reading if the
                        # lexicon doesn't carry this pair (a handful
                        # of runtime pairs have no 2002 P/S rows).
                        if phones is None:
                            phones = lookup(token.text, lang=lang)
                    else:
                        phones = lookup(token.text, lang=lang)
                    # ``'s`` contraction (``that's`` = ``that is``,
                    # ``it's`` = ``it is``). Strip the apostrophe + S
                    # and look up the base form; if found, append S
                    # (the encoder's voicing rule handles is/iz).
                    if (
                        phones is None and token.text.endswith("'S") and len(token.text) > 2  # noqa: PLR2004
                    ):
                        base = token.text[:-2]
                        base_phones = lookup(base, lang=lang)
                        if base_phones is None and lts_fallback:
                            # ``or None``: digit/symbol stems (``'90's``)
                            # produce an empty LTS stream; treat that as
                            # no-stem instead of indexing into it
                            # (issue #316 discovery-sweep crash).
                            base_phones = _dedupe_consecutive_phonemes(lts(base)) or None
                        if base_phones is not None:
                            # Sibilant-final stems take an epenthetic
                            # IX+Z (``judge's`` -> ``jh ahjh ixz``,
                            # ``fox's`` -> ``f aak s ixz``).
                            last_base = base_phones[-1].rstrip("0123456789")
                            if last_base in {"S", "Z", "SH", "ZH", "CH", "JH"}:
                                phones = [*base_phones, "IX", "Z"]
                            else:
                                phones = [*base_phones, "S"]
                            stem_stripped = True
                            # Pure-verb runtime-dictionary bases emit
                            # ``)`` before the base phonemes, exactly
                            # as C's suffix engine does when the
                            # ``-'s`` strip rule's stem lookup hits
                            # the main dictionary (``let's`` ->
                            # ``) ll` eht s``, issue #310).
                            if (
                                not vpstart_emitted
                                and suffix_root is not None
                                and suffix_rule_suffix == "'s"
                                and emits_vpstart(formclass_lex.get(suffix_root, 0))
                            ):
                                phones.insert(0, f"{punct_prefix})")
                                vpstart_emitted = True
                    # Plural / 3rd-person -s stem stripping: if the word
                    # isn't in the lexicon but its singular form is, use
                    # the singular's phonemes and append S (the encoder's
                    # voicing rule will pick Z when appropriate). DECtalk
                    # handles this via the runtime suffix engine; we
                    # short-circuit here for the common ``-s`` / ``-es``
                    # cases the corpus exercises.
                    if (
                        phones is None
                        and token.text.endswith("S")
                        and not token.text.endswith(("SS", "US", "IS"))
                    ):
                        stem = token.text[:-1]
                        s_silent_e = False
                        if homo_stem_reading is not None:
                            # Runtime homograph root (``tears`` →
                            # TEAR, ``lives`` → LIVE): use the reading
                            # the ls_homo_homo port selected at the
                            # top of the loop, against the root the
                            # suffix engine derived.
                            homo_root, homo_fc = homo_stem_reading
                            stem_phones = lookup(
                                homo_root, lang=lang, form_class=homo_fc
                            ) or lookup(homo_root, lang=lang)
                        elif stem.endswith("E") and len(stem) > 2:  # noqa: PLR2004
                            # ``minutes`` -> ``minute`` (drop the trailing
                            # E along with the S so we hit the stem entry).
                            stem_e_phones = lookup(stem, lang=lang)
                            s_silent_e = stem_e_phones is not None
                            stem_phones = stem_e_phones or lookup(stem[:-1], lang=lang)
                        else:
                            stem_phones = lookup(stem, lang=lang)
                        # ``cities`` -> ``citie`` (lookup fails) -> ``city``
                        # via the Y -> I orthographic alternation.
                        if stem_phones is None and len(stem) > 1 and stem.endswith("IE"):
                            stem_phones = lookup(stem[:-2] + "Y", lang=lang)
                            # Out-of-lexicon -y base (``envies`` -> ENVY,
                            # ``pities`` -> PITY): render the -Y form so the
                            # mutated ``i`` reads as the base's /iy/ rather
                            # than the whole-word LTS /ay/ (issue #321). The
                            # LTS's own y-rule keeps single-syllable bases
                            # /ay/ (``flies`` -> FLY) automatically.
                            if stem_phones is None and lts_fallback:
                                stem_phones = (
                                    _dedupe_consecutive_phonemes(lts(stem[:-2] + "Y")) or None
                                )
                        elif stem_phones is None and len(stem) > 1 and stem.endswith("I"):
                            stem_phones = lookup(stem[:-1] + "Y", lang=lang)
                        # Sibilant-final stems take ``-es``: try the
                        # base form with the trailing E dropped (``masses``
                        # -> ``mass``).
                        if stem_phones is None and stem.endswith("E") and len(stem) > 2:  # noqa: PLR2004
                            stem_phones = lookup(stem[:-1], lang=lang)
                        # LTS fallback so ``masses`` / ``foxes`` /
                        # ``classes`` etc. still get the IX+Z epenthesis
                        # treatment even when neither the full word nor
                        # the bare stem is in the lexicon.
                        if stem_phones is None and lts_fallback:
                            # Keep a trailing orthographic ``E`` so a
                            # magic-e base renders long (``pokes`` -> POKE,
                            # ``glides`` -> GLIDE, ``roses`` -> ROSE); a
                            # sibilant root (``masses`` -> MASSE, ``foxes``
                            # -> FOXE) still ends in a sibilant and picks up
                            # the IX+Z epenthesis below (issues #316, #320).
                            # ``or None``: digit stems (``'90s`` -> ``'90``)
                            # yield an empty LTS stream; treat as no-stem
                            # rather than crash on ``stem_phones[-1]`` below.
                            stem_phones = _dedupe_consecutive_phonemes(lts(stem)) or None
                        if stem_phones is not None:
                            # When the stem ends in a sonorant (L/N)
                            # preceded by a stop ("SECOND" -> S EH K N D
                            # ; "REASON" -> R IY Z N), the syllabic rule
                            # needs the L/N to read as ``el`` / ``en``
                            # even though the stem itself is followed by
                            # an inflectional consonant rather than a
                            # word break. Materialise that here by
                            # rewriting the relevant phoneme in the stem
                            # before concatenation.
                            stem_phones = _apply_pre_inflection_syllabic(stem_phones)
                            # Freeze the stem's weak vowel to its bare
                            # value so the appended ``-s`` doesn't shift
                            # the reduction context (``edits`` -> IX,
                            # ``limits`` -> IX; issue #322).
                            stem_phones = _freeze_stem_weak_vowels(stem_phones, silent_e=s_silent_e)
                            # Sibilant-final stems take an epenthetic
                            # IX before the inflectional Z (``classes``
                            # -> CLASS + IX + Z; ``horses`` -> HORSE +
                            # IX + Z; ``roses`` -> ROSE + IX + Z).
                            last_base = stem_phones[-1].rstrip("0123456789")
                            if last_base in {"S", "Z", "SH", "ZH", "CH", "JH"}:
                                phones = [*stem_phones, "IX", "Z"]
                            else:
                                phones = [*stem_phones, "S"]
                            stem_stripped = True
                            # Pure-verb runtime-dictionary roots emit
                            # the ``)`` VPSTART marker before the stem
                            # phonemes (``begins`` -> ``) b axg ' ihn
                            # z``), exactly as C's suffix engine does
                            # when its stripped-stem lookup hits the
                            # main dictionary (issue #310).
                            if (
                                not vpstart_emitted
                                and suffix_root is not None
                                and suffix_rule_suffix in ("s", "es", "ies")
                                and emits_vpstart(formclass_lex.get(suffix_root, 0))
                            ):
                                phones.insert(0, f"{punct_prefix})")
                                vpstart_emitted = True
                    # ``-ier`` / ``-iest`` comparative/superlative on a
                    # consonant+y adjective: the orthographic y -> i
                    # mutation (``happy`` -> ``happier``) reads in C as the
                    # base word's final /iy/, not the whole-word LTS /ay/
                    # ("happ-eye-er"). Recover the -Y base and append the
                    # inflection (``happier`` -> HAPPY + ER0, ``happiest``
                    # -> HAPPY + IX S T, ``heavier`` -> HEAVY + ER0). The
                    # base's final IY carries the vowel; the LTS y-rule
                    # keeps single-syllable bases /ay/ on its own. Runs
                    # before ``-er`` (which excludes ``IER``) and ``-est``
                    # (which leaves ``phones`` None for these). Issue #321.
                    for _y_suf, _y_strip, _y_tail in (
                        ("IEST", 4, ["IX", "S", "T"]),
                        ("IER", 3, ["ER0"]),
                    ):
                        if (
                            phones is None
                            and token.text.endswith(_y_suf)
                            and len(token.text) > _y_strip + 1
                            and token.text[-(_y_strip + 1)] not in "AEIOU"
                        ):
                            y_base = token.text[:-_y_strip] + "Y"
                            y_phones = lookup(y_base, lang=lang)
                            if y_phones is None and lts_fallback:
                                y_phones = _dedupe_consecutive_phonemes(lts(y_base)) or None
                            if y_phones is not None:
                                phones = [*y_phones, *_y_tail]
                    # ``-er`` agentive / comparative suffix: strip and
                    # look up the bare stem, then append ER0. Handles
                    # ``LATER`` (LATE+R), ``FASTER`` (FAST+ER), etc.
                    if (
                        phones is None
                        and token.text.endswith("ER")
                        and len(token.text) > 3  # noqa: PLR2004
                        and not token.text.endswith(("EER", "IER"))
                    ):
                        stem = token.text[:-2]
                        stem_e_phones = lookup(stem + "E", lang=lang)
                        er_silent_e = stem_e_phones is not None
                        stem_phones = stem_e_phones or lookup(stem, lang=lang)
                        # Doubled-final-consonant stems re-derive the
                        # runtime-dictionary root via the ACTIVE
                        # ``l_us_suf.c`` ``-er`` rule's un-doubling
                        # variants (``stopper`` -> STOP + ER, keeping
                        # the dictionary's AO vowel), with the C LTS
                        # engine's un-doubling as the fallback for
                        # roots outside the dictionaries (issue #310).
                        if (
                            stem_phones is None
                            and suffix_root is not None
                            and suffix_rule_suffix == "er"
                        ):
                            stem_phones = lookup(suffix_root, lang=lang)
                        if stem_phones is None and lts_fallback:
                            stem_phones = _lts_inflection_stem(stem, attach_e=True)
                        if stem_phones is not None:
                            stem_phones = _freeze_stem_weak_vowels(
                                stem_phones, silent_e=er_silent_e
                            )
                            phones = [*stem_phones, "ER0"]
                            if (
                                not vpstart_emitted
                                and suffix_root is not None
                                and suffix_rule_suffix == "er"
                                and emits_vpstart(formclass_lex.get(suffix_root, 0))
                            ):
                                phones.insert(0, f"{punct_prefix})")
                                vpstart_emitted = True
                    # ``-tion`` / ``-sion`` noun suffix: strip and append
                    # ``SH + AH0 + N`` (AH0 -> IX by the encoder's
                    # post-SH rule). Catches PENSION / MANSION / TENSION
                    # and many others not in the lexicon.
                    if (
                        phones is None
                        and (token.text.endswith("TION") or token.text.endswith("SION"))
                        and len(token.text) > 4  # noqa: PLR2004
                    ):
                        tion_stem = token.text[:-4]
                        stem_phones = lookup(tion_stem, lang=lang)
                        if stem_phones is None and lts_fallback:
                            # ``or None``: guard empty LTS output for
                            # non-alphabetic stems (issue #316).
                            stem_phones = _dedupe_consecutive_phonemes(lts(tion_stem)) or None
                        if stem_phones is not None:
                            phones = [*stem_phones, "SH", "AH0", "N"]
                    # ``-ive`` adjective suffix: strip and append
                    # ``AH0 + V``. The encoder's AH0+V word-final rule
                    # reduces AH0 to IX (``active`` -> stem ACT +
                    # ``AH0 V`` -> ``' aek t ixv``). LTS for ``IVE`` end
                    # gives a wrong AY0 vowel, so this short-circuits.
                    if (
                        phones is None and token.text.endswith("IVE") and len(token.text) > 4  # noqa: PLR2004
                    ):
                        ive_stem = token.text[:-3]
                        stem_phones = lookup(ive_stem, lang=lang)
                        if stem_phones is None and lts_fallback:
                            # ``or None``: guard empty LTS output for
                            # non-alphabetic stems (issue #316).
                            stem_phones = _dedupe_consecutive_phonemes(lts(ive_stem)) or None
                        if stem_phones is not None:
                            phones = [*stem_phones, "AH0", "V"]
                    # ``-ly`` adverb suffix: strip and append ``L + IY0``
                    # (``friendly`` -> ``FRIEND`` + ``L + IY`` ->
                    # ``f r ' ehn d lliy``). Consonant-final stems only;
                    # vowel-final stems would need extra handling we skip.
                    if (
                        phones is None and token.text.endswith("LY") and len(token.text) > 3  # noqa: PLR2004
                    ):
                        ly_stem = token.text[:-2]
                        stem_phones = lookup(ly_stem, lang=lang) or lookup(ly_stem + "E", lang=lang)
                        if stem_phones is not None:
                            last_base = stem_phones[-1].rstrip("0123456789")
                            # Only fire when the stem ends in a consonant
                            # so we don't break vowel-final ``happily`` /
                            # ``easily`` patterns that diverge from C.
                            if last_base not in {
                                "AA",
                                "AE",
                                "AH",
                                "AO",
                                "AX",
                                "AY",
                                "AW",
                                "EH",
                                "ER",
                                "EY",
                                "IH",
                                "IX",
                                "IY",
                                "OW",
                                "OY",
                                "UH",
                                "UW",
                            }:
                                phones = [*stem_phones, "L", "IY0"]
                    # ``-ness`` noun-forming suffix: strip and append
                    # ``N + IX + S`` (``darkness`` -> ``d ' aar k n ixs``).
                    # Also tries the Y->I morphological alternation:
                    # ``happiness`` -> stem ``HAPPI`` -> retry ``HAPPY``.
                    if (
                        phones is None and token.text.endswith("NESS") and len(token.text) > 4  # noqa: PLR2004
                    ):
                        ness_stem = token.text[:-4]
                        stem_phones = lookup(ness_stem, lang=lang)
                        if stem_phones is None and ness_stem.endswith("I"):
                            stem_phones = lookup(ness_stem[:-1] + "Y", lang=lang)
                        # If the stem isn't in the lexicon, fall back to
                        # LTS for the stem so words like ``firmness`` /
                        # ``oddness`` still get the IX-bearing suffix
                        # rather than the LTS engine's ``ehs`` default.
                        if stem_phones is None and lts_fallback:
                            stem_phones = lts(ness_stem)
                        if stem_phones is not None:
                            phones = [
                                *_dedupe_consecutive_phonemes(stem_phones),
                                "N",
                                "IX",
                                "S",
                            ]
                    # ``-ful`` adjective suffix: strip and append F + L
                    # (``helpful`` -> ``hx' ehllp f el``). Encoder's
                    # word-final syllabic-L rule handles the EL.
                    if (
                        phones is None and token.text.endswith("FUL") and len(token.text) > 3  # noqa: PLR2004
                    ):
                        ful_stem = token.text[:-3]
                        stem_phones = lookup(ful_stem, lang=lang)
                        if stem_phones is not None:
                            phones = [*stem_phones, "F", "L"]
                    # ``-less`` adjective suffix: strip and append L+IX+S
                    # (``helpless`` -> ``hx' ehllp llixs``).
                    if (
                        phones is None and token.text.endswith("LESS") and len(token.text) > 4  # noqa: PLR2004
                    ):
                        less_stem = token.text[:-4]
                        stem_phones = lookup(less_stem, lang=lang)
                        if stem_phones is not None:
                            phones = [*stem_phones, "L", "IX", "S"]
                    # ``-ify`` verb-forming suffix: strip and append
                    # ``IX + F + AY`` (``modify`` -> ``m ' aad ixf ay``).
                    # Most common -ify verbs aren't in the bundled lex;
                    # the LTS would mis-render the suffix as ``IH0 F
                    # IY0`` (wrong final vowel). The stem-strip path
                    # forces the C-faithful suffix and uses LTS for
                    # the stem.
                    if (
                        phones is None and token.text.endswith("IFY") and len(token.text) > 3  # noqa: PLR2004
                    ):
                        ify_stem = token.text[:-3]
                        stem_phones = lookup(ify_stem, lang=lang)
                        if stem_phones is None and lts_fallback:
                            stem_phones = _dedupe_consecutive_phonemes(lts(ify_stem))
                        if stem_phones:
                            phones = [*stem_phones, "IX", "F", "AY"]
                    # ``-ment`` noun-forming suffix: strip and append
                    # ``M + AX + N + T`` (``payment`` -> ``p ' eym axn t``).
                    # When the stem isn't in the lexicon, run the LTS
                    # over it so we still pick up the C-faithful AX+N+T
                    # tail for ``fragment`` / ``garment`` / ``ornament``
                    # rather than falling through to LTS for the whole
                    # word (which mis-renders the ``-ment`` suffix as
                    # ``M EH0 N T``).
                    if (
                        phones is None and token.text.endswith("MENT") and len(token.text) > 4  # noqa: PLR2004
                    ):
                        ment_stem = token.text[:-4]
                        stem_phones = lookup(ment_stem, lang=lang) or lookup(
                            ment_stem + "E", lang=lang
                        )
                        if stem_phones is not None:
                            phones = [*stem_phones, "M", "AX", "N", "T"]
                        elif lts_fallback:
                            stem_lts = _dedupe_consecutive_phonemes(lts(ment_stem))
                            if stem_lts:
                                phones = [*stem_lts, "M", "AX", "N", "T"]
                    # ``-est`` superlative suffix: strip and append
                    # ``IX + S + T`` (``oldest`` -> ``' owlld ixs t``).
                    # Try plain stem, silent-e stem, and (for words
                    # like ``biggest`` -> ``BIG``) single-consonant
                    # stem after collapsing a doubled final consonant.
                    if (
                        phones is None and token.text.endswith("EST") and len(token.text) > 4  # noqa: PLR2004
                    ):
                        est_stem = token.text[:-3]
                        # Prefer the silent-e stem so magic-e superlatives
                        # recover their long vowel (``cutest`` -> CUTE not
                        # CUT, ``finest`` -> FINE not FIN), matching the
                        # ``-ed`` / ``-ing`` lookup order (issue #320).
                        stem_e_phones = lookup(est_stem + "E", lang=lang)
                        est_silent_e = stem_e_phones is not None
                        stem_phones = stem_e_phones or lookup(est_stem, lang=lang)
                        if (
                            stem_phones is None
                            and len(est_stem) >= 2  # noqa: PLR2004
                            and est_stem[-1] == est_stem[-2]
                        ):
                            stem_phones = lookup(est_stem[:-1], lang=lang)
                        # LTS fallback so out-of-lexicon superlatives get
                        # the C stem: silent-e magic-e (``bravest`` ->
                        # BRAVE, ``palest`` -> PALE) and doubled un-doubling
                        # (``fittest`` -> FIT). The suffix is always the
                        # C-faithful ``IX S T`` (issue #320).
                        if stem_phones is None and lts_fallback:
                            stem_phones = _lts_inflection_stem(est_stem, attach_e=True)
                        if stem_phones is not None:
                            stem_phones = _freeze_stem_weak_vowels(
                                stem_phones, silent_e=est_silent_e
                            )
                            phones = [*stem_phones, "IX", "S", "T"]
                    # ``-ing`` gerund / present-participle suffix: strip
                    # and append ``IX + NG`` (the standard ``-ing`` form).
                    if (
                        phones is None and token.text.endswith("ING") and len(token.text) > 4  # noqa: PLR2004
                    ):
                        ing_stem = token.text[:-3]
                        ing_silent_e = False
                        if homo_stem_reading is not None:
                            # Runtime homograph root (``winding`` →
                            # WIND): use the ls_homo_homo reading.
                            homo_root, homo_fc = homo_stem_reading
                            stem_phones = lookup(
                                homo_root, lang=lang, form_class=homo_fc
                            ) or lookup(homo_root, lang=lang)
                        else:
                            stem_e_phones = lookup(ing_stem + "E", lang=lang)
                            ing_silent_e = stem_e_phones is not None
                            stem_phones = stem_e_phones or lookup(ing_stem, lang=lang)
                        # Doubled-final-consonant stems re-derive the
                        # runtime-dictionary root via the ACTIVE
                        # ``l_us_suf.c`` ``-ing`` rule's un-doubling
                        # variants (``stopping`` -> STOP + IX NG,
                        # keeping the dictionary's AO vowel). The
                        # ``-ing`` rule's variant list has no ``rr``
                        # pair, so ``stirring``-type words never get a
                        # dictionary root -- they fall through to the
                        # C LTS engine's own un-doubling, mirrored by
                        # ``_lts_inflection_stem`` (issue #310).
                        if (
                            stem_phones is None
                            and suffix_root is not None
                            and suffix_rule_suffix == "ing"
                        ):
                            stem_phones = lookup(suffix_root, lang=lang)
                        if stem_phones is None and lts_fallback:
                            stem_phones = _lts_inflection_stem(ing_stem, attach_e=True)
                        if stem_phones is not None:
                            stem_phones = _freeze_stem_weak_vowels(
                                stem_phones, silent_e=ing_silent_e
                            )
                            phones = [*stem_phones, "IX", "NG"]
                            if (
                                not vpstart_emitted
                                and suffix_root is not None
                                and suffix_rule_suffix == "ing"
                                and emits_vpstart(formclass_lex.get(suffix_root, 0))
                            ):
                                phones.insert(0, f"{punct_prefix})")
                                vpstart_emitted = True
                    # ``-ed`` past-tense suffix: strip and apply the
                    # voicing+epenthesis rule:
                    #   stem ends in T / D   -> append IX + D
                    #   stem ends in voiceless -> append T
                    #   otherwise (voiced)   -> append D
                    if (
                        phones is None and token.text.endswith("ED") and len(token.text) > 2  # noqa: PLR2004
                    ):
                        # Try with and without the silent ``-e`` re-attached,
                        # then fall back to the Y -> I alternation
                        # (``married`` -> ``marry``).
                        ed_stem = token.text[:-2]
                        ed_silent_e = False
                        if homo_stem_reading is not None:
                            # Runtime homograph root (``contrasted`` →
                            # CONTRAST): use the ls_homo_homo reading.
                            homo_root, homo_fc = homo_stem_reading
                            stem_phones = lookup(
                                homo_root, lang=lang, form_class=homo_fc
                            ) or lookup(homo_root, lang=lang)
                        else:
                            stem_e_phones = lookup(ed_stem + "E", lang=lang)
                            ed_silent_e = stem_e_phones is not None
                            stem_phones = stem_e_phones or lookup(ed_stem, lang=lang)
                        if stem_phones is None and ed_stem.endswith("I"):
                            stem_phones = lookup(ed_stem[:-1] + "Y", lang=lang)
                            # Out-of-lexicon -y base (``pitied`` -> PITY,
                            # ``envied`` -> ENVY): render the -Y form so the
                            # mutated ``i`` reads as the base's /iy/ rather
                            # than the whole-word LTS /ay/ (issue #321).
                            if stem_phones is None and lts_fallback:
                                stem_phones = (
                                    _dedupe_consecutive_phonemes(lts(ed_stem[:-1] + "Y")) or None
                                )
                        # Doubled-final-consonant stems re-derive the
                        # runtime-dictionary root via the ACTIVE
                        # ``l_us_suf.c`` ``-ed`` rule's un-doubling
                        # variants (``stopped`` -> STOP + T, keeping
                        # the dictionary's AO vowel); roots outside
                        # the dictionaries fall through to the C LTS
                        # engine's behaviour -- un-doubling plus the
                        # silent-e letter context -- mirrored by
                        # ``_lts_inflection_stem`` (``grabbed`` ->
                        # GRAB + D, ``vraked`` -> V R EY K + T)
                        # (issue #310).
                        if (
                            stem_phones is None
                            and suffix_root is not None
                            and suffix_rule_suffix == "ed"
                        ):
                            stem_phones = lookup(suffix_root, lang=lang)
                        if stem_phones is None and lts_fallback:
                            stem_phones = _lts_inflection_stem(ed_stem, attach_e=True)
                        if stem_phones is not None:
                            stem_phones = _freeze_stem_weak_vowels(
                                stem_phones, silent_e=ed_silent_e
                            )
                            last_base = stem_phones[-1].rstrip("0123456789")
                            if last_base in ("T", "D"):
                                phones = [*stem_phones, "IX", "D"]
                            elif last_base in ("P", "K", "F", "S", "TH", "CH", "SH"):
                                phones = [*stem_phones, "T"]
                            else:
                                phones = [*stem_phones, "D"]
                            if (
                                not vpstart_emitted
                                and suffix_root is not None
                                and suffix_rule_suffix == "ed"
                                and emits_vpstart(formclass_lex.get(suffix_root, 0))
                            ):
                                phones.insert(0, f"{punct_prefix})")
                                vpstart_emitted = True
                    if phones is None:
                        if not lts_fallback:
                            raise UnknownWordError(
                                f"word {token.text!r} is not in the {lang} lexicon."
                            )
                        phones = lts(token.text)
                # Deduplicate consecutive identical phonemes: the LTS
                # produces doubled L's / N's / etc. for ``-LL``,
                # ``-NN`` clusters in spelling (e.g. "sells" -> S EH L
                # L S), but DECtalk's phoneme stream collapses them.
                phones = _dedupe_consecutive_phonemes(phones)
                # Word-final ``-s`` after a voiced consonant voices to
                # Z ("sells" / "dogs" / etc.). Gated on the word's
                # spelling so root-internal S ("course" / "horse")
                # stays voiceless; gated on whether we did stem-stripping
                # so a vowel-final ``YES`` (whole word in lexicon) stays
                # voiceless while a vowel-final ``DAYS`` (stem stripped)
                # voices to Z.
                phones = _voice_final_s_after_consonant(
                    phones, token.text, from_stem_strip=stem_stripped
                )
                flat.extend(phones)
            elif token.kind in (TokenKind.PAUSE_LONG, TokenKind.PAUSE_SHORT):
                ch = token.text or ("." if token.kind is TokenKind.PAUSE_LONG else ",")
                flat.append(_punct_marker(ch, sentence_has_wh=sentence_has_wh))
                if ch in ".!?":
                    # Sentence boundary: the C resets ``fc_index`` when
                    # ``wstate`` returns to UNK_WH, so the next word is
                    # "first word" again for homograph purposes.
                    word_fcs.clear()
    return encode_to_dectalk(flat)


def speak(
    text: str,
    *,
    rate: float = 1.0,
    voice: str | VoicePreset | None = None,
    lang: str = "us",
    lts_fallback: bool = True,
) -> NDArray[np.int16]:
    """Synthesize the given text into PCM samples.

    When the locally-built DECtalk C library is available **and** ``lang``
    is ``"us"``, the output is byte-identical (after WAV decode) to
    ``say -fo <path>`` from the DECtalk binary. Otherwise the approximate
    Python pipeline is used — intelligible output, not bit-parity.

    Args:
        text: Input string. May contain ``[:cmd value]`` directives.
        rate: Speaking-rate multiplier; 1.0 = 180 WPM (binary's default),
            2.0 = slower (90 WPM), 0.5 = faster (360 WPM). Clamped to
            DECtalk's [75, 600] WPM range when routed through ``_capi``.
            Inline ``[:rate N]`` directives in ``text`` are absolute WPM
            (see :func:`dectalk.cmd.commands._cmd_rate`) and combine
            multiplicatively with this argument.
        voice: Initial voice preset (short name like ``"paul"`` or a
            :class:`VoicePreset` object).
        lang: Language tag (``"us"`` is bit-parity via the C library;
            ``"uk"`` etc. go through the approximate Python pipeline).
        lts_fallback: Whether to fall back to rule-based letter-to-sound
            for words missing from the lexicon. Only consulted on the
            Python path; the C library always pronounces.

    Returns:
        ``int16`` PCM samples at 11025 Hz.
    """
    if lang == "us":
        wav_bytes = _speak_via_capi(text, rate, voice)
        if wav_bytes is not None:
            return _wav_bytes_to_int16(wav_bytes)
    return _speak_via_python(text, rate, voice, lang, lts_fallback)


def to_wav(
    text: str,
    path: str | Path,
    *,
    rate: float = 1.0,
    voice: str | VoicePreset | None = None,
    lang: str = "us",
    lts_fallback: bool = True,
) -> None:
    """Synthesize ``text`` and write the audio to a WAV file.

    When the C library is available and ``lang == "us"``, the raw WAV
    bytes produced by the C library are written directly — the output
    file is byte-identical to ``say -fo <path>`` from the DECtalk
    binary. Otherwise falls back to the Python pipeline via
    :func:`speak` plus :func:`dectalk.nt.audio.write_wav`.
    """
    if lang == "us":
        wav_bytes = _speak_via_capi(text, rate, voice)
        if wav_bytes is not None:
            Path(path).write_bytes(wav_bytes)
            return
    samples = _speak_via_python(text, rate, voice, lang, lts_fallback)
    write_wav(samples, path)


def available_voices() -> list[str]:
    """Return the list of available voice preset names."""
    return sorted(PRESETS.keys())


# ARPABET pronunciation of each English letter name — the same phoneme
# sequences DECtalk's spell-out path emits. Shared between the
# :func:`text_to_dectalk_phonemes` oracle path and the synth path's
# acronym spell-out so the two stay byte-aligned.
_LETTER_NAMES: dict[str, list[str]] = {
    "A": ["EY1"],
    "B": ["B", "IY1"],
    "C": ["S", "IY1"],
    "D": ["D", "IY1"],
    "E": ["IY1"],
    "F": ["EH1", "F"],
    "G": ["JH", "IY1"],
    "H": ["EY1", "CH"],
    "I": ["AY1"],
    "J": ["JH", "EY1"],
    "K": ["K", "EY1"],
    "L": ["EH1", "L"],
    "M": ["EH1", "M"],
    "N": ["EH1", "N"],
    "O": ["OW1"],
    "P": ["P", "IY1"],
    "Q": ["K", "Y", "UW1"],
    "R": ["AA1", "R"],
    "S": ["EH1", "S"],
    "T": ["T", "IY1"],
    "U": ["Y", "UW1"],
    "V": ["V", "IY1"],
    "W": ["D", "AH1", "B", "AH0", "L", "Y", "UW1"],
    "X": ["EH1", "K", "S"],
    "Y": ["W", "AY1"],
    "Z": ["Z", "IY1"],
}

# An all-caps WORD is a spell-out candidate only at these lengths
# (matches ``ls_spel_say_it`` / :func:`dectalk.lts.spell_or_say.say_it`).
_MIN_SPELL_LEN: Final[int] = 2
_MAX_SPELL_LEN: Final[int] = 4


def _acronym_spell_out_words(text: str) -> set[str]:
    """Return the upper-cased WORD tokens in ``text`` that must be spelled out.

    Mirrors the tokenisation-time decision in
    :func:`text_to_dectalk_phonemes` (the LTS+dic oracle path): a
    whitespace chunk whose alphabetic core is all-upper-case and 2-4
    letters long is a spell-out candidate, and
    :func:`dectalk.lts.spell_or_say.say_it` decides spell-vs-speak
    (``False`` -> spell). The returned set is keyed by the upper-cased
    core, which equals the token text the kernel tokenizer emits (it
    upper-cases every word), so the synth path can test
    ``token.text in spell_out`` directly.

    The case test is done on the *original* text, before the tokenizer
    folds case, so a genuinely lower-case word like ``"bus"`` is never
    spelled even though its folded form (``"BUS"``) is a 3-letter token.
    """
    from dectalk.lts.spell_or_say import say_it  # noqa: PLC0415

    spell_out: set[str] = set()
    for chunk in text.split():
        inner = chunk
        # Strip surrounding non-alphanumeric punctuation, mirroring the
        # kernel tokenizer (and the text_to_dectalk_phonemes pre-pass).
        while inner and not inner[0].isalnum() and inner[0] != "$":
            inner = inner[1:]
        while inner and not inner[-1].isalnum():
            inner = inner[:-1]
        if (
            inner.isalpha()
            and inner.isupper()
            and _MIN_SPELL_LEN <= len(inner) <= _MAX_SPELL_LEN
            and not say_it(inner)
        ):
            spell_out.add(inner)
    return spell_out


def _spell_out_letters(word: str) -> list[str]:
    """Expand an acronym into the ARPABET letter-name phoneme stream.

    Each letter maps through :data:`_LETTER_NAMES`; unknown characters
    fall back to themselves so the stream never silently drops symbols.
    """
    phones: list[str] = []
    for letter in word:
        phones.extend(_LETTER_NAMES.get(letter, [letter]))
    return phones


def _tokens_to_phonemes(
    tokens: Iterable[Token],
    *,
    lang: str,
    lts_fallback: bool,
    spell_out: set[str] | None = None,
) -> list[str]:
    """Internal helper: flatten a token stream to ARPABET phonemes (approx. path).

    ``spell_out`` is the set of upper-cased acronym tokens to render
    letter-by-letter (from :func:`_acronym_spell_out_words`); WORD
    tokens in it bypass the lexicon/LTS lookup and emit their spelled
    letter names instead (so ``BBC`` -> "B-B-C", not the LTS reading
    ``['B', 'B', 'K']``).
    """
    phonemes: list[str] = []
    for token in tokens:
        if token.kind is TokenKind.WORD:
            if spell_out is not None and token.text in spell_out:
                phonemes.extend(_spell_out_letters(token.text))
                continue
            phones = lookup(token.text, lang=lang)
            if phones is None:
                if not lts_fallback:
                    raise UnknownWordError(f"word {token.text!r} is not in the {lang} lexicon.")
                phones = lts(token.text)
            phonemes.extend(phones)
        elif token.kind in (TokenKind.PAUSE_SHORT, TokenKind.PAUSE_LONG):
            phonemes.append("SIL")
    return phonemes


# Re-export the approximate-path symbols so existing imports still resolve.
__all__ = [
    "UnknownWordError",
    "available_voices",
    "speak",
    "synthesize_phonemes",
    "text_to_phonemes",
    "to_wav",
]
