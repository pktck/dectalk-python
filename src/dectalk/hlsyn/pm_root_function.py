"""``PmRootFunction`` Brent target from hlsyn/circuit.c.

Translated from ``src/dapi/src/hlsyn/circuit.c`` lines 329-346.
:c:func:`PmRootFunction` is the file-private callback that
:c:func:`Brent` (and :c:func:`BrentBracket`) drives to locate the
steady-state mean intraoral pressure ``Pm`` at which the
implicit-Euler wall-charge flow ``Uw = A * Pm - B`` balances the
nonlinear aerodynamic flow

``Uw = -ue + sqrt(2/rho) * (agf * FLOW_SQRT(ps - Pm)
       - (acx + an) * FLOW_SQRT(Pm))``

where ``agf = max(ag + Pm*Cg*Lg, 0) + ap`` is the
pressure-adjusted glottal area (the ``agx = max(agx0, 0)`` clamp
keeps it non-negative; ``ap`` is added on top because the
post-velar area is itself already clamped to ``>= 0`` at the
caller).

The return value is ``Uw - NEXT_Uw(Pm, args)``: a sign change
brackets the solution.

``FLOW_SQRT`` is the lookup-table square root (``DT_f_sqrt``,
ported in :mod:`dectalk.hlsyn.sqrt_table`). The C source defines
``FLOW_SQRT(p) == sqrt(p)`` for ``p >= 0`` and ``-sqrt(-p)`` for
``p < 0`` -- the ``DT_f_sqrt`` LUT honours this sign convention,
so we delegate to it directly rather than re-implementing it
here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dectalk.hlsyn.sqrt_table import dt_f_sqrt

if TYPE_CHECKING:
    from dectalk.hlsyn.pm_root_args import PmRootFunctionArgs


def pm_root_function(pm: float, args: PmRootFunctionArgs) -> float:
    """Brent target: aerodynamic Uw minus the implicit-Euler Uw at trial ``Pm``.

    Faithful translation of:

    .. code-block:: c

        static float
        PmRootFunction(float Pm, void* pVoidOtherArgs)
        {
          PmRootFunctionArgs* pOtherArgs = (PmRootFunctionArgs *)
              pVoidOtherArgs;
          float agx0, agf, Uw;

          agx0 = pOtherArgs->ag + Pm * pOtherArgs->Cg * pOtherArgs->Lg;
          agf = (agx0 < 0.0f ?  0.0f : agx0) + pOtherArgs->ap;
          Uw = (float)(
            -(pOtherArgs->ue) +
            pOtherArgs->rootTwoOverRho *
              (agf * FLOW_SQRT(pOtherArgs->ps - Pm)
                - (pOtherArgs->acx + pOtherArgs->an) * FLOW_SQRT(Pm))
            );
          return Uw - NEXT_Uw(Pm, pOtherArgs);
        }

    with ``FLOW_SQRT`` expanding to ``DT_f_sqrt`` (see
    :mod:`dectalk.hlsyn.sqrt_table`) and ``NEXT_Uw(Pm, p)``
    expanding to ``(p)->A * (Pm) - (p)->B`` (from
    ``#define NEXT_Uw(Pm, p)`` in ``circuit.c``).

    The C ``void *`` argument becomes a typed
    :class:`PmRootFunctionArgs` here -- Python has no need for
    the void-pointer indirection.

    Args:
        pm: Trial mean intraoral pressure (CGS).
        args: Aerodynamic state and implicit-Euler linearisation
            coefficients captured by :c:func:`SpeechCircuit`.

    Returns:
        ``Uw(aerodynamic) - Uw(implicit-Euler)`` at this trial
        ``Pm``. A sign change between two trial values brackets
        the steady-state solution.
    """
    agx0 = args.ag + pm * args.Cg * args.Lg
    agf = (0.0 if agx0 < 0.0 else agx0) + args.ap
    uw = -args.ue + args.rootTwoOverRho * (
        agf * dt_f_sqrt(args.ps - pm) - (args.acx + args.an) * dt_f_sqrt(pm)
    )
    # NEXT_Uw(Pm, p) == p->A * Pm - p->B
    return uw - (args.A * pm - args.B)


__all__ = ["pm_root_function"]
