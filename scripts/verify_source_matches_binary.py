#!/usr/bin/env python3
"""Verify the locally built DECtalk C source matches the shipped binary.

This is Phase A.3 of the C-to-Python port: the parity oracle for every
subsequent Python translation. If our locally compiled `libtts_us.so`
does not produce byte-identical WAV output to the shipped
`/tmp/dectalk-binary-stable/say`, the bit-parity goal is unreachable
because we'd be aiming at a moving target.

Usage:
    uv run python scripts/verify_source_matches_binary.py

Exits 0 on full corpus match, non-zero with a diff summary otherwise.

Env vars:
    DECTALK_SRC   path to /tmp/dectalk-src (default)
    DECTALK_BIN   path to /tmp/dectalk-binary-stable (default)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

_DEFAULT_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_DEFAULT_BIN = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))

_CORPUS: tuple[str, ...] = (
    "hello world",
    "the quick brown fox",
    "she sells sea shells",
    "one two three four five",
    "supercalifragilisticexpialidocious",
    "[:rate 250] testing one two three",
    "DECtalk version 6.2.0",
    "this is a test, with a comma, and a period.",
)


def _locate_built_artefacts(src: Path) -> tuple[Path, Path, Path]:
    """Return (say_binary, libtts_us_dir, libtts_dir)."""
    say = next(src.glob("src/samplosf/build/dtsamples/*/us/release/say"), None)
    libtts_us_dir = next(src.glob("src/dapi/build/dectalk/*/us/release"), None)
    libtts_dir = next(src.glob("src/dtalkml/build/*/us/release"), None)
    missing: list[str] = []
    if say is None:
        missing.append("say")
    if libtts_us_dir is None or not (libtts_us_dir / "libtts_us.so").exists():
        missing.append("libtts_us.so")
    if libtts_dir is None or not (libtts_dir / "libtts.so").exists():
        missing.append("libtts.so")
    if missing:
        raise SystemExit(
            f"Missing built artefacts under {src}: {', '.join(missing)}.\n"
            "Run: cd /tmp/dectalk-src/src && ./autogen.sh && ./configure && "
            "make -j english_release"
        )
    assert say is not None and libtts_us_dir is not None and libtts_dir is not None
    return say, libtts_us_dir, libtts_dir


def _render(say: Path, text: str, out: Path, *, ld_path: str, cwd: Path) -> None:
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = ld_path
    subprocess.run(
        [str(say), "-a", text, "-fo", str(out)],
        env=env,
        cwd=str(cwd),
        check=True,
        capture_output=True,
    )


def main() -> int:
    """Render each corpus prompt through both binaries and compare bytes."""
    src = _DEFAULT_SRC
    binary_dir = _DEFAULT_BIN
    if not (binary_dir / "say").is_file():
        raise SystemExit(f"Shipped binary not found at {binary_dir / 'say'}")
    if not (binary_dir / "DECtalk.conf").is_file():
        raise SystemExit(f"Shipped DECtalk.conf not found in {binary_dir}")

    local_say, libtts_us_dir, libtts_dir = _locate_built_artefacts(src)
    ld_path = f"{libtts_dir}:{libtts_us_dir}"

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i, text in enumerate(_CORPUS):
            local_wav = tmp / f"local_{i:02d}.wav"
            stable_wav = tmp / f"stable_{i:02d}.wav"
            _render(local_say, text, local_wav, ld_path=ld_path, cwd=binary_dir)
            _render(binary_dir / "say", text, stable_wav, ld_path="", cwd=binary_dir)
            local_bytes = local_wav.read_bytes()
            stable_bytes = stable_wav.read_bytes()
            if local_bytes == stable_bytes:
                print(f"MATCH    [{i + 1}/{len(_CORPUS)}] {text!r}")
            else:
                failures.append(
                    f"DIFFER   [{i + 1}/{len(_CORPUS)}] {text!r} "
                    f"(local={len(local_bytes)} B, stable={len(stable_bytes)} B)"
                )
                print(failures[-1])

    if failures:
        print(f"\n{len(failures)} of {len(_CORPUS)} prompts differ.")
        return 1
    print(f"\nAll {len(_CORPUS)} prompts produced byte-identical WAVs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
