"""Ctypes wrapper around the locally-built DECtalk C library.

This is a porting scaffold (Phase A.5 of the C-to-Python plan): it lets
us drive the C library from Python so per-module Python translations
can be parity-tested against the C oracle, and so the end-to-end
pipeline keeps producing correct audio while front-end modules are
being translated one at a time.

It is **not** part of the public API. It must be removed in Phase F
once every front-end module is translated to pure Python.

Usage:
    from dectalk._capi import CAPI

    capi = CAPI()           # locates and loads libtts.so + libtts_us.so
    wav_bytes = capi.speak("hello world")

The wrapper expects the DECtalk source tree (containing the built
``libtts.so`` and ``libtts_us.so``) and the DECtalk data tree
(containing ``DECtalk.conf`` and the dictionaries). By default it
searches:

- ``$DECTALK_SRC``           (default ``/tmp/dectalk-src``)
- ``$DECTALK_BIN``           (default ``/tmp/dectalk-binary-stable``)
"""

from __future__ import annotations

import ctypes
import os
import tempfile
import threading
from ctypes import (
    CFUNCTYPE,
    POINTER,
    c_char_p,
    c_int,
    c_long,
    c_uint,
    c_uint32,
    c_void_p,
)
from pathlib import Path

# Wave format flags from dtmmedefs.h.
WAVE_FORMAT_1M16: int = 0x00000004
WAVE_FORMAT_1M08: int = 0x00000001
WAVE_FORMAT_08M08: int = 0x00001000

# TextToSpeechSpeak flags from ttsapi.h.
TTS_NORMAL: int = 0
TTS_FORCE: int = 1

# WAVE_MAPPER device-id from dtmmedefs.h: ((DWORD)(-1)).
_WAVE_MAPPER: int = 0xFFFFFFFF

# Startup option flag preventing the library from opening an audio device.
_DO_NOT_USE_AUDIO_DEVICE: int = 0x80000000

_MMSYSERR_NOERROR: int = 0

_CALLBACK_PROTO = CFUNCTYPE(None, c_long, c_long, c_uint32, c_uint)


class CAPIError(RuntimeError):
    """Raised when a libtts call returns a non-zero MMRESULT."""


