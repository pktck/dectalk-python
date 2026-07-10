"""Issue #291: the Rule 2 clause-initial OOB read is unreachable + invariant.

``us_special_rules`` Rule 2 (the s-cluster kluge from ``p_us_st0.c``)
reads ``allophons[pDph_t->nphone - 2]`` with **no bounds guard**. At
``nphone < 2`` the shipped C binary reads out-of-bounds struct memory
(the ``short addjit`` / ``short sprate`` fields precede ``allophons``
in ``DPH_T``, ``ph_data.h`` line 526), while the Python port used to
wrap to the list tail. Issue #291 asked which behaviour the port must
model. Answer: **neither can ever execute**, because Rule 2's guard
requires the *previous* phone (``fealas``) to be a voiceless plosive
and the previous phone at ``nphone < 2`` is always the leading
``GEN_SIL``:

- at ``nphone == 0``, ``init_variables`` (``ph_setar.c``) hardwires
  ``pholas = GEN_SIL`` and ``struclm2 = 0``;
- at ``nphone == 1``, ``pholas = allophons[0]``, and every clause's
  ``allophons[0]`` is the leading silence: ``ph_task.c`` seeds
  ``symbols[0] = GEN_SIL``, ``phsort``'s output pass emits it per
  clause, and ``us_phalloph`` re-emits it as ``allophons[0]``
  (the empirically pinned 213-sample leading-silence prefix, #200);
- silence's feature word in the **active** ROM variant
  (``p_us_rom_dectalk_1996m_43f.c``, ``VOICE_ROM_DECTALK_1996M_43F``)
  is ``FSONOR`` alone — no ``FPLOSV`` bit — so the guard can't pass.

Empirical census (2026-07-10, issue #291): across the full 133K-prompt
corpus, the stratified 500-prompt FULL+VTM1 sample, and a ~90-prompt
adversarial set (clause-initial voiceless plosives, multi-clause
splits, phonemic/letter/number onsets), Rule 2 fired only at
``nphone >= 2``; every clause start had ``allophons[0] == GEN_SIL``;
and forcing the kluge's ``nphone < 2`` outcome BOTH ways produced
byte-identical per-frame packet streams.

The tests below pin all three legs:

1. C-source re-parse — the unguarded read, the ``init_variables``
   clause-start hardwiring, and the active ROM's silence feature word
   (skip when ``DECTALK_SRC`` is absent);
2. Python LUT facts — silence lacks ``FPLOSV`` and fails the
   ``FOBST+FCONSON`` equality for both the GEN_SIL sentinel and the
   old wrap value;
3. live pipeline — a subprocess census over adversarial prompts
   asserting no ``nphone < 2`` firing, GEN_SIL at every clause start,
   and forced-branch packet-stream invariance.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from dectalk.ph.phoneme_features import FCONSON, FOBST, FPLOSV
from dectalk.ph.rom_tables import us_featb
from dectalk.ph.timing import phone_feature
from dectalk.ph.utterance_constants import GEN_SIL

_SRC_ROOT = Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
_ST0 = _SRC_ROOT / "src/dapi/src/ph/p_us_st0.c"
_SETAR = _SRC_ROOT / "src/dapi/src/ph/ph_setar.c"
_ROM = _SRC_ROOT / "src/dapi/src/ph/p_us_rom_dectalk_1996m_43f.c"

# The three C-re-parse tests double-mark ``parity`` + ``c_oracle``:
# ``parity`` documents the source-re-parse contract (and skips locally
# without the tree), while ``c_oracle`` gets them SELECTED in the CI
# oracle lane (``pytest -m c_oracle`` with DECTALK_SRC set) — the 9-way
# matrix has no C source, so without the second marker they would skip
# everywhere in CI and never assert.
_c_source = pytest.mark.skipif(
    not (_ST0.is_file() and _SETAR.is_file() and _ROM.is_file()),
    reason="DECtalk C source not available at DECTALK_SRC",
)


def _extract_body(path: Path, pattern: str) -> str:
    """Return the brace-balanced body of the function matched by ``pattern``."""
    text = path.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(pattern, text)
    assert match is not None, f"{pattern!r} not found in {path.name}"
    start = text.index("{", match.end() - 1) + 1
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    assert depth == 0, f"unbalanced braces after {pattern!r} in {path.name}"
    return text[start : i - 1]


# -- 1. C-source re-parse ----------------------------------------------------


@pytest.mark.parity
@pytest.mark.c_oracle
@_c_source
def test_c_kluge_read_is_unguarded() -> None:
    """The st0 Rule 2 kluge still reads ``allophons[nphone - 2]`` raw.

    This is the reason the Python port carries an explicit
    ``nphone >= 2`` guard: the C read is unguarded (neither a
    ``get_phone`` clamp nor an index check), so at ``nphone < 2`` the
    binary reads out-of-bounds ``DPH_T`` memory. If upstream ever
    guards it, revisit the Python model (issue #291).
    """
    body = _extract_body(
        _ST0, r"static\s+void\s+us_special_rules\s*\(\s*LPTTS_HANDLE_T[^)]*\)[^{;]*\{"
    )
    kluge = re.search(
        r"phone_feature\s*\(\s*pDph_t\s*,\s*pDph_t->allophons\s*\[\s*pDph_t->nphone\s*-\s*2\s*\]"
        r"\s*\)\s*==\s*\(\s*FOBST\s*\+\s*FCONSON\s*\)",
        body,
    )
    assert kluge is not None, "st0 s-cluster kluge (allophons[nphone-2] read) not found"
    # No bounds guard anywhere in the function body.
    assert "get_phone" not in body
    assert re.search(r"nphone\s*>=?\s*2", body) is None


@pytest.mark.parity
@pytest.mark.c_oracle
@_c_source
def test_c_init_variables_hardwires_clause_start() -> None:
    """``init_variables`` forces ``pholas = GEN_SIL`` / ``struclm2 = 0`` at nphone 0.

    This is the C-side half of the unreachability proof: at
    ``nphone == 0`` the "previous phone" is hardwired to silence, so
    Rule 2's voiceless-plosive precondition on ``fealas`` cannot hold.
    """
    body = _extract_body(
        _SETAR, r"static\s+void\s+init_variables\s*\(\s*LPTTS_HANDLE_T[^)]*\)[^{;]*\{"
    )
    first_pos = re.search(
        r"if\s*\(\s*pDph_t->nphone\s*==\s*0\s*\)[^{]*\{(.*?)\}\s*else\s*\{",
        body,
        re.DOTALL,
    )
    assert first_pos is not None, "nphone == 0 branch not found in init_variables"
    branch = first_pos.group(1)
    assert re.search(r"\*psStruclm2\s*=\s*0", branch)
    assert re.search(r"\*psPholas\s*=\s*GEN_SIL", branch)


@pytest.mark.parity
@pytest.mark.c_oracle
@_c_source
def test_c_active_rom_silence_lacks_fplosv() -> None:
    """The active ROM's ``us_featb`` silence entry is ``FSONOR`` — no FPLOSV.

    ``fealas = phone_feature(GEN_SIL) = us_featb[0]``; without the
    FPLOSV bit the Rule 2 guard can never fire against a silence
    predecessor. Re-parses the **active** voice-ROM variant
    (``VOICE_ROM_DECTALK_1996M_43F``), not the BETA5 ``p_us_rom.c``
    (whose silence entry differs — the #229 wrong-variant lesson).
    """
    text = _ROM.read_bytes().replace(b"\r", b"").decode("latin-1")
    match = re.search(
        r"us_featb\s*\[\s*PHO_SYM_TOT\s*\]\s*=\s*\{\s*/\*\s*\[SI\]\s*\*/\s*([A-Z0-9_+ \t]+),",
        text,
    )
    assert match is not None, "us_featb [SI] entry not found in active ROM"
    si_expr = match.group(1).strip()
    assert si_expr == "FSONOR", f"silence feature word changed: {si_expr!r}"


# -- 2. Python LUT facts ------------------------------------------------------


def test_python_silence_feature_word_lacks_fplosv() -> None:
    """Silence can never satisfy Rule 2's voiceless-plosive precondition."""
    assert us_featb[0] == 16  # FSONOR in the active ROM variant
    assert phone_feature(GEN_SIL) == us_featb[0]
    assert phone_feature(GEN_SIL) & FPLOSV == 0


def test_sentinel_and_wrap_agree_on_kluge_outcome() -> None:
    """GEN_SIL sentinel and the old list-tail wrap both fail the equality.

    The Python port models the unreachable ``nphone < 2`` read with a
    documented ``GEN_SIL`` sentinel (the C codebase's own ``get_phone``
    out-of-range convention). The previous silent wrap read the zeroed
    list tail (phone code 0). Both fail ``== FOBST + FCONSON``, so the
    explicit guard changes nothing even in the unreachable branch.
    """
    assert phone_feature(GEN_SIL) != FOBST + FCONSON
    assert phone_feature(0) != FOBST + FCONSON


# -- 3. Live-pipeline census + forced-branch invariance -----------------------

# Adversarial prompts: voiceless plosive at the start of a clause (first
# clause, post-comma/semicolon/period clauses, letters, numbers, inline
# commands), each followed by a sonorant so Rule 2 fires as early as the
# phone stream allows.
_ADVERSARIAL: tuple[str, ...] = (
    "pat",
    "tea",
    "key",
    "two",
    "ten",
    "car",
    "cow",
    "cute",
    "pray",
    "play",
    "tray",
    "true",
    "twin",
    "clay",
    "crew",
    "quick",
    "Pat ran.",
    "Tom is here.",
    "Kay left early.",
    "go, pat",
    "yes, tom",
    "one; two",
    "stop. ten men.",
    "first: two",
    "pat, pat, pat",
    "Tom!",
    "Kay?",
    "2 men",
    "10 tons",
    "TV",
    "PC",
    "KP",
    "p",
    "t",
    "k",
    ",pat",
    "'pat'",
    "[:rate 300] pat",
    "pat,,tom",
)

_DRIVER = r"""
import hashlib, json, os, sys

import numpy as np

import dectalk.vtm.pump_frames as pump_mod
from dectalk.ph import parstochip_to_frames as ptf
from dectalk.ph import phsettar as ps
from dectalk.ph import us_special_rules as usr
from dectalk.ph.param_indices import OUT_T0
from dectalk.ph.phoneme_features import FCONSON, FOBST, FPLOSV, FSONOR, FVOICD
from dectalk.ph.utterance_constants import GEN_SIL

# Stub the VTM pump: the phsettar driver loop runs in full before the
# pump, so this keeps every us_special_rules call while skipping the
# (dominant) synthesis cost.
pump_mod.pump_frames_via_vtm1 = lambda frames, preset, **kw: np.zeros(0, dtype=np.int16)

stats = {"fires": 0, "fires_lt2": 0, "min_nphone": None, "clauses": 0}
allophons0 = set()
mode = ["off"]
packets = []
orig_usr = ps.us_special_rules
orig_pf = usr.phone_feature
orig_sp = ptf.send_pars_delaypars


def wrapped(**kw):
    p = kw["phTTS"].p_ph_thread_data
    if p.nphone == 0:
        stats["clauses"] += 1
        allophons0.add(p.allophons[0])
    fires = (
        (kw["fealas"] & FPLOSV) != 0
        and (kw["fealas"] & FVOICD) == 0
        and (kw["feacur"] & FSONOR) != 0
    )
    if fires:
        stats["fires"] += 1
        m = stats["min_nphone"]
        stats["min_nphone"] = p.nphone if m is None else min(m, p.nphone)
        if p.nphone < 2:
            stats["fires_lt2"] += 1
    if mode[0] != "off" and p.nphone < 2:
        usr.phone_feature = (
            (lambda ph: FOBST + FCONSON) if mode[0] == "eq" else (lambda ph: 0)
        )
        try:
            return orig_usr(**kw)
        finally:
            usr.phone_feature = orig_pf
    return orig_usr(**kw)


def cap(parstochip, *a, **k):
    # send_pars_delaypars is the per-frame #279 capture seam: the
    # driver calls it once per emitted frame with the raw current /
    # previous parstochip pair.
    packets.append(tuple(parstochip))
    return orig_sp(parstochip, *a, **k)


ps.us_special_rules = wrapped
ptf.send_pars_delaypars = cap

from dectalk.api.speak import _speak_via_python_full


def stream_hash(text, m):
    mode[0] = m
    packets.clear()
    _speak_via_python_full(text, rate=1.0, voice=None, lang="us", lts_fallback=True)
    h = hashlib.sha256()
    for pk in packets:
        h.update(repr(pk).encode())
    return h.hexdigest(), len(packets)


prompts = json.loads(sys.argv[1])

# OUT_T0 sanity gate (docs/PARITY-METHOD.md section 4): FULL+VTM1 shows a
# ~120 Hz ramping contour on "hello world"; flat ~110 Hz = wrong pipeline.
stream_hash("hello world", "off")
f0 = [40000.0 / pk[OUT_T0] for pk in packets if pk[OUT_T0] > 0]
f0_mean = sum(f0) / len(f0)
sanity_ok = 110.0 <= f0_mean <= 135.0 and (max(f0) - min(f0)) >= 20.0

mismatched = []
frames = 0
for t in prompts:
    a = stream_hash(t, "off")
    b = stream_hash(t, "eq")
    c = stream_hash(t, "ne")
    frames += a[1]
    if not (a == b == c):
        mismatched.append(t)

print(
    json.dumps(
        {
            "sanity_ok": sanity_ok,
            "f0_mean": f0_mean,
            "fires": stats["fires"],
            "fires_lt2": stats["fires_lt2"],
            "min_nphone": stats["min_nphone"],
            "clauses": stats["clauses"],
            "allophons0": sorted(allophons0),
            "gen_sil": GEN_SIL,
            "frames": frames,
            "mismatched_prompts": mismatched,
        }
    )
)
"""


@pytest.mark.slow
def test_rule2_never_fires_clause_initially_and_packets_invariant() -> None:
    """Live-pipeline pin: no ``nphone < 2`` firing; packet stream invariant.

    Runs the pure-Python FULL+VTM1 pipeline in a subprocess (env set
    before import, per docs/PARITY-METHOD.md section 4) over the
    adversarial prompt set, rendering each prompt three times: shipped
    code, kluge forced EQUAL at ``nphone < 2``, kluge forced UNEQUAL.

    Asserts:

    - the OUT_T0 sanity gate passes (right pipeline captured);
    - Rule 2 fired (the prompts do exercise it) but never below
      ``nphone == 2`` — the OOB window is unreachable;
    - every clause start had ``allophons[0] == GEN_SIL``;
    - the three packet streams are identical for every prompt — the
      value of the C binary's OOB read cannot influence any packet.
    """
    env = dict(os.environ)
    env["DECTALK_DISABLE_CAPI"] = "1"
    env["DECTALK_FULL_PIPELINE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", _DRIVER, json.dumps(list(_ADVERSARIAL))],
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, f"driver failed:\n{proc.stdout}\n{proc.stderr}"
    result = json.loads(proc.stdout.splitlines()[-1])

    assert result["sanity_ok"], f"OUT_T0 sanity gate failed: mean={result['f0_mean']:.1f} Hz"
    # The adversarial prompts genuinely exercise Rule 2 ...
    assert result["fires"] > 0, "adversarial prompts never fired Rule 2 -- prompt set rotted?"
    # ... but never inside the OOB window.
    assert result["fires_lt2"] == 0, f"Rule 2 fired at nphone < 2: {result}"
    assert result["min_nphone"] >= 2
    # Every clause starts with the leading silence.
    assert result["clauses"] >= len(_ADVERSARIAL)
    assert result["allophons0"] == [result["gen_sil"]]
    # Forced-branch packet invariance.
    assert result["frames"] > 0
    assert result["mismatched_prompts"] == [], (
        f"packet stream depends on the OOB read: {result['mismatched_prompts']}"
    )
