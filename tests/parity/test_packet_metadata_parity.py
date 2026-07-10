"""Per-packet OUT_PH/OUT_DU/OUT_PH2 metadata parity vs the C oracle dump.

Pins the packet-metadata acceptance of issues #277 / #290: every SPC
voice packet's phoneme-metadata cells must be byte-equal to the C
oracle's ``vtm_frames.dump`` (patch 0006) rows. Three mechanisms feed
these cells, and each has diverged at least once during the port:

- ``ph_claus.c:465-472`` — the driver writes ``OUT_PH``/``OUT_DU``/
  ``OUT_PH2`` when ``nphone`` advances; the ``nphone+1 > nallotot``
  guard does NOT exclude ``== nallotot``, so the final phone's
  ``OUT_PH2`` reads ``allophons[nallotot]`` — one past the populated
  range.
- ``ph_drwt01.c:3022-3023`` (active US variant tail) — ``pht0draw``
  re-stamps ``OUT_PH``/``OUT_DU`` every frame from its own F0-segment
  pointer ``np_drawt0``, overriding the driver values (ported in
  #297/#299; gates the vtm1.c:1318 silence ramp-down).
- ``ph_claus.c:597`` — ``phonemes`` aliases ``&allophons[SAFETY]``, so
  the one-past-end ``OUT_PH2`` read publishes phoneme-stream leftovers
  (e.g. ``hello world``'s final-phone ``OUT_PH2 == 7707`` = ``LL``
  showing through after ``phinton``'s dummy-schwa insert). The Python
  port replays the alias in ``us_phalloph2`` (#290).

Beyond correctness for its own sake, per-frame alignment tooling
(``scripts/diag_packet_diff.py``, the divergence maps) keys phoneme
context off these cells; wrong values mis-attribute frames to phones.

Method per ``docs/PARITY-METHOD.md`` §4: the oracle side dumps one
``vtm_frame 21 <p0> … <p20>`` line per voice packet via
``DECTALK_DUMP_DIR`` + patch 0006; the Python side captures the exact
packet list handed to ``pump_frames_via_vtm1`` (the post-``send_pars``
delaypars stream — the metadata cells ride the one-frame-delayed side
of the packet). Every capture is sanity-gated on OUT_T0 ramping.

Skips cleanly when the C oracle artefacts are missing.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from dectalk._capi import CAPI
from dectalk.ph.param_indices import OUT_DU, OUT_PH, OUT_PH2, OUT_T0

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_BIN_ROOT = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))


def _have_artefacts() -> bool:
    """True if both the source-built libtts.so and the shipped binary exist."""
    has_lib = any(_SRC_ROOT.glob("src/dtalkml/build/*/us/release/libtts.so")) and any(
        _SRC_ROOT.glob("src/dapi/build/dectalk/*/us/release/libtts_us.so")
    )
    has_bin = (_BIN_ROOT / "say").is_file() and (_BIN_ROOT / "DECtalk.conf").is_file()
    return has_lib and has_bin


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not _have_artefacts(),
        reason="locally-built libtts or shipped DECtalk binary not present",
    ),
]


# Pinned prompts. Each exercises a distinct metadata mechanism:
#   - "hello world": np_drawt0 lead/lag around HX (the #277 headline
#     case) AND the dummy-schwa OUT_PH2 one-past-end tail (C emits the
#     aliased phoneme-stream cell 7707 on all 71 final-phone packets).
#   - "testing one two three" / "the quick brown fox": longer streams;
#     one-past-end tail lands on the phalloph delete-shift SIL dup.
#   - "chairs, tables, lamps, and rugs": multi-clause — per-clause
#     np_drawt0 soft-init resets and cross-clause scratch staleness.
#   - "hi": nallotot < SAFETY, so the one-past-end read sits below the
#     phoneme-stream alias window (pre-clause zero scratch on both
#     sides).
_PROMPTS: tuple[str, ...] = (
    "hello world",
    "testing one two three",
    "the quick brown fox",
    "chairs, tables, lamps, and rugs",
    "hi",
)

_METADATA_CELLS: tuple[tuple[int, str], ...] = (
    (OUT_PH, "OUT_PH"),
    (OUT_DU, "OUT_DU"),
    (OUT_PH2, "OUT_PH2"),
)

# OUT_T0 capture sanity gate (PARITY-METHOD §4): a healthy declarative
# contour ramps well over 5 Hz; a flat series means the capture ran the
# wrong pipeline and every conclusion from it must be discarded.
_MIN_F0_SPAN_HZ: float = 5.0


@pytest.fixture(scope="module")
def capi() -> CAPI:
    """Module-scoped CAPI instance reused across the metadata tests."""
    return CAPI(src_root=_SRC_ROOT, data_root=_BIN_ROOT)


def _int16(value: int) -> int:
    """Reinterpret the low 16 bits as a signed int16 (dump cells are shorts)."""
    masked = value & 0xFFFF
    return masked - 0x10000 if masked >= 0x8000 else masked


def _assert_f0_ramps(packets: list[list[int]], label: str, text: str) -> None:
    """PARITY-METHOD §4 capture sanity gate: OUT_T0 must show a ramping F0."""
    f0s = [40000.0 / p[OUT_T0] for p in packets if p[OUT_T0] > 0]
    span = (max(f0s) - min(f0s)) if f0s else 0.0
    assert span > _MIN_F0_SPAN_HZ, (
        f"{label} capture for {text!r} has flat F0 (span {span:.1f} Hz) -- "
        "wrong pipeline captured? Discard this capture (PARITY-METHOD §4)."
    )


def _oracle_packets(capi: CAPI, text: str) -> list[list[int]]:
    """Capture the oracle's per-packet dump rows (all 21 cells).

    ``CAPI._speak_locked`` with ``DECTALK_DUMP_DIR`` set makes patch
    0006 write one ``vtm_frame`` line per SPC voice packet.
    """
    with tempfile.TemporaryDirectory(prefix="dectalk-meta-") as dump_dir:
        prev = os.environ.get("DECTALK_DUMP_DIR")
        os.environ["DECTALK_DUMP_DIR"] = dump_dir
        try:
            with capi._instance_lock:
                capi._speak_locked(text, speaker=0, rate=None, encoding=1)
        finally:
            if prev is None:
                os.environ.pop("DECTALK_DUMP_DIR", None)
            else:
                os.environ["DECTALK_DUMP_DIR"] = prev
        dump_path = Path(dump_dir) / "vtm_frames.dump"
        if not dump_path.is_file():
            pytest.skip(
                "vtm_frames.dump not produced; patch 0006 not applied "
                "to the C oracle? Re-run scripts/setup_c_oracle.sh."
            )
        payload = dump_path.read_bytes().decode("latin-1")

    packets: list[list[int]] = []
    for line in payload.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "vtm_frame":
            count = int(parts[1])
            packets.append([int(x) for x in parts[2 : 2 + count]])
    return packets


def _python_packets(text: str, monkeypatch: pytest.MonkeyPatch) -> list[list[int]]:
    """Capture the exact packet stream the Python driver feeds vtm1.

    Wraps :func:`dectalk.vtm.pump_frames.pump_frames_via_vtm1` (imported
    lazily by the driver, so patching the source module attribute is
    enough) and renders via ``_speak_via_python_full`` — the FULL+VTM1
    parity path. Cells are int16-wrapped to match the dump's shorts.
    """
    monkeypatch.setenv("DECTALK_DISABLE_CAPI", "1")
    monkeypatch.setenv("DECTALK_FULL_PIPELINE", "1")

    import dectalk.vtm.pump_frames as pf  # noqa: PLC0415
    from dectalk.api.speak import _speak_via_python_full  # noqa: PLC0415

    captured: list[list[int]] = []
    real = pf.pump_frames_via_vtm1

    def _capture(frames: list[list[int]], *args: object, **kwargs: object) -> object:
        captured.extend([_int16(v) for v in frame] for frame in frames)
        return real(frames, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pf, "pump_frames_via_vtm1", _capture)
    _speak_via_python_full(text, 1.0, None, "us", True)
    assert captured, f"pump_frames_via_vtm1 never called for {text!r}"
    return captured


@pytest.mark.parametrize("text", _PROMPTS, ids=lambda p: p.replace(" ", "_"))
def test_packet_metadata_cells_byte_equal(
    capi: CAPI, text: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OUT_PH/OUT_DU/OUT_PH2 match the oracle dump on every packet.

    Hard pass: packet counts must be equal and each metadata cell must
    be byte-equal on all packets — including the final phone's
    one-past-end ``OUT_PH2`` tail, which pins the ``phonemes`` →
    ``allophons[SAFETY]`` alias replay (#290) on top of the
    ``np_drawt0`` per-frame overwrite (#297/#299).
    """
    c_packets = _oracle_packets(capi, text)
    py_packets = _python_packets(text, monkeypatch)

    _assert_f0_ramps(c_packets, "oracle", text)
    _assert_f0_ramps(py_packets, "python", text)

    assert len(c_packets) == len(py_packets), (
        f"packet-count drift for {text!r}: C {len(c_packets)} vs "
        f"Python {len(py_packets)} -- metadata comparison would misalign"
    )

    for cell, name in _METADATA_CELLS:
        mismatches = [
            (j, c_packets[j][cell], py_packets[j][cell])
            for j in range(len(c_packets))
            if c_packets[j][cell] != py_packets[j][cell]
        ]
        if mismatches:
            j0, c_val, py_val = mismatches[0]
            pytest.fail(
                f"{name} diverges on {len(mismatches)}/{len(c_packets)} packets "
                f"for {text!r}; first at packet {j0}: C {c_val} vs Python {py_val} "
                f"(next: {mismatches[1:4]})"
            )
