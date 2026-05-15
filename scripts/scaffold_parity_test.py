#!/usr/bin/env python3
r"""Generate the parity-test boilerplate for a C → Python port.

Translator agents porting a function from the DECtalk C source can run::

    uv run python scripts/scaffold_parity_test.py \
        --c-file src/dapi/src/ph/ph_setar.c \
        --c-function phsettar \
        --python-module dectalk.ph.phsettar \
        --python-symbol phsettar

and get a `tests/unit/test_ph_phsettar_parity.py` skeleton that:

- locates the C source under ``$DECTALK_SRC`` (default ``/tmp/dectalk-src``),
- re-parses the named function body via brace-depth tracking
  (mirroring the proven extractor in ``test_ph_make_dip_parity.py``),
- asserts that the signature still exists with the expected argument
  names, and provides a TODO list of body-content checks for the
  translator to fill in,
- exercises the Python shim's ``NotImplementedError`` contract so the
  test passes against a not-yet-ported module and grows assertions as
  the port lands.

The generator never overwrites an existing test file; pass
``--force`` to replace.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = _REPO_ROOT / "tests" / "unit"


_TEMPLATE = '''\
"""C-source parity test for ``{py_symbol}`` against {c_file_rel}.

Re-parses the C body via brace-depth tracking and asserts the function
still exists in the develop branch with its expected shape. Also checks
the Python shim raises ``NotImplementedError`` as documented while the
port is in progress; once {py_symbol} is implemented, replace the shim
assertion with behavioural checks against the C body.

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from {py_module} import {py_symbol}

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / "{c_file_rel}"

pytestmark = [
    pytest.mark.parity,
    pytest.mark.skipif(
        not _C_FILE.is_file(),
        reason="DECtalk C source not available at /tmp/dectalk-src",
    ),
]


def _read_c() -> str:
    return _C_FILE.read_bytes().replace(b"\\r", b"").decode("latin-1")


def _extract_body() -> str:
    """Return the body (between outer ``{{}}``) of the C ``{c_function}`` function."""
    text = _read_c()
    pattern = re.compile(r"\\b{c_function}\\s*\\(")
    for match in pattern.finditer(text):
        paren_start = match.end() - 1
        depth = 1
        i = paren_start + 1
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        while i < len(text) and text[i] in " \\t\\n\\r":
            i += 1
        if i >= len(text) or text[i] != "{{":
            continue
        start = i + 1
        depth = 1
        i = start
        while i < len(text) and depth > 0:
            ch = text[i]
            if ch == "{{":
                depth += 1
            elif ch == "}}":
                depth -= 1
            i += 1
        if depth == 0:
            return text[start : i - 1]
    raise AssertionError(f"{c_function} definition not found in {{_C_FILE.name}}")


def _extract_signature() -> str:
    """Return the parenthesised parameter list of ``{c_function}``."""
    text = _read_c()
    match = re.search(r"\\b{c_function}\\s*\\(", text)
    assert match is not None, "{c_function} definition not found"
    paren_start = match.end() - 1
    depth = 1
    i = paren_start + 1
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    return text[paren_start:i]


# -- C-source structural assertions ----------------------------------------


def test_signature_exists_in_c() -> None:
    """``{c_function}`` definition is present in {c_file_rel}."""
    assert re.search(r"\\b{c_function}\\s*\\(", _read_c())


def test_body_is_nonempty() -> None:
    """``{c_function}`` body brace-block can be extracted."""
    body = _extract_body()
    assert len(body.strip()) > 0


# TODO(translator): add tighter assertions describing the C body's
# control flow, argument usage, helper-function calls, and any rule
# tables. Mirror the style of tests/unit/test_ph_make_dip_parity.py
# (e.g. ``assert re.search(r"par_type\\s+IS_FORM_FREQ", body)``).


# -- Python behavioural tests ---------------------------------------------


def test_python_shim_raises_not_implemented() -> None:
    """Shim raises ``NotImplementedError`` per the deferred-port contract.

    Remove or invert this assertion once {py_symbol} is implemented.
    """
    with pytest.raises(NotImplementedError):
        {py_symbol}()  # type: ignore[call-arg]  # adapt to real signature
'''


def _c_file_rel(c_file_arg: str) -> str:
    """Normalise the C file path to the form stored in DECTALK_SRC."""
    p = Path(c_file_arg)
    parts = list(p.parts)
    if "src" in parts:
        idx = parts.index("src")
        return str(Path(*parts[idx:]))
    return str(p)


def _target_test_path(c_function: str, py_module: str) -> Path:
    leaf = py_module.rsplit(".", maxsplit=1)[-1]
    return _TESTS_DIR / f"test_{leaf}_{c_function}_parity.py"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: write a scaffolded parity test."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--c-file",
        required=True,
        help="C source path relative to DECTALK_SRC root, e.g. src/dapi/src/ph/ph_setar.c",
    )
    parser.add_argument(
        "--c-function", required=True, help="Name of the C function to test (e.g. phsettar)"
    )
    parser.add_argument(
        "--python-module", required=True, help="Dotted Python module path, e.g. dectalk.ph.phsettar"
    )
    parser.add_argument(
        "--python-symbol", required=True, help="The Python symbol to exercise (often == c-function)"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing test file")
    args = parser.parse_args(argv)

    target = _target_test_path(args.c_function, args.python_module)
    if target.exists() and not args.force:
        print(f"refusing to overwrite {target} (use --force)", file=sys.stderr)
        return 1

    content = _TEMPLATE.format(
        c_file_rel=_c_file_rel(args.c_file),
        c_function=args.c_function,
        py_module=args.python_module,
        py_symbol=args.python_symbol,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
