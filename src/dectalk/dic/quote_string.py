"""``quote_string`` -- wrap a byte string in matching quote delimiters.

Translated from ``src/dapi/src/dic/dic_comm.c`` lines 1081-1097. The
build-time dictionary compiler uses this helper to surround dictionary
entry strings with quotes that don't collide with their content:

- If the string starts with ``"``, wrap it in single quotes (``'``).
- Otherwise wrap it in double quotes (``"``).

The C source mutates a fixed-size buffer in place; Python returns a
new ``bytes`` value instead, since Python strings/bytes are immutable
and we have no caller that needs the in-place mutation contract.
"""

from __future__ import annotations


def quote_string(s: bytes) -> bytes:
    """Wrap ``s`` in matching quote delimiters.

    Faithful translation of the C body. Picks single quotes when the
    input starts with a double quote, otherwise double quotes.

    Args:
        s: Byte string to wrap. Quotes from the body are not escaped --
            the C source assumes the caller's input never embeds the
            chosen wrapping quote, and we mirror that.

    Returns:
        ``q + s + q`` where ``q`` is ``b'\''`` or ``b'"'``.
    """
    q = b"'" if s[:1] == b'"' else b'"'
    return q + s + q


__all__ = ["quote_string"]
