"""Audio I/O for DECtalk: WAV file writing and live playback.

Replaces the platform-specific glue in the C `nt/` module (which targeted
Windows NT WaveOut). The Python implementation uses `wave` from the standard
library for file I/O and `sounddevice` for cross-platform live playback.
"""

from dectalk.nt.audio import play, write_wav

__all__ = ["play", "write_wav"]
