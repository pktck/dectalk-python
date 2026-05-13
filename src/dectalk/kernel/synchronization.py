"""Kernel semaphore / disable helpers from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c``:

- :func:`wait_semaphore` — line 826 (Linux branch, ``P_SEMAPHORE``)
- :func:`signal_semaphore` — line 841
- :func:`kernel_disable` — line 781 (``MSDOS``-gated body, Linux returns 0)

The Linux build of ``libtts_us.so`` does its real synchronisation via
pthread mutexes / condvars in ``opthread.h``; the legacy semaphore
helpers in ``services.c`` keep empty function bodies for call-site
parity. ``kernel_disable`` similarly wraps the only meaningful work
(pausing the five kernel pipes) inside ``#ifdef MSDOS``, so on Linux
it just returns 0. The Python port mirrors these no-ops with the same
signatures so call sites translated from the C source line up.
"""

from __future__ import annotations

from dectalk.kernel.ksd_t import KsdT


def wait_semaphore(semaphore: object) -> None:
    """Block on a counting semaphore. No-op on Linux.

    Faithful translation of the Linux branch:

    .. code-block:: c

        #if defined (__osf__) || defined (__linux__) || defined VXWORKS || ...
        void wait_semaphore( P_SEMAPHORE semaphore )
        #endif
        {
        }

    The C function's prototype is selected by preprocessor branch based
    on platform; on Linux (and OSF / VxWorks / Solaris / Emscripten /
    Apple) it takes a ``P_SEMAPHORE`` and has an empty body. The real
    synchronisation in the Linux build happens through ``opthread.h``
    pthread mutexes / condvars; this entry point exists only for legacy
    call-site parity.

    Args:
        semaphore: Semaphore object the caller wanted to wait on (unused).
    """


def signal_semaphore(semaphore: object) -> None:
    """Signal a counting semaphore. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void signal_semaphore( int * semaphore )
        {
        }

    Empty body across every build branch in services.c. As with
    :func:`wait_semaphore`, the real Linux signalling goes through
    pthread primitives, so this helper exists purely for call-site
    parity.

    Args:
        semaphore: Semaphore object the caller wanted to signal (unused).
    """


def kernel_disable(p_ksd_t: KsdT) -> int:
    """Pause the kernel pipes for a critical section. Returns 0 on Linux.

    Faithful translation of:

    .. code-block:: c

        unsigned int kernel_disable(PKSD_T pKsd_t)
        {
        #ifdef MSDOS
          pause_pipe( pKsd_t->cmd_pipe );
          pause_pipe( pKsd_t->lts_pipe );
          pause_pipe( pKsd_t->ph_pipe );
          pause_pipe( pKsd_t->vtm_pipe );
          pause_pipe( pKsd_t->sync_pipe );
        #endif

          return( 0 );
        }

    The pipe-pause body is wrapped in ``#ifdef MSDOS`` — on Linux this
    function only executes ``return( 0 );``. ``libtts_us.so`` runs the
    whole pipeline on a single thread, so there is nothing to pause.
    The companion :func:`dectalk.kernel.kernel_stubs.kernel_enable`
    likewise no-ops on Linux.

    The C return type is ``unsigned int``; the Python port uses ``int``
    consistent with the established convention for unsigned scalars in
    this codebase.

    Args:
        p_ksd_t: Kernel shared-data struct (unused on Linux).

    Returns:
        Always ``0`` — matches the Linux C body verbatim.
    """
    return 0


__all__ = ["kernel_disable", "signal_semaphore", "wait_semaphore"]
