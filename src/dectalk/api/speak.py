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
from collections.abc import Iterable
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
from dectalk.dic.markers import load_marker_lexicon, load_vpstart_words
from dectalk.kernel.text import Token, TokenKind, tokenize
from dectalk.lts import lts
from dectalk.lts.homo_disambig import HOMOGRAPH_FC_BITS, disambiguate
from dectalk.nt.audio import write_wav
from dectalk.ph.prosody import split_sentences
from dectalk.ph.sequencer import synthesize_phonemes

# Forward-declared imports for the experimental full pipeline. These
# names are only imported lazily inside _speak_via_python_full so the
# default import path stays cheap.
_FULL_PIPELINE_ENV: str = "DECTALK_FULL_PIPELINE"

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

# Default ``pKsd_t->vol_att`` value the C kernel sets at every full
# reset (``ttsapi.c`` lines 2050 / 6609: ``pKsd_t->vol_att = 100;``).
# ``int_volume_table[100] = 32767`` is Q15 unity within 1 LSB, so the
# default-volume post-scale in :func:`_pump_frames_to_samples` is a
# no-op. The constant lets the post-scale branch skip the (allocation +
# multiply + clip) work entirely when the caller hasn't changed
# volume — keeping the hot path zero-cost.
_DEFAULT_VOL_ATT_INDEX: int = 100

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


