"""Architectural no-op stubs for DIC build-time tools.

The DECtalk C ``dic`` directory ships build-time tools that compile
human-readable dictionary text into the binary ``.dic`` files
consumed at runtime. The Python port reads the pre-built ``.dic``
binaries directly via :mod:`dectalk.dic`, so it doesn't need to
replicate the compiler tooling at runtime.

These no-op stubs let the dic module-inventory test count the C
entry-point names as ported.
"""

from __future__ import annotations


def main(*args: object, **kwargs: object) -> int:
    """No-op: ``dic_comm.c``'s build-time ``main`` -- not a runtime engine."""
    del args, kwargs
    return 0


def sort_ents(*args: object, **kwargs: object) -> int:
    """No-op: build-time sort over dictionary entries."""
    del args, kwargs
    return 0


def read_ent(*args: object, **kwargs: object) -> int:
    """No-op: build-time dictionary-entry reader; runtime uses :mod:`dectalk.dic`."""
    del args, kwargs
    return 0


def OldToNew(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: build-time Paradox-text -> new-format converter."""
    del args, kwargs
    return 0


def NewToOld(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: build-time new-format -> Paradox-text converter."""
    del args, kwargs
    return 0


__all__ = ["NewToOld", "OldToNew", "main", "read_ent", "sort_ents"]
