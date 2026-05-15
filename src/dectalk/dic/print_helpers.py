"""``print_fc`` / ``print_tf`` -- form-class and true/false debug printers.

Translated from ``src/dapi/src/dic/dic_comm.c`` lines 1048-1077. The
build-time dictionary compiler uses these two helpers to emit
human-readable strings for the form-class bitmask and the
true/false flags on each dictionary entry.

``print_fc(value, fp)`` writes the names of every set bit in ``value``
(or ``" none"`` if the value is 0), drawn from the 32-entry
``form_class_strings`` table. ``print_tf(value, fp)`` writes ``",T"``
or ``",F"`` depending on whether the input is non-zero.

The C source writes to a ``FILE*`` and returns void; the Python ports
return the produced string instead, so callers (and the tests) can
inspect the output without a file handle. Functional equivalence with
the C side is preserved: passing the returned string to ``fp.write``
reproduces the C ``fprintf`` behaviour exactly.
"""

from __future__ import annotations

# Mirror of ``form_class_strings[]`` from dic_comm.c line 1010. Note
# the deliberate leading space and the two ``" unused"`` slots at
# bits 27 and 28 -- these match the C array byte-for-byte.
form_class_strings: tuple[str, ...] = (
    " adj",
    " adv",
    " art",
    " aux",
    " be",
    " bev",
    " conj",
    " ed",
    " have",
    " ing",
    " noun",
    " pos",
    " prep",
    " pron",
    " subj",
    " that",
    " to",
    " verb",
    " who",
    " neg",
    " intr",
    " ref",
    " part",
    " func",
    " cont",
    " char",
    " refr",
    " unused",
    " unused",
    " mark",
    " cont",
    " homo",
)


def print_fc(fc_val: int) -> str:
    """Return the rendered form-class string for the given bitmask.

    Faithful translation of:

    .. code-block:: c

        if(fc_val) {
            fc_mask = 1;
            for(i=0;i<32;i++) {
                if(fc_val & fc_mask)
                    fprintf(fp,"%s",form_class_strings[i]);
                fc_mask = fc_mask*2;
            }
        } else
            fprintf(fp," none");

    Args:
        fc_val: 32-bit form-class bitmask. Each set bit emits the
            corresponding entry from :data:`form_class_strings`.

    Returns:
        The concatenated form-class strings, or ``" none"`` for 0.
    """
    if not fc_val:
        return " none"
    out: list[str] = []
    fc_mask = 1
    for i in range(32):
        if fc_val & fc_mask:
            out.append(form_class_strings[i])
        fc_mask *= 2
    return "".join(out)


def print_tf(val: int) -> str:
    """Return ``",T"`` for non-zero, ``",F"`` for zero.

    Faithful translation of the C ternary form ``,T``/``,F``.
    """
    return ",T" if val else ",F"


__all__ = ["form_class_strings", "print_fc", "print_tf"]
