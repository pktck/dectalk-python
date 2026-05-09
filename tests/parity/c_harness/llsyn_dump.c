/*
 * Parity harness around the FONIX hlsyn LLSynthesize().
 *
 * Drives the C synthesiser with a hand-crafted Speaker + LLFrame and dumps
 * raw int16 PCM to stdout. The companion `tests/parity/test_synth_parity.py`
 * builds this harness, runs it for a battery of frame configurations, runs
 * the same configurations through `dectalk.hlsyn.synthesize.ll_synthesize`,
 * and asserts the two waveforms agree within a tight LSB tolerance.
 *
 * Build:
 *   gcc -O2 -o llsyn_dump llsyn_dump.c reson.c voice.c sample.c frame.c -lm
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "llsyn.h"

#define EXPECTED_ARGC 61  /* argv[0] + 11 speaker + 1 nframes + 48 frame fields */

static int parse_short(const char *s) {
  return (int) strtol(s, NULL, 10);
}

int main(int argc, char **argv) {
  if (argc != EXPECTED_ARGC) {
    fprintf(stderr, "usage: %s expects %d positional fields, got %d\n",
            argv[0], EXPECTED_ARGC - 1, argc - 1);
    return 2;
  }

  LLSynth synth;
  LLFrame frame;
  Speaker spkr;
  short wave[2048];

  memset(&synth, 0, sizeof(synth));
  memset(&frame, 0, sizeof(frame));
  memset(&spkr, 0, sizeof(spkr));

  int idx = 1;

  spkr.SR = parse_short(argv[idx++]);
  spkr.UI = parse_short(argv[idx++]);
  spkr.SS = parse_short(argv[idx++]);
  spkr.NF = parse_short(argv[idx++]);
  spkr.RS = parse_short(argv[idx++]);
  spkr.SB = parse_short(argv[idx++]);
  spkr.CP = parse_short(argv[idx++]);
  spkr.OS = parse_short(argv[idx++]);
  spkr.GV = parse_short(argv[idx++]);
  spkr.GH = parse_short(argv[idx++]);
  spkr.GF = parse_short(argv[idx++]);
  synth.spkr = spkr;

  int nframes = parse_short(argv[idx++]);

  frame.F0  = parse_short(argv[idx++]);
  frame.AV  = parse_short(argv[idx++]);
  frame.OQ  = parse_short(argv[idx++]);
  frame.SQ  = parse_short(argv[idx++]);
  frame.TL  = parse_short(argv[idx++]);
  frame.FL  = parse_short(argv[idx++]);
  frame.DI  = parse_short(argv[idx++]);
  frame.Ah  = parse_short(argv[idx++]);
  frame.Af  = parse_short(argv[idx++]);
  frame.F1  = parse_short(argv[idx++]);
  frame.B1  = parse_short(argv[idx++]);
  frame.DF1 = parse_short(argv[idx++]);
  frame.DB1 = parse_short(argv[idx++]);
  frame.F2  = parse_short(argv[idx++]);
  frame.B2  = parse_short(argv[idx++]);
  frame.F3  = parse_short(argv[idx++]);
  frame.B3  = parse_short(argv[idx++]);
  frame.F4  = parse_short(argv[idx++]);
  frame.B4  = parse_short(argv[idx++]);
  frame.F5  = parse_short(argv[idx++]);
  frame.B5  = parse_short(argv[idx++]);
  frame.F6  = parse_short(argv[idx++]);
  frame.B6  = parse_short(argv[idx++]);
  frame.FNP = parse_short(argv[idx++]);
  frame.BNP = parse_short(argv[idx++]);
  frame.FNZ = parse_short(argv[idx++]);
  frame.BNZ = parse_short(argv[idx++]);
  frame.FTP = parse_short(argv[idx++]);
  frame.BTP = parse_short(argv[idx++]);
  frame.FTZ = parse_short(argv[idx++]);
  frame.BTZ = parse_short(argv[idx++]);
  frame.A2f = parse_short(argv[idx++]);
  frame.A3f = parse_short(argv[idx++]);
  frame.A4f = parse_short(argv[idx++]);
  frame.A5f = parse_short(argv[idx++]);
  frame.A6f = parse_short(argv[idx++]);
  frame.Ab  = parse_short(argv[idx++]);
  frame.B2F = parse_short(argv[idx++]);
  frame.B3F = parse_short(argv[idx++]);
  frame.B4F = parse_short(argv[idx++]);
  frame.B5F = parse_short(argv[idx++]);
  frame.B6F = parse_short(argv[idx++]);
  frame.ANV = parse_short(argv[idx++]);
  frame.A1V = parse_short(argv[idx++]);
  frame.A2V = parse_short(argv[idx++]);
  frame.A3V = parse_short(argv[idx++]);
  frame.A4V = parse_short(argv[idx++]);
  frame.ATV = parse_short(argv[idx++]);

  for (int fi = 0; fi < nframes; fi++) {
    LLSynthesize(&synth, &frame, wave);
    fwrite(wave, sizeof(short), spkr.UI, stdout);
  }
  return 0;
}
