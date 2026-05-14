#!/usr/bin/env python3
"""Apply local C-source patches under ``$DECTALK_SRC`` and rebuild libtts_us.

This is part of the C-to-Python port infrastructure (see
``/root/.claude/plans/create-a-python-port-smooth-hoare.md``). The
patches live in ``tests/parity/c_patches/`` and are kept under version
control here rather than in the upstream dectalk/dectalk repo so we can
maintain them independently of the original source.

What's patched:

- ``0001-expose-convert-to-phonemes-on-linux.patch`` — moves
  ``TextToSpeechConvertToPhonemes`` out of an ``#ifdef WIN32`` block in
  ``src/dapi/src/api/ttsapi.c`` so the symbol is exported on Linux/macOS
  too. Otherwise the multi-lang dispatcher in ``libtts.so`` resolves the
  function pointer to NULL at startup and invoking the public symbol
  segfaults at the indirect call. This patch lets us use it as a
  per-module parity oracle for the front-end translation work.
- ``0002-stage-boundary-dumps.patch`` — adds opt-in per-stage
  boundary dump hooks to ``src/dapi/src/api/ttsapi.c``. When
  ``DECTALK_DUMP_DIR`` is set in the environment, the library writes
  a deterministic text dump of each pipeline stage's output to
  ``<DECTALK_DUMP_DIR>/<stage>.dump``. Currently implements the
  ``kernel`` stage only; ``cmd``/``lts``/``ph``/``vtm`` are TODO and
  will be added as the per-stage Python ports land. See
  ``docs/c_audit/stage_boundaries.md`` for the boundary catalogue.

Usage:
    uv run python scripts/apply_c_patches.py             # apply + rebuild
    uv run python scripts/apply_c_patches.py --check     # report patch status
    uv run python scripts/apply_c_patches.py --rebuild   # skip apply, just rebuild

Env vars:
    DECTALK_SRC   path to /tmp/dectalk-src (default)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PATCH_DIR = _REPO_ROOT / "tests" / "parity" / "c_patches"
_DEFAULT_SRC = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))


def _patches() -> list[Path]:
    """Return all `.patch` files in ``c_patches/`` sorted by name."""
    return sorted(_PATCH_DIR.glob("*.patch"))


def _patch_status(src_root: Path, patch: Path) -> str:
    """Return one of: ``applied``, ``not-applied``, ``conflict``."""
    # ``patch --dry-run -R`` succeeds only if the patch is already applied.
    rc_rev = subprocess.run(
        ["patch", "--dry-run", "-R", "-p1", "-i", str(patch)],
        cwd=str(src_root),
        capture_output=True,
        check=False,
    ).returncode
    if rc_rev == 0:
        return "applied"
    rc_fwd = subprocess.run(
        ["patch", "--dry-run", "-p1", "-i", str(patch)],
        cwd=str(src_root),
        capture_output=True,
        check=False,
    ).returncode
    return "not-applied" if rc_fwd == 0 else "conflict"


def _apply(src_root: Path, patch: Path) -> None:
    """Apply ``patch`` to ``src_root``. Raises on conflict."""
    status = _patch_status(src_root, patch)
    if status == "applied":
        print(f"  already applied: {patch.name}")
        return
    if status == "conflict":
        raise SystemExit(
            f"Patch {patch.name} would conflict — neither cleanly applied nor "
            f"already applied. Check {src_root} state."
        )
    subprocess.run(
        ["patch", "-p1", "-i", str(patch)],
        cwd=str(src_root),
        check=True,
    )
    print(f"  applied: {patch.name}")


def _rebuild(src_root: Path) -> None:
    """Re-run ``./autogen.sh && ./configure && make english_release``."""
    src_dir = src_root / "src"
    if not (src_dir / "configure").is_file():
        subprocess.run(["./autogen.sh"], cwd=str(src_dir), check=True)
    if not (src_dir / "Makefile").is_file():
        subprocess.run(["./configure"], cwd=str(src_dir), check=True)
    # Touch the patched file so make picks up the change even if its mtime
    # is older than the build artefacts.
    patched = src_dir / "dapi" / "src" / "api" / "ttsapi.c"
    if patched.is_file():
        patched.touch()
    subprocess.run(["make", "-j4", "english_release"], cwd=str(src_dir), check=True)


def main() -> int:
    """Entry point. See module docstring for usage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report status only")
    parser.add_argument("--rebuild", action="store_true", help="skip patches, run a build only")
    parser.add_argument(
        "--src-root", type=Path, default=_DEFAULT_SRC, help=f"default: {_DEFAULT_SRC}"
    )
    args = parser.parse_args()

    src_root: Path = args.src_root
    if not src_root.is_dir():
        raise SystemExit(f"{src_root} is not a directory; set DECTALK_SRC")

    patches = _patches()
    if not patches:
        print(f"No patches found in {_PATCH_DIR}")
        return 0

    if args.check:
        for p in patches:
            print(f"  {p.name}: {_patch_status(src_root, p)}")
        return 0

    if not args.rebuild:
        print(f"Applying patches in {src_root}:")
        for p in patches:
            _apply(src_root, p)

    print("Rebuilding libtts_us.so + samples …")
    _rebuild(src_root)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