def _pump_frames_to_samples(  # pyright: ignore[reportUnusedFunction]
    frames: list[object],
    preset: VoicePreset | None,
    vol_att: int = 100,
) -> NDArray[np.int16]:
    """Pump a Klatt frame sequence through ``ll_synthesize`` to int16 PCM.

    Bridge between the (still-being-ported) ph_draw frame-emission stage
    and the bit-accurate hlsyn synthesizer. Each frame is one Klatt
    target; ``ll_synthesize`` consumes ``synth.spkr.UI`` samples per
    frame and writes int16 PCM to the output buffer.

    After synthesis, applies the per-clause ``vol_att`` post-scale
    matching ``vtm3.c`` line 1642 (``out = frac1mul(out, vol_att)``,
    a Q15 multiply with ``vol_att = int_volume_table[pKsd_t->vol_att]``).
    This is the post-synthesis hook the ``[:volume N]`` / ``[:vol set
    sp N]`` directives ultimately drive (per
    ``docs/vtm-divergence-audit.md`` §5). With the C kernel's default
    ``pKsd_t->vol_att = 100`` (``cm_copt.c`` line 2050,
    ``ttsapi.c`` line 6609) and ``int_volume_table[100] = 32767``
    the multiplier is ~Q15 unity (within 1 LSB), so the default-volume
    output is unchanged.

    Args:
        frames: Sequence of :class:`~dectalk.hlsyn.llsyn.LLFrame` (typed
            as ``object`` here to keep the import lazy; runtime type is
            checked by ``ll_synthesize``).
        preset: Voice preset for speaker selection; ``None`` uses the
            default neutral voice.
        vol_att: ``pKsd_t->vol_att`` index in ``[0, 140]`` (clamped to
            range per ``vtm3.c`` lines 515-518). Indexed into
            :data:`~dectalk.vtm.volume_table.int_volume_table` to get
            the Q15 post-scale. Defaults to ``100`` (the C kernel's
            initial value, unity-gain Q15).

    Returns:
        1-D int16 array, ``len(frames) * synth.spkr.UI`` samples long.
    """
    from dectalk.hlsyn.llsyn import LLFrame, LLSynth  # noqa: PLC0415
    from dectalk.hlsyn.synthesize import ll_synthesize  # noqa: PLC0415
    from dectalk.hlsyn.vowels import default_speaker  # noqa: PLC0415
    from dectalk.vtm.volume_table import int_volume_table  # noqa: PLC0415

    if not frames:
        return np.zeros(0, dtype=np.int16)

    spkr = preset.speaker if preset is not None else default_speaker()
    synth = LLSynth(spkr=spkr)
    samples_per_frame = synth.spkr.UI
    out = np.zeros(len(frames) * samples_per_frame, dtype=np.int16)
    for fi, frame in enumerate(frames):
        # ll_synthesize requires LLFrame; cast here at the boundary so
        # callers (ph_draw) don't need to import it themselves.
        ll_frame = frame if isinstance(frame, LLFrame) else LLFrame(**vars(frame))  # type: ignore[arg-type]
        ll_synthesize(synth, ll_frame, out[fi * samples_per_frame : (fi + 1) * samples_per_frame])

    # Per-clause vol_att post-scale (vtm3.c line 1642, applied to every
    # synthesised sample). Clamp to the table range (vtm3.c lines 515-518:
    # ``if (vol_att > 141) vol_att = 141; if (vol_att <= 0) vol_att = 0;``)
    # — note the table has 141 entries (indices 0..140), so we cap at 140.
    # ``int_volume_table[100]`` is the no-op default (~Q15 unity); skip
    # the multiply in that case to keep the default-volume path zero-
    # cost. ``100`` is the C kernel's default ``pKsd_t->vol_att`` value
    # (``ttsapi.c`` lines 2050 / 6609) — see the module-level
    # :data:`_DEFAULT_VOL_ATT_INDEX` constant below.
    vol_att_clamped = max(0, min(vol_att, len(int_volume_table) - 1))
    vol_mul = int_volume_table[vol_att_clamped]
    if vol_att_clamped != _DEFAULT_VOL_ATT_INDEX:
        # Q15 multiply: ``(out * vol_mul) >> 15``. Compute in int32 to avoid
        # overflow (worst case |out|=32768 * vol_mul=131071 ~= 2^32 fits in
        # int64 but we use int32 to mirror the C ``S32`` cast in frac1mul).
        scaled = (out.astype(np.int32) * vol_mul) >> 15
        # The C path clamps to [-16384, 16383] then ``<< 1`` (vtm3.c lines
        # 1643-1647). The hlsyn synth already emits the full int16 range
        # (no ``<< 1`` expansion needed because ``ll_synthesize``'s output
        # is end-stage), so the equivalent clamp is to the full int16
        # range after the scale.
        np.clip(scaled, -32768, 32767, out=scaled)
        out[:] = scaled.astype(np.int16)
    return out


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

    Gated behind ``DECTALK_FULL_PIPELINE=1``. Routes the input through
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
         ``phdraw`` and emitting one :class:`~dectalk.hlsyn.llsyn.LLFrame`
         per 6.4 ms tick.
      7. :func:`ll_synthesize` pumps frames to int16 PCM.

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

        if seg.state.phoneme_mode:
            # ``[:phoneme on]`` bodies are direct ARPABET; skip the
            # tokenize + LTS path. We could feed the full pipeline,
            # but the legacy ``synthesize_phonemes`` is the bit-
            # accurate-on-its-own-axis route here.
            phones = seg.body.split()
            if not phones:
                continue
            preset = _resolve_voice(seg_voice)
            chunks.append(
                synthesize_phonemes(
                    phones,
                    rate=seg.state.rate,
                    preset=preset,
                    question=False,
                )
            )
            continue

        # Split the segment body into individual sentences and render
        # each as its own declination clause (issue #218 COMMIT 2). The
        # C kernel processes one ``.`` / ``!`` / ``?`` terminated segment
        # per ``phclause()`` call, so each sentence gets a fresh F0
        # reset (phinton baseline), its own leading-silence prefix, and
        # its own sentence-final long pause -- whereas a single
        # ``_render_clause_full`` over the whole body renders them as one
        # continuous declination contour and collapses the inter-sentence
        # silence. Measured against the C oracle, concatenating the
        # per-sentence renders matches ``say -a`` to within ~1 frame
        # (``hello. world.``: C 21016 / Py-sum 20945). Comma / semicolon
        # clauses do NOT split here -- ``split_sentences`` only breaks on
        # sentence terminators, so a comma-only body like ``one, two,
        # three.`` stays a single clause (its internal pauses are handled
        # by the boundary-feature fix-up in ``_render_clause_full``).
        #
        # ``split_sentences`` returns the whole body unchanged as a single
        # element when there is no internal sentence terminator, so this
        # is byte-identical to the previous single-call path for ordinary
        # one-sentence prompts.
        sentences = split_sentences(seg.body)
        if not sentences:
            # Body with no speakable content (e.g. whitespace only):
            # fall back to rendering it directly so behaviour matches the
            # pre-split path for degenerate inputs.
            sentences = [(seg.body, False)]
        for sentence_text, _is_question in sentences:
            chunk = _render_clause_full(
                sentence_text,
                rate=seg.state.rate,
                voice=seg_voice,
                lang=lang,
                lts_fallback=lts_fallback,
            )
            if chunk.size:
                chunks.append(chunk)

    if not chunks:
        return np.zeros(0, dtype=np.int16)
    return np.concatenate(chunks)


