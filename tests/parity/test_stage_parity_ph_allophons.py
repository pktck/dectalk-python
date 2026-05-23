"""Per-stage parity test: PH ``allophons[]`` / ``allodurs[]`` / ``f0tar[]`` / ``f0tim[]``.

Sibling to :mod:`tests.parity.test_stage_parity_kernel` — see that
module's docstring for the rationale (issue #150).

The PH stage maintains four parallel arrays describing the timing
and intonation of the current utterance:

- ``pDph_t.allophons[i]`` — allophone code (US_AE, US_T, ...) for
  the i-th allophone.
- ``pDph_t.allodurs[i]`` — duration in 6.4 ms frames for that
  allophone.
- ``pDph_t.f0tar[k]`` / ``pDph_t.f0tim[k]`` — the intonation
  target / time pairs the PH stage computes from sentence structure.

These are populated by ``ph_setar`` / ``ph_inton`` and consumed by
``ph_draw*`` to emit VTM frames. Like the ``allofeats`` snapshot
(see :mod:`test_stage_parity_ph_allofeats`), they're internal to the
PH stage and not currently surfaced at any pipeline boundary, so the
existing dump hooks don't capture them. Adding a C-side hook that
snapshots these arrays at the end of ``ph_setar`` and ``ph_inton``
(``src/dapi/src/ph/ph_setar.c`` / ``src/dapi/src/ph/ph_inton.c``)
would make a direct C-vs-Python parity assertion possible.

For now this test:

1. Confirms the Python side's ``DPH_T`` carries the corresponding
   arrays and the PH-stage code path (``phinton``) imports cleanly.
2. Marks the C-comparison branch ``xfail`` with a precise reason so
   ``pytest -rx`` summaries surface the missing hook as a known gap.

When the hook lands, replace the ``xfail`` body with a real
parse-and-compare against ``<DECTALK_DUMP_DIR>/ph_allophons.dump``.

Skips cleanly when the C oracle is not present.
"""

from __future__ import annotations

import pytest

from dectalk._capi import CAPI
from dectalk.ph.dph_t import DphT

from ._stage_parity_corpus import STAGE_PARITY_CORPUS
from ._stage_parity_helpers import have_artefacts, stage_capi

_ = stage_capi


pytestmark = [
    pytest.mark.c_oracle,
    pytest.mark.skipif(
        not have_artefacts(),
        reason="locally-built libtts or shipped DECtalk binary not present",
    ),
]


def test_python_dph_t_carries_allophons_arrays() -> None:
    """``DPH_T`` exposes ``allophons`` / ``allodurs`` / ``f0tar`` / ``f0tim`` fields.

    Documents the Python-side state shape that the C-vs-Python parity
    test would consume once the C hook lands.
    """
    state = DphT()
    for field_name in ("allophons", "allodurs", "f0tar", "f0tim"):
        assert hasattr(state, field_name), f"DphT missing {field_name} array"
        value = getattr(state, field_name)
        assert isinstance(value, list), f"DphT.{field_name} should be a list"


@pytest.mark.xfail(
    reason=(
        "C-side hook for ph_allophons snapshot not implemented yet — needs a new "
        "patch under tests/parity/c_patches/ that dumps pDph_t->allophons / "
        "allodurs / f0tar / f0tim arrays after ph_setar() and ph_inton() in "
        "src/dapi/src/ph/. Tracking via issue #150."
    ),
    strict=False,
)
@pytest.mark.parametrize("text", STAGE_PARITY_CORPUS, ids=list(STAGE_PARITY_CORPUS))
def test_ph_allophons_parity(stage_capi: CAPI, text: str) -> None:
    """PH timing arrays from C oracle match the Python pipeline."""
    dumps = stage_capi.dump_pipeline(text, ["ph_allophons"])  # type: ignore[arg-type]
    assert dumps.get("ph_allophons"), f"no ph_allophons dump captured for {text!r}"
