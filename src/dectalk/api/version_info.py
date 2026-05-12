"""Version / language enumeration structs from ttsapi.h.

Translated from ``src/dapi/src/api/ttsapi.h``:

- :class:`VersionInfo` — engine version block returned by
  ``TextToSpeechVersionEx``.
- :class:`LangEntry` — one language entry (3-char code + display
  name) in the enumeration returned by
  ``TextToSpeechEnumLangs``.
- :class:`LangEnum` — enumeration result: count + list of
  :class:`LangEntry`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class VersionInfo:
    """Engine version block.

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            DWORD  StructSize;
            DWORD  StructVersion;
            WORD   DLLVersion;
            WORD   DTalkVersion;
            LPSTR  VerString;
            LPSTR  Language;
            DWORD  Features;
        } VERSION_INFO;

    Attributes:
        struct_size: Size of this struct (set by the caller).
        struct_version: Microsoft-style version number for the
            struct layout itself. Currently ``0x0001``.
        dll_version: Engine DLL/library version.
        dtalk_version: DECtalk engine version.
        ver_string: Human-readable version string.
        language: Current language identifier.
        features: Bitmask of supported features.
    """

    struct_size: int = 0
    struct_version: int = 0
    dll_version: int = 0
    dtalk_version: int = 0
    ver_string: str = ""
    language: str = ""
    features: int = 0


@dataclass(slots=True)
class LangEntry:
    """One language entry from ``TextToSpeechEnumLangs``.

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            char lang_code[3];   // 2-letter code + NUL
            char lang_name[40];  // human-readable name
        } LANG_ENTRY;

    Attributes:
        lang_code: 2-letter language code (e.g. ``"us"`` / ``"uk"``).
        lang_name: Human-readable language name.
    """

    lang_code: str = ""
    lang_name: str = ""


@dataclass(slots=True)
class LangEnum:
    """Result of ``TextToSpeechEnumLangs``.

    Faithful translation of:

    .. code-block:: c

        typedef struct {
            DWORD        Languages;
            BOOL         MultiLang;
            LPLANG_ENTRY Entries;
        } LANG_ENUM;

    Attributes:
        languages: Number of language entries.
        multi_lang: True iff the engine supports multi-language
            synthesis in one call.
        entries: Python list of :class:`LangEntry`.
    """

    languages: int = 0
    multi_lang: bool = False
    entries: list[LangEntry] = field(default_factory=list[LangEntry])


__all__ = ["LangEntry", "LangEnum", "VersionInfo"]
