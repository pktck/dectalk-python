"""Case-insensitive unique-prefix string matcher for inline commands.

Translated from ``src/dapi/src/cmd/cm_util.c``:

- :func:`cm_util_string_match` — case-insensitive prefix matcher
  used by the inline-command parser. Returns the index of the
  matching string in the options array if there's exactly one
  prefix match, otherwise :data:`NO_STRING_MATCH`.
- :data:`NO_STRING_MATCH` — sentinel from ``cmd/cm_defs.h``.
"""

from __future__ import annotations

from typing import Final

from dectalk.lts.char_features import ls_lower

NO_STRING_MATCH: Final[int] = 0xFFFF


def cm_util_string_match(
    options: list[bytes] | tuple[bytes, ...],
    string: str | bytes,
) -> int:
    """Return the index of the unique prefix-match in ``options`` or NO_STRING_MATCH.

    Faithful translation of:

    .. code-block:: c

        int cm_util_string_match(const unsigned char *sa[], unsigned char *s) {
            unsigned char *t, *ta;
            int index, matches, match_index = 0;
            matches = 0;
            if (s == NULL) return NO_STRING_MATCH;
            for (index = 0; sa[index]; index++) {
                t = s;
                ta = sa[index];
                while (TRUE) {
                    if (*ta == par_lower[*t]) {
                        if (*ta == 0) return index;     // exact match
                        ta++; t++;
                    } else {
                        if (*t == 0) {
                            matches++;
                            match_index = index;
                            break;                       // prefix match
                        }
                        break;                           // mismatch
                    }
                }
            }
            if (matches == 1) return match_index;
            return NO_STRING_MATCH;
        }

    The matcher returns:

    * the index immediately on an **exact** case-insensitive match
      (``s`` consumed at the same time as the option),
    * the index for a **unique prefix** match (``s`` is a strict
      prefix of exactly one option),
    * :data:`NO_STRING_MATCH` if ``s`` is ambiguous (matches > 1
      option as prefix) or matches no option.

    The C source uses ``par_lower[]`` (= :data:`ls_lower`) to
    case-fold the input byte-by-byte; the options array is expected
    to be pre-lowercased.

    Args:
        options: Sequence of NUL-terminated option strings (bytes
            without a trailing NUL, as the loop terminates on
            ``ta == 0`` which we model by end-of-bytes). Strings
            must already be lower-case.
        string: Input to match. ``None`` returns NO_STRING_MATCH;
            empty string returns the first option's index if there
            are options (matches all as prefix, so ambiguous → NO).

    Returns:
        The index of the matched option, or :data:`NO_STRING_MATCH`.
    """
    if string is None:  # pyright: ignore[reportUnnecessaryComparison] — C source explicitly guards None
        return NO_STRING_MATCH
    s = string.encode("latin-1", errors="replace") if isinstance(string, str) else string

    matches = 0
    match_index = 0
    for index, opt in enumerate(options):
        ta_pos = 0
        t_pos = 0
        opt_len = len(opt)
        s_len = len(s)
        while True:
            # ``*ta`` == byte at ta_pos (0 once past the end), same for *t.
            ta_byte = opt[ta_pos] if ta_pos < opt_len else 0
            t_byte = s[t_pos] if t_pos < s_len else 0
            t_lower = ls_lower[t_byte] if t_byte else 0
            if ta_byte == t_lower:
                if ta_byte == 0:
                    return index  # exact match
                ta_pos += 1
                t_pos += 1
            else:
                if t_byte == 0:
                    # Input ended before option — prefix match candidate.
                    matches += 1
                    match_index = index
                break

    if matches == 1:
        return match_index
    return NO_STRING_MATCH


__all__ = ["NO_STRING_MATCH", "cm_util_string_match"]
