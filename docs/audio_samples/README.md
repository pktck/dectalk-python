# Audio samples

Side-by-side renderings of the **bit-parity corpus** (the same 33-prompt
set the binary-WAV parity test gates against) so a human reviewer can
listen to the Python port output alongside the original FONIX DECtalk
binary.

Each prompt produces two WAV files at 11025 Hz mono int16:

- `<slug>.python.wav` — `dectalk.speak(prompt)` (this repo).
- `<slug>.binary.wav` — DECtalk 4.61 Linux `say` binary, default voice
  (Perfect Paul). Generated on a Linux host that has the binary
  release at `/tmp/dectalk-binary-stable/`. The binary itself is not
  bundled here; only its outputs.

The corpus is the canonical list in `tests/parity/_corpus.py` —
`tests/parity/test_binary_wav_parity.py` asserts each prompt produces
a **byte-identical** WAV between the two paths. As of `c68406b` every
prompt in the corpus passes, so `<slug>.python.wav` and
`<slug>.binary.wav` are bit-identical files (you can `cmp` them).

The 33 prompts (see `tests/parity/_corpus.py` for the source of truth):

| category | sample prompts |
|---|---|
| baseline | hello world; the quick brown fox; she sells sea shells; … |
| numbers | the answer is 42; 3 point 14; 1234567890; … |
| punctuation | hello! how are you?; wait... what just happened?; yes; no; maybe. |
| inline rate | `[:rate 100] slow`; `[:rate 250] testing one two three`; `[:rate 400] fast speech` |
| voice presets | `[:nb] betty`, `[:nh] harry`, `[:nf] frank`, `[:nd] dennis`, `[:nk] kit`, `[:nu] ursula`, `[:nr] rita`, `[:nw] wendy` |
| spell-outs | FBI; NASA; USA; MIT |
| phonotactics | judge thought rhythms; knight light right |
| abbreviations | Dr. Smith said hello. |
| long sentence | the rain in spain falls mainly on the plain |

## Prosody comparison

`scripts/diagnose_audio.py --binary-dir <dir>` runs a quantitative
acoustic comparison alongside the listening test. Each prompt gets a
DTW-aligned spectrogram comparison and the report at `report.md`
records:

- **LSD** (log-spectral distance) in dB — primary gate. Measures
  direct log-mel divergence; "spectrograms look similar" maps onto
  small LSD.
- **MCD** (mel-cepstral distortion) — informational. Reported but
  not gated, because pipeline-vs-pipeline comparisons land in a
  different MCD band than the speaker-vs-speaker comparisons MCD was
  calibrated for in academic TTS work.
- **DTW warp ratio** — how much the alignment had to repeat frames.
  Values near 1.0 mean similar pacing.

Per-prompt JSON detail is written under
`docs/audio_samples/comparisons/`;
`comparisons/baseline.json` captures the pre-Phase-4 numbers so
subsequent improvements have a delta to point at.

## Listening

Open both files for a prompt in any audio player and play them
back-to-back. At bit parity the two are identical — `python.wav` and
`binary.wav` should sound the same on every prompt. `cmp` confirms it:

```sh
cmp docs/audio_samples/hello-world.python.wav docs/audio_samples/hello-world.binary.wav
# (no output, exit 0)
```

`report.md` next to these files has per-prompt metrics from
`scripts/diagnose_audio.py` — inter-harmonic SNR, voiced-only high-band
power, and DTW-aligned spectrogram cosine similarity vs the binary.
Since the WAVs are byte-identical, `spectrogram_cosine: 1.0`,
`mcd_chunk_mean_db: 0.0`, and `lsd_global_db: 0.0` across every prompt
in the corpus.

## Regenerating

```sh
uv run python scripts/diagnose_audio.py \
    --bit-parity-corpus \
    --out-dir docs/audio_samples
```

The `--bit-parity-corpus` flag pulls prompts from
`tests/parity/_corpus.py` (the same list the parity test uses) so the
two paths stay in sync. Without that flag the script falls back to a
small 7-prompt default corpus.

The harness skips the binary leg automatically when
`/tmp/dectalk-binary-stable/say` isn't present, so this command works
on any machine — but binary WAVs only refresh on hosts that have the
release installed.
