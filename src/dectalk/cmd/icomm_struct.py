"""Immediate-command struct from cm_data.h.

Translated from ``src/dapi/src/cmd/cm_data.h``. ``ICOMM_T`` is a
small struct the CMD parser uses to hold an immediate (in-line)
command's text plus a loop-detection counter.

The C source defines a 60-byte command-text buffer; the Python
port stores the text as :class:`bytes` so callers don't have to
manage the buffer's NUL terminator.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class IComm:
    """Immediate-command buffer used by the CMD parser.

    Faithful translation of:

    .. code-block:: c

        typedef struct ICOMM_TAG {
            char cmd[60];
            short seen;     // loop-detect counter
        } ICOMM_T, *PICOMM_T;

    Attributes:
        cmd: Command text as bytes (the C source has a fixed
            ``char[60]`` buffer; Python uses a variable-length
            :class:`bytes` blob terminated implicitly).
        seen: Loop-detection counter — bumped each time the parser
            re-encounters this command without making progress.
    """

    cmd: bytes = b""
    seen: int = 0


__all__ = ["IComm"]
