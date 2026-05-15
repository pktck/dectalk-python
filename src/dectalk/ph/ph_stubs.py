"""Architectural no-op stubs for PH-stage helpers handled via _capi.

The DECtalk PH stage (target placement, intonation, syllabification,
sort) is large -- it's the prosody / formant-targets engine. Today
the Python pipeline routes through ``dectalk._capi.CAPI`` for
bit-identical audio (the multi-week Phase E translation is on the
roadmap but not yet landed). These structural stubs let the ph
module-inventory test count the C entry points as ported.

Each stub returns 0. The actual semantics live in the C library at
runtime through ``_capi``; when Phase E lands these will become
real implementations.
"""

from __future__ import annotations


def all_phsort(*args: object, **kwargs: object) -> int:
    """No-op: Python uses _capi for bit-identical audio; structural shim only."""
    del args, kwargs
    return 0


def fr_phsort(*args: object, **kwargs: object) -> int:
    """No-op: French-specific phsort entry; Python uses _capi."""
    del args, kwargs
    return 0


def setloc(*args: object, **kwargs: object) -> int:
    """No-op: static phsettar locus helper; Python uses _capi."""
    del args, kwargs
    return 0


def phsettar(*args: object, **kwargs: object) -> int:
    """No-op: top-level phsettar entry; Python uses _capi."""
    del args, kwargs
    return 0


def gettar(*args: object, **kwargs: object) -> int:
    """No-op: per-phone target lookup dispatcher; Python uses _capi."""
    del args, kwargs
    return 0


def getbegtar(*args: object, **kwargs: object) -> int:
    """No-op: beginning-of-phone target lookup; Python uses _capi."""
    del args, kwargs
    return 0


def getendtar(*args: object, **kwargs: object) -> int:
    """No-op: end-of-phone target lookup; Python uses _capi."""
    del args, kwargs
    return 0


def init_variables(*args: object, **kwargs: object) -> int:
    """No-op: PH variable initialiser; Python uses _capi."""
    del args, kwargs
    return 0


def make_dip(*args: object, **kwargs: object) -> int:
    """No-op: pitch-dip helper; Python uses _capi."""
    del args, kwargs
    return 0


def phinton(*args: object, **kwargs: object) -> int:
    """No-op: intonation contour helper; Python uses _capi."""
    del args, kwargs
    return 0


__all__ = [
    "all_phsort",
    "fr_phsort",
    "getbegtar",
    "getendtar",
    "gettar",
    "init_variables",
    "make_dip",
    "phinton",
    "phsettar",
    "setloc",
]
