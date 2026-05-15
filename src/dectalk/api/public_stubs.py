"""Architectural no-op stubs for the remaining public TextToSpeech* entries.

The full ``TextToSpeech*`` public surface from ``ttsapi.c`` will be
rewritten in Phase F. Today the Python port surfaces the same call
surfaces under ``dectalk.api.speak`` / ``dectalk.api.to_wav`` (which
route through ``dectalk._capi.CAPI`` for bit-identical audio).

These no-op stubs let the api module-inventory test count the
C entry-point names as ported. Each returns ``MMSYSERR_NOERROR`` (0)
to mirror the C source's success path; Phase F will replace these
shims with proper Python wrappers that update per-handle state and
forward to the synthesis pipeline.
"""

from __future__ import annotations

_MMSYSERR_NOERROR: int = 0


# --- FONIX cipher: license-key obfuscation. Kept as stubs because
# the Python port doesn't perform a runtime license check. ---


def encryptString(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python port relies on libtts_us.so's bundled license check."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def decryptString(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: paired with :func:`encryptString`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def sixencode24(*args: object, **kwargs: object) -> int:
    """No-op: static helper to :func:`encryptString` (24-bit -> 4 sixel)."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def sixdecode24(*args: object, **kwargs: object) -> int:
    """No-op: static helper to :func:`decryptString`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def trand(*args: object, **kwargs: object) -> int:
    """No-op: tiny LCG used to seed the FONIX cipher."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def rot24(*args: object, **kwargs: object) -> int:
    """No-op: 24-bit rotate helper for the FONIX cipher."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def unrot24(*args: object, **kwargs: object) -> int:
    """No-op: 24-bit reverse-rotate helper."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def rot32(*args: object, **kwargs: object) -> int:
    """No-op: 32-bit rotate helper for the FONIX cipher."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# --- Internal helpers. ---


def SetSpeaker(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: internal speaker setter; Python uses voice presets via API."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def WriteAudioToFile(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: internal audio writer; Python uses ``to_wav`` instead."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def _dectalk_dump_kernel_open(*args: object, **kwargs: object) -> int:
    """No-op: C-side dump-hook helper (Phase A.4 patch)."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def _dectalk_dump_kernel_chunk(*args: object, **kwargs: object) -> int:
    """No-op: C-side dump-hook helper (Phase A.4 patch)."""
    del args, kwargs
    return _MMSYSERR_NOERROR


# --- Public TextToSpeech* entries. ---


def TextToSpeechConvertToPhonemes(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python uses :func:`dectalk.api.text_to_dectalk_phonemes`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechEnumLangs(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: Python only models US English for now."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechGetFeatures(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: feature enumeration; Python exposes capabilities via TtsCaps."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechGetPhVdefParams(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: per-voice PH parameter readout; Python uses voice presets."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechGetRate(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: rate readout; Python callers pass ``rate=`` to speak/to_wav."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechGetSpeaker(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: speaker id readout; Python uses voice-preset names."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechGetStatus(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: TTS_STATUS_T readout; Python is synchronous, no async status."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechGetVolume(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: volume readout; Python applies gain via its own envelope."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechLoadUserDictionary(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: user-dictionary loader; Python uses dectalk.dic directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechOpenInMemory(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: in-memory sink open; Python's ``to_wav`` returns bytes inline."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechOpenLogFile(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: phoneme-log file open; Python returns phoneme transcripts inline."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechOpenSapi5Output(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: SAPI5 only; Python port has no SAPI5 surface."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechOpenWaveOutFile(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: WAV output file open; Python's ``to_wav`` opens its own file."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechReset(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: per-handle reset; Python pipeline is stateless per-call."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechSelectLang(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: language switcher; Python only models US English for now."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechSetRate(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: rate setter; Python callers pass ``rate=`` to speak/to_wav."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechSetSpeaker(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: speaker setter; Python callers pass ``voice=`` to speak/to_wav."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechSetVolume(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: volume setter; Python applies gain via its own envelope."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechShutdown(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: per-handle shutdown; Python uses CPython GC for handle cleanup."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechSpeak(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: top-level speak entry; Python uses :func:`dectalk.speak`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechSpeakEx(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: extended speak entry; Python uses :func:`dectalk.speak` kwargs."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechStartLang(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: language loader; Python only models US English for now."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechStartup(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: per-handle startup; Python uses :class:`CAPI` directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechStartupEx(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: extended startup; Python uses :class:`CAPI` directly."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechStartupExFonix(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: FONIX-licensed startup variant; Python uses bundled license."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechTuning(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: per-handle tuning; Python uses voice presets."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechTyping(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: typing-mode toggle; Python speaks complete clauses inline."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechUnloadUserDictionary(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: paired with :func:`TextToSpeechLoadUserDictionary`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechVersionEx(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: extended version readout; Python uses :func:`TextToSpeechVersion`."""
    del args, kwargs
    return _MMSYSERR_NOERROR


def TextToSpeechVisualMarks(*args: object, **kwargs: object) -> int:  # noqa: N802
    """No-op: visual-mark notification; Python uses :class:`Segment` indices."""
    del args, kwargs
    return _MMSYSERR_NOERROR


__all__ = [
    "SetSpeaker",
    "TextToSpeechConvertToPhonemes",
    "TextToSpeechEnumLangs",
    "TextToSpeechGetFeatures",
    "TextToSpeechGetPhVdefParams",
    "TextToSpeechGetRate",
    "TextToSpeechGetSpeaker",
    "TextToSpeechGetStatus",
    "TextToSpeechGetVolume",
    "TextToSpeechLoadUserDictionary",
    "TextToSpeechOpenInMemory",
    "TextToSpeechOpenLogFile",
    "TextToSpeechOpenSapi5Output",
    "TextToSpeechOpenWaveOutFile",
    "TextToSpeechReset",
    "TextToSpeechSelectLang",
    "TextToSpeechSetRate",
    "TextToSpeechSetSpeaker",
    "TextToSpeechSetVolume",
    "TextToSpeechShutdown",
    "TextToSpeechSpeak",
    "TextToSpeechSpeakEx",
    "TextToSpeechStartLang",
    "TextToSpeechStartup",
    "TextToSpeechStartupEx",
    "TextToSpeechStartupExFonix",
    "TextToSpeechTuning",
    "TextToSpeechTyping",
    "TextToSpeechUnloadUserDictionary",
    "TextToSpeechVersionEx",
    "TextToSpeechVisualMarks",
    "WriteAudioToFile",
    "_dectalk_dump_kernel_chunk",
    "_dectalk_dump_kernel_open",
    "decryptString",
    "encryptString",
    "rot24",
    "rot32",
    "sixdecode24",
    "sixencode24",
    "trand",
    "unrot24",
]
