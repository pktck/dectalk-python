r"""Clause-segmentation architectural shim from cm_text.c.

Architectural shim for ``src/dapi/src/cmd/cm_text.c`` lines 276-1301
(``void cm_text_getclause(LPTTS_HANDLE_T phTTS)``).

The C body runs a per-character state machine over an inter-thread
``cmd_pipe`` -- reading one character at a time via ``read_pipe``,
appending it to ``pCmd_t->clausebuf`` at offset ``input_counter``,
and setting ``pCmd_t->done`` to ``1`` (or ``2`` for rolling-buffer
splits) once a clause boundary is recognised. The boundary is the
combination of:

* a clause-terminating punctuation byte (``.``, ``!``, ``?``, ``;``,
  ``:``, ``,``) -- ``char_types[c] & MARK_clause`` from
  :mod:`dectalk.cmd.char_types_table`.
* immediately followed by a ``MARK_space`` byte (or the ``0x82``
  inline-DM control byte).

The state machine also tracks two side-channel fields:

* ``parser_flag`` (U16) -- preserved across calls via
  ``pCmd_t->ret_value.parser_flag`` so the rule-table parser keeps
  context.
* ``temp_mode`` (U32) -- assembled from ``punct_mode``, the
  ``MODE_EMAIL`` flag and the ``email_header`` slot before each
  ``par_process_input`` call.

Phonemic-mode bracketing uses the ``0x80`` / ``0x81`` byte pair:
the LTS engine emits ASCKY phonemes for any bytes between those
markers. Index markers (``[:index <N>]``) accumulate in
``pCmd_t->input_indexes`` and are surfaced via
``pCmd_t->index_counter``.

The Python port operates on the full input string in one pass and
routes the actual clause-segmentation through
:mod:`dectalk._capi` -- this module captures the structural output
shape of one boundary detection (the clause text, the parser_flag
side-channel, the temp_mode bits, the index-marker positions and
the boundary-character code) so the rest of the parser machinery
can import a stable signature today.

The boundary-type codes match the C source's ``MARK_clause``
member ASCII bytes; they are exposed as module-level constants so
callers can switch on them without re-deriving them from
``char_types``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from dectalk.cmd.char_types_table import MARK_clause, MARK_space, char_types

# Boundary-type codes. These match the literal ASCII byte that
# triggered the boundary in the C source (cm_text.c only looks at
# ``MARK_clause`` bytes after the most recent non-space, so the
# byte value uniquely identifies which punctuation closed the
# clause). ``BOUNDARY_NONE`` is used when the input ran out before
# any clause-terminating punctuation was seen.

BOUNDARY_NONE: Final[int] = 0
"""No clause-terminating punctuation was seen in the input."""

BOUNDARY_PERIOD: Final[int] = ord(".")
"""A ``.`` ended the clause (statement)."""

BOUNDARY_EXCLAIM: Final[int] = ord("!")
"""A ``!`` ended the clause (exclamation)."""

BOUNDARY_QUESTION: Final[int] = ord("?")
"""A ``?`` ended the clause (question)."""

BOUNDARY_COMMA: Final[int] = ord(",")
"""A ``,`` ended the clause (intra-sentence pause)."""

BOUNDARY_SEMICOLON: Final[int] = ord(";")
"""A ``;`` ended the clause (semicolon)."""

BOUNDARY_COLON: Final[int] = ord(":")
"""A ``:`` ended the clause (colon)."""


# Phonemic-mode bracket bytes. The LTS engine treats any bytes
# between ``PHONEMIC_ON`` and ``PHONEMIC_OFF`` as ASCKY phonemes,
# even when the surrounding clause is regular text.
PHONEMIC_ON: Final[int] = 0x80
"""Inline ``[:phoneme arpabet on]`` marker -- start of an ASCKY run."""

PHONEMIC_OFF: Final[int] = 0x81
"""Inline ``[:phoneme arpabet off]`` marker -- end of an ASCKY run."""

# Inline DM (display-mode) control byte. The C source treats this
# like a space when scanning for clause boundaries (see the
# ``MARK_space | 0x82`` checks throughout cm_text_getclause).
INLINE_DM: Final[int] = 0x82


@dataclass
class ClauseSegmentation:
    r"""One clause-boundary detection.

    Mirrors the per-iteration output shape of the C state machine in
    ``cm_text_getclause``: the text accumulated into
    ``pCmd_t->clausebuf`` up to the boundary, plus the U16
    ``parser_flag`` and U32 ``temp_mode`` side-channels and the
    index-marker positions.

    Attributes:
        clause_text: The assembled clause text. Mirrors
            ``pCmd_t->clausebuf`` after the C body's
            ``clausebuf[input_counter] = '\0'`` line. The terminating
            NUL is *not* included in the Python value.
        parser_flag: The ``pCmd_t->ret_value.parser_flag`` U16
            preserved across calls. ``0`` on the first boundary.
        mode: The U32 ``temp_mode`` assembled from ``punct_mode``,
            ``MODE_EMAIL`` and ``email_header`` before
            ``par_process_input`` is called. ``0`` when no mode bits
            are active.
        index_markers: Positions (byte offsets into
            :attr:`clause_text`) of any ``[:index <N>]`` markers
            that the inline-command parser saw inside the clause.
            Empty when ``pCmd_t->index_counter == 0``.
        boundary_type: One of :data:`BOUNDARY_NONE`,
            :data:`BOUNDARY_PERIOD`, :data:`BOUNDARY_EXCLAIM`,
            :data:`BOUNDARY_QUESTION`, :data:`BOUNDARY_COMMA`,
            :data:`BOUNDARY_SEMICOLON`, :data:`BOUNDARY_COLON`.
    """

    clause_text: bytes
    parser_flag: int = 0
    mode: int = 0
    index_markers: list[int] = field(default_factory=lambda: [])
    boundary_type: int = BOUNDARY_NONE


def _is_clause_boundary(byte: int) -> bool:
    """Mirror ``char_types[c] & MARK_clause`` from the C source."""
    return bool(char_types[byte] & MARK_clause)


def _is_space_or_dm(byte: int) -> bool:
    """Mirror ``(char_types[c] & MARK_space) || c == 0x82`` from the C source."""
    return bool(char_types[byte] & MARK_space) or byte == INLINE_DM


def cm_text_getclause(text: bytes, phoneme_mode: bool = False) -> list[ClauseSegmentation]:
    """Segment ``text`` into clauses.

    Architectural shim. The Python port does not own the real
    clause-segmentation logic -- :mod:`dectalk._capi` routes the
    full input through the C library when bit-accurate output is
    required, and the synchronous Python fallback pipeline already
    operates on whole strings rather than driving a state machine
    one character at a time. This function captures the
    *structural* shape of the C body's output so callers can
    interface with the eventual full port through a stable
    signature.

    Args:
        text: The clause-input bytes that the synchronous Python
            pipeline already has in hand. May be empty.
        phoneme_mode: Whether we are inside an open
            ``[:phoneme arpabet on]`` block (``0x80``/``0x81``
            bracketing). When ``True`` the shim does not split on
            clause punctuation -- the LTS engine wants the entire
            phonemic span as a single segmentation.

    Returns:
        One :class:`ClauseSegmentation` per detected boundary. The
        last segmentation in the list always corresponds to the
        text after the final boundary (or the entire text when no
        boundary was found). Empty input returns an empty list.
    """
    if not text:
        return []

    # Phonemic-mode short-circuit. The C source emits every byte
    # between 0x80 and 0x81 verbatim through the phonemic path;
    # clause punctuation inside the bracketed run does not
    # terminate the clause.
    if phoneme_mode:
        return [ClauseSegmentation(clause_text=bytes(text), boundary_type=BOUNDARY_NONE)]

    segments: list[ClauseSegmentation] = []
    parser_flag = 0
    mode = 0
    start = 0
    index_markers: list[int] = []

    i = 0
    n = len(text)
    while i < n:
        byte = text[i]
        if _is_clause_boundary(byte):
            # Boundary candidate: a MARK_clause byte must be followed by
            # MARK_space (or INLINE_DM, or end-of-input) to flush. This
            # mirrors the C body's check at line 481:
            #
            #     if ((char_types[clausebuf[input_counter-1]] & MARK_space)
            #         || clausebuf[input_counter-1] == 0x82)
            #         && (char_types[clausebuf[input_counter-2]] & MARK_clause)
            j = i + 1
            if j >= n or _is_space_or_dm(text[j]):
                # The C source's ``clausebuf`` includes the boundary
                # punctuation byte itself but not the trailing
                # whitespace -- the parser's ``input_counter`` reset
                # discards the space (and the C body even prefills
                # ``clausebuf[0] = ' '`` on the next clause). Mirror
                # that: keep the boundary byte in the clause text,
                # consume any run of whitespace / 0x82 control bytes
                # before starting the next clause.
                segments.append(
                    ClauseSegmentation(
                        clause_text=bytes(text[start:j]),
                        parser_flag=parser_flag,
                        mode=mode,
                        index_markers=list(index_markers),
                        boundary_type=byte,
                    )
                )
                index_markers = []
                # Skip the boundary whitespace run.
                while j < n and _is_space_or_dm(text[j]):
                    j += 1
                start = j
                i = j
                continue
        i += 1

    # Trailing text after the last boundary (or all of it, if no
    # boundary was hit) becomes one final segmentation. The C body
    # does the equivalent when ``done == 0`` and the input buffer
    # is shorter than ``PAR_ROLLING_STOP_VALUE`` -- callers see
    # one final flush.
    if start < n:
        segments.append(
            ClauseSegmentation(
                clause_text=bytes(text[start:n]),
                parser_flag=parser_flag,
                mode=mode,
                index_markers=list(index_markers),
                boundary_type=BOUNDARY_NONE,
            )
        )

    return segments


__all__ = [
    "BOUNDARY_COLON",
    "BOUNDARY_COMMA",
    "BOUNDARY_EXCLAIM",
    "BOUNDARY_NONE",
    "BOUNDARY_PERIOD",
    "BOUNDARY_QUESTION",
    "BOUNDARY_SEMICOLON",
    "INLINE_DM",
    "PHONEMIC_OFF",
    "PHONEMIC_ON",
    "ClauseSegmentation",
    "cm_text_getclause",
]
