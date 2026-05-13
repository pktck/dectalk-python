"""``TTS_HANDLE_T`` engine handle struct from ph_data.h.

Translated from ``src/dapi/src/ph/ph_data.h`` lines 720-726.

The C source's "TTS handle" is a two-pointer aggregate that
threads kernel-shared state and per-thread PH state through every
``LPTTS_HANDLE_T phTTS`` parameter in the engine. The C declaration:

.. code-block:: c

    struct TTS_HANDLE_TAG
    {
        PKSD_T          pKernelShareData;  // shared kernel-state block
        PDPH_T          pPHThreadData;     // per-thread PH instance data
    };
    typedef struct TTS_HANDLE_TAG *LPTTS_HANDLE_T;

In Python the field types are ``object`` placeholders so the handle
can be constructed and passed through helpers before the full
``KSD_T`` / ``DPH_T`` dataclasses land. Specific helpers narrow the
type via ``cast`` at the use site.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TtsHandle:
    """Two-pointer aggregate threading shared + per-thread engine state.

    Attributes:
        p_kernel_share_data: Pointer to the engine-wide ``KSD_T``
            kernel-shared state block. ``None`` until ``init`` runs.
        p_ph_thread_data: Pointer to the per-thread ``DPH_T`` PH
            instance state. ``None`` until ``phinit`` runs.
    """

    p_kernel_share_data: object | None = None
    p_ph_thread_data: object | None = None


__all__ = ["TtsHandle"]
