# DECtalk Python port — audio diagnostic report

Binary reference dir: `/tmp/dectalk-binary-stable`

## `hello world` — PASS
- Python WAV: `hello-world.python.wav`
- Binary WAV: `hello-world.binary.wav`

- `python_duration_s`: 0.958
- `python_peak`: 15799
- `inter_harmonic_snr_db`: 17.86
- `voiced_high_band_db`: -88.65
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.256
- `length_ratio`: 0.763
- `rms_correlation`: 0.693
- `spectrogram_cosine`: 0.727
- `mcd_global_db`: 50.36
- `mcd_chunk_mean_db`: 51.3
- `mcd_chunk_p95_db`: 55.01
- `lsd_global_db`: 13.15
- `dtw_warp_ratio`: 1.077
- `lsd_chunk_p95_db`: 14.26

## `this is a test` — PASS
- Python WAV: `this-is-a-test.python.wav`
- Binary WAV: `this-is-a-test.binary.wav`

- `python_duration_s`: 1.197
- `python_peak`: 11627
- `inter_harmonic_snr_db`: 15.14
- `voiced_high_band_db`: -74.12
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.436
- `length_ratio`: 0.834
- `rms_correlation`: 0.284
- `spectrogram_cosine`: 0.621
- `mcd_global_db`: 55.15
- `mcd_chunk_mean_db`: 54.9
- `mcd_chunk_p95_db`: 62.4
- `lsd_global_db`: 13.72
- `dtw_warp_ratio`: 1.151
- `lsd_chunk_p95_db`: 16.22

## `the quick brown fox` — PASS
- Python WAV: `the-quick-brown-fox.python.wav`
- Binary WAV: `the-quick-brown-fox.binary.wav`

- `python_duration_s`: 1.576
- `python_peak`: 19790
- `inter_harmonic_snr_db`: 11.49
- `voiced_high_band_db`: -80.61
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.797
- `length_ratio`: 0.877
- `rms_correlation`: -0.291
- `spectrogram_cosine`: 0.559
- `mcd_global_db`: 58.17
- `mcd_chunk_mean_db`: 57.39
- `mcd_chunk_p95_db`: 60.11
- `lsd_global_db`: 14.83
- `dtw_warp_ratio`: 1.099
- `lsd_chunk_p95_db`: 16.86

## `computer` — PASS
- Python WAV: `computer.python.wav`
- Binary WAV: `computer.binary.wav`

- `python_duration_s`: 0.838
- `python_peak`: 14659
- `inter_harmonic_snr_db`: 23.84
- `voiced_high_band_db`: -81.48
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.108
- `length_ratio`: 0.757
- `rms_correlation`: 0.158
- `spectrogram_cosine`: 0.618
- `mcd_global_db`: 58.41
- `mcd_chunk_mean_db`: 60.39
- `mcd_chunk_p95_db`: 65.26
- `lsd_global_db`: 16.21
- `dtw_warp_ratio`: 1.068
- `lsd_chunk_p95_db`: 21.91

## `she sells sea shells` — PASS
- Python WAV: `she-sells-sea-shells.python.wav`
- Binary WAV: `she-sells-sea-shells.binary.wav`

- `python_duration_s`: 1.586
- `python_peak`: 14262
- `inter_harmonic_snr_db`: 25.13
- `voiced_high_band_db`: -77.82
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.822
- `length_ratio`: 0.87
- `rms_correlation`: -0.206
- `spectrogram_cosine`: 0.653
- `mcd_global_db`: 47.72
- `mcd_chunk_mean_db`: 51.3
- `mcd_chunk_p95_db`: 62.14
- `lsd_global_db`: 13.47
- `dtw_warp_ratio`: 1.023
- `lsd_chunk_p95_db`: 13.97

## `good morning` — PASS
- Python WAV: `good-morning.python.wav`
- Binary WAV: `good-morning.binary.wav`

- `python_duration_s`: 0.968
- `python_peak`: 18169
- `inter_harmonic_snr_db`: 16.63
- `voiced_high_band_db`: -87.11
- `soft_limiter_triggered`: no
- `binary_duration_s`: 1.224
- `length_ratio`: 0.791
- `rms_correlation`: -0.163
- `spectrogram_cosine`: 0.693
- `mcd_global_db`: 53.88
- `mcd_chunk_mean_db`: 54.56
- `mcd_chunk_p95_db`: 58.3
- `lsd_global_db`: 14.22
- `dtw_warp_ratio`: 1.028
- `lsd_chunk_p95_db`: 15.08

## `good morning, my friend. how are you today? have a great day!` — PASS
- Python WAV: `good-morning-my-friend-how-are-you-today-have-a-great-day.python.wav`
- Binary WAV: `good-morning-my-friend-how-are-you-today-have-a-great-day.binary.wav`

- `python_duration_s`: 4.669
- `python_peak`: 19920
- `inter_harmonic_snr_db`: 17.27
- `voiced_high_band_db`: -77.19
- `soft_limiter_triggered`: no
- `binary_duration_s`: 4.92
- `length_ratio`: 0.949
- `rms_correlation`: 0.263
- `spectrogram_cosine`: 0.69
- `mcd_global_db`: 47.96
- `mcd_chunk_mean_db`: 47.97
- `mcd_chunk_p95_db`: 60.65
- `lsd_global_db`: 12.56
- `dtw_warp_ratio`: 1.207
- `lsd_chunk_p95_db`: 16.26

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
