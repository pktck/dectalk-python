# DECtalk pipeline — stage boundaries

Inventory of the inter-stage data shapes inside the DECtalk C library
(`/tmp/dectalk-src`, `develop` branch), to be consumed by the per-stage
parity-oracle infrastructure (Phase A.4 of the C-to-Python port).

The synthesizer is a 5-stage pipeline glued together by four kernel
pipes. Each stage runs in its own thread; the pipes carry the boundary
data between them.

```
   TextToSpeechSpeak()  ──► [KERNEL]  ──► cmd_pipe (bytes)
   cm_pars_loop()       ──► [CMD]     ──► lts_pipe (16-bit words)
   lts_main_loop()      ──► [LTS+dic] ──► new_lts_pipe (32-bit dwords)
   ph_main()            ──► [PH]      ──► ph_pipe   (16-bit words)
   vtm_main()           ──► [VTM]     ──► vtm_pipe  (16-bit words) ──► PCM
```

Pipe type constants (`src/dapi/src/include/pipe.h:31159-31161`):
`BYTE_PIPE = 0`, `WORD_PIPE = 1`, `DWORD_PIPE = 2`.

## Per-stage boundaries

| Stage | Exit-pipe variable | Pipe type | Writer site (file:line) | Reader site (file:line) | What flows over the wire |
|---|---|---|---|---|---|
| KERNEL | `pKsd_t->cmd_pipe` | `BYTE_PIPE` (uint8) | `src/dapi/src/api/ttsapi.c:9326,9350` (`TextToSpeechThreadMain`, Linux/macOS branch) | `src/dapi/src/cmd/cm_pars.c:1815,1913` (`cm_pars_getseq` via `read_pipe`) | Raw input text byte stream after the `TextToSpeechSpeak`/`SpeakEx` queue, including the appended force-character `cForce = (PFASCII<<PSFONT)+0xb` when `TTS_FORCE` is set (`ttsapi.c:4783`). One contiguous chunk per `Speak()` call, up to `MAX_TEXT_WRITE_LENGTH` bytes per `write_pipe` call. |
| CMD | `pKsd_t->lts_pipe` | `WORD_PIPE` (uint16) | `src/dapi/src/cmd/cm_util.c` (`cm_util_write_pipe` wrapper), call sites e.g. `cm_cmd.c:1785,1792`, `cm_copt.c:2921,2964,3022,3637,3668`, `cm_pars.c` (via `cm_util_sendat`) | `src/dapi/src/lts/ls_task.c` (LTS task input; `lts_main_loop` at `ls_task.c:53349`) | 16-bit "pipe tokens" emitted by the command-parser state machine: classified text/punctuation characters, in-band control codes (PFASCII-tagged), voice-change events, phonetic-mode escapes from `[...]` brackets. TODO: enumerate the token tag bits exhaustively. |
| LTS+dic | `pKsd_t->new_lts_pipe` | `DWORD_PIPE` (uint32) | LTS routines under `src/dapi/src/lts/` (e.g. `lsw_main.c`, `ls_task.c`, `ls_util.c`); the patched `TextToSpeechConvertToPhonemes` path already reads this pipe via `ls_util` logging. | `src/dapi/src/ph/ph_main.c:271494,271521,271527,271529` (`ph_main`) | 32-bit phoneme records: ARPABET allophone code in the low byte, stress bits + boundary flags + voice/language nybbles in the high bits. This is the boundary the existing `CAPI.convert_to_phonemes()` already exposes (NUL-terminated, space-separated lowercase ARPABET). TODO: document the exact bit packing. |
| PH | `pKsd_t->ph_pipe` | `WORD_PIPE` (uint16) | `src/dapi/src/ph/ph_main.c`, `ph_task.c:279035`; writes at `ttsapi.c:6478`, `kernel/services.c:1280` (`LastVoice` injection); flush sentinel at `ttsapi.c:3888` | `src/dapi/src/vtm/vtmio.c:297937,297954,298018,298064,298128,298447`; `vtm/vtmiont.c:299176,300161,300227,300347` (`vtm_main`) | Packed VTM-parameter command words: a 16-bit `control` token (`VOICE`, `TONE`, `SPDEF`, `INDEX`, frame), optionally followed by N parameter words (e.g. `VOICE_PARS`, `TONE_PARS`). Encodes per-frame F0, formant frequencies/bandwidths, voicing/aspiration, source switch. TODO: enumerate `control` tags and per-tag payload widths from `vfphdefs.h` / `viphdefs.h`. |
| VTM | `pKsd_t->vtm_pipe` (and onward to the audio buffer) | `WORD_PIPE` (uint16) | `src/dapi/src/kernel/services.c:354`, `vtm/vtm.c` / `vtm_f.c` / `vtm_i.c` / `vtm[0-9].c` (synth loops); flush sentinel `ttsapi.c:3858` | Audio buffer drain — `vtm_main` (`vtm/vtmio.c:297864`, `vtm/vtmiont.c:298936-298944`) feeds the wave-output device or `WriteAudioToFile` sink. | Final formant-synthesizer command stream just before PCM rendering. The actual audio (signed 16-bit mono samples at the speaker's sample rate, typically 11025 Hz) is what leaves the stage. TODO: decide whether to dump VTM-input control words or the synthesised PCM frames; the latter is the byte-identical parity target already exercised by `tests/parity/test_binary_wav_parity.py`. |

## Boundaries currently exposed for parity testing

| Boundary | How accessed today | Notes |
|---|---|---|
| KERNEL exit | (new) `CAPI.dump_pipeline(text, ["kernel"])` — see `tests/parity/c_patches/0002-stage-boundary-dumps.patch` | Patch dumps the buffer handed to `write_pipe(pKsd_t->cmd_pipe, …)` to `$DECTALK_DUMP_DIR/kernel.dump` for byte-equality checks against the Python kernel port. |
| CMD exit | exposed via 0003 patch — `CAPI.dump_pipeline(text, ["cmd"])` reads `$DECTALK_DUMP_DIR/cmd.dump`, see `tests/parity/c_patches/0003-cmd-stage-dump-hooks.patch` | The Linux build is `SINGLE_THREADED`, so the CMD-stage no longer writes to `pKsd_t->lts_pipe` — instead `cm_util.c` and friends call `lts_loop()` directly with the same 16-bit token. The patch hooks `lts_loop` at function entry and emits `cmd_write 1\n<%04x>\n` per call. |
| LTS exit | `CAPI.convert_to_phonemes(text)` (existing) — also reachable via the planned `lts.dump` once added. | The ASCII allophone string already serves as a parity oracle for `src/dectalk/lts/`. A future `lts.dump` could emit the raw 32-bit DWORD stream instead, for downstream parity on PH input. |
| PH exit | TODO | Hook to add: tap writes to `pKsd_t->ph_pipe`. Output: per-frame VTM-parameter records (`(control, [payload])` tuples) in a canonical textual form. |
| VTM exit | `CAPI.speak(text)` returns byte-identical WAV (existing) — `tests/parity/test_binary_wav_parity.py`. | Already covered for the byte-equality goal; a finer-grain VTM-input dump would help debug isolated PH-vs-VTM regressions. |

## Conventions for `<stage>.dump` files

To keep the dumps diff-able and language-agnostic between C and Python:

- **Plain ASCII text**, one record per line, `\n` line terminator.
- **Deterministic ordering**: written in the order the C code emits them.
- **Stable encoding**: bytes shown as `%02x`, words as `%04x`, dwords as
  `%08x`. Multi-field records are space-separated, e.g.
  `04 frame fc 8a fd 0c …`.
- **No timestamps, no PIDs**, no `\r`.
- **File naming**: `<DECTALK_DUMP_DIR>/<stage>.dump` for
  `stage ∈ {kernel, cmd, lts, ph, vtm}`.
- **Append within a single `speak()` call**, truncate on each
  `Startup()` so multi-call sessions are kept separate. (The Python
  wrapper sets a fresh `DECTALK_DUMP_DIR` per call, so this is mostly
  defensive.)

## Source-anchor reference for follow-up patches

For Phase A.4 expansion (patches `0004` … `0006`), the relevant
write-site anchors are:

- **CMD exit** — `src/dapi/src/cmd/cm_util.c` `cm_util_write_pipe`
  (centralised helper used by `cm_cmd.c`, `cm_pars.c`, `cm_copt.c`,
  `cm_chari.c`). On Linux/`SINGLE_THREADED` builds this helper is
  unreachable; the CMD stage hands tokens to `lts_loop()` directly.
  Patch `0003` therefore hooks `lts_loop` at function entry instead.
- **LTS exit** — `src/dapi/src/lts/ls_util.c` (the same helper the
  existing `0001` patch already touches indirectly via the phoneme
  log).
- **PH exit** — direct `write_pipe(pKsd_t->ph_pipe, …)` call sites
  (single-pass `grep` in `src/dapi/src/ph/`).
- **VTM exit** — direct `write_pipe(pKsd_t->vtm_pipe, …)` call sites
  in `src/dapi/src/kernel/services.c` plus the per-frame writers in
  `src/dapi/src/vtm/`.

Each new patch should:

1. Add a `_dectalk_dump_open(<stage>)` call once per `Startup()`
   (lazy, env-gated, idempotent — see `0002` for the pattern).
2. Emit one canonical record per pipe-write site, gated on
   `_dectalk_dump_fp_<stage> != NULL`.
3. Land alongside a Python parity test under `tests/parity/` that
   skips when `/tmp/dectalk-src` is absent.
