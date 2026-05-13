"""Trivial kernel-helper stubs from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c``:

- :func:`kernel_enable` — line 800 (Linux build: ``MSDOS``-gated body)
- :func:`set_gpio` — line 851
- :func:`clr_gpio` — line 861
- :func:`sleep_ms` — Linux build has no body (only ``#ifdef WIN32``)
- :func:`putseq` — line 885 (``__linux__`` branch returns 0)
- :func:`vol_up` — line 1443 (entire definition under ``#ifdef MSDOS``)
- :func:`vol_down` — line 1455 (entire definition under ``#ifdef MSDOS``)
- :func:`vol_set` — line 1465 (entire definition under ``#ifdef MSDOS``)

These all existed to drive MS-DOS / Windows / VXWORKS hardware paths
(GPIO lines on the SPC chip, Windows ``Sleep``, the MSDOS resume-pipe
machinery, MSDOS volume hardware). On Linux they are either empty
function bodies or never compiled in at all. ``libtts_us.so`` doesn't
drive any such hardware, so the Python port keeps them as no-ops with
the same signatures for call-site parity with libp.h.
"""

from __future__ import annotations

from dectalk.kernel.ksd_t import KsdT


def set_gpio(dummy: int) -> None:
    """Set a GPIO bit on the SPC chip. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void set_gpio( int dummy )
        {
        }

    Marked ``(STUB)`` in the C source banner. The original drove the
    DTC0X serial-DECtalk GPIO lines (``GPIO_RESET`` / ``GPIO_STOP``);
    the Linux / libtts_us.so build has no such hardware, so the body
    is empty.

    Args:
        dummy: GPIO mask the caller wanted to set (unused).
    """


def clr_gpio(dummy: int) -> None:
    """Clear a GPIO bit on the SPC chip. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void clr_gpio( int dummy )
        {
        }

    Marked ``(STUB)`` in the C source banner. The original cleared
    the DTC0X serial-DECtalk GPIO lines; the Linux build has no such
    hardware, so the body is empty.

    Args:
        dummy: GPIO mask the caller wanted to clear (unused).
    """


def kernel_enable(p_ksd_t: KsdT, flags: int) -> None:
    """Re-enable kernel pipes after a critical section. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void kernel_enable( PKSD_T pKsd_t, unsigned int flags )
        {

        #ifdef MSDOS

          resume_pipe( pKsd_t->sync_pipe );
          resume_pipe( pKsd_t->vtm_pipe );
          resume_pipe( pKsd_t->ph_pipe );
          resume_pipe( pKsd_t->lts_pipe );
          resume_pipe( pKsd_t->cmd_pipe );
        #endif

          return;
        }

    The body that resumes the five kernel pipes is wrapped in
    ``#ifdef MSDOS`` — on Linux the function only executes ``return;``.
    ``libtts_us.so`` runs everything on a single thread, so there are
    no pipes to resume.

    Args:
        p_ksd_t: Kernel shared-data struct (unused on Linux).
        flags: Saved interrupt-flag word from ``kernel_disable``
            (unused on Linux).
    """


def vol_up(count: int) -> None:
    """Bump volume up "count" notches. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void vol_up( int count )
        {
        }

    The entire definition is wrapped in ``#ifdef MSDOS`` in the C
    source, so on Linux the symbol does not exist at all. The Python
    port keeps it for call-site parity but does nothing — the Linux
    audio path goes through ``PA_SetVolume`` in ``SetStereoVolume``
    instead.

    Args:
        count: Number of volume notches to bump (unused).
    """


def vol_down(count: int) -> None:
    """Bump volume down "count" notches. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void vol_down( int count )
        {
        }

    The entire definition is wrapped in ``#ifdef MSDOS`` in the C
    source, so on Linux the symbol does not exist at all. The Python
    port keeps it for call-site parity but does nothing.

    Args:
        count: Number of volume notches to drop (unused).
    """


def vol_set(count: int) -> None:
    """Set volume to "count". Out-of-range values ignored. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void vol_set( int count )
        {
        }

    The entire definition is wrapped in ``#ifdef MSDOS`` in the C
    source, so on Linux the symbol does not exist at all. The Python
    port keeps it for call-site parity but does nothing.

    Args:
        count: Absolute volume level the caller wanted (unused).
    """


def putseq(sp: object) -> int:
    """Ship a ``SEQ`` packet out the serial DECtalk link. Stub returning 0.

    Faithful translation of the Linux branch:

    .. code-block:: c

        int putseq( void *sp )
        {
          return(0);
        }

    The ``#if defined __linux__ || defined VXWORKS || ...`` branch of
    the function takes a ``void *`` and immediately returns 0; the
    MSDOS branch would have actually pushed the sequence onto the
    serial-DECtalk wire. ``libtts_us.so`` has no serial peripheral, so
    the Linux build is the always-zero stub the Python port preserves.

    Args:
        sp: Sequence packet pointer (unused).

    Returns:
        Always ``0`` — matches the Linux C body verbatim.
    """
    return 0


def sleep_ms(ms: int) -> None:
    """Sleep for ``ms`` milliseconds. No-op on Linux for the Python port.

    The C source only defines ``sleep`` under ``#ifdef WIN32``:

    .. code-block:: c

        #ifdef WIN32
        void sleep( unsigned int uiTimeInMsec )
        {
          Sleep((DWORD)uiTimeInMsec );
        }
        #endif

    On Linux the function does not exist as part of the kernel
    services file — call sites instead rely on libc ``sleep`` (which
    takes *seconds*, not milliseconds, so the two signatures are
    incompatible anyway). The Python kernel pipeline isn't driving a
    real-time audio thread, so we don't need real sleep semantics
    here; the stub is a no-op named ``sleep_ms`` to avoid shadowing
    :func:`time.sleep`.

    Args:
        ms: Sleep duration in milliseconds (unused).
    """


__all__ = [
    "clr_gpio",
    "kernel_enable",
    "putseq",
    "set_gpio",
    "sleep_ms",
    "vol_down",
    "vol_set",
    "vol_up",
]
