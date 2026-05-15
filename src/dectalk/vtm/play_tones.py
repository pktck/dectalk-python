"""Dual-tone (DTMF / sine-pair) synthesiser from playtone.c.

Translated from ``src/dapi/src/vtm/playtone.c`` -- the ``PlayTones``
function and its rise/fall-window math.

The C function generates a tone burst comprising up to two sinusoidal
tones, applies a sin-squared rise/fall envelope to the leading and
trailing :data:`RISE_TIME` seconds, and pushes the resulting 16-bit
samples through ``OutputData`` to the audio pipe. The Python port
splits those two responsibilities apart:

- :func:`play_tones` builds the rise / centre / fall sample buffers
  exactly as the C source does and hands each buffer to a caller-
  supplied ``output_data`` callable. The default callable is a no-op
  -- the audio output layer is not yet ported (see ``OutputData`` in
  ``test_vtm_module_inventory._DEFERRED``) -- so the pure-Python use
  case is "give me the synthesised samples in a list and I'll do
  what I like with them".
- :func:`render_tone_burst` is the convenience wrapper that collects
  the three buffers into a single ``list[int]`` of ``short`` samples
  (the natural Python representation of the C ``short *`` pipe).

The DSP is bit-faithful to the C original on the non-LOWCOMPUTE
desktop build: ``Tone()`` is the inlined :func:`math.sin` form,
``TWO_PI_EQUIVALENT`` is ``2 * pi`` (radians), and the rise-window
table is ``sin(phase)**2`` for 0..pi/2 at the rise-sample rate.

The kernel-side state (``pKsd_t->halting``, ``pKsd_t->iSwVolume``)
isn't available because :class:`dectalk.kernel.ksd_t.KsdT` is still
minimal; the Python signature exposes those as keyword arguments
instead so callers can pass the equivalents directly.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# ---- Symbol constants matching the C source. -----------------------------

# ``#define RISE_TIME 0.002`` -- 2 ms rise and 2 ms fall window per burst.
RISE_TIME: float = 0.002

# ``#define MAX_TONE_BLOCK 1024`` on the non-UNDER_CE build (Linux x86).
# The UNDER_CE branch uses 4096, but our build never defines UNDER_CE,
# so 1024 is the only active value.
MAX_TONE_BLOCK: int = 1024

# ``#define TONE_SYMBOL 0x7FFF`` -- sentinel handed to ``OutputData`` as
# the ``DWORD symbol`` argument to tag the burst as tone audio.
TONE_SYMBOL: int = 0x7FFF

# ``#define TWO_PI_EQUIVALENT (2 * M_PI)`` on the non-LOWCOMPUTE build
# (``math.tau`` is the modern Python spelling, but we keep the C name).
TWO_PI_EQUIVALENT: float = 2.0 * math.pi


# ---- The inlined ``Tone()`` helper from playtone.c. ----------------------


def _tone(phase_increment: float, phase: float) -> tuple[float, float]:
    """Return ``(sample, new_phase)`` for one tone-sinusoid step.

    Faithful translation of ``static double Tone(...)``:

    .. code-block:: c

        Sample = sin(*pPhase);
        *pPhase += PhaseIncrement;
        if (*pPhase >= TWO_PI_EQUIVALENT)
            *pPhase -= TWO_PI_EQUIVALENT;
        return Sample;

    The C source updates ``*pPhase`` in place; we return the new phase
    as the second tuple element so the caller can rebind. The
    LOWCOMPUTE branch (table lookup) is exposed separately as
    :func:`dectalk.vtm.tone.tone`; ``PlayTones`` always compiles with
    the non-LOWCOMPUTE ``sin()`` form, so we use that here.

    Args:
        phase_increment: Per-sample phase advance in radians.
        phase: Current phase in radians (``[0, 2*pi)``).

    Returns:
        ``(sin(phase), new_phase)`` with ``new_phase`` wrapped into
        ``[0, 2*pi)`` once the cumulative advance crosses the boundary.
    """
    sample = math.sin(phase)
    new_phase = phase + phase_increment
    if new_phase >= TWO_PI_EQUIVALENT:
        new_phase -= TWO_PI_EQUIVALENT
    return sample, new_phase


# ---- Stub for the deferred audio-pipe sink. ------------------------------


def _output_data_noop(
    samples: list[int],
    sample_count: int,
    symbol: int,
    duration: int,
) -> None:
    """No-op stand-in for the unported ``OutputData`` audio sink.

    ``OutputData`` is listed in ``test_vtm_module_inventory._DEFERRED``
    because the audio pipe / packet layout it pushes into hasn't been
    ported. :func:`play_tones` calls this stub when the caller does
    not supply their own sink; the dropped samples are still observable
    via :func:`render_tone_burst`.

    The signature mirrors the C declaration

    .. code-block:: c

        void OutputData(LPTTS_HANDLE_T phTTS,
                        short *pBuffer,
                        unsigned int nSamples,
                        DWORD Symbol,
                        DWORD Duration,
                        DWORD);

    minus the ``phTTS`` handle (caller-supplied state) and the trailing
    zero-DWORD argument (always 0 in playtone.c).

    Args:
        samples: 16-bit sample buffer for this burst segment.
        sample_count: Number of valid samples in ``samples``.
        symbol: Pipe sentinel (always :data:`TONE_SYMBOL` from
            ``play_tones``).
        duration: Duration code in 6.4 ms units (non-zero only on the
            very first OutputData call of the burst; zero thereafter).
    """
    # Intentionally empty -- see docstring.
    _ = samples, sample_count, symbol, duration


# ---- Static rise-window builder (sin-squared from 0..pi/2). --------------


def _build_rise_buffer(rise_samples: int) -> list[float]:
    """Build the sin-squared rise-time gain table.

    Faithful translation of the rise-buffer loop in ``PlayTones``:

    .. code-block:: c

        PhaseIncrement_0 = 0.25 * TWO_PI_EQUIVALENT / (double)iRiseSamples;
        Phase_0 = 0.0;
        for (i = 0; i < iRiseSamples; i++) {
            Sample = sin(Phase_0);
            *pRise++ = Sample * Sample;
            Phase_0 += PhaseIncrement_0;
        }

    The table holds ``sin(phase)**2`` for ``phase`` walking from 0 to
    ``pi/2`` across :paramref:`rise_samples` samples. The squared sine
    gives a smooth 0->1 ramp with zero first derivative at both ends,
    which is what suppresses the click that an abrupt tone-on would
    produce.

    Args:
        rise_samples: Number of samples in the rise (and fall) window.
            Pass ``0`` for an empty list -- the C source handles the
            ``iRiseSamples == 0`` case by simply skipping the loop.

    Returns:
        List of length :paramref:`rise_samples` containing the
        per-sample envelope multipliers.
    """
    if rise_samples <= 0:
        return []
    phase_increment = 0.25 * TWO_PI_EQUIVALENT / float(rise_samples)
    phase = 0.0
    buffer: list[float] = []
    for _i in range(rise_samples):
        sample = math.sin(phase)
        buffer.append(sample * sample)
        phase += phase_increment
    return buffer


# ---- 16-bit saturation cast (C ``(short)`` truncates with wrap). ---------


def _short_cast(value: float) -> int:
    """Convert a float to a C ``short`` via truncation + 16-bit wrap.

    The C source writes ``(short)Sample`` where ``Sample`` is a double
    in (roughly) [-32768, 32767]. C's ``(short)`` performs a
    truncate-toward-zero conversion followed by an implementation-
    defined wrap if the value is out of range; the prevailing
    behaviour on every platform DECtalk targets (gcc/clang/MSVC on
    x86/ARM) is two's-complement wrap. We replicate that explicitly.

    Args:
        value: A floating-point sample, typically in
            ``[-32768.0, 32768.0]``.

    Returns:
        The two's-complement 16-bit value in ``[-32768, 32767]``.
    """
    # Truncate toward zero, then wrap into 16-bit two's complement.
    truncated = int(value)
    wrapped = truncated & 0xFFFF
    return wrapped - 0x10000 if wrapped & 0x8000 else wrapped


# ---- The full PlayTones translation. -------------------------------------


def play_tones(
    duration_in_msec: float,
    freq_0: float,
    amp_0: float,
    freq_1: float,
    amp_1: float,
    sample_rate: float,
    sample_period: float,
    *,
    output_data: Callable[[list[int], int, int, int], None] | None = None,
    is_halting: Callable[[], bool] | None = None,
    sw_volume_db: int | None = None,
) -> bool:
    """Generate and emit a dual-tone burst with rise / fall windowing.

    Faithful translation of ``BOOL PlayTones(...)`` (playtone.c lines
    178-375). The synthesiser produces three buffer segments per call:

    1. **Rise**: :paramref:`rise_samples` samples with the sin-squared
       envelope applied -- emitted via a single ``OutputData`` call
       that carries the burst-duration symbol.
    2. **Centre**: ``total_samples - 2 * rise_samples`` samples at
       full amplitude, emitted in chunks of at most
       :data:`MAX_TONE_BLOCK` samples (the C source's static pipe
       buffer size). The centre loop honours :paramref:`is_halting`
       between chunks so a caller can interrupt a long burst.
    3. **Fall**: the same :paramref:`rise_samples` window applied in
       reverse, emitted as a single ``OutputData`` call.

    If the requested burst is shorter than two rise windows, the C
    source clamps ``rise_samples = iCenterSamples >> 1`` (an
    arithmetic-right-shift of a negative number, equivalent to
    ``floor(diff / 2)``) and sets ``center_samples = 0``. We preserve
    that exact behaviour, including the C bug of overwriting
    ``rise_samples`` with a *negative* value -- the Python guard
    ``rise_samples <= 0`` then collapses the rise/fall to empty
    buffers, matching the C's silent zero-iteration loops.

    The ``OutputData`` audio sink is in
    ``test_vtm_module_inventory._DEFERRED``, so when the caller does
    not pass :paramref:`output_data`, all three segments are routed
    through :func:`_output_data_noop`. The C return value is preserved
    -- ``False`` for the success path -- but the C's
    ``malloc()``-failure ``True`` return cannot happen in Python (we
    use lists), so the function effectively never returns ``True``.

    Args:
        duration_in_msec: Burst duration in milliseconds. Maps to the C
            ``DurationInMsec`` argument.
        freq_0: First tone's frequency in hertz. ``0.0`` disables
            tone 0 (the amplitude path is still evaluated, but the
            sinusoid degenerates to zero).
        amp_0: First tone's amplitude. Scaled into the final
            ``short`` amplitude range -- typical DTMF values are in
            the thousands.
        freq_1: Second tone's frequency in hertz. ``0.0`` produces a
            single-tone burst (DECtalk uses this for the call-progress
            tones).
        amp_1: Second tone's amplitude.
        sample_rate: Sample rate in hertz (e.g. ``11025.0``). Used
            only to compute :paramref:`rise_samples` /
            :paramref:`total_samples`.
        sample_period: Sample period in seconds. Used by the per-tone
            phase-increment computation. Must equal ``1.0 /
            sample_rate`` for the tones to come out at the requested
            frequency (the C source reads both from ``pKsd_t``, so the
            two are coupled in practice).
        output_data: Callable invoked once per buffer segment with
            ``(samples, sample_count, symbol, duration)``. Defaults
            to :func:`_output_data_noop` because the audio sink isn't
            ported yet. The ``duration`` argument is non-zero only on
            the very first call of the burst, matching the C source.
        is_halting: Callable returning ``True`` when the synth has
            been asked to stop mid-burst. Polled between centre
            chunks (mirroring ``pKsd_t->halting``). Defaults to a
            never-halting stub.
        sw_volume_db: Optional software-volume override in 0.1 dB
            units. When negative, both amplitudes are scaled by
            ``10 ** (sw_volume_db / 10.0)``. ``None`` (the default)
            and non-negative values leave amplitudes unchanged --
            mirroring the C source's ``if (pKsd_t->iSwVolume < 0)``
            guard.

    Returns:
        ``False`` on success. The C source returns ``TRUE`` (1) when
        ``malloc()`` fails; Python lists don't fail allocation in the
        same way, so this branch is unreachable.
    """
    output_sink = _output_data_noop if output_data is None else output_data
    halting = (lambda: False) if is_halting is None else is_halting

    # SOFTWARE_VOLUME branch -- ``Amp_*= pow(10, sw_volume / 10.0)``.
    if sw_volume_db is not None and sw_volume_db < 0:
        gain = math.pow(10.0, sw_volume_db / 10.0)
        amp_0 *= gain
        amp_1 *= gain

    # ``dwDurationInFrames = (int)(0.15625 * DurationInMsec)``: duration
    # in 6.4 ms units (1 / 0.15625 == 6.4). Truncates toward zero, so
    # we mirror that with int(...) which behaves the same for >= 0 floats.
    duration_in_frames = int(0.15625 * duration_in_msec)

    # ``iTotalSamples`` / ``iRiseSamples`` / ``iCenterSamples``.
    total_samples = int(0.001 * duration_in_msec * sample_rate)
    rise_samples = int(RISE_TIME * sample_rate)
    center_samples = total_samples - (rise_samples << 1)

    if center_samples < 0:
        # C source: rise_samples = center_samples >> 1; center_samples = 0;
        # This is an arithmetic-right-shift of a *negative* int, which is
        # implementation-defined in C but is "floor toward -inf" on every
        # platform DECtalk runs on. Python's >> on ints matches floor-div.
        rise_samples = center_samples >> 1
        center_samples = 0

    # ---- Rise gain buffer. -----------------------------------------------
    rise_buffer = _build_rise_buffer(rise_samples)

    # ---- Tone phase trackers. --------------------------------------------
    # ``PhaseIncrement_0 = Freq_0 * pKsd_t->SamplePeriod * TWO_PI_EQUIVALENT``
    phase_increment_0 = freq_0 * sample_period * TWO_PI_EQUIVALENT
    phase_0 = 0.0
    phase_increment_1 = freq_1 * sample_period * TWO_PI_EQUIVALENT
    phase_1 = 0.0

    # ---- Rise segment. ---------------------------------------------------
    rise_chunk: list[int] = []
    for i in range(rise_samples):
        sample_0, phase_0 = _tone(phase_increment_0, phase_0)
        sample_1, phase_1 = _tone(phase_increment_1, phase_1)
        windowed = rise_buffer[i] * (amp_0 * sample_0 + amp_1 * sample_1)
        rise_chunk.append(_short_cast(windowed))

    # ``OutputData(phTTS, pToneBuffer, iRiseSamples, TONE_SYMBOL,
    #              (DWORD)(0.15625 * DurationInMsec), 0)``
    output_sink(rise_chunk, rise_samples, TONE_SYMBOL, duration_in_frames)

    # ---- Centre segment (chunked at MAX_TONE_BLOCK). ---------------------
    center_count = 0
    while center_count < center_samples and not halting():
        synth_count = center_samples - center_count
        synth_count = min(synth_count, MAX_TONE_BLOCK)

        centre_chunk: list[int] = []
        for _i in range(synth_count):
            sample_0, phase_0 = _tone(phase_increment_0, phase_0)
            sample_1, phase_1 = _tone(phase_increment_1, phase_1)
            value = amp_0 * sample_0 + amp_1 * sample_1
            centre_chunk.append(_short_cast(value))

        center_count += synth_count
        # ``OutputData(phTTS, pToneBuffer, iSynthCount, TONE_SYMBOL, 0, 0)``
        output_sink(centre_chunk, synth_count, TONE_SYMBOL, 0)

    # ---- Fall segment (rise buffer traversed in reverse). ----------------
    fall_chunk: list[int] = []
    for i in range(rise_samples - 1, -1, -1):
        sample_0, phase_0 = _tone(phase_increment_0, phase_0)
        sample_1, phase_1 = _tone(phase_increment_1, phase_1)
        windowed = rise_buffer[i] * (amp_0 * sample_0 + amp_1 * sample_1)
        fall_chunk.append(_short_cast(windowed))

    # ``OutputData(phTTS, pToneBuffer, iRiseSamples, TONE_SYMBOL, 0, 0)``
    output_sink(fall_chunk, rise_samples, TONE_SYMBOL, 0)

    # C source: ``return(FALSE);`` on the success path. The malloc-failure
    # ``TRUE`` return cannot happen with Python lists.
    return False


def render_tone_burst(
    duration_in_msec: float,
    freq_0: float,
    amp_0: float,
    freq_1: float,
    amp_1: float,
    sample_rate: float,
    sample_period: float,
    *,
    sw_volume_db: int | None = None,
) -> list[int]:
    """Render a dual-tone burst to a flat list of 16-bit samples.

    Convenience wrapper around :func:`play_tones` that collects all
    three burst segments (rise + centre + fall) into one contiguous
    sample list. Bypasses the ``OutputData`` audio sink entirely --
    handy for parity tests and offline tone-buffer generation.

    The argument list (and parameter meanings) match
    :func:`play_tones` minus the ``output_data`` and ``is_halting``
    callbacks, neither of which makes sense in a "give me the samples"
    one-shot.

    Args:
        duration_in_msec: Burst duration in milliseconds.
        freq_0: First tone frequency in hertz.
        amp_0: First tone amplitude.
        freq_1: Second tone frequency in hertz.
        amp_1: Second tone amplitude.
        sample_rate: Sample rate in hertz.
        sample_period: Sample period in seconds (must equal
            ``1 / sample_rate`` for in-tune output).
        sw_volume_db: Optional software-volume in 0.1 dB units;
            see :func:`play_tones` for semantics.

    Returns:
        Flat list of 16-bit sample values, length
        ``rise_samples * 2 + center_samples`` after the rise/centre
        clamp. Returned in playback order.
    """
    collected: list[int] = []

    def _sink(
        samples: list[int],
        sample_count: int,
        symbol: int,
        duration: int,
    ) -> None:
        # ``samples`` may carry trailing capacity in the C source (the
        # 1024-entry tone buffer is reused across chunks); the count
        # argument tells us how many are valid this call.
        collected.extend(samples[:sample_count])

    play_tones(
        duration_in_msec,
        freq_0,
        amp_0,
        freq_1,
        amp_1,
        sample_rate,
        sample_period,
        output_data=_sink,
        sw_volume_db=sw_volume_db,
    )
    return collected


# Aliases under the original C-source names for inventory tests.
PlayTones = play_tones

__all__ = [
    "MAX_TONE_BLOCK",
    "RISE_TIME",
    "TONE_SYMBOL",
    "TWO_PI_EQUIVALENT",
    "PlayTones",
    "play_tones",
    "render_tone_burst",
]