def _render_clause_full(  # noqa: PLR0915 — orchestration is intrinsically long
    text: str,
    *,
    rate: float,
    voice: str | VoicePreset | None,
    lang: str,
    lts_fallback: bool,
) -> NDArray[np.int16]:
    """Render a single parser segment's body through the full PH pipeline.

    Pure ``[:cmd]``-free text. Called by :func:`_speak_via_python_full`
    once per :class:`~dectalk.cmd.Segment`.
    """
    from dectalk.kernel.ksd_t import KsdT  # noqa: PLC0415
    from dectalk.kernel.lang_codes import LANG_english  # noqa: PLC0415
    from dectalk.ph.dph_settar_st import DphSettarSt  # noqa: PLC0415
    from dectalk.ph.dph_t import DphT  # noqa: PLC0415
    from dectalk.ph.init_phclause import init_phclause  # noqa: PLC0415
    from dectalk.ph.init_timing import init_timing  # noqa: PLC0415
    from dectalk.ph.phsettar import phsettar  # noqa: PLC0415
    from dectalk.ph.tts_handle import TtsHandle  # noqa: PLC0415
    from dectalk.ph.us_phtiming import us_phtiming  # noqa: PLC0415
    from dectalk.ph.voice_definitions import spdefs_for_voice  # noqa: PLC0415

    voice_preset = _resolve_voice(voice)
    # Per-voice scalar table (Spdefs). Threading these through the
    # phinton / pht0draw scalars below removes the Paul-only literals
    # that used to live here (issue #164): non-Paul voices like Betty
    # (AS=35, HR=0, SR=20, AP=208, PR=240, QU=80) now get their
    # documented C voice-table values rather than Paul's defaults.
    spdefs = spdefs_for_voice(_voice_name_for_spdefs(voice))

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
    raw_phonemes = text_to_dectalk_phonemes(text, lang=lang, lts_fallback=lts_fallback)
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

    from dectalk.vtm.spd_chip import default_us_paul_spd  # noqa: PLC0415

    _us_paul_spd = default_us_paul_spd()

    p_dph_t = DphT()
    p_dph_t.dipspec = [0] * 256
    p_dph_t.parstochip = [0] * 64
    p_dph_t.last_lang = 0  # forces gettar to load tables on first call.
    p_dph_t.sprate = wpm
    # ``fnscale`` is the per-voice Q12 formant-frequency scaler loaded
    # from the speaker-definition table (vtm_i.c line 625 reads it from
    # SPD_CHIP.fnscale). Load it from the US-Paul defaults so the value
    # is tied to the canonical voice-table source rather than a bare
    # literal. For Paul, fnscale = 4096 (Q12 unity, HS = 100 = nominal
    # head size), so phdraw's ``frac4mul(F_n, fnscale) + complement_n``
    # reduces to the identity and the formant trajectory flows through
    # unchanged. Without this seed, fnscale stays 0 and every formant
    # collapses to ``(4096 - 0) >> N`` regardless of the per-phone target.
    p_dph_t.fnscale = _us_paul_spd.fnscale
    # malfem: 1=MALE, 0=FEMALE. The C kernel loads it from the SPD_CHIP
    # source-section (vtm-side struct) but the value mirrors the
    # public-side ``Spdefs.sex`` field — both are derived from the same
    # SEX entry in the voice-definition row. We keep the SPD_CHIP load
    # here (it's the canonical vtm seed) and assert/observe the
    # equivalent on Spdefs in the parity tests.
    p_dph_t.malfem = _us_paul_spd.sex
    # F0 parameters derived from speaker definition (ph_vset.c lines 610-619).
    # f0_lp_filter = 1500 + 15 * QU       (QU = quickness, % of max)
    # f0minimum   = (AP - 12) * 10        (AP = average pitch, Hz)
    # f0scalefac  = PR * 41               (PR = pitch range, %)
    # All three now thread through the per-voice :class:`Spdefs` so
    # non-Paul voices pick up their documented C voice-table scalars.
    p_dph_t.f0_lp_filter = 1500 + 15 * spdefs.quickness
    p_dph_t.f0minimum = (spdefs.average_pitch - 12) * 10
    p_dph_t.f0scalefac = spdefs.pitch_range * 41
    # Hat-rise / stress-rise scalars. ``phinton`` Rule 1 (ph_inton.c
    # line 376) reads ``pDph_t->size_hat_rise`` for the hat-pattern F0
    # rise amplitude; Rule 2 (line 459) scales the stress-impulse height
    # by ``pDph_t->scale_str_rise``. Both are direct copies of the SPDEF
    # ``HR`` and ``SR`` fields (per-voice row in ``p_us_vdf_dectalk43.c``
    # -- Paul: HR=18, SR=32; Betty: HR=0, SR=20; Harry: HR=20, SR=30;
    # Frank: HR=20, SR=22). Without these the per-frame OUT_T0 clamps
    # at f0minimum +/- flutter (issue #94 / #122 F0 contour follow-up).
    p_dph_t.size_hat_rise = spdefs.hat_rise
    p_dph_t.scale_str_rise = spdefs.stress_rise
    # Assertiveness: SPD AS (final F0-fall, % of full fall) scaled to the
    # Q12-style multiplier ``phinton`` Rules 3/4/6 pass to ``frac4mul`` on
    # the rule's f0fall / targf0 magnitude. The C bridge in ``phram.c``
    # derives it as ``pDph_t->assertiveness = pDph_t->curspdef[SPD_AS] * 41``
    # — so AS = 100 (Paul's default) becomes 4100, just above Q12 unity
    # (4096) for a full final fall. Without this seed the field stays 0
    # and the ``frac4mul(*, 0)`` calls in ``phinton.py`` lines 514/611/650
    # zero out every Rule 3/4/6 final-fall target — visible in traces as
    # ``tar=0`` for every Rule 6 event (issue #122 / F0 contour follow-up).
    p_dph_t.assertiveness = spdefs.assertiveness * 41
    # Speaker-tuning scalars consulted by ``phdraw``'s per-frame
    # bandwidth computations. C's ``ph_vset.c`` (lines 607-630) loads
    # these from ``curspdef[]`` once per voice change; without the seeds
    # the breathy-voice B1 modifier ``frac4mul(B1, 0)`` zeros OUT_B1 on
    # every frame (issue #148 / frame-parity audit §2). ``f0_dep_tilt``
    # feeds the source-spectral-tilt formula in ``phdraw``: on the US
    # build (HLSYN / CHANGES_AFTER_V43 undefined) the active branch at
    # ``ph_draw.c`` lines 617-742 computes ``OUT_TLT`` as
    # ``(12 - frac4mul(1400 - f0, f0_dep_tilt)) + (spdeftltoff - 6)``
    # clamped to [0, 31] (issue #226). ``spdeftltoff`` is left at the
    # DphT default of 0 because Paul's ``SM`` (smoothness) is 0, and C's
    # ``ph_vset.c`` line 625 computes ``spdeftltoff = (SM * 25) / 100``.
    # Paul's ``paul_8`` SPDEF row in ``p_us_vdf1.c`` lines 126/150 supplies:
    #
    # - ``FT = 73`` → ``f0_dep_tilt = 73`` (Q12-style multiplier on the
    #   ``(1400 - f0)`` tilt-vs-f0 slope; the ``(f0 - 900)`` MALE variant
    #   at ``ph_draw.c`` lines 640-643 is ``#if HLSYN||CHANGES_AFTER_V43``
    #   dead on this build).
    # - ``BR = 0`` → ``spdefb1off = (0*0)>>1 + 4096 = 4096`` (Q12 unity;
    #   ``ph_draw.c`` line 417 multiplies parstochip[OUT_B1] by this so
    #   any non-unity value scales the first-formant bandwidth — at 4096
    #   it's a passthrough, at 0 it zeros B1).
    p_dph_t.f0_dep_tilt = 73  # FT for Paul (p_us_vdf1.c line 150)
    p_dph_t.spdefb1off = 4096  # BR=0 for Paul → (0*0)>>1 + 4096 (ph_vset.c line 629)
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

    # 4. Per-clause init -- MUST run before the phalloph2 chain
    # because :func:`init_phclause` zeroes / sizes the per-clause
    # arrays (``allophons`` / ``allofeats`` / ``allodurs`` / ``f0tar``
    # / ``f0tim``). The phalloph2 chain then writes through those
    # arrays as it walks the symbol stream.
    init_phclause(p_dph_t)

    # 4a. Run the byte-exact ``phsort + us_phalloph`` chain. Decodes the
    # DECtalk ASCII stream from step 1 into the packed ``symbols[]`` array
    # and runs:
    #
    #   - ``all_phsort`` (``ph_sort.c`` lines 428-1712) -- walks the
    #     symbol stream emitting ``phonemes[]`` / ``sentstruc[]`` with the
    #     full per-phone feature word.
    #   - ``us_phalloph`` (``ph_aloph1.c`` lines 444-1546) -- applies the
    #     US-English allophonic-substitution rules and writes through to
    #     ``allophons[]`` / ``allofeats[]`` (setting ``nallotot``),
    #     including the leading-silence prefix and trailing-PERIOD silence
    #     pad (``ph_task.c`` lines 437-439).
    #
    # Because ``raw_phonemes`` already carries the C kernel's punctuation /
    # phrase / boundary markers (``COMMA`` / ``PERIOD`` / ``QUEST`` /
    # ``EXCLAIM`` / ``VPSTART`` / ``MBOUND`` / …), ``all_phsort`` emits the
    # internal + trailing ``GEN_SIL`` phones and sets the ``FSENTENDS`` /
    # clause-boundary features itself — exactly as it does for the C
    # kernel's own ``symbols[]`` stream. The hand-rolled boundary-feature
    # fix-ups this function used to need (the former issue #72 / #218
    # ``nallotot-2`` and internal-``GEN_SIL`` passes) are therefore gone:
    # the markers do it natively. A clause-final ``!`` arrives as an
    # ``EXCLAIM`` marker, still driving ``all_phsort``'s
    # ``raise_last_stress`` hook (issue #212); a yes/no ``?`` arrives as a
    # ``QUEST`` marker, still setting the question clausetype ``phinton``
    # reads for rising intonation. Both are encoded in the stream, so no
    # separate sentence-type flag is needed.
    from dectalk.ph.us_phalloph2 import phalloph2_from_dectalk  # noqa: PLC0415

    phalloph2_from_dectalk(handle, raw_phonemes)

    # 4a-ter. Per-clause pause-length defaults from ``phclause()``
    # lines 247-255 of ``ph_claus.c`` (English branch). These are
    # consulted by ``us_phtiming``'s Rule 1 when computing the
    # GEN_SIL ``dpause`` value (``nfperiod + perpause + asperation``
    # for sentence-end, ``nfcomma + compause + asperation`` for
    # comma-end). Without them the trailing SIL gets the default
    # 15-frame minimum and the Python output is ~360 ms shorter than
    # the C reference (issue #72 trailing-silence pad gap).
    #
    # The English ``nfperiod`` value is gated by
    # ``#if defined(HLSYN) || defined(CHANGES_AFTER_V43)``:
    # 94 with HLSYN, **75** without. The shipped Linux
    # ``libtts_us.so`` builds with neither macro defined (see
    # ``dectalkf_klsyn.h`` line 116-118: ``HLSYN`` is gated behind
    # ``EPSON_ARM7``), so the active default is 75 (issue #155).
    p_dph_t.nfperiod = 75
    p_dph_t.nfcomma = 16

    init_timing(
        p_dph_t,
        settar,
        sprate_ref=[wpm],
        lang_curr=LANG_english,
    )

    # 4b. Per-allophone duration rules (us_phtiming). Walks the clause
    # applying the 26 named duration rules and writing per-phone frame
    # durations into pDph_t.allodurs. Must run AFTER init_timing (which
    # seeds sprat0/sprat1/sprat2) and BEFORE the per-frame loop below
    # (which needs durfon = allodurs[nphone] for its target/transition
    # math and frame-advance bookkeeping).
    us_phtiming(handle)

    # 5. phinton: F0 contour generation, ONCE per clause before the
    # per-frame loop. Walks the allophone stream firing pitch events
    # (hat-rise / stress impulses / comma+question gestures /
    # continuation rises / baseline reset / dummy schwa). Writes
    # f0tar / f0type / f0length / f0tim on DphT.
    from dectalk.ph.init_clause import init_clause  # noqa: PLC0415
    from dectalk.ph.param_indices import OUT_DU, OUT_PH, OUT_PH2  # noqa: PLC0415
    from dectalk.ph.parstochip_to_frames import (  # noqa: PLC0415
        parstochip_to_llframe_delayed,
    )
    from dectalk.ph.phdraw import phdraw  # noqa: PLC0415
    from dectalk.ph.phinton import phinton  # noqa: PLC0415
    from dectalk.ph.pht0draw import pht0draw  # noqa: PLC0415

    # init_clause sets nf0ev=-2 (hard init) so pht0draw's first call
    # performs a full hard+soft initialisation — matching ph_claus.c.
    init_clause(p_dph_t)

    phinton(handle)

    # 6. Per-frame driver loop -- mirrors ph_claus.c's phclause while-
    # loop (lines 367-505). For each 6.4 ms frame:
    #
    #   * Increment tcum. If it has passed the current allophone's
    #     duration, advance ``nphone`` (returning when allophones run
    #     out), reset ``tcum``, set ``durfon`` from ``allodurs``, and
    #     re-run phsettar for the new allophone.
    #   * Call pht0draw to generate the F0 contour for this frame,
    #     writing ``parstochip[OUT_T0]``.
    #   * Call phdraw to update ``parstochip[]`` for this frame.
    #   * Convert ``parstochip[]`` to an LLFrame and append.
    #
    # The first iteration enters the "advance" branch (tcum starts at
    # -1, durfon at 0), so phsettar gets called for nphone=0 inside
    # the loop -- matching the C init_pars() setup.
    p_dph_t.tcum = -1
    p_dph_t.nphone = -1
    p_dph_t.durfon = 0
    frames: list[object] = []
    # Also accumulate raw parstochip snapshots so the alternative vtm1
    # synth path (issue #158) can pump them through
    # ``speech_waveform_generator`` without re-running the PH stage.
    # Only used when ``DECTALK_USE_VTM1=1`` is set; the conversion
    # itself is cheap (list copy), so we always populate.
    parstochip_frames: list[list[int]] = []
    # Cap the loop to keep buggy state from running away during the
    # multi-month port. 8000 frames is ~51 s of audio -- well past
    # any reasonable clause.
    max_frames = 8000
    # One-frame-delay buffer mirroring ph_claus.c's ``delaypars[]``
    # (lines 706-820). Holds the previous frame's parstochip so the
    # F1/B1/F2/B2/F3/B3/FZ/A2..A6/AB/AP slots of the *emitted*
    # LLFrame come from one frame ago, while AV / TL / T0 come from
    # the current frame.
    previous_parstochip: list[int] | None = None
    # ``ph_claus.c::send_pars`` (lines 706-781) implements the one-
    # frame delay by allocating ``delaypars[]`` on its first call and
    # ONLY initialising it (TLT=T0=AV=0) — it does NOT spcwrite that
    # first frame. The synthesizer only receives the delayed buffer
    # on the SECOND call onwards. The Python loop therefore must
    # also discard the first iteration's frame: it represents the
    # synth-side delay-buffer fill, not an emitted PCM frame
    # (issue #157 leading-frame bleed -- removes 1 LLSynth-frame of
    # leading silence per prompt, ~110 samples at 11025 Hz).
    first_frame_consumed = False
    # ``phinton`` may insert a dummy schwa (ph_inton2.c lines 1685-1725)
    # which increments ``p_dph_t.nallotot``. Read it from state inside
    # the loop so the per-frame driver walks the FINAL allophone array
    # length, not the pre-phinton snapshot captured above. Without this
    # the trailing GEN_SIL is silently skipped and the clause ends one
    # allophone short, dropping the long-pause trailing silence (#72).
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
            # Phoneme-code / duration metadata writes from ph_claus.c
            # lines 465-472 (BATS 887, eab 5/3/99 — output from the
            # correct place so SAPI / debug time-alignment is correct).
            # These cells are consumed by debug / instrumentation
            # readers (frame dumps), not by the Klatt synthesiser
            # itself; LLFrame has no corresponding fields so the
            # parstochip → LLFrame adapter drops them. Writing them
            # here keeps frame-dump parity with the C binary.
            p_dph_t.parstochip[OUT_PH] = p_dph_t.allophons[p_dph_t.nphone]
            p_dph_t.parstochip[OUT_DU] = p_dph_t.allodurs[p_dph_t.nphone]
            if p_dph_t.nphone + 1 > p_dph_t.nallotot:
                p_dph_t.parstochip[OUT_PH2] = 0
            else:
                p_dph_t.parstochip[OUT_PH2] = p_dph_t.allophons[p_dph_t.nphone + 1]
            phsettar(handle)
        pht0draw(handle)
        phdraw(handle)
        if first_frame_consumed:
            frames.append(
                parstochip_to_llframe_delayed(p_dph_t.parstochip, previous_parstochip, _us_paul_spd)
            )
            parstochip_frames.append(list(p_dph_t.parstochip))
        else:
            # First iteration: matches C's send_pars initpardelay==0
            # branch, which only seeds delaypars and skips the
            # spcwrite. The synthesizer never sees this frame.
            first_frame_consumed = True
        previous_parstochip = list(p_dph_t.parstochip)

    # 7. Pump the collected Klatt frames through the synthesizer for
    # int16 PCM output. By default this routes through the hlsyn
    # SenSyn 2.2 cascade-parallel synth (the existing
    # bit-accurate path). When ``DECTALK_USE_VTM1=1`` is set, frames
    # are pumped through the alternative ``speech_waveform_generator``
    # (vtm1.c) path -- the same synthesiser the shipped
    # ``libtts_us.so`` uses (issue #158).
    if os.environ.get("DECTALK_USE_VTM1") == "1":
        from dectalk.vtm.pump_frames import pump_frames_via_vtm1  # noqa: PLC0415

        return pump_frames_via_vtm1(list(parstochip_frames), voice_preset)
    return _pump_frames_to_samples(frames, voice_preset, p_ksd_t.vol_att)


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
    """Approximate-Python audio pipeline (pre-Phase-B implementation).

    When ``DECTALK_FULL_PIPELINE=1`` is set, dispatches to the
    work-in-progress :func:`_speak_via_python_full` that calls the
    real translated PH modules. Otherwise falls back to the legacy
    approximate path (parse -> tokenize -> LTS -> sequencer) used
    for languages other than US English and when the C library is
    unavailable.

    Used as the fallback when the C library isn't available, and for
    languages other than US English. Output is intelligible but not
    byte-identical to the DECtalk binary.

    The output is wrapped with leading + trailing silence pads matching
    the C reference's per-utterance envelope (issue #201). The
    approximate phoneme sequencer renders only the audible phoneme
    contents, so without these pads every prompt under-ran the C
    reference by ~4000 samples (the missing trailing pause). The pad
    sizes mirror the C kernel's ``nfperiod`` / leading-onset behaviour
    on the 15-prompt parity corpus.
    """
    if os.environ.get(_FULL_PIPELINE_ENV) == "1":
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

        if seg.state.phoneme_mode:
            phones = seg.body.split()
            if phones:
                chunks.append(
                    synthesize_phonemes(
                        phones,
                        rate=seg.state.rate,
                        preset=preset,
                        question=False,
                    )
                )
            continue

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
    from dectalk.dic.dectalk_phonemes import encode_to_dectalk  # noqa: PLC0415

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
            "PUTS",
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
        # Title-abbreviation sentinels (see ``title_abbrevs`` below).
        # ``Dr.`` reads as ``d aak t rr`` (unstressed AA + K + T + ER)
        # -- subtly different from the spelled-out word "doctor" which
        # would be ``d ' aok t rr`` (stressed AO + K + T + ER). The
        # other title forms aren't currently in the parity corpus but
        # are filled in for completeness.
        "__TITLE_DR__": ["D", "AA0", "K", "T", "ER0"],
        "__TITLE_MR__": ["M", "IH1", "S", "T", "ER0"],
        "__TITLE_MRS__": ["M", "IH1", "S", "IX", "Z"],
        "__TITLE_MS__": ["M", "IH1", "Z"],
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
        if seg.state.phoneme_mode:
            # ``[:phoneme on]`` body is already a phoneme stream; skip
            # the LTS path entirely.
            continue
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
        # Tokenize with C-faithful digit-string handling: for each
        # whitespace-delimited chunk, if (after stripping surrounding
        # punctuation) it's a pure digit-string or dotted decimal,
        # route through ``_digit_expand`` -- otherwise let
        # ``kernel.text.tokenize`` handle it.
        tokens: list[Token] = []
        for chunk in seg.body.split():
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
            _ = leading  # leading-punct ignored (matches tokenize)
            if inner and _digits_strict.match(inner):
                tokens.extend(_digit_expand(int(inner.replace(",", ""))))
            elif inner and _dotted.match(inner):
                parts = inner.split(".")
                for i_part, part in enumerate(parts):
                    if i_part > 0:
                        tokens.append(Token(TokenKind.WORD, "POINT"))
                    for w in number_to_words(int(part.replace(",", ""))):
                        tokens.append(Token(TokenKind.WORD, w))
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
        # Pre-pass B: expand ``Dr.`` -> ``DOCTOR`` / ``Mr.`` -> ``MISTER``
        # / ``Mrs.`` -> ``MISSUS`` etc. when the abbreviation is
        # followed by a name (PAUSE_LONG '.' + WORD pattern). DECtalk's
        # tokenizer does this; ours doesn't, so the abbreviation leaked
        # through as a spelled-out word.
        # Title abbreviation -> a sentinel word that lands in
        # ``word_phoneme_overrides`` with the title-specific phoneme
        # form ("Dr." reads ``d aak t rr``, slightly different from the
        # spelled-out "doctor" which is ``d ' aok t rr``).
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
        for tok_idx, token in enumerate(tokens):
            if token.kind is TokenKind.WORD:
                # Only insert an inter-word break if there's no
                # punctuation marker just before -- the C source's
                # punctuation emit (``, `` / ``. `` / ``! `` /
                # ``? ``) already carries its own trailing space.
                if flat and not flat[-1].startswith(punct_prefix):
                    flat.append("_")
                if token.text in vpstart_words:
                    flat.append(f"{punct_prefix})")
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
                # First-verbs hack: at the start of a sentence/clause, six
                # auxiliary verbs (are/had/is/was/were/will) get secondary
                # stress applied through a fixed phoneme sequence.
                is_sentence_initial = all(t.kind is not TokenKind.WORD for t in tokens[:tok_idx])
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
                    # LTS audit §2). Words like RECORD / PRESENT / OBJECT
                    # ship two readings in the lexicon (``WORD|P`` and
                    # ``WORD|S``); pick the right one from context.
                    homo_fc: str | None = None
                    if token.text in HOMOGRAPH_FC_BITS:
                        prev_word_text: str | None = None
                        prev_prev_word_text: str | None = None
                        for back_tok in reversed(tokens[:tok_idx]):
                            if back_tok.kind is TokenKind.WORD:
                                if prev_word_text is None:
                                    prev_word_text = back_tok.text
                                else:
                                    prev_prev_word_text = back_tok.text
                                    break
                        homo_fc = disambiguate(
                            token.text,
                            prev_word=prev_word_text,
                            prev_prev_word=prev_prev_word_text,
                            is_sentence_initial=is_sentence_initial,
                        )
                    if homo_fc is not None:
                        phones = lookup(token.text, lang=lang, form_class=homo_fc)
                        # Fall back to the default reading if the
                        # specific form-class entry isn't present (e.g.
                        # an N-only homograph that doesn't ship P/S).
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
                            base_phones = _dedupe_consecutive_phonemes(lts(base))
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
                        if stem.endswith("E") and len(stem) > 2:  # noqa: PLR2004
                            # ``minutes`` -> ``minute`` (drop the trailing
                            # E along with the S so we hit the stem entry).
                            stem_phones = lookup(stem, lang=lang) or lookup(stem[:-1], lang=lang)
                        else:
                            stem_phones = lookup(stem, lang=lang)
                        # ``cities`` -> ``citie`` (lookup fails) -> ``city``
                        # via the Y -> I orthographic alternation.
                        if stem_phones is None and len(stem) > 1 and stem.endswith("IE"):
                            stem_phones = lookup(stem[:-2] + "Y", lang=lang)
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
                            ltstem = stem
                            if ltstem.endswith("E"):
                                ltstem = ltstem[:-1]
                            stem_phones = _dedupe_consecutive_phonemes(lts(ltstem))
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
                        stem_phones = lookup(stem + "E", lang=lang) or lookup(stem, lang=lang)
                        if stem_phones is not None:
                            phones = [*stem_phones, "ER0"]
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
                            stem_phones = _dedupe_consecutive_phonemes(lts(tion_stem))
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
                            stem_phones = _dedupe_consecutive_phonemes(lts(ive_stem))
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
                        stem_phones = lookup(est_stem, lang=lang) or lookup(
                            est_stem + "E", lang=lang
                        )
                        if (
                            stem_phones is None
                            and len(est_stem) >= 2  # noqa: PLR2004
                            and est_stem[-1] == est_stem[-2]
                        ):
                            stem_phones = lookup(est_stem[:-1], lang=lang)
                        if stem_phones is not None:
                            phones = [*stem_phones, "IX", "S", "T"]
                    # ``-ing`` gerund / present-participle suffix: strip
                    # and append ``IX + NG`` (the standard ``-ing`` form).
                    if (
                        phones is None and token.text.endswith("ING") and len(token.text) > 4  # noqa: PLR2004
                    ):
                        ing_stem = token.text[:-3]
                        stem_phones = lookup(ing_stem + "E", lang=lang) or lookup(
                            ing_stem, lang=lang
                        )
                        if stem_phones is not None:
                            phones = [*stem_phones, "IX", "NG"]
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
                        stem_phones = lookup(ed_stem + "E", lang=lang) or lookup(ed_stem, lang=lang)
                        if stem_phones is None and ed_stem.endswith("I"):
                            stem_phones = lookup(ed_stem[:-1] + "Y", lang=lang)
                        if stem_phones is not None:
                            last_base = stem_phones[-1].rstrip("0123456789")
                            if last_base in ("T", "D"):
                                phones = [*stem_phones, "IX", "D"]
                            elif last_base in ("P", "K", "F", "S", "TH", "CH", "SH"):
                                phones = [*stem_phones, "T"]
                            else:
                                phones = [*stem_phones, "D"]
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
