"""Numeric-format chunk expansion — the ls_task.c number dispatch.

Mirrors the numeric sections of the C front end's per-word dispatch
(``src/dapi/src/lts/ls_task.c``, main loop lines 830-869):

- ``ls_task_set_sign_flag`` (ls_task.c:3089) — leading ``-`` / ``+``.
- ``ls_task_currency_processing`` (ls_task.c:3183) — ``$N`` /
  ``$N.NN`` / ``$N million`` (nwdtab lookahead).
- ``ls_task_date_processing`` (ls_task.c:3581) — ``23-Aug[-1984]``
  dates via :func:`~dectalk.lts.date_emit.ls_proc_do_date`, and
  ``H:MM[:SS]`` times via :func:`~dectalk.lts.time_emit.ls_proc_do_time`
  (with the C's am/pm lookahead exposed as :func:`am_pm_phonemes`).
- ``ls_task_frac_processing`` (ls_task.c:3679) — ``N/M[%]``
  fractions via :func:`~dectalk.lts.frac_emit.ls_proc_do_frac`.
- ``ls_task_plain_number_processing`` (ls_task.c:3738) — ordinal
  suffixes (``1st`` / ``42nd`` / ``103rd``, ls_task.c:3953), plural
  digits (``60s`` / ``60's``, ls_task.c:3934/3969), and signed
  integers (``-5`` → "minus five").
- ``ls_task_part_number`` (ls_task.c:4095) — digit/dash/slash part
  numbers (``10-20`` → "ten dash twenty") via
  :func:`~dectalk.lts.part_number_emit.ls_proc_do_part_number_full`.

Each branch emits C phoneme codes through an
:class:`~dectalk.lts.emitter.LtsEmitter` and renders them to the
2-bytes-per-code ASCII stream of ``TextToSpeechConvertToPhonemes``
via ``usa_arpa`` — the exact stringification the oracle applies —
so the result can be spliced verbatim into the phoneme stream that
:func:`dectalk.api.speak.text_to_dectalk_phonemes` byte-compares
against the C oracle.

Scope gates (deliberate fall-through to the legacy path, returning
``None``):

- non-ASCII chunks (the C library reads UTF-8 bytes as Latin-1;
  ``¢ £ ° ± ¼ ½`` behaviour is an encoding question, not a numeric
  one),
- pure digit strings (the corpus-proven ``_digit_expand`` path in
  ``speak.py`` owns those, including 4-digit year forms),
- NANP phone-number shapes (``DDD-DDDD`` / ``DDD-DDD-DDDD`` /
  ``D{1,3}-DDD-DDD-DDDD``) — the C handles those in the CMD-level
  NWS pre-processor, not the LTS number dispatch,
- ``M/D/Y`` slash dates claimed by :mod:`dectalk.kernel.normalize`,
- times with fractional-second tails (NWS pre-processed in C),
- ``%`` / cent / degree suffixes on plain numbers (NWS in C).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from dectalk.include.phoneme_codes import WBOUND, USPhoneme
from dectalk.include.usa_arpa import usa_arpa
from dectalk.lts.char_features import is_digit, ls_lower
from dectalk.lts.date_emit import ls_proc_do_date
from dectalk.lts.date_recognizer import (
    ls_proc_is_am_pm,
    ls_proc_is_date,
    ls_proc_is_frac,
    ls_proc_is_time,
)
from dectalk.lts.emitter import LtsEmitter
from dectalk.lts.frac_emit import ls_proc_do_frac
from dectalk.lts.number_emit import ls_proc_do_number_full
from dectalk.lts.number_tables import nwdtab
from dectalk.lts.parse_number import ls_task_parse_number
from dectalk.lts.part_number_emit import ls_proc_do_part_number_full
from dectalk.lts.phoneme_words import pand, pcent, pdollar
from dectalk.lts.pluralize import ls_util_pluralize
from dectalk.lts.proc_emit import ls_proc_do_sign_full
from dectalk.lts.spell_emit import ls_spel_spell
from dectalk.lts.time_emit import ls_proc_do_time
from dectalk.lts.util_helpers import ls_util_is_ordinal

_US_Z: Final[int] = int(USPhoneme.Z)
_US_S: Final[int] = int(USPhoneme.S)

_SIGN_CHARS: Final[frozenset[int]] = frozenset((ord("-"), ord("+")))
"""ASCII subset of the C sign set (``§ ± ¶`` are non-ASCII, gated out)."""

_CURRENCY_SIGNS: Final[frozenset[int]] = frozenset((ord("-"), ord("+")))
"""Signs accepted after ``$`` (C also takes Latin-1 ``±``)."""

_ORDINAL_SUFFIX_LEN: Final[int] = 2
_CENT_FRACTION_DIGITS: Final[int] = 2

_PART_NUMBER_RE: Final[re.Pattern[bytes]] = re.compile(rb"[0-9a-z/-]+")
_PART_ALPHA_RUN_RE: Final[re.Pattern[bytes]] = re.compile(rb"[a-z]+")
_PART_MAX_ALPHA_RUN: Final[int] = 2
"""Alpha runs of >= 3 chars go through ``ls_util_lookup`` in C — the
dictionary probe isn't wired into the Python part-number port, so
chunks containing them fall through to the legacy path."""

_TIME_RE: Final[re.Pattern[bytes]] = re.compile(rb"\d{1,2}:\d{2}(:\d{2})?")
"""Bare clock times. ``ls_proc_is_time`` also accepts fractional
seconds (``12:45:30.5``) but the C front end routes those through the
NWS pre-processor before the LTS ever sees them — gate them out."""

_PHONE_SHAPE_RES: Final[tuple[re.Pattern[bytes], ...]] = (
    re.compile(rb"\d{3}-\d{4}"),
    re.compile(rb"\d{3}-\d{3}-\d{4}"),
    re.compile(rb"\d{1,3}-\d{3}-\d{3}-\d{4}"),
)
"""NANP phone shapes the C NWS pre-processor claims (digit-by-digit
with COMMA pauses) before part-number processing can see them."""


@dataclass(frozen=True, slots=True)
class NumericExpansion:
    """Result of a successful numeric-chunk expansion.

    Attributes:
        phonemes: Raw DECtalk ASCII phoneme stream for the chunk —
            byte-identical to what ``convert_to_phonemes`` produces
            for the same chunk in isolation.
        consumed_next: True when ``next_word`` was folded into this
            expansion (the ``$5 million`` nwdtab lookahead) and the
            caller must skip it.
        is_time: True when the chunk was a clock time — the caller
            should check the following chunk against
            :func:`am_pm_phonemes` (the C am/pm lookahead).
    """

    phonemes: bytes
    consumed_next: bool = False
    is_time: bool = False


def _render(emitter: LtsEmitter) -> bytes:
    """Stringify emitted phoneme codes exactly like the C oracle.

    ``TextToSpeechConvertToPhonemes`` prints 2 ASCII bytes per code
    from ``usa_arpa`` (1-char codes carry a trailing space). Spell
    paths emit font-encoded codes (``0x1E00 | code`` from
    ``usa_ascky_rev``); the low byte is the plain code.
    """
    return b"".join(usa_arpa[2 * (c & 0xFF) : 2 * (c & 0xFF) + 2] for c in emitter.phones)


def _wlookup(word: bytes, table: bytes) -> bytes | None:
    """C ``ls_task_wlookup``: packed-record lookup with case folding.

    Records are ``<len><name><EOS=0><phonemes><SIL=0>``, ``len``
    counting from just after the length byte to the next record.
    Returns the SIL-terminated phoneme list on a full-word match.
    """
    tp = 0
    while tp < len(table) and table[tp] != 0:
        ln = table[tp]
        tp += 1
        cp = tp
        lp = 0
        while True:
            c = ls_lower[word[lp]] if lp < len(word) else 0
            if cp >= len(table) or c != table[cp]:
                break
            cp += 1
            if c == 0:
                end = table.find(b"\x00", cp)
                return table[cp : end if end >= 0 else len(table)]
            lp += 1
        tp += ln
    return None


def am_pm_phonemes(word: str) -> bytes | None:
    """Spelled am/pm following a clock time, or None.

    The C date path (``ls_task.c:3616-3646``) looks one word ahead
    after ``ls_proc_do_time`` and spells it (``ls_spel_spell``) when
    ``ls_proc_is_am_pm`` matches. Case-insensitive (the C word was
    case-folded by ``ls_task_remove_case``).
    """
    if not word or not word.isascii():
        return None
    lowered = bytes(ls_lower[b] for b in word.encode("ascii"))
    if not ls_proc_is_am_pm(lowered):
        return None
    emitter = LtsEmitter()
    ls_spel_spell(emitter, lowered)
    return _render(emitter)


def _currency(  # noqa: PLR0911, PLR0912 — mirrors the C branch ladder
    rest: bytes, sign: int, next_word: str | None
) -> NumericExpansion | None:
    """``ls_task_currency_processing`` (ls_task.c:3183-3555), US arm.

    ``$3`` → "three dollars"; ``$3.24`` → "three dollars and twenty
    four cents"; ``$3.00`` → "three dollars"; ``$3.240`` → "three
    point two four zero dollars"; ``$5 million`` → "five million
    dollars" (consuming the nwdtab scale word).
    """
    i = 1  # past '$'
    if i == len(rest):
        return None  # lone currency mark — C spells; out of scope
    if rest[i] in _CURRENCY_SIGNS:
        if sign != 0:
            return None  # double sign — C spells
        sign = rest[i]
        i += 1
        if i == len(rest):
            return None  # "$+" — C spells
    body = rest[i:]
    num, end = ls_task_parse_number(body)
    if num.n_elp is not None or end != len(body):
        return None  # exponent / trailing garbage — C spells
    emitter = LtsEmitter()
    # Lookahead: "$5 million" reorders to "five million dollars".
    scale = None
    if next_word is not None and next_word.isascii() and next_word.isalpha():
        scale = _wlookup(next_word.encode("ascii"), nwdtab)
    if scale is not None:
        ls_proc_do_sign_full(emitter, sign)
        ls_proc_do_number_full(emitter, body)
        emitter.send_phone(WBOUND)  # pLts_t->rbphone
        emitter.send_phone_list(scale)
        emitter.send_phone_list(pdollar)
        emitter.send_phone(_US_Z)
        return NumericExpansion(_render(emitter), consumed_next=True)
    ls_proc_do_sign_full(emitter, sign)
    fpos = body.find(b".") if num.n_flp is not None else -1
    frac_digits = body[fpos + 1 :] if fpos >= 0 else b""
    if num.n_flp is None or len(frac_digits) == _CENT_FRACTION_DIGITS:
        if num.n_ilp is not None:
            pflag = ls_proc_do_number_full(emitter, body[:fpos] if fpos >= 0 else body)
            emitter.send_phone_list(pdollar)
            if pflag:
                emitter.send_phone(_US_Z)
            if num.n_flp is None:
                return NumericExpansion(_render(emitter))
            if frac_digits == b"00":
                return NumericExpansion(_render(emitter))
            emitter.send_phone_list(pand)
        cents = frac_digits
        if cents and cents[0] == ord("0"):
            cents = cents[1:]  # "just after the '.'": skip one zero
        pflag = ls_proc_do_number_full(emitter, cents)
        emitter.send_phone(WBOUND)
        emitter.send_phone_list(pcent)
        if pflag:
            emitter.send_phone(_US_S)
        return NumericExpansion(_render(emitter))
    # Fraction that isn't exactly 2 digits: "$3.240" — read the whole
    # thing as a decimal number, then "dollars".
    pflag = ls_proc_do_number_full(emitter, body)
    emitter.send_phone_list(pdollar)
    if pflag:
        emitter.send_phone(_US_Z)
    return NumericExpansion(_render(emitter))


def _part_number_claimable(word: bytes) -> bool:
    """True when the chunk is safe for the ported part-number walker.

    Mirrors ``ls_task_part_number``'s character scan (digits, ``/``,
    ``-``, alpha; a quote punts to spelling) with three port-side
    gates: at least one digit AND one separator (bare digit strings
    belong to the plain-number path, bare alpha to the word path),
    no alpha run of 3+ chars (those hit ``ls_util_lookup`` in C),
    and no NANP phone shape (NWS-claimed upstream in C).
    """
    if not _PART_NUMBER_RE.fullmatch(word):
        return False
    if not any(is_digit(b) for b in word):
        return False
    if b"-" not in word and b"/" not in word:
        return False
    if any(len(m.group()) > _PART_MAX_ALPHA_RUN for m in _PART_ALPHA_RUN_RE.finditer(word)):
        return False
    return all(not pat.fullmatch(word) for pat in _PHONE_SHAPE_RES)


def _slash_claimed_upstream(chunk: str) -> bool:
    """True when kernel.normalize's date matcher claims this chunk.

    ``M/D/Y`` chunks are expanded by :mod:`dectalk.kernel.normalize`
    inside ``tokenize`` — the legacy path must keep them.
    """
    if "/" not in chunk:
        return False
    from dectalk.kernel.normalize import try_date  # noqa: PLC0415 — cycle break

    return try_date(chunk) is not None


def numeric_chunk_phonemes(  # noqa: PLR0911, PLR0912 — mirrors the C dispatch ladder
    chunk: str,
    *,
    sign_prefix: str = "",
    next_word: str | None = None,
    had_leading_punct: bool = False,
) -> NumericExpansion | None:
    """Expand one whitespace-delimited numeric chunk, C-faithfully.

    Follows the ``ls_task_main`` dispatch order for the numeric
    stages: sign → currency → date → time → fraction → plain number
    (ordinal / plural / signed) → part number. Returns ``None``
    whenever the chunk is not a recognised numeric format — the
    caller keeps its legacy handling for those (including pure digit
    strings, which the corpus-proven ``_digit_expand`` path owns).

    Args:
        chunk: The chunk with surrounding punctuation already
            stripped (the caller's ``inner``), original case.
        sign_prefix: ``"-"`` / ``"+"`` when the stripped leading
            punctuation ended with a sign character (C keeps signs:
            its LSTRIP class excludes them, then
            ``ls_task_set_sign_flag`` consumes them).
        next_word: The next whitespace chunk (stripped, original
            case) when it carries no attached punctuation — enables
            the ``$5 million`` scale-word lookahead.
        had_leading_punct: True when non-sign punctuation preceded
            the chunk (``"(3:30)"``). Oracle-verified behaviour:
            wrapped clock times read "three colon thirty" in C
            (every other numeric format keeps its normal reading
            under wrappers), so the time branch declines these.

    Returns:
        A :class:`NumericExpansion`, or ``None`` to fall through.
    """
    if not chunk or not chunk.isascii():
        return None
    if sign_prefix and (len(sign_prefix) != 1 or not sign_prefix.isascii()):
        return None
    raw = (sign_prefix + chunk).encode("ascii")
    lowered = bytes(ls_lower[b] for b in raw)  # ls_task_remove_case
    # --- ls_task_set_sign_flag ---
    sign = 0
    i = 0
    if lowered[0] in _SIGN_CHARS:
        sign = lowered[0]
        i = 1
        if i == len(lowered):
            return None  # bare sign — C spells; out of scope
    rest = lowered[i:]
    emitter = LtsEmitter()
    # --- ls_task_currency_processing ---
    if rest[0] == ord("$"):
        return _currency(rest, sign, next_word)
    # --- ls_task_date_processing: dates ---
    if sign == 0 and ls_proc_is_date(rest):
        ls_proc_do_date(emitter, rest)
        return NumericExpansion(_render(emitter))
    # --- ls_task_date_processing: times ---
    # Wrapped times ("(3:30)") read "three colon thirty" in the C
    # pipeline — only claim bare ones (had_leading_punct gate).
    if sign == 0 and not had_leading_punct and _TIME_RE.fullmatch(rest) and ls_proc_is_time(rest):
        ls_proc_do_time(emitter, rest)
        return NumericExpansion(_render(emitter), is_time=True)
    # --- ls_task_frac_processing ---
    # The '%'-suffixed form is gated out: the C kernel splits a bare
    # '%' into its own word upstream (spelled "percent" + trailing
    # boundary), so ls_proc_do_frac's %-arm never fires in the
    # shipped pipeline; isolated-symbol chunks belong to the
    # punctuation/symbol path, not this one.
    if b"%" not in rest and ls_proc_is_frac(rest):
        ls_proc_do_sign_full(emitter, sign)
        ls_proc_do_frac(emitter, rest)
        return NumericExpansion(_render(emitter))
    # --- ls_task_plain_number_processing ---
    if is_digit(rest[0]):
        num, end = ls_task_parse_number(rest)
        _ = num
        if b"," in rest[:end] and end != len(rest):
            # Digit-comma words with a trailing suffix ("1,234th",
            # "1,000s") get split at the comma by the C kernel before
            # the LTS sees them ("one" + spelled "comma" + "234th") —
            # keep the legacy path for those.
            return None
        if end == len(rest):
            # Pure number. Signed integers are C's do_sign + do_number
            # (the year form is explicitly sign-gated in C); unsigned
            # pure digits stay with the legacy corpus-proven path.
            if sign != 0:
                ls_proc_do_sign_full(emitter, sign)
                ls_proc_do_number_full(emitter, rest)
                return NumericExpansion(_render(emitter))
            return None
        suffix = rest[end:]
        if len(suffix) == _ORDINAL_SUFFIX_LEN:
            # Plurals like "60's".
            if suffix == b"'s":
                ls_proc_do_sign_full(emitter, sign)
                ls_proc_do_number_full(emitter, rest[:end])
                for p in ls_util_pluralize(emitter.lphone):
                    emitter.send_phone(p)
                return NumericExpansion(_render(emitter))
            # Ordinals like "1st", "42nd", "103rd" (ls_task.c:3953).
            if sign == 0 and ls_util_is_ordinal(rest, end):
                ls_proc_do_number_full(emitter, rest[:end], oflag=True)
                return NumericExpansion(_render(emitter))
        elif len(suffix) == 1 and suffix == b"s":
            # Plurals like "60s".
            ls_proc_do_sign_full(emitter, sign)
            ls_proc_do_number_full(emitter, rest[:end])
            for p in ls_util_pluralize(emitter.lphone):
                emitter.send_phone(p)
            return NumericExpansion(_render(emitter))
        # '%' / cent / degree suffixes: NWS-claimed in C — fall through.
    # --- ls_task_part_number (original-case word, sign included) ---
    if _part_number_claimable(lowered) and not _slash_claimed_upstream(sign_prefix + chunk):
        ls_proc_do_part_number_full(emitter, lowered)
        return NumericExpansion(_render(emitter))
    return None


__all__ = [
    "NumericExpansion",
    "am_pm_phonemes",
    "numeric_chunk_phonemes",
]
