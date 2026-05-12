"""NEW_LTS word-tracking structs from ls_data.h.

Translated from ``src/dapi/src/lts/ls_data.h``. Two dataclasses
the NEW_LTS build uses to track per-word state across the parse
pipeline:

- :class:`CommandData` — one entry in the command stream associated
  with a word (e.g. an inline ``[:rate 200]`` command applied to a
  particular word).
- :class:`WordStruct` — the per-word state record carrying mode
  flags, parse flags, LTS flags, form-class, dict / suffix /
  command indices, pronunciation flag, dict-type / hit-type /
  command-index / num-commands / homograph fields.

Lives behind the NEW_LTS macro in C; the Python port translates
the data shape without gating on the build flag.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CommandData:
    """One command attached to a word in the new-LTS pipeline.

    Faithful translation of:

    .. code-block:: c

        typedef struct command_data_tag {
            U16 command;
            U16 nextra[3];
        } command_data_t;

    Attributes:
        command: 16-bit command code (matches the inline command
            phoneme codes in :mod:`dectalk.include.cmd_codes`).
        nextra: 3-entry array of additional command parameters.
    """

    command: int = 0
    nextra: list[int] = field(default_factory=lambda: [0, 0, 0])


@dataclass(slots=True)
class WordStruct:
    """Per-word state record in the new-LTS pipeline.

    Faithful translation of:

    .. code-block:: c

        typedef struct word_struct_tag {
            U32 mode_flag;
            U32 parse_flags;
            U32 lts_flags;
            U32 form_class;
            U16 data_index;
            U16 dict_index;
            U16 suff_index;
            U16 pron_flag;
            U8  dict_type;
            U8  dict_hit_type;
            U8  command_index;
            U8  num_commands;
            U8  homograph;
        } word_struct_t;

    Attributes:
        mode_flag: 32-bit copy of the kernel ``modeflag`` at the
            time this word was scanned.
        parse_flags: 32-bit PRO_* flags (see
            :mod:`dectalk.lts.pro_flags`).
        lts_flags: 32-bit LTS pipeline flags
            (:mod:`dectalk.lts.lts_flags`).
        form_class: 32-bit form-class mask
            (:mod:`dectalk.dic.form_class_bits`).
        data_index: Index into the word-data byte buffer.
        dict_index: Index into the dictionary entries.
        suff_index: Index into the suffix table.
        pron_flag: Pronunciation-specific bits
            (:mod:`dectalk.kernel.mode_flags` PRON_DIC_*).
        dict_type: Which dictionary slot matched (main / user /
            foreign).
        dict_hit_type: HIT / ABBREV result from the search.
        command_index: Offset into the per-word command_data array.
        num_commands: Number of commands attached to the word.
        homograph: Non-zero if a homograph disambiguation was
            chosen.
    """

    mode_flag: int = 0
    parse_flags: int = 0
    lts_flags: int = 0
    form_class: int = 0
    data_index: int = 0
    dict_index: int = 0
    suff_index: int = 0
    pron_flag: int = 0
    dict_type: int = 0
    dict_hit_type: int = 0
    command_index: int = 0
    num_commands: int = 0
    homograph: int = 0


@dataclass(slots=True)
class IndexInfo:
    """Index-marker info from ls_data.h.

    Faithful translation of:

    .. code-block:: c

        typedef struct index_info {
            U16 pos;
            S16 data[3];
        } index_info_t;

    Attributes:
        pos: Position offset where the index marker was hit.
        data: 3-entry index payload.
    """

    pos: int = 0
    data: list[int] = field(default_factory=lambda: [0, 0, 0])


__all__ = ["CommandData", "IndexInfo", "WordStruct"]
