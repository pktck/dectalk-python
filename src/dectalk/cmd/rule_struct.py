"""Rule-table entry struct from par_def.h.

Translated from ``src/dapi/src/cmd/par_def.h``. A ``rule_t`` is one
compiled rule in the CMD parser's rule table — header fields
followed by the variable-length rule body.

The header carries:
  - Special-rule tag (0 = normal, 1 = stop, 2 = return, 3 = goto,
    4 = goret).
  - Tag-specific data (special_value).
  - Language and mode bitmasks (lang_flag / mode_flag).
  - Rule number plus the four "go-to" targets for hit/miss/
    goret-hit/goret-miss outcomes.
  - Dictionary hit/miss flag.

The Python port stores the rule body as :class:`bytes` instead of
the C source's fixed-size ``unsigned char rule[300]`` buffer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

PAR_MAX_RULE_LENGTH: Final[int] = 300
"""Maximum length of a rule body (matches par_def.h)."""


@dataclass(slots=True)
class Rule:
    """One compiled rule in the CMD parser's rule table.

    Faithful translation of:

    .. code-block:: c

        struct rule_struct {
            S16 special_rule;
            S16 special_value;
            S32 lang_flag;
            S32 mode_flag;
            S16 rule_number;
            S16 next_hit_rule;
            S16 next_miss_rule;
            S16 next_goret_hit;
            S16 next_goret_miss;
            S16 dict_flag;
            unsigned char rule[PAR_MAX_RULE_LENGTH];
        };

    Attributes:
        special_rule: 0 normal, 1 stop, 2 return, 3 goto, 4 goret.
        special_value: Data for the special rule (target rule number,
            return value, etc.).
        lang_flag: Bitmask of languages this rule applies to.
        mode_flag: Bitmask of modes (citation, math, ...) gating the
            rule.
        rule_number: This rule's index in the table.
        next_hit_rule: Rule to jump to on match.
        next_miss_rule: Rule to jump to on miss.
        next_goret_hit: Subroutine rule on hit (return after).
        next_goret_miss: Subroutine rule on miss.
        dict_flag: Dictionary hit/miss flag.
        rule: Rule-body bytes (left-side / context / right-side /
            action / states — interpreted by the rule matcher).
    """

    special_rule: int = 0
    special_value: int = 0
    lang_flag: int = 0
    mode_flag: int = 0
    rule_number: int = 0
    next_hit_rule: int = 0
    next_miss_rule: int = 0
    next_goret_hit: int = 0
    next_goret_miss: int = 0
    dict_flag: int = 0
    rule: bytes = b""


__all__ = ["PAR_MAX_RULE_LENGTH", "Rule"]
