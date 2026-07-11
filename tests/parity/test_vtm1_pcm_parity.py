"""Parity test: FULL-pipeline vtm1 PCM output vs the C oracle WAV.

Acceptance test for issue #158 — verifies the vtm1 synth path (the
only FULL-pipeline render since the #279 retirement) produces audio
that matches the C oracle's WAV output for a small
set of representative prompts.

**Current status (Phase E rollout, issue #297)**: 348/500 of the
stratified corpus sample renders **byte-identical** from pure Python
on the FULL+VTM1 path. This file holds three tiers of gate:

1. Smoke: the vtm1 path produces *some* int16 PCM for the prompts.
2. Sample-count exactness on the #270 audit set (wide-tolerance
   length checks retained for the legacy smoke prompts).
3. **Byte-identical WAV equality** on ``_BYTE_EXACT_PROMPTS`` — a
   hard pass since #297, one pinned prompt group per fixed
   divergence cluster.

Skips cleanly when the C oracle artefacts are missing.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
import pytest

from dectalk.api.speak import _speak_via_python_full

_DECTALK_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_DECTALK_BIN = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _have_artefacts() -> bool:
    """True when both the source-built libtts and the shipped binary exist."""
    has_src = any(_DECTALK_SRC.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so"))
    has_bin = (_DECTALK_BIN / "say").is_file() and (_DECTALK_BIN / "DECtalk.conf").is_file()
    return has_src and has_bin


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not _have_artefacts(),
        reason="locally-built libtts or shipped DECtalk binary not present",
    ),
]


# Small corpus the PH stage handles well today. Longer / inflected
# prompts diverge more (the PH timing port is incomplete).
_PROMPTS: tuple[str, ...] = ("hi", "hello", "test")


def _binary_pcm_int16(text: str) -> np.ndarray:
    """Render ``text`` via the shipped binary and return int16 PCM samples."""
    with tempfile.TemporaryDirectory() as td:
        wav_path = Path(td) / "ref.wav"
        subprocess.run(
            [str(_DECTALK_BIN / "say"), "-a", text, "-fo", str(wav_path)],
            cwd=str(_DECTALK_BIN),
            check=True,
            capture_output=True,
        )
        with wave.open(str(wav_path), "rb") as fh:
            raw = fh.readframes(fh.getnframes())
    return np.frombuffer(raw, dtype=np.int16)


def _python_vtm1_pcm(text: str, monkeypatch: pytest.MonkeyPatch) -> np.ndarray:
    """Render ``text`` via the Python FULL-pipeline (vtm1) path."""
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")
    return _speak_via_python_full(text, 1.0, None, "us", True)


@pytest.mark.parametrize("text", _PROMPTS)
def test_vtm1_produces_nontrivial_pcm(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The vtm1 synth path produces non-empty int16 audio for the prompt."""
    samples = _python_vtm1_pcm(text, monkeypatch)
    assert samples.dtype == np.int16
    assert samples.size > 0, f"vtm1 path produced zero samples for {text!r}"
    assert np.any(samples != 0), f"vtm1 path produced all-zero samples for {text!r}"


