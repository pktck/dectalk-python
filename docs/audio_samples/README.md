# Audio samples

Side-by-side renderings of a fixed prompt set so a human reviewer can
compare the Python port against the original FONIX DECtalk binary.

Each prompt produces two WAV files at 11025 Hz mono int16:

- `<slug>.python.wav` — `dectalk.speak(prompt)` (this repo).
- `<slug>.binary.wav` — DECtalk 4.61 Linux `say` binary, default voice
  (Perfect Paul). Generated on a Linux host that has the binary
  release at `/tmp/dectalk-binary-stable/`. The binary itself is not
  bundled here; only its outputs.

Prompts (deliberately small and varied):

| slug | text |
|---|---|
| `hello-world` | hello world |
| `this-is-a-test` | this is a test |
| `the-quick-brown-fox` | the quick brown fox |
| `computer` | computer |
| `she-sells-sea-shells` | she sells sea shells |
| `good-morning` | good morning |
| `good-morning-how-are-you-today-have-a-great-day` | good morning. how are you today? have a great day! |

The last one is the multi-sentence prompt — it exercises sentence-level
prosody on all three terminators (`.`, `?`, `!`) so a reviewer can hear
that each sentence resets its declination contour rather than ramping
down monotonically across the full span.

## Listening

Open both files for a prompt in any audio player and play them
back-to-back. Things you'll likely hear:

- Voice timbre is close (same Klatt model).
- Prosody and segmental durations differ — the binary's prosody
  pipeline is more elaborate than ours, so words are roughly 25 %
  longer there. The Python output sounds a bit clipped in time but
  not choppy.
- The Python rendering has no audible static, hum, or whistle on any
  of these prompts. If a sample acquires one, that's a regression.

`report.md` next to these files has the per-prompt metrics that
`scripts/diagnose_audio.py` computes — inter-harmonic SNR,
voiced-only high-band power (the static check), and spectrogram
cosine similarity vs the binary.

## Regenerating

```sh
uv run python scripts/diagnose_audio.py --out-dir docs/audio_samples
```

The harness skips the binary leg automatically when
`/tmp/dectalk-binary-stable/say` isn't present, so this command
works on any machine — but binary WAVs only refresh on hosts that
have the release installed.
