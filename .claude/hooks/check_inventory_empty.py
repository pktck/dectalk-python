#!/usr/bin/env python3
"""Verify every module-inventory test's ``_DEFERRED`` dict is empty.

Used by the stop hook as a cheap gate before running the slow
end-to-end parity test. When every inventory's ``_DEFERRED`` is
empty AND the parity test passes, the project goal (byte-identical
WAV vs the DECtalk binary) is provably met and the hook may allow
stop.

Exits 0 if all inventories are empty (every C function has a Python
port). Exits 1 otherwise, emitting a one-line summary of which
inventories still have deferred entries.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEST_DIR = _REPO_ROOT / "tests" / "unit"
_INVENTORY_TESTS = (
    "test_kernel_services_inventory.py",
    "test_ph_module_inventory.py",
    "test_cmd_module_inventory.py",
    "test_lts_module_inventory.py",
    "test_vtm_module_inventory.py",
    "test_dic_module_inventory.py",
    "test_api_module_inventory.py",
    "test_hlsyn_module_inventory.py",
)


def _count_deferred(path: Path) -> int:
    """Count keys in the ``_DEFERRED`` dict at module level.

    Parses the file via :mod:`ast` so we don't need to import it
    (which would pull in pytest + dependencies).
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return -1
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        target = node.target
        if not isinstance(target, ast.Name) or target.id != "_DEFERRED":
            continue
        if not isinstance(node.value, ast.Dict):
            return -1
        return len(node.value.keys)
    return -1


def main() -> int:
    """Walk the inventory tests and exit 0 iff every ``_DEFERRED`` is empty."""
    summary: list[str] = []
    total = 0
    missing_files = 0
    for name in _INVENTORY_TESTS:
        path = _TEST_DIR / name
        if not path.is_file():
            missing_files += 1
            summary.append(f"{name}: missing")
            continue
        n = _count_deferred(path)
        if n < 0:
            summary.append(f"{name}: parse-error")
            total += 1  # treat as non-empty
            continue
        if n > 0:
            summary.append(f"{name}: {n} deferred")
            total += n
    if missing_files or total > 0:
        print(
            f"inventory-deferred: {total} entries across {len(_INVENTORY_TESTS) - missing_files} "
            f"inventories ({', '.join(summary)})",
            file=sys.stderr,
        )
        return 1
    print("inventory-deferred: all empty", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
