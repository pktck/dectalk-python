"""SPC kernel stub helpers from kernel/services.c.

Translated from ``src/dapi/src/kernel/services.c`` lines 540-682.

:func:`send_index`, :func:`start_flush`, and :func:`reset_spc` are
all kernel-services entry points whose bodies are entirely
commented out in the Linux build. The original implementations
drove DTC0X serial hardware (index marks back over the serial
link), system-wide buffer flushes through the kernel pipes /
semaphores, and the SPC chip reset GPIO lines. None of those
mechanisms exist in the libtts_us.so build path that this Python
port targets — the active bodies are wrapped in C comment markers
so the functions compile as no-ops.

The Python port mirrors that no-op behaviour. The C bodies are
reproduced verbatim in each docstring so the original intent is
preserved alongside the port.
"""

from __future__ import annotations


def send_index(how: int, value: int) -> None:
    """Send an index mark back to the host. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void send_index( int how, int value )
        {
        /*
          SEQ     seq;

          WAIT_PRINT;
          if(how == ESCAPE_OUTPUT)
          {
            seq.s_type   = DCS;
            seq.s_pintro = 0;
            seq.s_final  = DCS_F_DECTALK;
            seq.s_ninter = 0;
            seq.s_nparam = 3;
            seq.s_dflag[0] = FALSE;
            seq.s_param[0] = P1_DECTALK;
            seq.s_param[1] = R2_IX_REPLY;
            seq.s_dflag[1] = FALSE;
            seq.s_param[2] = value;
            seq.s_dflag[2] = FALSE;
            if (seq.s_param[2] == 0)
            seq.s_dflag[2] = TRUE;
            putseq((SEQ _far *)&seq);
            seq.s_type = ST;
            putseq((SEQ _far *)&seq);
          }
          else
          {
            printf("/n[:index %d]",value);
          }
          SIGNAL_PRINT;
        */
          return;
        }

    The entire body is commented out in the Linux build — only the
    bare ``return;`` survives. This routine was DTC0X-only (a serial
    DECtalk peripheral that delivered index marks back over the
    RS-232 link); ``libtts_us.so`` exposes index marks via the
    callback API instead, so this stub does nothing.

    Args:
        how: Originally ``ESCAPE_OUTPUT`` vs printf branch selector
            (unused — kept for signature parity with libp.h).
        value: Originally the index mark value to ship back (unused).
    """
    _ = (how, value)  # Signature parity — Linux body is commented out.


def start_flush(serial_mode: int) -> None:
    """Begin a system-wide buffer flush. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void start_flush( int serial_mode )
        {
        /*
        #ifdef WIN32
          int i;
          LPTTS_HANDLE_T phTTS;

          phTTS = TextToSpeechGetHandle();

          TextToSpeechReset( phTTS, TRUE );

          return;
        #endif
        */

        /*
          unsigned int            temp,flags;
          int                                     old_volume,old_log;
          PCB _far        *sw;


          status_set_update(STAT_flushing);

          flags=kernel_disable();

          old_volume = KS.volume;
          old_log = KS.logflag;
          KS.logflag = 0;
          vol_set(0);

          if(serial_mode == false)
          {
            KS.cmd_flush = CMD_flush_toss;
            flush_ring(KS.in_ring);
            status_set(STAT_rr_char);
          }

          flush_ring(KS.out_ring);
          KS.spc_flush_type = SPC_flush_all;
          KS.spc_flush = true;
          KS.halting = true;

          flush_pipe(KS.lts_pipe);
          flush_pipe(KS.ph_pipe);

          if(KS.spc_sync.queue)
            signal_semaphore(&KS.spc_sync);
          if(KS.spc_resume.queue)
            signal_semaphore(&KS.spc_resume);

        */
        /*
         *  hack time ... now the pipes may be waiting for some data (psnextra is
         *  was set, so push some data through the pipe to insure we see the sync
         *  pop out ...
         */
        /*
          set_gpio(GPIO_STOP);

          KS.spc_sync.value = 0;
          temp = ((PFASCII<<PSFONT)+0xb);
          write_pipe(KS.lts_pipe,&temp,1);
          temp = SYNC;
          write_pipe(KS.lts_pipe,&temp,1);

          kernel_enable(flags);
          wait_semaphore(&KS.spc_sync);
          KS.spc_sync.value = 1;
          flags=kernel_disable();

          KS.spc_flush = false;
          KS.halting = false;
          KS.logflag = old_log;

          reset_spc();
          vol_set(old_volume);
          kernel_enable(flags);
        */
        }

    Every block of the function body is commented out — the Linux
    build relies on the higher-level ``TextToSpeechReset`` /
    audio-queue plumbing rather than the kernel ring / pipe /
    semaphore dance, so this routine is a true no-op.

    Args:
        serial_mode: Originally ``false`` meant flush input ring and
            set the ``rr_char`` status bit; ``true`` skipped that
            branch. Unused here — kept for signature parity with
            libp.h.
    """
    _ = serial_mode  # Signature parity — Linux body is commented out.


def reset_spc() -> None:
    """Reset the SPC (synthesizer-processor) chip. No-op on Linux.

    Faithful translation of:

    .. code-block:: c

        void reset_spc()
        {
        /*
          unsigned int temp,old_vol;

          old_vol = KS.volume;
          vol_set(0);
          clr_gpio(GPIO_RESET+GPIO_STOP);
          set_gpio(GPIO_RESET+GPIO_STOP);
          if(KS.pause)
            clr_gpio(GPIO_STOP);
          temp = LAST_VOICE;
          write_pipe(KS.lts_pipe,&temp,1);
          while(old_vol)
          {
            vol_up(1);
            old_vol -= 1;
          }
        */
        }

    Marked ``NOT IMPLEMENTED`` in the C source — the body is entirely
    commented out. The original would have toggled the SPC chip's
    reset / stop GPIO lines and replayed the last voice through the
    LTS pipe; the libtts_us.so build does not drive any such chip,
    so this routine does nothing.
    """
    return None


__all__ = ["reset_spc", "send_index", "start_flush"]
