"""LTS-thread instance data struct (LTS_T) from ls_data.h.

Translated from ``src/dapi/src/lts/ls_data.h`` lines 138-243.

``LTS_T`` is the per-thread LTS module instance state — the
aggregate that holds the letter-to-sound state as it walks
a word's grapheme stream and emits phonemes.

Key fields:

- ``cword`` / ``rword`` — current word being scanned (left/right).
- ``phead`` — head of the phone-list linked list.
- ``cgraph`` / ``rgraph`` — current grapheme being scanned.
- ``wstate`` — wh-word detection state (UNK_WH/IS_WH/NOT_WH).
- ``fc_struct`` / ``word_info`` — per-word feature/form-class arrays.
- ``citem`` / ``nitem`` / ``ritem`` — current / next / right item.
- ``rule_*`` — rule-engine cursor state.

All scalar fields default to 0; arrays default to empty lists;
nested-struct fields default to ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class LtsT:
    """LTS-thread instance data (LTS_T in C)."""

    rpart: int = 0
    bachus_wordgrammarinfo: object | None = None  # wordgrammarinfo
    graph: list[int] = field(default_factory=list[int])
    pflp: object | None = None  # PHONE
    sylp: list[int] = field(default_factory=list[int])
    nsyl: int = 0
    rsyl: int = 0
    psyl: int = 0
    lphone: int = 0
    comp_str: list[int] = field(default_factory=list[int])
    str_vowel: int = 0
    indexes: list[int] = field(default_factory=list[int])
    num_indexes: int = 0
    cur_index: int = 0
    first_pass: int = 0
    pro_markers: list[int] = field(default_factory=list[int])
    length: int = 0
    input_array: list[int] = field(default_factory=list[int])
    cur_input_pos: int = 0
    cur_read_pos: int = 0
    word_info: list[int] = field(default_factory=list[int])
    word_data: list[int] = field(default_factory=list[int])
    command_data: list[int] = field(default_factory=list[int])
    current_word_pos: int = 0
    last_phones: list[int] = field(default_factory=list[int])
    last_phone_pos: int = 0
    num_words: int = 0
    end_of_sentence_found: int = 0
    cur_word_index: int = 0
    fc_struct: list[int] = field(default_factory=list[int])
    fc_index: int = 0
    old_fc_index: int = 0
    wstate: int = 0
    phead: object | None = None  # PHONE
    fchar: int = 0
    schar: int = 0
    no_pars: int = 0
    abbrev_look: int = 0
    lflag: int = 0
    isnumabr: int = 0
    citem: object | None = None  # ITEM
    nitem: object | None = None  # ITEM
    cword: list[int] = field(default_factory=list[int])
    nword: list[int] = field(default_factory=list[int])
    tlflag: int = 0
    sign: int = 0
    lbphone: int = 0
    rbphone: int = 0
    pflag: int = 0
    hit_type: int = 0
    name: list[int] = field(default_factory=list[int])
    name_size: int = 0
    pnode: list[int] = field(default_factory=list[int])
    namef: int = 0
    ord: int = 0
    flag: int = 0
    dic_offset: int = 0
    got_quote: int = 0
    precedent: list[int] = field(default_factory=list[int])
    PilSauv: list[int] = field(default_factory=list[int])
    PtPilSauv: int = 0
    Tamp: object | None = None  # TypTamp
    F_CodBl: int = 0
    Ph1: list[int] = field(default_factory=list[int])
    Ph2: list[int] = field(default_factory=list[int])
    contgc: int = 0


__all__ = ["LtsT"]
