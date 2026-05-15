"""Square-root lookup wrapper from sqrttable.c.

Translated from ``src/dapi/src/hlsyn/sqrttable.c``. The HLsyn module
calls into :func:`dt_f_sqrt` (and its alias macro ``DTsqrt`` /
``FLOW_SQRT`` in ``hlsyn.h``) wherever it needs a square root --
acxf1c.c, hlframe.c, nasalf1x.c and circuit.c all use it.

In the C source ``DTsqrt(x)`` is a preprocessor alias for
``DT_f_sqrt(x)`` (defined in ``hlsyn.h``):
``#define FLOW_SQRT(X) DTsqrt(X)`` and
``#define DTsqrt(x) DT_f_sqrt(x)``. A single Python entry point
covers both names. The Python ports
under :mod:`dectalk.hlsyn` use :func:`math.sqrt` directly when they
don't need bit-for-bit parity with the lookup-table approximation;
this module exists for callers that DO want the same coarse
quantisation the C binary applies.

Table layout (verbatim from sqrttable.c):

- ``sqrttable[i]`` holds ``sqrt(i)`` for ``i`` in ``[0, 403]``.
- Entries past index 403 sit in a ``#if 0`` block and are not
  compiled. The lookup logic never indexes past 400 anyway:

    * ``input > 40000`` -> fall back to :func:`math.sqrt`.
    * ``input < -40000`` -> fall back to ``-math.sqrt(-input)``.
    * ``pos = int(input)``, ``pos > 400`` -> ``sqrttable[pos // 100] * 10``.
    * ``pos < -400`` -> ``-sqrttable[-pos // 100] * 10``.
    * ``0 <= pos <= 400`` -> ``sqrttable[pos]``.
    * ``pos < 0`` (and ``pos >= -400``) -> ``-sqrttable[-pos]``.

The ``int(input)`` truncation matches C's cast-to-int (truncate
toward zero) for the range of inputs the helper accepts.
"""

from __future__ import annotations

import math
from typing import Final

# Outer math.sqrt fallback bounds: outside this range the LUT can't
# represent the result and the C source defers to ``sqrt`` / ``-sqrt``.
_MATH_SQRT_BOUND: Final[float] = 40000.0
# Inner divide-by-100 bound: for ``|pos|`` in ``(400, 40000]`` the
# lookup hops by 100 (``sqrttable[pos // 100] * 10``).
_LUT_DIRECT_BOUND: Final[int] = 400