@pytest.mark.parametrize("text", _PROMPTS)
def test_vtm1_pcm_length_within_tolerance(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python vtm1 PCM length is within a wide tolerance of the C oracle.

    Until the PH timing layer ports (Phase E), exact length parity is
    not expected. This test enforces a 50% length tolerance to catch
    egregious regressions (e.g. the path producing zero or 100x output).
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size > 0
    assert ref.size > 0
    ratio = py.size / ref.size
    assert 0.5 <= ratio <= 2.0, (
        f"vtm1 PCM length {py.size} vs C oracle {ref.size} (ratio {ratio:.2f}) "
        f"outside the 50% tolerance — likely a wiring regression"
    )


# Prompts whose FULL+VTM1 sample count is exactly the C oracle's after
# the #270 timing fixes (sole-secondary lexicon stress alignment,
# per-clause phclause segmentation, HLSYN-only WBOUND step-past
# removal). Byte-level content still diverges (Phase E frame-content
# work), but the per-allophone durations — and therefore the total
# sample count — are phone-for-phone equal to the oracle. Pinned as a
# hard gate so timing regressions surface immediately.
_COUNT_EXACT_PROMPTS: tuple[str, ...] = (
    "hello world",
    "testing one two three",
    "the quick brown fox",
    "a box of cats",
    "and then we left",
    "chairs, tables, lamps, and rugs",
)


@pytest.mark.parametrize("text", _COUNT_EXACT_PROMPTS)
def test_vtm1_pcm_sample_count_exact(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python FULL+VTM1 sample count equals the C oracle's exactly.

    Issue #270: the per-allophone durations on these prompts match the
    oracle phone-for-phone (verified via the OUT_PH/OUT_DU cells of
    ``vtm_frames.dump``), so the emitted frame count — and the PCM
    sample count — must be identical. This is the timing-layer parity
    gate; byte equality remains tracked by the xfail test below.
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size == ref.size, (
        f"sample-count drift for {text!r}: Python {py.size} vs C {ref.size} "
        f"({(py.size - ref.size) / _SAMPLES_PER_FRAME:+.1f} frames)"
    )


# Prompts pinned BYTE-IDENTICAL to the oracle WAV on the FULL+VTM1
# path — the Phase E goal metric, held as a **hard** gate (issue #297;
# 348/500 of the corpus sample render byte-exact as of the #297 fixes).
# Each group pins a named divergence-cluster fix so a regression names
# its cluster directly:
#   - "hi" / "hello" / "test": the original #158 smoke prompts (were
#     xfail; flipped by the #283..#294 wave and promoted here).
#   - "hello world" / "the quick brown fox" / "chairs, tables, lamps,
#     and rugs": the #270 count-exact gate prompts, now byte-exact.
#   - "BBC" / "bite" / "stop!": the pht0draw OUT_PH/OUT_DU per-frame
#     overwrite (ph_drwt01.c:3021-3024) feeding the vtm1.c:1318
#     silence ramp-down gate — the #297 primary cluster (+115 prompts).
#   - "MRI" / "wait, he is honest": the live consonant→stressed-vowel
#     glottal branch in the active set_tglst (ph_drwt01.c:3118).
#   - "listen down" / "my dog is near the bedroom": primary-only
#     stress counting in remaining_stresses_til (ph_aloph1.c:1566)
#     placing the FHAT_ENDS hat fall on the last *primary* stress.
#   - "999" / "1234567890": the non-HLSYN all_phsort cleanup rules
#     (ph_sort.c 536-556 compound-destress + SPECIALWORD zap;
#     1234-1264 zap_weaker_bound) — the digit-expansion "hundred
#     WBOUND VPSTART and" boundary pair must merge to one VPSTART so
#     get_next_bound_type stamps FVPNEXT on the "-dred" phones
#     (issue #302 cluster 1; +144 byte-exact prompts on the
#     500-sample).
#   - "[:nr] rita rough" / "[:nw] wendy whispery" / "[:nk] kit the
#     kid": per-voice setspdef seeding (ph_vset.c 541-831 via
#     dectalk.ph.setspdef) + the [:nX] voice-name shortcuts in the
#     light command parser (issue #302 cluster 3).
#   - "we color the car pink": trailing-silence formant draw toward
#     the one-past-end allophons context — fixed by #303's
#     phonemes->allophons[SAFETY] alias replay (issue #302 cluster 2).
#   - "this book tells it" / "he must tell" / "the boy knows that it
#     is gone": the clause-final hat fall is the *else* of the
#     promote_last_2 test (ph_aloph1.c:1391-1452 preprocessed on
#     ENGLISH_US) — a promoted following secondary stress keeps the
#     hat up until that stress (issue #307 verb-form trio).
#   - "this is easy for Mary to rest" / "go to bed": modeflag boots
#     as MODE_CITATION (kernel/main.c:188), permanently disabling
#     phalloph's 'to'-flap rule (ph_aloph1.c:902-912) — issue #307.
#   - "hello! how are you?" / "wait... what just happened?" /
#     "well, no..." / "one. two. three.": one continuous
#     PH->send_pars->vtm1 stream per utterance — sentence-terminated
#     clauses share the delay pipeline / F0 declination / synth
#     state; ph_task's empty-clause suppression (nsymbtot > 1) drops
#     the "..." empty clause — issue #307.
#   - "a. b? c!" / "for. and? to!" / "a, for, and, to.": citation-mode
#     lane — the LTS/sdic ``^`` SPECIALWORD marker arms per-clause
#     ``docitation`` (ph_task.c:621), gating ph_aloph1.c's unreduce
#     rules ("a"->EY at 718, "for"->OR at 725, "to"->UW at 889) for
#     short clauses; cleared per clause at ph_claus.c:307 —
#     issue #309.
#   - "stopped" / "the rain stopped." / "she grabbed it" / "we
#     planned a trip" / "he admitted it": the -ed suffix on
#     doubled-final-consonant stems — the l_us_suf.c un-doubling
#     variants re-derive the runtime-dictionary root (STOP's AO
#     vowel, the devoiced T tail) and pure-verb roots emit the
#     root entry's ``)`` VPSTART marker (issue #310).
#   - "you & me" / "a = b" / "email me @ work" / "one# two": symbol
#     tokens (standalone and word-attached) speaking via their
#     Dic_us.txt rows, plus the primary-stressed single-letter
#     reading of "b" (issue #244).
#   - "Mr. Smith" / "Mrs. Brown called today." / "St. Paul is a
#     city." / "Prof. White teaches here.": title abbreviations via
#     the period-keyed runtime-dictionary rows (destressed mister /
#     missus) and the ls_task_Dr_St_process saint branch (issue #246).
#   - "[:comma 1000] a, b" / "[:period 2000] a. b" / "[:comma 45000]
#     a, b": the CPAUSE/PPAUSE user pause overrides threaded into
#     DphT.compause/perpause, including the 16-bit LTS-pipe wrap on
#     the unclamped comma value (45000 -> -20536 -> deadstop -280)
#     (issue #249).
_BYTE_EXACT_PROMPTS: tuple[str, ...] = (
    "hi",
    "hello",
    "test",
    "hello world",
    "the quick brown fox",
    "chairs, tables, lamps, and rugs",
    "BBC",
    "bite",
    "stop!",
    "MRI",
    "wait, he is honest",
    "listen down",
    "my dog is near the bedroom",
    "999",
    "1234567890",
    "[:nr] rita rough",
    "[:nw] wendy whispery",
    "[:nk] kit the kid",
    "we color the car pink",
    "this book tells it",
    "he must tell",
    "the boy knows that it is gone",
    "this is easy for Mary to rest",
    "go to bed",
    "hello! how are you?",
    "wait... what just happened?",
    "well, no...",
    "one. two. three.",
    "a. b? c!",
    "for. and? to!",
    "a, for, and, to.",
    "stopped",
    "the rain stopped.",
    "she grabbed it",
    "we planned a trip",
    "he admitted it",
    "you & me",
    "a = b",
    "email me @ work",
    "one# two",
    "Mr. Smith",
    "Mrs. Brown called today.",
    "St. Paul is a city.",
    "Prof. White teaches here.",
    "[:comma 1000] a, b",
    "[:period 2000] a. b",
    "[:comma 45000] a, b",
    # issue #225 — numeric-format expansion (ordinal / currency /
    # clock time / fraction / digit-dash range), each byte-verified
    # against the shipped binary before pinning.
    "42nd",
    "$1.50",
    "3:30",
    "12/25",
    "10-20",
    # issue #248: ``[:phoneme on]`` (and the asky/arpabet/off/silent
    # submatrix) is a state-only directive — it selects how ``[...]``
    # bracket blocks are read (``cm_pars.c:361``) and never turns the plain
    # segment body into phonemes, so a leading ``[:phoneme ...]`` speaks the
    # following text exactly like the bare prompt. (Mid-text ``[:phoneme]``
    # is deliberately NOT pinned: it splits the utterance into separately-
    # rendered segments and inherits the pre-existing multi-segment
    # over-run that also affects mid-text ``[:rate]`` — orthogonal to #248.)
    "[:phoneme on] hello",
    "[:phoneme off] hello",
    "[:phoneme arpabet on] hello",
    "[:phoneme asky on] hello",
    "[:phoneme silent] hello",
    "[:phoneme on] hello world",
    "[:phoneme on] the quick brown fox",
)


@pytest.mark.parametrize("text", _BYTE_EXACT_PROMPTS)
def test_vtm1_pcm_byte_identical_to_oracle(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python vtm1 PCM is byte-identical to the C oracle's WAV.

    Hard pass (no xfail) since issue #297: the pure-Python FULL+VTM1
    render is byte-identical on every prompt above. The vtm1
    synth-stage port itself is verified by
    ``test_vtm_speech_waveform_generator_parity`` and the synth-state
    seeding by ``test_vtm_pump_frames``; this asserts the whole
    PH-parameter + synth chain end to end.
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size == ref.size, f"length mismatch {py.size} vs {ref.size}"
    np.testing.assert_array_equal(py, ref)


# --- issue #315: spoken-punctuation-name lane -----------------------
# Punctuation-only input does NOT synthesize a silence clause: the C
# cmd stage forwards an isolated mark as its own one-char word and the
# LTS spells it through the language typing table (``usa_type.tab``),
# so the binary SPEAKS the mark's name — bare ``...`` renders the
# 182-frame "period" clause, not ~1 frame. Rules pinned here (each
# verified byte-exact vs the shipped binary):
#   - punctuation-only input speaks the name: ``...``/``.`` ->
#     "period", ``!`` -> "exclamation point", ``?`` -> "question
#     mark", ``,`` -> "comma", ``;`` -> "semi#colon", ``:`` -> "colon";
#   - ``..`` is the LTS word ``.`` + attached ``.`` right-punct
#     ("period." — same WAV as ``...`` whose utterance-final PERIOD
#     comes from the ph_task flush instead);
#   - isolated multi-dot runs after a word speak the name too
#     (``hello ...`` / ``text with trailing ...``), while a SINGLE
#     isolated mark after a word attaches as the ordinary marker
#     (``hello .`` / ``one . two`` — cm_text.c rev 074 space removal);
#   - a name closes the clause, so marks after a name are spoken by
#     name as well (``... !`` / ``... , hello``).
# Deliberately NOT pinned (pre-existing divergence, out of #315's
# scope): shapes where the say binary's char-stream feed disagrees
# with the C library's own single-buffer path — ``. hello`` (say takes
# the cm_util_sendat ``pcnt==1`` branch and speaks "dot"), ``. .``,
# ``... .``, ``. . .``, and 5+ dot runs (a cm_pars buffer bug
# degenerates them to a lone ``t`` word).
_PUNCT_NAME_BYTE_EXACT_PROMPTS: tuple[str, ...] = (
    "...",
    ".",
    "!",
    "?",
    "..",
    "....",
    "... ...",
    "text with trailing ...",
    ",",
    ";",
    ":",
    "hello ...",
    "hello ..",
    "hello .",
    "one . two",
    "one, .",
    ", hello",
    "; hello",
    ": hello",
    "! hello",
    "? hello",
    "hello ... world",
    "... !",
    "... , hello",
)


@pytest.mark.parametrize("text", _PUNCT_NAME_BYTE_EXACT_PROMPTS)
def test_vtm1_pcm_byte_identical_punct_names(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Spoken-punctuation-name prompts are byte-identical to the binary.

    The #315 lane: isolated punctuation is spoken by name (typing-table
    spell path), single marks attach to a preceding word, and dot runs
    follow the C parser's collapse rules — see the block comment on
    ``_PUNCT_NAME_BYTE_EXACT_PROMPTS``.
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size == ref.size, f"length mismatch {py.size} vs {ref.size}"
    np.testing.assert_array_equal(py, ref)


# --- end issue #315 lane ---------------------------------------------


# --- issue #331: [:dv <field> <value>] design-voice lane -------------
# The design-voice command overwrites ``curspdef[SPD_<field>]`` with the
# user value, clamped to the ``limit[]`` range (``ph_vdefi.c``); the
# per-voice ``tunedef`` add is all-zero on the active 11025 Hz build, so
# the value flows straight to the speaker reload
# (``dectalk.ph.setspdef.apply_dv_overrides`` -> ``seed_dph_scalars`` +
# ``spd_chip_from_row``). Same sample count as the un-prefixed prompt
# (the params retune formants / F0 / gains, not timing), different bytes.
# ``[:dv as 100]`` is byte-identical to no command because 100 is Paul's
# default ``SPD_AS`` — the render path was always correct; only the
# parameter application was missing (issue #331). Each row pins one field
# family at a representative grid value, plus the two clamp edges
# (``ap 40`` -> AP floor 50, ``hs 200`` -> HS ceiling 145) and a
# multi-field write in a single command.
_DV_PARAM_BYTE_EXACT_PROMPTS: tuple[str, ...] = (
    "[:dv as 100] hello",  # no-op regression guard (100 == Paul default)
    "[:dv ap 90] hello",  # average pitch
    "[:dv ap 200] hello world",  # average pitch, longer body
    "[:dv pr 250] hello",  # pitch range (at limit ceiling)
    "[:dv hs 120] testing",  # head size
    "[:dv br 40] hello",  # breathiness
    "[:dv ri 30] hello",  # richness
    "[:dv sm 100] hello",  # smoothness
    "[:dv gv 55] hello",  # voicing gain
    "[:dv ap 40] hello",  # below AP floor -> clamps to 50
    "[:dv hs 200] hello",  # above HS ceiling -> clamps to 145
    "[:dv br 40 ri 30] hello",  # multiple field/value pairs, one command
    "[:dv sm 100 sr 10 bf 20 qu 60 gv 55] hello",  # five params at once
)


@pytest.mark.parametrize("text", _DV_PARAM_BYTE_EXACT_PROMPTS)
def test_vtm1_pcm_byte_identical_dv_params(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """``[:dv <field> <value>]`` design-voice params are byte-exact vs the binary.

    The #331 lane: each parameter overwrites ``curspdef`` (clamped to its
    ``limit[]`` range) and re-seeds the speaker definition, matching the C
    ``cm_cmd_define`` -> ``ph_vset.c`` per-param setter. Sample count is
    unchanged (back-end-content); the bytes retune to the new voice.
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size == ref.size, f"length mismatch {py.size} vs {ref.size}"
    np.testing.assert_array_equal(py, ref)


# --- issue #331: [:volume set N] output-gain lane --------------------
# On the SOFTWARE_VOLUME build (the shipped Linux libtts) [:volume set N]
# does NOT post-scale the output — StereoVolumeControl converts N to a dB
# offset (DBtable[Decode(Encode(N))]) that ph_vset.c folds into the
# speaker chip's voicing / frication / aspiration gains, so the effect is
# a non-linear retune of the synth, not a uniform scale. Sample count is
# unchanged. ``set 100`` (and any N >= 100) is unity because Encode
# saturates at MAX_VOLUME=99 -> DBtable 0 dB. ``att`` / ``sset`` drive the
# hardware vol_att path, which the ``say -fo`` WAV render never applies,
# so they are WAV no-ops pinned here as regression guards. ``up`` / ``down``
# / ``lset`` / ``rset`` are deliberately absent: the fresh-handle device
# volume is uninitialised, so the binary renders them non-deterministically
# (different WAV bytes each run) and there is no byte-exact target.
_VOLUME_BYTE_EXACT_PROMPTS: tuple[str, ...] = (
    "[:volume set 100] hello",  # unity / no-op regression guard
    "[:volume set 140] hello",  # N >= 100 saturates to unity
    "[:volume att 50] hello",  # hardware path -> WAV no-op
    "[:volume sset 50] hello",  # hardware path -> WAV no-op
    "[:volume set 0] hello",  # near-mute (-40 dB)
    "[:volume set 25] hello",
    "[:volume set 50] hello",
    "[:volume set 50] hello world",  # longer body
    "[:volume set 75] testing",
    "[:volume set 90] hello",
    "[:volume set 60] the quick brown fox",
)


@pytest.mark.parametrize("text", _VOLUME_BYTE_EXACT_PROMPTS)
def test_vtm1_pcm_byte_identical_volume(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """``[:volume set N]`` output gain is byte-exact vs the binary.

    The #331 lane: ``set N`` retunes the speaker chip gains by the
    ``SOFTWARE_VOLUME`` dB offset (``services.c`` DBtable ->
    ``ph_vset.c``); ``att`` / ``sset`` are WAV no-ops. Sample count is
    unchanged (back-end-content).
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)
    assert py.size == ref.size, f"length mismatch {py.size} vs {ref.size}"
    np.testing.assert_array_equal(py, ref)


# --- end issue #331 [:dv] / [:volume] lane ---------------------------


# Frame size at the active 11025 Hz build (vtm1.c uiNumberOfSamplesPerFrame).
_SAMPLES_PER_FRAME = 71

# Prompts whose leading silence is governed entirely by the speaker-def
# silence latch: a leading GEN_SIL phone followed directly by a voiced
# onset, so the oracle's first audible sample is the latch boundary at
# frame 3 (sample 213) with no extra leading silent phones. Prompts that
# open on a stop closure (e.g. "test") or a different onset accrue extra
# leading silence from phone timing — a separate barrier — so they are
# intentionally excluded here (issue #266).
_LEADING_SILENCE_PROMPTS: tuple[str, ...] = (
    "hello world",
    "hello",
    "hi",
    "how are you",
)


def _first_audio_sample(pcm: np.ndarray) -> int:
    """Index of the first non-zero sample, or ``-1`` if all-zero."""
    nz = np.nonzero(pcm)[0]
    return int(nz[0]) if nz.size else -1


@pytest.mark.parametrize("text", _LEADING_SILENCE_PROMPTS)
def test_vtm1_leading_silence_matches_oracle(text: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Python vtm1 leading silence matches the C oracle's, frame-for-frame.

    The shipped ``libtts_us.so`` holds three leading frames as real
    silence after the speaker-definition packet (``vtm1.c`` ``ldspdef``
    latch). On ``hello world`` the oracle's first non-zero sample is 213
    (frame 3); the Python vtm1 path previously emitted aspiration one
    frame early (first non-zero at 142, frame 2), which was the first
    byte divergence. This pins the fix as a *parity* assertion — the
    Python first-audio sample equals the oracle's, and every leading
    silent frame is byte-identical (all-zero in both) — rather than
    hard-coding the magic frame index (issue #266).
    """
    ref = _binary_pcm_int16(text)
    py = _python_vtm1_pcm(text, monkeypatch)

    ref_first = _first_audio_sample(ref)
    py_first = _first_audio_sample(py)

    assert ref_first >= 0, f"oracle produced all-zero PCM for {text!r}"
    # The Python first-audio sample must match the oracle's exactly: the
    # leading silence is byte-identical up to (and not past) that point.
    assert py_first == ref_first, (
        f"vtm1 leading silence diverges for {text!r}: Python first-audio "
        f"sample {py_first} (frame {py_first / _SAMPLES_PER_FRAME:.2f}) vs "
        f"oracle {ref_first} (frame {ref_first / _SAMPLES_PER_FRAME:.2f})"
    )

    # Every fully-leading silent frame must be all-zero in both streams
    # (the byte-identical-prefix claim, restricted to the silent region).
    leading_silent_frames = ref_first // _SAMPLES_PER_FRAME
    silent_len = leading_silent_frames * _SAMPLES_PER_FRAME
    np.testing.assert_array_equal(
        py[:silent_len],
        ref[:silent_len],
        err_msg=f"leading silent frames differ for {text!r}",
    )
    if silent_len:
        assert not np.any(py[:silent_len]), f"Python leading frames not silent for {text!r}"
