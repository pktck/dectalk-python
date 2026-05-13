"""Inventory parity test for kernel/services.c SPC-chain helpers.

Asserts that every SPC-chain helper defined in the C source has a
matching Python port under :mod:`dectalk.kernel`.

The C source defines six functions that manipulate
``pKsd_t->spc_pkt_save``:

- ``save_index``       → :mod:`dectalk.kernel.save_index`
- ``check_index``      → :mod:`dectalk.kernel.check_index`
- ``adjust_index``     → :mod:`dectalk.kernel.adjust_index`
- ``adjust_allo``      → :mod:`dectalk.kernel.adjust_allo`
- ``set_index_allo``   → :mod:`dectalk.kernel.adjust_allo`
- ``free_index``       → :mod:`dectalk.kernel.free_index`

Skips cleanly when ``DECTALK_SRC`` / ``/tmp/dectalk-src`` is absent.
"""

from __future__ import annotations

import importlib
import os
import re
from pathlib import Path

import pytest

_C_FILE = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src")) / (
    "src/dapi/src/kernel/services.c"
)

pytestmark = pytest.mark.skipif(
    not _C_FILE.is_file(),
    reason="DECtalk C source not available at /tmp/dectalk-src",
)


def _read_services_c() -> str:
    """Read services.c with CRLF endings normalised."""
    return _C_FILE.read_bytes().replace(b"\r", b"").decode("latin-1")


# Mapping from C function name to ``(python_module, python_attr)``.
_SPC_CHAIN_PORTS: dict[str, tuple[str, str]] = {
    "save_index": ("dectalk.kernel.save_index", "save_index"),
    "check_index": ("dectalk.kernel.check_index", "check_index"),
    "adjust_index": ("dectalk.kernel.adjust_index", "adjust_index"),
    "adjust_allo": ("dectalk.kernel.adjust_allo", "adjust_allo"),
    "set_index_allo": ("dectalk.kernel.adjust_allo", "set_index_allo"),
    "free_index": ("dectalk.kernel.free_index", "free_index"),
}


def _find_function_definitions() -> set[str]:
    """Return the names of every SPC-chain helper defined in services.c.

    A "definition" is matched by ``void name(...) {`` (open-brace),
    distinguishing from the forward declarations ending in ``;``.
    """
    text = _read_services_c()
    defs: set[str] = set()
    for name in _SPC_CHAIN_PORTS:
        # Match the definition (followed by `{`), not the forward decl.
        pat = rf"void\s+{re.escape(name)}\s*\([^)]*\)\s*\{{"
        if re.search(pat, text):
            defs.add(name)
    return defs


def test_c_source_defines_all_six_helpers() -> None:
    """All six helpers are defined (not just forward-declared) in services.c."""
    defs = _find_function_definitions()
    assert defs == set(_SPC_CHAIN_PORTS.keys()), (
        f"missing C definitions: {set(_SPC_CHAIN_PORTS.keys()) - defs}"
    )


def test_every_c_helper_has_python_port() -> None:
    """Each C SPC-chain helper has an importable Python callable."""
    defs = _find_function_definitions()
    for c_name in defs:
        module_name, attr = _SPC_CHAIN_PORTS[c_name]
        module = importlib.import_module(module_name)
        func = getattr(module, attr, None)
        assert callable(func), (
            f"C function {c_name} -> Python {module_name}.{attr} missing/not callable"
        )


def test_helper_count_matches() -> None:
    """The Python port covers exactly the six SPC-chain helpers (no more, no less)."""
    defs = _find_function_definitions()
    assert len(defs) == len(_SPC_CHAIN_PORTS) == 6