# The 404-entry Linux-active slice of ``sqrttable[]`` from
# ``src/dapi/src/hlsyn/sqrttable.c``. Entry ``i`` is ``sqrt(i)``.
# Indices 404..4000 live inside a ``#if 0`` block in the C source
# and are not compiled; the lookup logic in :func:`dt_f_sqrt` only
# touches indices 0..400.
SQRTTABLE: Final[tuple[float, ...]] = (
    0.00000000,
    1.00000000,
    1.41421356,
    1.73205081,
    2.00000000,
    2.23606798,
    2.44948974,
    2.64575131,
    2.82842712,
    3.00000000,
    3.16227766,
    3.31662479,
    3.46410162,
    3.60555128,
    3.74165739,
    3.87298335,
    4.00000000,
    4.12310563,
    4.24264069,
    4.35889894,
    4.47213595,
    4.58257569,
    4.69041576,
    4.79583152,
    4.89897949,
    5.00000000,
    5.09901951,
    5.19615242,
    5.29150262,
    5.38516481,
    5.47722558,
    5.56776436,
    5.65685425,
    5.74456265,
    5.83095189,
    5.91607978,
    6.00000000,
    6.08276253,
    6.16441400,
    6.24499800,
    6.32455532,
    6.40312424,
    6.48074070,
    6.55743852,
    6.63324958,
    6.70820393,
    6.78232998,
    6.85565460,
    6.92820323,
    7.00000000,
    7.07106781,
    7.14142843,
    7.21110255,
    7.28010989,
    7.34846923,
    7.41619849,
    7.48331477,
    7.54983444,
    7.61577311,
    7.68114575,
    7.74596669,
    7.81024968,
    7.87400787,
    7.93725393,
    8.00000000,
    8.06225775,
    8.12403840,
    8.18535277,
    8.24621125,
    8.30662386,
    8.36660027,
    8.42614977,
    8.48528137,
    8.54400375,
    8.60232527,
    8.66025404,
    8.71779789,
    8.77496439,
    8.83176087,
    8.88819442,
    8.94427191,
    9.00000000,
    9.05538514,
    9.11043358,
    9.16515139,
    9.21954446,
    9.27361850,
    9.32737905,
    9.38083152,
    9.43398113,
    9.48683298,
    9.53939201,
    9.59166305,
    9.64365076,
    9.69535971,
    9.74679434,
    9.79795897,
    9.84885780,
    9.89949494,
    9.94987437,
    10.00000000,
    10.04987562,
    10.09950494,
    10.14889157,
    10.19803903,
    10.24695077,
    10.29563014,
    10.34408043,
    10.39230485,
    10.44030651,
    10.48808848,
    10.53565375,
    10.58300524,
    10.63014581,
    10.67707825,
    10.72380529,
    10.77032961,
    10.81665383,
    10.86278049,
    10.90871211,
    10.95445115,
    11.00000000,
    11.04536102,
    11.09053651,
    11.13552873,
    11.18033989,
    11.22497216,
    11.26942767,
    11.31370850,
    11.35781669,
    11.40175425,
    11.44552314,
    11.48912529,
    11.53256259,
    11.57583690,
    11.61895004,
    11.66190379,
    11.70469991,
    11.74734012,
    11.78982612,
    11.83215957,
    11.87434209,
    11.91637529,
    11.95826074,
    12.00000000,
    12.04159458,
    12.08304597,
    12.12435565,
    12.16552506,
    12.20655562,
    12.24744871,
    12.28820573,
    12.32882801,
    12.36931688,
    12.40967365,
    12.44989960,
    12.48999600,
    12.52996409,
    12.56980509,
    12.60952021,
    12.64911064,
    12.68857754,
    12.72792206,
    12.76714533,
    12.80624847,
    12.84523258,
    12.88409873,
    12.92284798,
    12.96148140,
    13.00000000,
    13.03840481,
    13.07669683,
    13.11487705,
    13.15294644,
    13.19090596,
    13.22875656,
    13.26649916,
    13.30413470,
    13.34166406,
    13.37908816,
    13.41640786,
    13.45362405,
    13.49073756,
    13.52774926,
    13.56465997,
    13.60147051,
    13.63818170,
    13.67479433,
    13.71130920,
    13.74772708,
    13.78404875,
    13.82027496,
    13.85640646,
    13.89244399,
    13.92838828,
    13.96424004,
    14.00000000,
    14.03566885,
    14.07124728,
    14.10673598,
    14.14213562,
    14.17744688,
    14.21267040,
    14.24780685,
    14.28285686,
    14.31782106,
    14.35270009,
    14.38749457,
    14.42220510,
    14.45683229,
    14.49137675,
    14.52583905,
    14.56021978,
    14.59451952,
    14.62873884,
    14.66287830,
    14.69693846,
    14.73091986,
    14.76482306,
    14.79864859,
    14.83239697,
    14.86606875,
    14.89966443,
    14.93318452,
    14.96662955,
    15.00000000,
    15.03329638,
    15.06651917,
    15.09966887,
    15.13274595,
    15.16575089,
    15.19868415,
    15.23154621,
    15.26433752,
    15.29705854,
    15.32970972,
    15.36229150,
    15.39480432,
    15.42724862,
    15.45962483,
    15.49193338,
    15.52417470,
    15.55634919,
    15.58845727,
    15.62049935,
    15.65247584,
    15.68438714,
    15.71623365,
    15.74801575,
    15.77973384,
    15.81138830,
    15.84297952,
    15.87450787,
    15.90597372,
    15.93737745,
    15.96871942,
    16.00000000,
    16.03121954,
    16.06237840,
    16.09347694,
    16.12451550,
    16.15549442,
    16.18641406,
    16.21727474,
    16.24807681,
    16.27882060,
    16.30950643,
    16.34013464,
    16.37070554,
    16.40121947,
    16.43167673,
    16.46207763,
    16.49242250,
    16.52271164,
    16.55294536,
    16.58312395,
    16.61324773,
    16.64331698,
    16.67333200,
    16.70329309,
    16.73320053,
    16.76305461,
    16.79285562,
    16.82260384,
    16.85229955,
    16.88194302,
    16.91153453,
    16.94107435,
    16.97056275,
    17.00000000,
    17.02938637,
    17.05872211,
    17.08800749,
    17.11724277,
    17.14642820,
    17.17556404,
    17.20465053,
    17.23368794,
    17.26267650,
    17.29161647,
    17.32050808,
    17.34935157,
    17.37814720,
    17.40689519,
    17.43559577,
    17.46424920,
    17.49285568,
    17.52141547,
    17.54992877,
    17.57839583,
    17.60681686,
    17.63519209,
    17.66352173,
    17.69180601,
    17.72004515,
    17.74823935,
    17.77638883,
    17.80449381,
    17.83255450,
    17.86057110,
    17.88854382,
    17.91647287,
    17.94435844,
    17.97220076,
    18.00000000,
    18.02775638,
    18.05547009,
    18.08314132,
    18.11077028,
    18.13835715,
    18.16590212,
    18.19340540,
    18.22086716,
    18.24828759,
    18.27566688,
    18.30300522,
    18.33030278,
    18.35755975,
    18.38477631,
    18.41195264,
    18.43908891,
    18.46618531,
    18.49324201,
    18.52025918,
    18.54723699,
    18.57417562,
    18.60107524,
    18.62793601,
    18.65475811,
    18.68154169,
    18.70828693,
    18.73499400,
    18.76166304,
    18.78829423,
    18.81488772,
    18.84144368,
    18.86796226,
    18.89444363,
    18.92088793,
    18.94729532,
    18.97366596,
    19.00000000,
    19.02629759,
    19.05255888,
    19.07878403,
    19.10497317,
    19.13112647,
    19.15724406,
    19.18332609,
    19.20937271,
    19.23538406,
    19.26136028,
    19.28730152,
    19.31320792,
    19.33907961,
    19.36491673,
    19.39071943,
    19.41648784,
    19.44222210,
    19.46792233,
    19.49358869,
    19.51922130,
    19.54482029,
    19.57038579,
    19.59591794,
    19.62141687,
    19.64688270,
    19.67231557,
    19.69771560,
    19.72308292,
    19.74841766,
    19.77371993,
    19.79898987,
    19.82422760,
    19.84943324,
    19.87460691,
    19.89974874,
    19.92485885,
    19.94993734,
    19.97498436,
    20.00000000,
    20.02498439,
    20.04993766,
    20.07485990,
)


