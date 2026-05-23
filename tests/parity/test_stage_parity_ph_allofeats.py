"""Per-stage parity test: PH internal ``allofeats[]`` / ``sentstruc[]``.

Sibling to :mod:`tests.parity.test_stage_parity_kernel` — see that
module's docstring for the rationale (issue #150).

The PH stage maintains two parallel arrays of per-allophone metadata:

- ``pDph_t.allofeats[i]`` — feature bitmask (FVOICD, FWINITC, ...)
  for the i-th allophone in the current utterance.
- ``pDph_t.sentstruc[...]`` — sentence-structure metadata used by the
  intonation model.

These are internal to the PH stage and are not currently surfaced at
any pipeline boundary, so the existing ``DECTALK_DUMP_DIR`` hooks
(kernel / cmd / ph / vtm) don't capture them. Adding a C-side hook
that snapshots these arrays at the end of ``ph_setallofeats``
(``src/dapi/src/ph/ph_setar.c``) would make a direct C-vs-Python
parity assertion possible.

For now the test serves as a placeholder that:

1. Confirms the Python side's ``DPH_T`` carries the corresponding
   ``allofeats`` / ``allophons`` / ``nallotot`` fields with sensible
   defaults (catches the refactor that accidentally renames them).
2. Marks the C-comparison branch ``xfail`` with a precise reason so
   ``pytest -rx`` summaries surface the missing hook as a known gap.

When the hook lands, replace the ``xfail`` body with a real
parse-and-compare against ``<DECTALK_DUMP_DIR>/ph_allofeats.dump``.

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


def test_python_dph_t_carries_allofeats_field() -> None:
    """``DPH_T`` exposes the ``allofeats`` / ``nallotot`` fields used by PH.

    Cheap structural check that documents the Python-side state shape
    the C-vs-Python parity test would consume once the C hook lands.
    """
    state = DphT()
    assert hasattr(state, "allofeats"), "DphT missing allofeats array"
    assert hasattr(state, "allophons"), "DphT missing allophons array"
    assert hasattr(state, "nallotot"), "DphT missing nallotot counter"
    assert isinstance(state.allofeats, list), "DphT.allofeats should be a list"
    assert isinstance(state.allophons, list), "DphT.allophons should be a list"
    assert isinstance(state.nallotot, int), "DphT.nallotot should be an int"


@pytest.mark.xfail(
    reason=(
        "C-side hook for ph_allofeats snapshot not implemented yet — needs a new "
        "patch under tests/parity/c_patches/ that dumps pDph_t->allofeats[0:nallotot] "
        "and sentstruc metadata after ph_setallofeats() in src/dapi/src/ph/ph_setar.c. "
        "Tracking via issue #150."
    ),
    strict=False,
)
@pytest.mark.parametrize("text", STAGE_PARITY_CORPUS, ids=list(STAGE_PARITY_CORPUS))
def test_ph_allofeats_parity(stage_capi: CAPI, text: str) -> None:
    """PH ``allofeats[]`` snapshot from C oracle matches the Python pipeline."""
    # The C oracle's dump_pipeline does not currently emit a
    # ph_allofeats stage; this call exercises the validation path and
    # surfaces the missing hook as the xfail reason above.
    dumps = stage_capi.dump_pipeline(text, ["ph_allofeats"])  # type: ignore[arg-type]
    assert dumps.get("ph_allofeats"), f"no ph_allofeats dump captured for {text!r}"
