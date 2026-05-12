"""Phoneme emitter and lphone tracking for the LTS pipeline.

The C source writes phoneme codes into an interprocess pipe via
``ls_util_send_phone(phTTS, ph)``, which also updates
``pLts_t->lphone`` (the last phone emitted, used by
:func:`ls_util_pluralize` and other downstream helpers).

This module models the minimum LTS thread state needed to port
the state-mutating "do_*" emit functions: an output queue plus the
``lphone`` tracker. Together they let us port :func:`ls_proc_do_sign`,
:func:`ls_proc_do_part_number`, :func:`ls_proc_do_date`, etc.
without yet modelling the full PLTS_T.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _empty_int_list() -> list[int]:
    """Default factory for :class:`LtsEmitter.phones`."""
    return []


@dataclass(slots=True)
class LtsEmitter:
    """Minimal LTS-side phoneme emitter / state holder.

    Mirrors the subset of ``pLts_t`` that the "do_*" emit functions
    in ``l_us_pr1.c`` and friends touch:

    Attributes:
        phones: Output queue. Every :meth:`send_phone` /
            :meth:`send_phone_list` call appends here.
        lphone: Last phoneme code emitted (the C source's
            ``pLts_t->lphone``). Used by :func:`ls_util_pluralize`
            etc. to make features-aware decisions about the next
            suffix.
        lbphone: Last "boundary" phone — typically WBOUND when
            we've just emitted a word boundary. Tracked because
            the C source resets it to WBOUND at word ends.
        rbphone: Same idea, paired with lbphone in the C source.
        schar: Separator character for numbers (e.g. ``,`` for
            "1,234"). US English uses ``,`` by default.
        fchar: Fractional separator (e.g. ``.`` for "3.14"). US
            English uses ``.``.
    """

    phones: list[int] = field(default_factory=_empty_int_list)
    lphone: int = 0
    lbphone: int = 0
    rbphone: int = 0
    schar: int = ord(",")
    fchar: int = ord(".")

    def send_phone(self, ph: int) -> None:
        """Emit a single phoneme code, updating :attr:`lphone`.

        Faithful translation of:

        .. code-block:: c

            void ls_util_send_phone(LPTTS_HANDLE_T phTTS, int ph) {
                // push ph into the pipe ...
                pLts_t->lphone = ph;
            }

        The C source does additional work (writes into a pipe,
        respects ``pKsd_t->halting``, etc.). For the in-memory
        port we just append to ``phones`` and update ``lphone``.

        Args:
            ph: The phoneme code to emit.
        """
        self.phones.append(ph)
        self.lphone = ph

    def send_phone_list(self, byte_string: bytes) -> None:
        """Emit a SIL-terminated list of phonemes.

        Faithful translation of:

        .. code-block:: c

            void ls_util_send_phone_list(LPTTS_HANDLE_T phTTS,
                                          const char *pp) {
                int ph;
                while ((ph = *pp++) != SIL && !pKsd_t->halting)
                    ls_util_send_phone(phTTS, ph);
            }

        The terminator is byte 0 (treated as SIL by the C source's
        loop condition). Calls :meth:`send_phone` for each byte so
        ``lphone`` is updated to the last non-SIL emission.

        Args:
            byte_string: Sequence of phoneme bytes terminated by 0.
        """
        for ph in byte_string:
            if ph == 0:
                break
            self.send_phone(ph)


__all__ = ["LtsEmitter"]
