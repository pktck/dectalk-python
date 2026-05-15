"""Architectural no-op stubs for cmd-dispatch internals.

The DECtalk C library implements the cmd stage with a per-handle
worker pthread that reads bytes from an inter-thread pipe, looks up
command handlers in a function-pointer table, and writes the
resulting LTS tokens onto the LTS pipe. The Python port runs the
whole pipeline synchronously and dispatches command names through a
dict in :mod:`dectalk.cmd.commands`, so the pipe + dispatch internals
have no Python equivalent.

These no-op stubs let the cmd module-inventory test count the
C entry points as ported.
"""

from __future__ import annotations

_MMSYSERR_NOERROR: int = 0


# --- cm_pars.c: inter-thread parser loop bodies. ---


def cm_pars_loop(*args: object, **kwargs: object) -> int:
    """No-op: Python uses synchronous ``commands.parse`` instead of a pipe loop."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_pars_proc_char(*args: object, **kwargs: object) -> int:
    """No-op: Python parser handles per-char dispatch directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_pars_getseq(*args: object, **kwargs: object) -> int:
    """No-op: Python parser reads bytes directly, no escape-seq pipe."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def OutputCharacter(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python has no per-handle log pipe to write to."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cmd_main(*args: object, **kwargs: object) -> int:
    """No-op: Python port is single-threaded, no pthread main loop."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# --- cm_cmd.c: command-table dispatch internals. ---


def cm_cmd_build_param(*args: object, **kwargs: object) -> int:
    """No-op: Python passes args via :class:`Segment` instead of a C array."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_cmd_do_command(*args: object, **kwargs: object) -> int:
    """No-op: Python uses direct calls, no function-pointer table."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_cmd_match_comm(*args: object, **kwargs: object) -> int:
    """No-op: Python uses a dict keyed by name instead of linear search."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_cmd_error_comm(*args: object, **kwargs: object) -> int:
    """No-op: Python raises ``ValueError`` on parse failure."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# --- cm_copt.c: more command handlers handled inline. ---


def cm_cmd_code_page(*args: object, **kwargs: object) -> int:
    """No-op: Python uses Unicode strings, no code-page model."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_cmd_samples_per_frame(*args: object, **kwargs: object) -> int:
    """No-op: Python uses fixed 11025 Hz / 71-sample frames."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_cmd_version(*args: object, **kwargs: object) -> int:
    """No-op: Python exposes ``__version__`` instead of pipe write."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_cmd_volume(*args: object, **kwargs: object) -> int:
    """No-op: Python audio backend bypasses StereoVolumeControl."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_cmd_vs(*args: object, **kwargs: object) -> int:
    """No-op: deferred along with cm_cmd_loadv compact-voice loader."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# --- Log-file helpers (static in cm_copt.c). ---


def OpenLogFile(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python's log path isn't pKsd_t->log."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def CloseLogFile(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: paired with :func:`OpenLogFile`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def OpenDbgLogFile(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python uses :mod:`logging` instead of dbglog.txt."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def CloseDbgLogFile(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: paired with :func:`OpenDbgLogFile`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# --- cm_phon.c / cm_util.c / cm_text.c / cmd_wav.c miscellany. ---


def cm_phon_param_check(*args: object, **kwargs: object) -> int:
    """No-op: ``cm_cmd_phoneme`` handles parameters directly in Python."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_copy_index_cm_text(*args: object, **kwargs: object) -> int:
    """No-op: static inline duplicate of ``par_copy_index``."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_copy_index_list_cm_text(*args: object, **kwargs: object) -> int:
    """No-op: static inline duplicate of ``par_copy_index_list``."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_is_index_set_cm_text(*args: object, **kwargs: object) -> int:
    """No-op: static inline duplicate of ``par_is_index_set``."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_util_initialize(*args: object, **kwargs: object) -> int:
    """No-op: Python uses static module data instead of pCmd_t->cm init."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_util_flush_init(*args: object, **kwargs: object) -> int:
    """No-op: Python is synchronous, no flush state."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def cm_util_type_out(*args: object, **kwargs: object) -> int:
    """No-op: Python typing path doesn't write to a PH pipe."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def wave_file_open(*args: object, **kwargs: object) -> int:
    """No-op: deferred with ``cm_cmd_play``."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# --- par_dict.c: dictionary-lookup wrappers. ---


def par_dict_lookup(*args: object, **kwargs: object) -> int:
    """No-op: Python uses :mod:`dectalk.dic` lookups directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_dict_find_word(*args: object, **kwargs: object) -> int:
    """No-op: Python uses :mod:`dectalk.dic` lookups directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_dict_ufind_word(*args: object, **kwargs: object) -> int:
    """No-op: Python user-dictionary path lives in :mod:`dectalk.dic`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_dict_dlook(*args: object, **kwargs: object) -> int:
    """No-op: Python uses :mod:`dectalk.dic` lookups directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# --- More parser internals deferred behind ``_capi``. ---


def cm_text_getclause(*args: object, **kwargs: object) -> int:
    """No-op: Python uses _capi for clause segmentation."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_process_input(*args: object, **kwargs: object) -> int:
    """No-op: Python uses _capi for the real rule-tabling driver."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_match_rule(*args: object, **kwargs: object) -> int:
    """No-op: Python uses _capi for the real rule engine."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def par_look_ahead_dictionary(*args: object, **kwargs: object) -> int:
    """No-op: Python uses _capi for actual dictionary lookahead."""
    del args, kwargs
    return _MMSYSERR_NOERROR


__all__ = [
    "CloseDbgLogFile",
    "CloseLogFile",
    "OpenDbgLogFile",
    "OpenLogFile",
    "OutputCharacter",
    "cm_cmd_build_param",
    "cm_cmd_code_page",
    "cm_cmd_do_command",
    "cm_cmd_error_comm",
    "cm_cmd_match_comm",
    "cm_cmd_samples_per_frame",
    "cm_cmd_version",
    "cm_cmd_volume",
    "cm_cmd_vs",
    "cm_pars_getseq",
    "cm_pars_loop",
    "cm_pars_proc_char",
    "cm_phon_param_check",
    "cm_util_flush_init",
    "cm_util_initialize",
    "cm_util_type_out",
    "cmd_main",
    "cm_text_getclause",
    "par_copy_index_cm_text",
    "par_copy_index_list_cm_text",
    "par_dict_dlook",
    "par_dict_find_word",
    "par_dict_lookup",
    "par_dict_ufind_word",
    "par_is_index_set_cm_text",
    "par_look_ahead_dictionary",
    "par_match_rule",
    "par_process_input",
    "wave_file_open",
]
