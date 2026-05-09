"""Command-line interface for the DECtalk port.

Phase 0 ships a minimal CLI that supports `--play-test` (a sine tone through
the speakers) and `--write-test` (a sine tone written to a WAV path). Once
the synthesizer lands in Phase 1, this module grows to accept text input.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

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
    return parser


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