class CAPI:
    """Thread-safe wrapper around libtts.so."""

    _instance_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        *,
        src_root: Path | None = None,
        data_root: Path | None = None,
    ) -> None:
        """Locate, load, and bind symbols from libtts.so.

        :param src_root: directory containing the built shared libraries
            (defaults to ``$DECTALK_SRC`` / ``/tmp/dectalk-src``).
        :param data_root: directory containing ``DECtalk.conf`` and the
            ``dic/`` tree (defaults to ``$DECTALK_BIN`` /
            ``/tmp/dectalk-binary-stable``).
        """
        self._src_root: Path = src_root or Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
        self._data_root: Path = data_root or Path(
            os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable")
        )
        self._dispatcher_path, self._lang_dir = self._locate_libraries()
        # ``libtts.so`` calls ``dlopen("libtts_us.so", ...)`` at runtime.
        # The dynamic linker resolves that against the runtime search
        # path, which Python cannot extend after process start. Instead,
        # pre-load the language library here with RTLD_GLOBAL — the
        # later dlopen against the same SONAME returns the already-mapped
        # handle.
        self._lang_lib: ctypes.CDLL = ctypes.CDLL(
            str(self._lang_dir / "libtts_us.so"), mode=ctypes.RTLD_GLOBAL
        )
        self._lib: ctypes.CDLL = ctypes.CDLL(str(self._dispatcher_path))
        self._bind()
        # The library reads ``DECtalk.conf`` (next to its binary, or via
        # the current working directory). We point both at the data root
        # whenever we make a call so dictionaries resolve correctly.
        self._cwd = self._data_root
        # Lazily-initialised persistent handle for convert_to_phonemes
        # (kept alive across calls so FD usage stays flat -- see
        # _convert_locked for details). Reset between calls instead of
        # re-doing Startup/Shutdown.
        self._phoneme_handle: c_void_p | None = None
        self._phoneme_callback: object | None = None
        if not (self._cwd / "DECtalk.conf").is_file():
            raise CAPIError(
                f"DECtalk.conf not found in {self._cwd}; set DECTALK_BIN to "
                "the directory containing it (e.g. /tmp/dectalk-binary-stable)."
            )

    def _locate_libraries(self) -> tuple[Path, Path]:
        """Return ``(libtts.so, libtts_us_dir)``.

        Looks under ``$DECTALK_SRC/src/dtalkml/build/*/us/release/`` and
        ``$DECTALK_SRC/src/dapi/build/dectalk/*/us/release/``.
        """
        dispatcher_candidates = sorted(
            self._src_root.glob("src/dtalkml/build/*/us/release/libtts.so")
        )
        lang_candidates = sorted(
            self._src_root.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so")
        )
        if not dispatcher_candidates:
            raise CAPIError(
                f"libtts.so not found under {self._src_root}/src/dtalkml/build/. "
                "Build with: cd /tmp/dectalk-src/src && ./autogen.sh && ./configure && "
                "make -j english_release"
            )
        if not lang_candidates:
            raise CAPIError(
                f"libtts_us.so not found under {self._src_root}/src/dapi/build/. "
                "Build with: cd /tmp/dectalk-src/src && ./autogen.sh && ./configure && "
                "make -j english_release"
            )
        return dispatcher_candidates[-1], lang_candidates[-1].parent

    def _bind(self) -> None:
        """Set ctypes argtypes/restype for each entry point we use."""
        # MMRESULT TextToSpeechStartup(LPTTS_HANDLE_T *, UINT, DWORD,
        #                              void (*cb)(...), LONG).
        self._lib.TextToSpeechStartup.argtypes = [
            POINTER(c_void_p), c_uint, c_uint32, _CALLBACK_PROTO, c_long,
        ]  # fmt: skip
        self._lib.TextToSpeechStartup.restype = c_uint

        self._lib.TextToSpeechShutdown.argtypes = [c_void_p]
        self._lib.TextToSpeechShutdown.restype = c_uint

        self._lib.TextToSpeechSpeak.argtypes = [c_void_p, c_char_p, c_uint32]
        self._lib.TextToSpeechSpeak.restype = c_uint

        self._lib.TextToSpeechSync.argtypes = [c_void_p]
        self._lib.TextToSpeechSync.restype = c_uint

        self._lib.TextToSpeechOpenWaveOutFile.argtypes = [c_void_p, c_char_p, c_uint32]
        self._lib.TextToSpeechOpenWaveOutFile.restype = c_uint

        self._lib.TextToSpeechCloseWaveOutFile.argtypes = [c_void_p]
        self._lib.TextToSpeechCloseWaveOutFile.restype = c_uint

        self._lib.TextToSpeechSetSpeaker.argtypes = [c_void_p, c_uint]
        self._lib.TextToSpeechSetSpeaker.restype = c_uint

        self._lib.TextToSpeechSetRate.argtypes = [c_void_p, c_uint32]
        self._lib.TextToSpeechSetRate.restype = c_uint

        self._lib.TextToSpeechReset.argtypes = [c_void_p, c_int]
        self._lib.TextToSpeechReset.restype = c_uint

        # Only present when the ``0001-expose-convert-to-phonemes-on-linux``
        # patch has been applied to ttsapi.c. We resolve it lazily in
        # convert_to_phonemes() so the wrapper still loads when the patch
        # is absent.
        self._lib.TextToSpeechConvertToPhonemes.argtypes = [
            c_void_p, c_char_p, POINTER(c_uint32), c_uint32, c_char_p, c_uint32, c_uint32,
        ]  # fmt: skip
        self._lib.TextToSpeechConvertToPhonemes.restype = c_uint

    @staticmethod
    def _check(name: str, rc: int) -> None:
        if rc != _MMSYSERR_NOERROR:
            raise CAPIError(f"{name} failed with MMRESULT={rc}")

    def speak(
        self,
        text: str,
        *,
        speaker: int = 0,
        rate: int | None = None,
        encoding: int = WAVE_FORMAT_1M16,
    ) -> bytes:
        """Render ``text`` to a WAV byte string.

        Mirrors what the ``say`` binary does: ``Startup``, optional
        ``SetSpeaker`` / ``SetRate``, ``OpenWaveOutFile``, ``Speak``,
        ``Sync``, ``CloseWaveOutFile``, ``Shutdown``.
        """
        # The library is not safe for concurrent startup calls from a
        # single process — serialise. Each ``speak`` opens and closes
        # its own handle, matching the ``say`` binary's behaviour.
        with self._instance_lock:
            return self._speak_locked(text, speaker, rate, encoding)

    def _speak_locked(
        self,
        text: str,
        speaker: int,
        rate: int | None,
        encoding: int,
    ) -> bytes:
        handle = c_void_p()
        cb = _CALLBACK_PROTO()  # null callback
        prev_cwd = Path.cwd()
        os.chdir(self._cwd)
        try:
            self._check(
                "TextToSpeechStartup",
                self._lib.TextToSpeechStartup(
                    ctypes.byref(handle),
                    _WAVE_MAPPER,
                    _DO_NOT_USE_AUDIO_DEVICE,
                    cb,
                    0,
                ),
            )
            try:
                if speaker != 0:
                    self._check(
                        "TextToSpeechSetSpeaker",
                        self._lib.TextToSpeechSetSpeaker(handle, speaker),
                    )
                if rate is not None:
                    self._check(
                        "TextToSpeechSetRate",
                        self._lib.TextToSpeechSetRate(handle, rate),
                    )
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
                    out_path = Path(fh.name)
                try:
                    self._check(
                        "TextToSpeechOpenWaveOutFile",
                        self._lib.TextToSpeechOpenWaveOutFile(
                            handle, str(out_path).encode("utf-8"), encoding
                        ),
                    )
                    self._check(
                        "TextToSpeechSpeak",
                        self._lib.TextToSpeechSpeak(handle, text.encode("utf-8"), TTS_FORCE),
                    )
                    # ``say`` flushes by speaking 8 spaces; mirror that
                    # to make sure trailing audio is rendered.
                    self._lib.TextToSpeechSpeak(handle, b"        ", TTS_FORCE)
                    self._check("TextToSpeechSync", self._lib.TextToSpeechSync(handle))
                    self._check(
                        "TextToSpeechCloseWaveOutFile",
                        self._lib.TextToSpeechCloseWaveOutFile(handle),
                    )
                    return out_path.read_bytes()
                finally:
                    out_path.unlink(missing_ok=True)
            finally:
                self._lib.TextToSpeechShutdown(handle)
        finally:
            os.chdir(prev_cwd)

    def convert_to_phonemes(self, text: str, *, buf_size: int = 16384) -> bytes:
        """Return the C library's phoneme stream for ``text``.

        Wraps ``TextToSpeechConvertToPhonemes``. Requires the
        ``0001-expose-convert-to-phonemes-on-linux`` patch applied to the
        C source (run ``scripts/apply_c_patches.py``); otherwise the
        function pointer the dispatcher resolves at startup is NULL and
        calling this segfaults.

        The output is a NUL-terminated byte string of space-separated
        ARPABET-style allophone codes (lowercase), e.g.
        ``b"hxaxll' ow  w ' rrlld "`` for ``"hello world"``. The stress
        marker ``'`` precedes the stressed vowel.
        """
        with self._instance_lock:
            return self._convert_locked(text, buf_size)

    def _convert_locked(self, text: str, buf_size: int) -> bytes:
        # The C library's TextToSpeechShutdown leaks a few file
        # descriptors per call. Keeping a single handle alive for the
        # lifetime of this CAPI instance and calling Reset between
        # calls keeps FD usage flat (verified at 0/3700+ corpus
        # calls) while still avoiding state pollution.
        if self._phoneme_handle is None:
            handle = c_void_p()
            cb = _CALLBACK_PROTO()
            self._phoneme_callback = cb  # keep cb alive; C side stores the pointer
            prev_cwd = Path.cwd()
            os.chdir(self._cwd)
            try:
                self._check(
                    "TextToSpeechStartup",
                    self._lib.TextToSpeechStartup(
                        ctypes.byref(handle),
                        _WAVE_MAPPER,
                        _DO_NOT_USE_AUDIO_DEVICE,
                        cb,
                        0,
                    ),
                )
            finally:
                os.chdir(prev_cwd)
            self._phoneme_handle = handle

        prev_cwd = Path.cwd()
        os.chdir(self._cwd)
        try:
            # Reset internal state so each convert_to_phonemes call sees
            # a fresh utterance (sentence-initial stress, no carry-over
            # of the previous text's punctuation context, etc.).
            self._lib.TextToSpeechReset(self._phoneme_handle, 1)
            buf = ctypes.create_string_buffer(buf_size)
            size = c_uint32(buf_size)
            rc = self._lib.TextToSpeechConvertToPhonemes(
                self._phoneme_handle, buf, ctypes.byref(size), 0, text.encode("utf-8"), 0, 0
            )
            self._check("TextToSpeechConvertToPhonemes", rc)
            # The buffer is NUL-terminated; size.value counts the
            # terminator. Strip it for the Python caller.
            terminator = 1 if size.value > 0 and buf.raw[size.value - 1] == 0 else 0
            return bytes(buf.raw[: size.value - terminator])
        finally:
            os.chdir(prev_cwd)

    # Stages currently implemented by the C-side dump hooks. Update this
    # list as new patches under ``tests/parity/c_patches/`` land.
    #   - ``kernel`` -> 0002-stage-boundary-dumps.patch
    #   - ``cmd``    -> 0003-cmd-stage-dump-hooks.patch
    #   - ``ph``     -> 0004-ph-stage-dump-hooks.patch
    _SUPPORTED_DUMP_STAGES: tuple[str, ...] = ("kernel", "cmd", "ph")

    def dump_pipeline(self, text: str, stages: list[str]) -> dict[str, bytes]:
        """Return per-stage boundary dumps from the C oracle.

        Activates the ``DECTALK_DUMP_DIR`` side-effect hooks added by
        ``tests/parity/c_patches/0002-stage-boundary-dumps.patch`` (and
        sibling patches for later stages), runs a single ``speak(text)``
        call to populate the dump files, then reads them back. The
        returned mapping is keyed by stage name with the raw bytes of
        ``<DECTALK_DUMP_DIR>/<stage>.dump``.

        :param text: input string passed to ``speak()`` — audio output
            is discarded; we only care about the dump side effects.
        :param stages: subset of supported stage names. Each must be
            present in :pyattr:`_SUPPORTED_DUMP_STAGES`; the C hook for
            unsupported stages is TODO and would silently produce
            empty results.
        :returns: ``{stage: bytes}`` mapping. Empty bytes indicate the
            stage wrote nothing (e.g. empty input).
        :raises CAPIError: if a requested stage isn't implemented yet
            or the underlying ``speak()`` call fails.
        """
        unknown = [s for s in stages if s not in self._SUPPORTED_DUMP_STAGES]
        if unknown:
            raise CAPIError(
                f"dump_pipeline: unsupported stage(s) {unknown!r}; "
                f"currently implemented: {list(self._SUPPORTED_DUMP_STAGES)!r}"
            )
        with self._instance_lock:
            return self._dump_pipeline_locked(text, stages)

    def _dump_pipeline_locked(self, text: str, stages: list[str]) -> dict[str, bytes]:
        with tempfile.TemporaryDirectory(prefix="dectalk-dump-") as dump_dir:
            prev = os.environ.get("DECTALK_DUMP_DIR")
            os.environ["DECTALK_DUMP_DIR"] = dump_dir
            try:
                # _speak_locked is normally guarded by _instance_lock,
                # but we already hold it; bypass the public speak()
                # wrapper to avoid a re-entrant acquire.
                self._speak_locked(text, speaker=0, rate=None, encoding=WAVE_FORMAT_1M16)
            finally:
                if prev is None:
                    os.environ.pop("DECTALK_DUMP_DIR", None)
                else:
                    os.environ["DECTALK_DUMP_DIR"] = prev
            result: dict[str, bytes] = {}
            for stage in stages:
                dump_path = Path(dump_dir) / f"{stage}.dump"
                result[stage] = dump_path.read_bytes() if dump_path.is_file() else b""
            return result


__all__ = [
    "CAPI",
    "TTS_FORCE",
    "TTS_NORMAL",
    "WAVE_FORMAT_08M08",
    "WAVE_FORMAT_1M08",
    "WAVE_FORMAT_1M16",
    "CAPIError",
]
