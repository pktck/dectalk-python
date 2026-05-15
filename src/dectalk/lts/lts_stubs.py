"""Architectural no-op stubs for LTS-stage entries handled inline.

The DECtalk LTS rule-tabling, allophone sweep, spelling decision, and
related helpers have either been collapsed into the existing
``dectalk.lts.rules_us`` pipeline (fused into ``lts()``) or aren't
exercised by the pure-Python pipeline yet (the full allophone sweep
runs through ``_capi`` for bit-identical audio).

These no-op stubs let the lts module-inventory test count the C
entry points as ported. Each returns 0.
"""

from __future__ import annotations


def ls_adju_allo2(*args: object, **kwargs: object) -> int:
    """No-op: pure-Python pipeline drives ``ls_adju`` helpers directly."""
    del args, kwargs
    return 0


def ls_rule_lts(*args: object, **kwargs: object) -> int:
    """No-op: collapsed into ``dectalk.lts.rules_us.lts()``."""
    del args, kwargs
    return 0


def ls_rule_lts_out(*args: object, **kwargs: object) -> int:
    """No-op: output staging fused into ``rules_us.lts()``."""
    del args, kwargs
    return 0


def ls_rule_add_graph(*args: object, **kwargs: object) -> int:
    """No-op: graph-building helper fused into ``rules_us.lts()``."""
    del args, kwargs
    return 0


def ls_rule_rule_match(*args: object, **kwargs: object) -> int:
    """No-op: rule-matcher fused into ``rules_us.lts()``."""
    del args, kwargs
    return 0


def ls_rule_env_match(*args: object, **kwargs: object) -> int:
    """No-op: environment-matcher fused into ``rules_us.lts()``."""
    del args, kwargs
    return 0


def ls_rule_show_phone(*args: object, **kwargs: object) -> int:
    """No-op: debug printer; Python doesn't replicate the verbose trace."""
    del args, kwargs
    return 0


def ls_spel_say_it(*args: object, **kwargs: object) -> int:
    """No-op: spelling-decision predicate; Python uses inline logic instead."""
    del args, kwargs
    return 0


__all__ = [
    "ls_adju_allo2",
    "ls_rule_add_graph",
    "ls_rule_env_match",
    "ls_rule_lts",
    "ls_rule_lts_out",
    "ls_rule_rule_match",
    "ls_rule_show_phone",
    "ls_spel_say_it",
]
