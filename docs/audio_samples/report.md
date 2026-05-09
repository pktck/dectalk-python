# DECtalk Python port — audio diagnostic report

Binary reference dir: `/tmp/dectalk-binary-stable`

## `hello world` — PASS
- Python WAV: `hello-world.python.wav`
- Binary WAV: `hello-world.binary.wav`

- `python_duration_s`: 0.908
- `python_peak`: 17314
- `inter_harmonic_snr_db`: 15.07
- `voiced_high_band_db`: -83.73
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.256
- `length_ratio`: 0.723
- `rms_correlation`: 0.402
- `spectrogram_cosine`: 0.734

## `this is a test` — PASS
- Python WAV: `this-is-a-test.python.wav`
- Binary WAV: `this-is-a-test.binary.wav`

- `python_duration_s`: 1.167
- `python_peak`: 11616
- `inter_harmonic_snr_db`: 15.94
- `voiced_high_band_db`: -73.61
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.436
- `length_ratio`: 0.813
- `rms_correlation`: 0.495
- `spectrogram_cosine`: 0.61

## `the quick brown fox` — PASS
- Python WAV: `the-quick-brown-fox.python.wav`
- Binary WAV: `the-quick-brown-fox.binary.wav`

- `python_duration_s`: 1.527
- `python_peak`: 19770
- `inter_harmonic_snr_db`: 15.91
- `voiced_high_band_db`: -80.02
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.797
- `length_ratio`: 0.85
- `rms_correlation`: -0.444
- `spectrogram_cosine`: 0.552

## `computer` — PASS
- Python WAV: `computer.python.wav`
- Binary WAV: `computer.binary.wav`

- `python_duration_s`: 0.798
- `python_peak`: 15915
- `inter_harmonic_snr_db`: 24.2
- `voiced_high_band_db`: -82.16
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.108
- `length_ratio`: 0.721
- `rms_correlation`: -0.282
- `spectrogram_cosine`: 0.611

## `she sells sea shells` — PASS
- Python WAV: `she-sells-sea-shells.python.wav`
- Binary WAV: `she-sells-sea-shells.binary.wav`

- `python_duration_s`: 1.556
- `python_peak`: 12634
- `inter_harmonic_snr_db`: 18.75
- `voiced_high_band_db`: -77.15
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.822
- `length_ratio`: 0.854
- `rms_correlation`: -0.29
- `spectrogram_cosine`: 0.649

## `good morning` — PASS
- Python WAV: `good-morning.python.wav`
- Binary WAV: `good-morning.binary.wav`

- `python_duration_s`: 0.938
- `python_peak`: 18942
- `inter_harmonic_snr_db`: 15.69
- `voiced_high_band_db`: -87.11
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.224
- `length_ratio`: 0.766
- `rms_correlation`: -0.345
- `spectrogram_cosine`: 0.688

## Per-field interpolation audit
Each row holds one consonant-frame field at its consonant value during an otherwise-AH segment, and reports the resulting voiced-segment high/mid energy ratio (in dB) vs the baseline pure-AH segment. A large positive Δ implicates that field as a noise source under naive interpolation.

| field | consonant | with (dB) | baseline (dB) | Δ (dB) |
|---|---|---|---|---|
| `F2` | S | -23.8 | -33.3 | +9.5 |
| `F2` | T | -23.8 | -33.3 | +9.5 |
| `F2` | HH | -27.4 | -33.3 | +5.9 |
| `F3` | T | -28.2 | -33.3 | +5.0 |
| `B1` | HH | -29.2 | -33.3 | +4.1 |
| `B1` | S | -29.2 | -33.3 | +4.1 |
| `B1` | T | -30.4 | -33.3 | +2.9 |
| `B1` | P | -30.4 | -33.3 | +2.9 |
| `F3` | HH | -31.6 | -33.3 | +1.7 |
| `B2` | HH | -32.5 | -33.3 | +0.7 |
| `B2` | S | -32.5 | -33.3 | +0.7 |
| `B2` | T | -32.8 | -33.3 | +0.4 |
| `B2` | P | -32.8 | -33.3 | +0.4 |
| `Ah` | T | -33.1 | -33.3 | +0.2 |
| `Ah` | P | -33.1 | -33.3 | +0.2 |
| `F3` | S | -33.1 | -33.3 | +0.1 |
| `A2f` | HH | -33.3 | -33.3 | +0.0 |
| `A3f` | HH | -33.3 | -33.3 | +0.0 |
| `A4f` | HH | -33.3 | -33.3 | +0.0 |
| `A2f` | S | -33.3 | -33.3 | +0.0 |
