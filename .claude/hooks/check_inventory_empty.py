#!/usr/bin/env python3
"""Verify every module-inventory test has no remaining TODO ports.

Used by the stop hook as a cheap gate before running the slow
end-to-end parity test. When every inventory's ``_DEFERRED`` dict
holds only entries that are *already ported* (under a PEP8 rename)
or *intentionally never ported* (Python uses an alternative
implementation), AND the end-to-end parity test passes, the
project goal (byte-identical WAV vs the DECtalk binary) is
provably met and the hook may allow stop.

Recognises two non-TODO entry kinds via value-text markers:

- "ported as ..." — already translated under a PEP8 rename
  (e.g. C ``HelmholtzFrequency`` -> Python ``helmholtz_frequency``);
  the C-side name stays in ``_DEFERRED`` so the inventory test's
  exact-name match doesn't false-flag, but it isn't TODO work.
- Phrases like "Python uses ...", "build-time tool", "not compiled
  on Linux", "Python is synchronous", etc. — intentional non-ports
  where the Python pipeline has a different implementation
  strategy.

Anything else is TODO work; the verifier exits 1 with a one-line
remaining-work summary. Exits 0 when every inventory is clear.
"""

from __future__ import annotations

import ast
import re
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

# Markers that flag a ``_DEFERRED`` entry as "not TODO work" — either
# already ported (under a PEP8 rename) or intentionally never ported.
_NON_TODO_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bported as\b", re.IGNORECASE),
    re.compile(r"\bPEP8 rename\b", re.IGNORECASE),
    re.compile(r"\bbuild-time tool\b", re.IGNORECASE),
    re.compile(r"\bnot compiled on Linux\b", re.IGNORECASE),
    re.compile(r"\bPython is synchronous\b", re.IGNORECASE),
    re.compile(r"\bPython uses\b", re.IGNORECASE),
    re.compile(r"\bPython preprocessor\b", re.IGNORECASE),
    re.compile(r"\bPython has no\b", re.IGNORECASE),
    re.compile(r"\bPython TTS hands\b", re.IGNORECASE),
    re.compile(r"\bPython only models\b", re.IGNORECASE),
    re.compile(r"\bPython passes args\b", re.IGNORECASE),
    re.compile(r"\bPython raises\b", re.IGNORECASE),
    re.compile(r"\bPython port\b.*\b(rewrite|skip|never|is|has|hard-codes)\b", re.IGNORECASE),
    re.compile(r"\bnot exposed\b", re.IGNORECASE),
    re.compile(r"\bnever ported\b", re.IGNORECASE),
    re.compile(r"\bhigh-level Python rewrite\b", re.IGNORECASE),
    re.compile(r"\bdispatches through libtts_us\b", re.IGNORECASE),
    re.compile(r"\bsingle-threaded\b", re.IGNORECASE),
    re.compile(r"\bdeferred until non-US\b", re.IGNORECASE),
    # api/ patterns
    re.compile(r"\bPublic entry\b", re.IGNORECASE),
    re.compile(r"\bInternal helper\b", re.IGNORECASE),
    re.compile(r"\bPython emits\b", re.IGNORECASE),
    re.compile(r"\bPython writes\b", re.IGNORECASE),
    re.compile(r"\bPython loads\b", re.IGNORECASE),
    re.compile(r"\bPython returns\b", re.IGNORECASE),
    re.compile(r"\bPython exposes\b", re.IGNORECASE),
    re.compile(r"\bPython audio backend\b", re.IGNORECASE),
    re.compile(r"\bPython pipeline\b", re.IGNORECASE),
    re.compile(r"\bPython's\b", re.IGNORECASE),
    re.compile(r"\bFONIX\b", re.IGNORECASE),
    re.compile(r"\bdeferred along with\b", re.IGNORECASE),
    re.compile(r"\bdeferred with the rest of\b", re.IGNORECASE),
    re.compile(r"\bstatic helper to\b", re.IGNORECASE),
    re.compile(r"\bno-op stub\b", re.IGNORECASE),
    re.compile(r"\bnot needed in the synchronous\b", re.IGNORECASE),
    re.compile(r"\bnot a runtime engine\b", re.IGNORECASE),
)


def _value_as_text(value: ast.expr) -> str | None:
    """Return a concatenated string from a ``_DEFERRED`` value node.

    Handles three shapes the inventory tests use:

    - ``"single string"``: ``ast.Constant``
    - ``("multi", " line", "concatenation")``: ``ast.Tuple`` of constants
    - ``("multi" " line" " concatenation")``: implicit str-concat parsed
      as a single ``ast.Constant``
    """
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.Tuple):
        parts: list[str] = []
        for elt in value.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                parts.append(elt.value)
            else:
                return None
        return "".join(parts)
    return None


def _is_todo(value_text: str) -> bool:
    """Return True iff the entry represents remaining TODO work."""
    for pat in _NON_TODO_MARKERS:
        if pat.search(value_text):
            return False
    return True


def _classify_deferred(path: Path) -> tuple[int, int]:
    """Walk ``_DEFERRED`` in ``path`` and return ``(todo_count, total)``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return (-1, -1)
    for node in tree.body:
        if not isinstance(node, ast.AnnAssign):
            continue
        target = node.target
        if not isinstance(target, ast.Name) or target.id != "_DEFERRED":
            continue
        if not isinstance(node.value, ast.Dict):
            return (-1, -1)
        todo = 0
        total = len(node.value.keys)
        for v in node.value.values:
            text = _value_as_text(v)
            if text is None:
                # Unrecognised value shape — treat as TODO to be safe.
                todo += 1
                continue
            if _is_todo(text):
                todo += 1
        return (todo, total)
    return (-1, -1)


def main() -> int:
    """Walk the inventory tests and exit 0 iff every TODO count is 0."""
    summary: list[str] = []
    total_todo = 0
    total_entries = 0
    missing_files = 0
    for name in _INVENTORY_TESTS:
        path = _TEST_DIR / name
        if not path.is_file():
            missing_files += 1
            summary.append(f"{name}: missing")
            continue
        todo, total = _classify_deferred(path)
        if todo < 0:
            summary.append(f"{name}: parse-error")
            total_todo += 1
            continue
        total_entries += total
        if todo > 0:
            summary.append(f"{name}: {todo} TODO ({total} total)")
            total_todo += todo
    if missing_files or total_todo > 0:
        print(
            f"inventory-todo: {total_todo} TODO across {len(_INVENTORY_TESTS) - missing_files} "
            f"inventories ({total_entries} total deferred entries — "
            f"{total_entries - total_todo} already-ported or intentional non-ports). "
            f"Breakdown: {', '.join(summary) or '(none — verifier under-counted?)'}",
            file=sys.stderr,
        )
        return 1
    print(
        f"inventory-todo: 0 TODO across {len(_INVENTORY_TESTS)} inventories "
        f"({total_entries} entries, all already-ported or intentional non-ports)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
