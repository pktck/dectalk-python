"""First-word verb lookup from ls_task.c.

Translated from ``src/dapi/src/lts/ls_task.c``:

- :func:`ls_task_lookup_first_verbs` — Kerzweil/MGS hack: at the
  start of a sentence, check the first word against a hardcoded
  list of common verbs (``are`` ``had`` ``is`` ``was`` ``were``
  ``will``) and, if matched, return the matched :class:`VerbWord`
  so the caller can emit its phonemes and assign its form-class.

The C source uses ``pLts_t->cword`` (the current word's LETTER
buffer) and emits phonemes via ``ls_util_send_phone``; the Python
port returns the matched entry instead.
"""

from __future__ import annotations

from dectalk.lts.char_features import ls_lower
from dectalk.lts.phone_list import EOS
from dectalk.lts.structs import Letter
from dectalk.lts.verbs_table import VerbWord, verbs


def ls_task_lookup_first_verbs(cword: list[Letter]) -> VerbWord | None:
    """Return the matched :class:`VerbWord` or ``None`` if no match.

    Faithful translation of:

    .. code-block:: c

        int ls_task_lookup_first_verbs(LPTTS_HANDLE_T phTTS) {
            LETTER *llp = &pLts_t->cword[0];
            for (i = 0; i < 6; i++) {
                int j = 0;
                LETTER *elp = llp;
                while (elp->l_ch != EOS) {
                    if (verbs[i].word[j] != ls_lower[elp->l_ch])
                        break;
                    j++; elp++;
                }
                if (verbs[i].word[j] == ls_lower[elp->l_ch]
                  && verbs[i].word[j] == 0) {
                    pLts_t->word_info[1].form_class = verbs[i].fc;
                    while (verbs[i].phone[j] != SIL) {
                        ls_util_send_phone(phTTS, verbs[i].phone[j]);
                        j++;
                    }
                    ... return FINISHED_WORD ...
                }
            }
            return ...;
        }

    The C source's match condition is a touch unusual: it tests
    ``verbs[i].word[j] == ls_lower[elp->l_ch] && verbs[i].word[j] == 0``,
    which only fires when BOTH sides are at NUL — i.e. when the
    LETTER stream and the verb word ended at exactly the same point
    after a successful character-by-character match.

    Args:
        cword: Current word as an EOS-terminated LETTER list.

    Returns:
        The matched :class:`VerbWord` if the word equals one of the
        6 first-verbs (case-insensitively), or ``None`` if no match.
    """
    for verb in verbs:
        j = 0
        ei = 0  # position in cword
        word_bytes = verb.word.encode("latin-1")
        while ei < len(cword) and cword[ei].l_ch != EOS:
            if j >= len(word_bytes) or word_bytes[j] != ls_lower[cword[ei].l_ch]:
                break
            j += 1
            ei += 1
        # Match condition: both sides ended together. The C source has
        # ``verbs[i].word[j] == ls_lower[elp->l_ch] && verbs[i].word[j] == 0``;
        # the first conjunct just says "both bytes equal"; the second says
        # "and the verb is at its NUL terminator".
        if j == len(word_bytes):
            # ei must also be at EOS (or end of LETTER list).
            ei_byte = cword[ei].l_ch if ei < len(cword) else EOS
            if ei_byte == EOS:
                return verb
    return None


__all__ = ["ls_task_lookup_first_verbs"]
