"""``Tongue_acx_f1c`` top-level tongue-body acoustic mapping from acxf1c.c.

Translated from ``src/dapi/src/hlsyn/acxf1c.c`` lines 48-129.

This is the top-level orchestrator that maps the tongue-body
parameters (``al``, ``ab``, ``f1``, ``f2``, ``f3``) to the constriction
area (:attr:`HLState.acx`) and the constriction-adjusted first formant
(:attr:`HLState.f1c`). It is called first inside ``HLSynthesizeLLFrame``
and dispatches through four helpers:

- :func:`~dectalk.hlsyn.helmholtz.helmholtz_frequency` -- forward
  Helmholtz frequency for the lateral / labial constrictions.
- :func:`~dectalk.hlsyn.compute_ac.compute_acl` -- lateral
  constriction area.
- :func:`~dectalk.hlsyn.compute_ac.compute_acd` -- dorsal
  constriction area.
- :func:`~dectalk.hlsyn.set_acx_loc.set_acx_loc` -- pick the smallest
  of (acl, acd, al, ab) and write ``state.acx`` / ``state.loc``.

The ``MMSQ_TO_CMSQ`` macro in ``hlsyn.h`` is ``(x) * 0.01f`` (mm^2 to
cm^2); inlined here as a literal.

The ``TONGUE_BODY_AREA`` symbol is *not* defined in the Linux build,
so only the ``#ifndef TONGUE_BODY_AREA`` branches are active here.
The early-exit guard uses just ``ab < 30 || al < 30`` (no ``atb``
check), the ``R1ab`` call always passes ``frame.ab`` (never
``frame.atb``), and ``state.acd`` is set directly from
``compute_acd`` without an ``atb`` cap.
"""

from __future__ import annotations

from dectalk.hlsyn.compute_ac import compute_acd, compute_acl
from dectalk.hlsyn.helmholtz import helmholtz_frequency
from dectalk.hlsyn.set_acx_loc import set_acx_loc
from dectalk.ph.hl_speaker import HLSpeaker
from dectalk.ph.hlsyn_structs import HLFrame, HLState


def tongue_acx_f1c(frame: HLFrame, speaker: HLSpeaker, state: HLState) -> None:
    """Compute ``acx`` / ``loc`` / ``f1c`` / ``acl`` / ``acd`` for one frame.

    Faithful translation of (with ``TONGUE_BODY_AREA`` *undefined*, which
    matches the Linux build):

    .. code-block:: c

        void Tongue_acx_f1c(HLFrame *frame, HLSpeaker *speaker,
                            HLState *state) {
            float R1al, R1ab;

            if (frame->ab < 30.0f || frame->al < 30.0f) {
                R1al = HelmholtzFrequency(MMSQ_TO_CMSQ(frame->al),
                    speaker->Val, speaker->Lc_al,
                    speaker->HelmholtzZeroAreaFrequency);
                R1ab = HelmholtzFrequency(MMSQ_TO_CMSQ(frame->ab),
                    speaker->Vab, speaker->Lc_ab,
                    speaker->HelmholtzZeroAreaFrequency);

                if (R1al < R1ab && R1al < frame->f1)
                    state->f1c = R1al;
                else if (R1ab <= R1al && R1ab < frame->f1)
                    state->f1c = R1ab;
                else
                    state->f1c = frame->f1;
            } else {
                state->f1c = frame->f1;
            }

            state->acl = Compute_acl(frame, speaker);
            state->acd = Compute_acd(frame, speaker);

            Set_acx_loc(frame, state);
        }

    The 30 mm^2 threshold is the constriction-presence test: when both
    ``ab`` and ``al`` exceed it there is no real constriction, so
    ``f1c`` collapses to ``frame.f1`` and the (expensive) Helmholtz
    branch is skipped. Inside the constriction branch, ``f1c`` is the
    minimum of ``f1``, the labial Helmholtz frequency ``R1ab``, and the
    lateral Helmholtz frequency ``R1al``; the tie-break (``<`` vs
    ``<=``) prefers ``R1al`` when ``R1al == R1ab``.

    After the ``f1c`` decision the routine populates the two back
    constriction areas (``acl`` / ``acd``) via the dedicated helpers,
    then defers to :func:`set_acx_loc` to choose the dominant
    constriction.

    Args:
        frame: HL frame (read ``al`` / ``ab`` / ``f1`` / ``f2`` / ``f3``).
        speaker: HL speaker (read ``Val`` / ``Lc_al`` / ``Vab`` /
            ``Lc_ab`` / ``HelmholtzZeroAreaFrequency`` plus everything
            the helpers consume).
        state: HL state, mutated: ``f1c`` / ``acl`` / ``acd`` / ``acx`` /
            ``loc`` are all written.
    """
    if frame.ab < 30.0 or frame.al < 30.0:  # noqa: PLR2004 - threshold from C source
        # EAB Ken agreed: only apply when there is a constriction
        # (also saves computes). MMSQ_TO_CMSQ multiplies by 0.01.
        r1al = helmholtz_frequency(
            frame.al * 0.01,
            speaker.Val,
            speaker.Lc_al,
            speaker.HelmholtzZeroAreaFrequency,
        )
        r1ab = helmholtz_frequency(
            frame.ab * 0.01,
            speaker.Vab,
            speaker.Lc_ab,
            speaker.HelmholtzZeroAreaFrequency,
        )

        # Bug-comment from the C source: if ab and al are both closed
        # then r1ab == r1al; we'd ideally revert to further back, but
        # the simple minimum below is what the C does.
        if r1al < r1ab and r1al < frame.f1:
            state.f1c = r1al
        elif r1ab <= r1al and r1ab < frame.f1:
            state.f1c = r1ab
        else:
            state.f1c = frame.f1
    else:
        state.f1c = frame.f1

    # Compute the minimum constriction area (acx) and its location (loc)
    # which is the minimum of acl, acd, al and ab.
    state.acl = compute_acl(frame, speaker)
    state.acd = compute_acd(frame, speaker)

    set_acx_loc(frame, state)


# Aliases under the original C-source names for inventory tests.
Tongue_acx_f1c = tongue_acx_f1c

__all__ = [
    "Tongue_acx_f1c",
    "tongue_acx_f1c",
]
