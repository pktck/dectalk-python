"""Command-line interface for the DECtalk port.

Phase 0 ships smoke commands (``--play-test`` / ``--write-test``); Phase 1
adds ``--vowel`` for synthesizing a steady vowel through the Klatt
synthesizer. Once the front-end (text normalization + LTS + lexicon) lands
in Phase 2, the positional ``text`` argument will drive full synthesis.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import numpy as np

from dectalk.hlsyn.llsyn import LLSynth
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.vowels import VOWELS, default_speaker
from dectalk.nt.audio import play, sine_tone, write_wav


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="dectalk",
        description="DECtalk Python port — text-to-speech synthesizer.",
    )
    parser.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Text to synthesize (later phases). Phase 0 ignores this argument.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Write WAV output to this path instead of playing through speakers.",
    )
    parser.add_argument(
        "--play-test",
        action="store_true",
        help="Play a 1-second 440 Hz sine tone through the default audio device.",
    )
    parser.add_argument(
        "--write-test",
        type=str,
        metavar="PATH",
        default=None,
        help="Write a 1-second 440 Hz sine tone WAV to PATH.",
    )
    parser.add_argument(
        "--vowel",
        type=str,
        choices=sorted(VOWELS.keys()),
        default=None,
        help="Synthesize a 1-second steady vowel (ah/ee/oo/eh/aw). "
        "Combine with -o to write WAV, otherwise plays through speakers.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="Vowel duration in seconds (default: 1.0).",
    )
    return parser


def _synthesize_vowel(vowel_id: str, duration_sec: float) -> np.ndarray:  # type: ignore[type-arg]
    """Synthesize a steady vowel and return its int16 PCM samples.

    Args:
        vowel_id: One of the keys in :data:`dectalk.hlsyn.vowels.VOWELS`.
        duration_sec: Length of the synthesized vowel in seconds.

    Returns:
        1-D ``int16`` array of PCM samples at 11025 Hz.
    """
    spkr = default_speaker()
    frame = VOWELS[vowel_id]
    n_frames = max(1, round(duration_sec * spkr.SR / spkr.UI))
    wave = np.zeros(spkr.UI * n_frames, dtype=np.int16)
    synth = LLSynth(spkr=spkr)
    for fi in range(n_frames):
        ll_synthesize(synth, frame, wave[fi * spkr.UI : (fi + 1) * spkr.UI])
    return wave


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point invoked by the `dectalk` console script and `python -m dectalk`.

    Args:
        argv: Optional argument vector (without the program name). Defaults
            to ``sys.argv[1:]``.

    Returns:
        Process exit code: 0 on success, non-zero on failure.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.play_test:
        tone = sine_tone(freq_hz=440.0, duration_sec=1.0)
        play(tone)
        return 0

    if args.write_test is not None:
        tone = sine_tone(freq_hz=440.0, duration_sec=1.0)
        write_wav(tone, args.write_test)
        return 0

    if args.vowel is not None:
        wave = _synthesize_vowel(args.vowel, args.duration)
        if args.output is not None:
            write_wav(wave, args.output)
        else:
            play(wave)
        return 0

    if args.text is None:
        parser.print_help()
        return 0

    print(
        "Synthesis not implemented yet — Phase 0 only supports --play-test / --write-test.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