def dt_f_sqrt(input_value: float) -> float:
    """Square root via lookup table, falling back to :func:`math.sqrt`.

    Faithful translation of ``DT_f_sqrt(float input)`` from
    ``src/dapi/src/hlsyn/sqrttable.c``:

    .. code-block:: c

        float DT_f_sqrt(float input) {
            int pos;
            if (input >  40000.0f) return (float)sqrt(input);
            if (input < -40000.0f) return (float)(-sqrt(-input));
            pos = (int)input;
            if (pos >  400) return (float)(sqrttable[pos / 100] * 10.0f);
            if (pos < -400) return (float)(-sqrttable[-pos / 100] * 10.0f);
            pos = (int)input;
            if (pos < 0) return -sqrttable[-pos];
            return sqrttable[pos];
        }

    The ``DTsqrt`` / ``FLOW_SQRT`` macros in ``hlsyn.h`` are just
    spellings of this function; callers can use this Python helper
    in their place.

    :param input_value: Value to find the square root of.
    :returns: Approximation of ``sqrt(input_value)`` using the
        ``SQRTTABLE`` lookup, with :func:`math.sqrt` fallback for
        ``|input| > 40000``.
    """
    if input_value > _MATH_SQRT_BOUND:
        return math.sqrt(input_value)

    if input_value < -_MATH_SQRT_BOUND:
        return -math.sqrt(-input_value)

    pos = int(input_value)
    if pos > _LUT_DIRECT_BOUND:
        return SQRTTABLE[pos // 100] * 10.0

    if pos < -_LUT_DIRECT_BOUND:
        # In C: ``-sqrttable[-pos / 100] * 10.0f`` with ``-pos`` as int.
        # C integer division truncates toward zero, matching ``//`` only
        # for non-negative operands -- ``-pos`` is positive here so the
        # two agree.
        return -SQRTTABLE[(-pos) // 100] * 10.0

    if pos < 0:
        return -SQRTTABLE[-pos]
    return SQRTTABLE[pos]


# Aliases under the original C-source names for inventory tests.
DT_f_sqrt = dt_f_sqrt

__all__ = [
    "SQRTTABLE",
    "DT_f_sqrt",
    "dt_f_sqrt",
]
