"""CMD-thread instance data struct (CMD_T) from cm_data.h.

Translated from ``src/dapi/src/cmd/cm_data.h`` lines 129-267.

``CMD_T`` is the per-thread CMD module instance state — the
aggregate that holds the inline-command parser's state as it
walks a stream of input characters and emits commands plus text.

Key fields:

- ``params`` / ``defaults`` / ``string_buff`` — parser scratch
  arrays holding the in-progress command being parsed.
- ``parse_state`` — current ``STATE_*`` enum (NORMAL / BRACKET /
  COMMAND / PHONEME / PARAM / TOSS / KEEP).
- ``error_mode`` / ``punct_mode`` — ``ERROR_*`` / ``PUNCT_*`` modes.
- ``esc_seq`` / ``command_seq`` — ANSI escape-sequence buffers.
- ``setv[10]`` — saved-command record from the ``[:setv]`` /
  ``[:loadv]`` pair.

All scalar fields default to 0; arrays default to empty lists;
nested-struct fields default to ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CmdT:
    """CMD-thread instance data (CMD_T in C). 55 fields total."""

    params: list[int] = field(default_factory=list[int])
    setv: list[int] = field(default_factory=list[int])
    pString: list[bytes] = field(default_factory=list[bytes])  # noqa: N815
    defaults: list[int] = field(default_factory=list[int])
    param_index: int = 0
    p_count: int = 0
    cmd_p_flag: int = 0
    q_flag: int = 0
    international_flag: int = 0
    international_temp: int = 0
    international_phon_lang: int = 0
    cm: list[int] = field(default_factory=list[int])
    total_matches: int = 0
    cmd_index: int = 0
    last_char: int = 0
    string_buff: list[int] = field(default_factory=list[int])
    next_char: int = 0
    format_index: int = 0
    parse_state: int = 0
    error_mode: int = 0
    punct_mode: int = 0
    skip_mode: int = 0
    lastchar: int = 0
    last_punct: int = 0
    esc_command: int = 0
    cmd_count: int = 0
    cmd_number: int = 0
    insertflag: int = 0
    esc_seq: object | None = None  # INPUT_SEQ
    ParseChar: int = 0
    tone_wait: int = 0
    last_wait: int = 0
    dtmf_start_clock: object | None = None  # long
    dtmf_stop_clock: object | None = None  # long
    input_counter: int = 0
    index_counter: int = 0
    roll_text: int = 0
    email_header: int = 0
    clausebuf: list[int] = field(default_factory=list[int])
    wordbuf: list[int] = field(default_factory=list[int])
    output_buf: list[int] = field(default_factory=list[int])
    new_input: list[int] = field(default_factory=list[int])
    dict_hit_buf: list[int] = field(default_factory=list[int])
    input_indexes: list[int] = field(default_factory=list[int])
    new_input_indexes: list[int] = field(default_factory=list[int])
    output_indexes: list[int] = field(default_factory=list[int])
    match_array: object | None = None  # match_arrays_t
    prevword: int = 0
    prev_word_index: int = 0
    done: int = 0
    ret_value: object | None = None  # return_value_t
    timeout: int = 0
    bracket_space: int = 0
    letter_mode_flag: int = 0
    lpchar: int = 0
    postel: int = 0
    digcnt: int = 0
    laschar: int = 0
    dcnt: int = 0
    heldchar: list[int] = field(default_factory=list[int])
    last_was_phoneme: int = 0
    hold_phonemes: int = 0
    hold_strbuf: list[int] = field(default_factory=list[int])
    hold_count: int = 0
    hold_q_flag: int = 0
    hold_international_flag: int = 0
    hold_international_temp: int = 0
    hold_international_phon_lang: int = 0
    hold_replay_ignore: int = 0


__all__ = ["CmdT"]
