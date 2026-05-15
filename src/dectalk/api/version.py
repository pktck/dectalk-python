"""``TextToSpeechVersion`` -- public API version-string + bitfield function.

Translated from ``src/dapi/src/api/ttsapi.c`` lines 10942-10964 (the
non-Windows ``__linux__`` branch). The C source builds a static
version string ``"<DTALK_STR_VERSION> <CUSTR_STR_VERSION>"`` and
returns a packed 32-bit version integer

    (DTALK_MAJ_VERSION << 24)
    | (DTALK_MIN_VERSION << 16)
    | (DLL_MAJ_VERSION << 8)
    | DLL_MIN_VERSION

For the Linux ``us`` build, ``coop.h`` defines:

- ``DTALK_MAJ_VERSION = 5``, ``DTALK_MIN_VERSION = 0``
- ``DLL_MAJ_VERSION = 3``, ``DLL_MIN_VERSION = 0``
- ``DTALK_STR_VERSION = "v5.00 Github NORMAL"``
- ``CUSTR_STR_VERSION = "US"``

so the packed integer is ``0x05000300`` and the version string is
``"v5.00 Github NORMAL US"``.
"""

from __future__ import annotations

# Build-time constants mirrored from coop.h. Update these when the
# corresponding C defines change.
DTALK_MAJ_VERSION: int = 5
DTALK_MIN_VERSION: int = 0
DLL_MAJ_VERSION: int = 3
DLL_MIN_VERSION: int = 0
DTALK_STR_VERSION: str = "v5.00 Github NORMAL"
CUSTR_STR_VERSION: str = "US"

DECTALK_VERSION_STRING: str = f"{DTALK_STR_VERSION} {CUSTR_STR_VERSION}"


def TextToSpeechVersion(  # noqa: N802 — mirror C entry-point name
    VersionStr: list[str] | None = None,  # noqa: N803 — mirror C arg name
) -> int:
    """Return the packed 32-bit DECtalk version and optionally write the string.

    Faithful translation of the Linux branch:

    .. code-block:: c

        static char DECtalk_Version_String[50];
        sprintf(DECtalk_Version_String, "%s %s",
                DTALK_STR_VERSION, CUSTR_STR_VERSION);
        if (VersionStr != NULL) *VersionStr = DECtalk_Version_String;
        return (DTALK_MAJ_VERSION << 24)
             + (DTALK_MIN_VERSION << 16)
             + (DLL_MAJ_VERSION  << 8)
             +  DLL_MIN_VERSION;

    Args:
        VersionStr: Single-element list used as an out-parameter; the
            version string is written to ``VersionStr[0]`` when non-None.

    Returns:
        Packed 32-bit version, ``0x05000300`` for this build.
    """
    if VersionStr is not None:
        if VersionStr:
            VersionStr[0] = DECTALK_VERSION_STRING
        else:
            VersionStr.append(DECTALK_VERSION_STRING)
    return (
        (DTALK_MAJ_VERSION << 24)
        | (DTALK_MIN_VERSION << 16)
        | (DLL_MAJ_VERSION << 8)
        | DLL_MIN_VERSION
    )


__all__ = [
    "CUSTR_STR_VERSION",
    "DECTALK_VERSION_STRING",
    "DLL_MAJ_VERSION",
    "DLL_MIN_VERSION",
    "DTALK_MAJ_VERSION",
    "DTALK_MIN_VERSION",
    "DTALK_STR_VERSION",
    "TextToSpeechVersion",
]
