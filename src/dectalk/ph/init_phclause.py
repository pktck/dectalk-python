"""Per-clause PH state initializer from ph_claus.c.

Translated from ``src/dapi/src/ph/ph_claus.c`` lines 575-612.

The PH module calls :func:`init_phclause` at the start of each
clause to clear the per-clause scratch arrays (``allophons``,
``allofeats``, ``allodurs``, ``f0tar``, ``f0tim``) and re-seed
the offset-window pointers that index into those arrays from the
``SAFETY``-th element.

The C source uses raw arrays of fixed size ``NPHON_MAX + SAFETY +
2``. The Python port grows each list to the same size and zeros
every element. The offset-window views (``phonemes``,
``sentstruc``, etc.) are not implemented as Python *views* —
callers should index ``allophons[SAFETY + i]`` directly, but for
parity we expose helper attribute references back to the array.

This is the first state-mutating Phase F function — it consumes
a :class:`dectalk.ph.dph_t.DphT` instance and mutates its array
fields in-place.

Field-by-field audit vs C oracle (issue #74)
--------------------------------------------

The C function in ``ph_claus.c`` zeroes **only** the five arrays
listed below and resets two scalars. Every other ``DPH_T`` field
is *intentionally* left untouched — the per-clause init is a
scratch-buffer reset, not a struct-wide reset. The Python port
matches this contract exactly:

.. list-table::
   :header-rows: 1

   * - Field
     - C default after ``init_phclause``
     - Python default
   * - ``allophons``
     - zeros, length ``NPHON_MAX + SAFETY + 2``
     - same
   * - ``allofeats``
     - zeros, length ``NPHON_MAX + SAFETY + 2``
     - same
   * - ``allodurs``
     - zeros, length ``NPHON_MAX + SAFETY + 2``
     - same
   * - ``f0tar``
     - zeros, length ``NPHON_MAX + SAFETY + 2``
     - same
   * - ``f0tim``
     - zeros, length ``NPHON_MAX + SAFETY + 2``
     - same
   * - ``fvvtran``
     - 0
     - 0
   * - ``bvvtran``
     - 0
     - 0
   * - ``phonemes``
     - ``&allophons[SAFETY]`` (pointer into array)
     - aliases ``allophons`` (see note below)
   * - ``sentstruc``
     - ``&allofeats[SAFETY]``
     - aliases ``allofeats``
   * - ``user_durs``
     - ``&allodurs[SAFETY]``
     - aliases ``allodurs``
   * - ``user_f0``
     - ``&f0tar[SAFETY]``
     - aliases ``f0tar``
   * - ``user_offset``
     - ``&f0tim[SAFETY]``
     - aliases ``f0tim``
   * - ``fconsfeats``
     - zeroed only if ``FRENCH`` is defined
     - untouched (no FRENCH build in this port)
   * - ``new_sentence``
     - ``TRUE`` only if ``GERMAN`` is defined
     - untouched (no GERMAN build in this port)

Window-pointer convention
~~~~~~~~~~~~~~~~~~~~~~~~~

In C the five window pointers (``phonemes``, ``sentstruc``,
``user_durs``, ``user_f0``, ``user_offset``) point at the
``SAFETY``-th element of the underlying array — so
``phonemes[i]`` in C equals ``allophons[SAFETY + i]``. The Python
port aliases the *whole* parent list instead, so
``p_dph_t.phonemes[i]`` equals ``p_dph_t.allophons[i]``. All
in-tree Python callers use this no-offset convention; the SAFETY
offset is folded into the parent array's index space at the
boundary (e.g. ``allophons[0]`` is the first real phoneme slot in
Python, whereas in C the first real phoneme lives at
``allophons[SAFETY]``). See ``api/speak.py`` for the canonical
caller pattern.

Fields **not** zeroed (verified against C)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These DPH_T fields are *not* touched by ``init_phclause`` and
keep their previous values (or the zero from ``calloc`` on the
very first clause):

- ``alloopenq`` — open-quotient per-phoneme array. Overwritten
  fresh during phoneme processing each clause, so re-zeroing is
  unnecessary.
- ``symbols`` / ``nsymbtot`` / ``nphonetot`` / ``nallotot`` —
  written by upstream parsing.
- ``wordclass`` — written by the front-end.
- All scalars except ``fvvtran`` and ``bvvtran`` — voice / speaker
  / timing state that survives a clause boundary.

The unit test ``tests/unit/test_ph_init_phclause.py`` enforces
all of the above invariants.
"""

from __future__ import annotations

from dectalk.ph.dph_t import DphT
from dectalk.ph.inton_constants import SAFETY
from dectalk.ph.numeric_constants import NPHON_MAX

_BUF_SIZE: int = NPHON_MAX + SAFETY + 2


def init_phclause(p_dph_t: DphT) -> None:
    """Initialise per-clause arrays on ``p_dph_t``.

    Faithful translation of:

    .. code-block:: c

        void init_phclause(PDPH_T pDph_t) {
            int i;
            for (i = 0; i < (NPHON_MAX + SAFETY + 2); i++) {
                pDph_t->allophons[i] = 0;
                pDph_t->allofeats[i] = 0;
                pDph_t->allodurs[i] = 0;
                pDph_t->f0tar[i] = 0;
                pDph_t->f0tim[i] = 0;
            }
            pDph_t->fvvtran = 0;
            pDph_t->bvvtran = 0;

            pDph_t->phonemes   = &(pDph_t->allophons[SAFETY]);
            pDph_t->sentstruc  = &(pDph_t->allofeats[SAFETY]);
            pDph_t->user_durs  = &(pDph_t->allodurs[SAFETY]);
            pDph_t->user_f0    = &(pDph_t->f0tar[SAFETY]);
            pDph_t->user_offset = &(pDph_t->f0tim[SAFETY]);
        }

    The 5 offset-window pointer fields (``phonemes``,
    ``sentstruc``, ``user_durs``, ``user_f0``, ``user_offset``)
    in C are pointers to the ``SAFETY``-th element of the
    underlying array. The Python port can't faithfully model
    pointer aliasing, so we record the parent array on the
    pointer field — callers access ``p_dph_t.phonemes[i]`` and
    the caller-side code does the ``+SAFETY`` index adjustment.

    Args:
        p_dph_t: The PH thread state instance to initialise.
    """
    # Re-allocate the 5 main per-clause arrays at full size with zeros.
    p_dph_t.allophons = [0] * _BUF_SIZE
    p_dph_t.allofeats = [0] * _BUF_SIZE
    p_dph_t.allodurs = [0] * _BUF_SIZE
    p_dph_t.f0tar = [0] * _BUF_SIZE
    p_dph_t.f0tim = [0] * _BUF_SIZE

    # Per-clause scalar resets.
    p_dph_t.fvvtran = 0
    p_dph_t.bvvtran = 0

    # The C source sets up SAFETY-offset window pointers.
    # In Python, we record the parent array on each pointer field —
    # readers index parent[SAFETY + i] explicitly.
    p_dph_t.phonemes = p_dph_t.allophons
    p_dph_t.sentstruc = p_dph_t.allofeats
    p_dph_t.user_durs = p_dph_t.allodurs
    p_dph_t.user_f0 = p_dph_t.f0tar
    p_dph_t.user_offset = p_dph_t.f0tim


__all__ = ["init_phclause"]
