r"""Bounded string-concatenation helper from kernel/loader.c.

Translated from ``src/dapi/src/kernel/loader.c`` line 238.

``mystrcat`` is a tiny pure leaf utility used by the kernel loader to
append the build's version / spoken-version banner into the fixed-size
``KS.version`` / ``KS.versionspeak`` byte buffers. It is a bounded
analogue of ``strcat`` that:

- scans ``dest`` for the existing NUL terminator,
- gives up (without modifying anything) if the destination is already
  within one byte of the buffer cap,
- otherwise copies bytes from ``src`` until either ``src`` hits NUL or
  the running offset would reach ``count - 2``, and finally
- writes the trailing ``'\\0'`` at the new end-of-string position.

The off-by-one boundary (``sofar < count - 2``) means the function
guarantees a NUL byte at index ``count - 1`` is never written to, but
the *highest* destination index it will write is ``count - 2`` (the
NUL terminator). That is, the function treats ``count`` as the total
buffer size and reserves the final slot.

The C source uses Microsoft-specific ``_far`` qualifiers and accepts
``unsigned char *`` pointers. The Python port operates on a mutable
``bytearray`` for ``dest`` (so it can write the NUL terminator and the
copied bytes back) and accepts any ``bytes``-like value for ``src``.
"""

from __future__ import annotations


def mystrcat(dest: bytearray, src: bytes, count: int) -> None:
    r"""Append ``src`` to NUL-terminated ``dest`` with a hard cap of ``count``.

    Faithful translation of:

    .. code-block:: c

        void mystrcat(unsigned char _far *dest,unsigned char _far *src, unsigned int count)
        {
            unsigned int sofar,inptr;
            for (sofar=0;dest[sofar]!='\\0';sofar++)
            ;
            inptr = 0;
            if (sofar>=count-1)
                return;
            while ((sofar<count-2) && (src[inptr]!='\\0'))
            {
                dest[sofar++] = src[inptr++];
            }
            dest[sofar] = '\\0';
            return;
        }

    The function scans ``dest`` forward until it finds the current NUL
    terminator, then copies bytes from ``src`` into the trailing slack
    space without ever writing past index ``count - 1``. The internal
    loop bound ``sofar < count - 2`` plus the final ``dest[sofar] = '\\0'``
    means the highest index written is ``count - 1`` (for ``count >= 2``
    when the destination has at least one slack byte).

    The early-return guard ``if (sofar >= count - 1)`` triggers when
    ``dest`` is already so long that no source byte can fit before the
    trailing NUL — in that case the function does **not** rewrite the
    terminator, leaving ``dest`` byte-identical to its input.

    The behaviour for ``count == 0`` or ``count == 1`` is preserved
    verbatim from the C source. With ``count == 0`` the unsigned
    arithmetic ``count - 1`` wraps to ``UINT_MAX`` in C — Python's
    arbitrary-precision integers make ``count - 1 == -1`` instead, and
    the ``sofar >= -1`` guard never fires for a non-negative ``sofar``.
    Callers in ``loader.c`` only ever pass ``count >= 5`` (the smallest
    buffer is ``" L M "`` into ``SPEAKLEN``), so the degenerate cases
    are not exercised by the binary.

    Args:
        dest: NUL-terminated destination buffer (mutated in place).
            Must have len >= ``count`` so the final NUL write does not
            raise ``IndexError``.
        src: Bytes to append. The first NUL byte (if any) ends the copy.
        count: Total size of the ``dest`` buffer in bytes. The function
            never writes past index ``count - 1``.
    """
    sofar = 0
    while dest[sofar] != 0:
        sofar += 1
    inptr = 0
    if sofar >= count - 1:
        return
    while sofar < count - 2 and inptr < len(src) and src[inptr] != 0:
        dest[sofar] = src[inptr]
        sofar += 1
        inptr += 1
    dest[sofar] = 0


__all__ = ["mystrcat"]
