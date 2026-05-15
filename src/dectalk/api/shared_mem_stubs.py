"""Shared-memory ELF init/fini stubs from ``api/ttsapi.c``.

The Linux libtts.so build includes empty ``__init_shared_mem`` /
``__fini_shared_mem`` constructor / destructor stubs (the ELF
``.init_array`` / ``.fini_array`` slots). These run once at library
load / unload time and do nothing -- the Linux port uses no shared
memory between processes.

The Python port has no shared memory either; these functions exist
as no-op stubs under the C names so the api module-inventory test
counts them as ported.
"""

from __future__ import annotations


def __init_shared_mem() -> None:
    """ELF .init_array stub; no-op in the Python port."""


def __fini_shared_mem() -> None:
    """ELF .fini_array stub; no-op in the Python port."""


__all__ = ["__fini_shared_mem", "__init_shared_mem"]
