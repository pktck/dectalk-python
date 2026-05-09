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

from dectalk.api import UnknownWordError, available_voices, speak
from dectalk.data.voices import get_preset
from dectalk.dic import set_extra_lexicon
from dectalk.hlsyn.llsyn import LLSynth
from dectalk.hlsyn.synthesize import ll_synthesize
from dectalk.hlsyn.vowels import VOWELS, default_speaker
from dectalk.nt.audio import play, sine_tone, write_wav
from dectalk.ph.sequencer import synthesize_phonemes


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
        help="Text to synthesize. Words must be in the bundled lexicon; "
        "use --phonemes for arbitrary ARPABET strings.",
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
    parser.add_argument(
        "--phonemes",
        type=str,
        default=None,
        metavar='"P1 P2 ..."',
        help="Synthesize a space-separated ARPABET phoneme sequence. "
        "Example: --phonemes \"HH AH L OW\" pronounces 'hello'. "
        "Combine with -o to write WAV.",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=1.0,
        help="Speaking rate multiplier (1.0 nominal, > 1 slower, < 1 faster).",
    )
    parser.add_argument(
        "--voice",
        type=str,
        choices=available_voices(),
        default=None,
        help="DECtalk voice for --text or --phonemes (paul/betty/harry/...).",
    )
    parser.add_argument(
        "--lang",
        type=str,
        choices=("us", "uk"),
        default="us",
        help="Language / lexicon variant. Default: us.",
    )
    parser.add_argument(
        "--lexicon",
        type=str,
        default=None,
        metavar="PATH",
        help="Optional CMUDict-format lexicon file. When supplied, it takes "
        "precedence over the bundled mini-lexicon.",
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


def _emit(wave: np.ndarray, output_path: str | None) -> None:  # type: ignore[type-arg]
    """Either write ``wave`` to ``output_path`` or play it through speakers."""
    if output_path is not None:
        write_wav(wave, output_path)
    else:
        play(wave)


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

    if args.lexicon is not None:
        set_extra_lexicon(args.lexicon)

    if args.play_test:
        play(sine_tone(freq_hz=440.0, duration_sec=1.0))
    elif args.write_test is not None:
        write_wav(sine_tone(freq_hz=440.0, duration_sec=1.0), args.write_test)
    elif args.vowel is not None:
        _emit(_synthesize_vowel(args.vowel, args.duration), args.output)
    elif args.phonemes is not None:
        preset = get_preset(args.voice) if args.voice else None
        _emit(
            synthesize_phonemes(args.phonemes.split(), rate=args.rate, preset=preset),
            args.output,
        )
    elif args.text is None:
        parser.print_help()
    else:
        try:
            wave = speak(args.text, rate=args.rate, voice=args.voice, lang=args.lang)
        except UnknownWordError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 3
        _emit(wave, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
