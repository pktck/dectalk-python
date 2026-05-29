# F2 stop→vowel "stuck high" + steady-state offset — root cause (2026-05-29)

Worker-lane diagnostic note for the pure-Python byte-parity effort
(`DECTALK_DISABLE_CAPI=1 DECTALK_FULL_PIPELINE=1`).

**Lane investigated:** `src/dectalk/ph/{gettar,getbegtar,getendtar,make_dip,
dph_settar_st}.py` and the `*_locus_tables.py` family (the PH target-lookup
and obstruent→sonorant locus chain).

**Assigned symptoms:**
1. stop→vowel F2 "stuck ~440 Hz high" (e.g. `pa`/`ta`/`ka`: Py F2 ≈ 1697 vs
   C ≈ 1190 through the vowel);
2. a "~70 Hz steady-state F2 smoothing offset".

## TL;DR — the lane is correct; both symptoms are upstream of it

Per-frame F1/F2/F3 verification against the C oracle (`[:debug 2200]`
frame dump) shows the target-lookup / locus / `make_dip` chain is
**already at parity** wherever the C and Python allophone streams agree:

| prompt | phone | C F2 | Py F2 | ΔF2 |
|---|---|---:|---:|---:|
| `ah` | AA (steady plateau) | 1200 | 1196 | **−4** |
| `hot` | AA | 1449 | 1473 | +24 |
| `father` | AA | 1267 | 1277 | +10 |
| `see` | IY (steady plateau) | 2032 | 2032 | **0** |

The reported ~440 Hz "stuck high" is **not** an F2-target, `make_dip`, or
smoothing error. It is an **upstream letter-to-sound (LTS) vowel-identity
substitution**: for `pa`/`ta`/`ka` the C oracle says the vowel is **AA**
(F2 ≈ 1200), while the Python LTS emits **AE** (F2 ≈ 1700). 1697 ≈ AE's F2;
1190 ≈ AA's F2 — i.e. both pipelines render *their* vowel correctly; they
just disagree on *which vowel it is*.

The "~70 Hz steady-state offset" does not exist as a uniform smoothing bias.
The signed steady-state ΔF2 across matched vowels has **median ≈ +0.5 Hz**.
The ~70 Hz figure is a corpus *average* diluted from the ~500 Hz
vowel-identity errors on a large minority of prompts (see the scan below).

**Recommendation: make no change in this lane.** Redirect the work to the
LTS / dictionary lane (`src/dectalk/lts/rules_us.py`).

## Evidence

### 1. `pa`/`ta`/`ka`: vowel identity differs, F2 of each vowel is correct

C `[:debug 2200]` vs Python full-pipeline per-frame dump, steady-state of
each phone run:

```
pa   C : US_P(F2 1055)  US_AA(F2 1197)  SIL
     Py: P  (F2 1257)   AE  (F2 1697)   SIL      <- code 5 = US_AE, not US_AA(6)
ta   C : US_T           US_AA(F2 1196)  SIL
     Py: T              AE  (F2 1697)   SIL
ka   C : US_K           US_AA(F2 1198)  SIL
     Py: K              AE  (F2 1698)   SIL
```

The Python allophone code for the vowel is **5** (`US_AE`); the C oracle's
is **6** (`US_AA`) — confirmed against the upstream enum
(`src/dapi/src/include/l_all_ph.h`: `US_AE 5`, `US_AA 6`).

The two phones legitimately point at different diphthong dips, and *both*
dips are transcribed correctly in `rom_tables.py`:

```
AA F2 target = us_maltar[63] = -92  -> us_maldip[92] = [1200, 40, 1200, 200, 1200]  (steady 1200)
AE F2 target = us_maltar[62] = -68  -> us_maldip[68] = [1533, 40, 1698, 120, 1698]  (steady 1698)
```

So `gettar`→`make_dip` faithfully produces 1200 for AA and 1698 for AE.
Nothing in this lane is wrong; the lane is fed the wrong phone.

### 2. The substitution is in the LTS, not the allophone encoder

```
lts("pa")  -> ['P', 'AE1']      lts("ah")    -> ['AA1']        (correct)
lts("ta")  -> ['T', 'AE1']      lts("father")-> [...,'AE1',...] (but dict overrides -> AA)
lts("ka")  -> ['K', 'AE1']      lts("bar")   -> ['B','AA1','R'] (correct, 'r' triggers AA)
lts("spa") -> ['S','P','AE1']   lts("la")    -> ['L','AE1']
```

Word-final stressed **open** `a` is mapped to **AE1**; it should be **AA**
(as in `spa`, `ma`, `bra`, `pa`). Dictionary words (`father`, `hot`) are
unaffected because the dictionary supplies AA directly — which is exactly
why their AA F2 matches the C oracle in the table above.

**Handoff pointer:** `src/dectalk/lts/rules_us.py` — add/repair the rule for
word-final stressed open `a` → `AA` (the existing `_Rule("AH","","$",("AA",))`
covers the digraph "ah" only). This is the LTS lane.

### 3. Matched-sequence per-frame F2 scan (250-prompt corpus sample)

```
prompts analysed: 250
  sequence MATCH    : 28
  sequence MISMATCH : 222   (vowel-substitution in 100)

per-frame |ΔF2| on MATCHED-sequence prompts (THIS LANE): mean=22.6 Hz, rms=46.4 Hz
per-frame |ΔF2| over ALL prompts (LTS-contaminated):     mean=104.1 Hz, rms=184.2 Hz
```

- **89 % of prompts have a different phone sequence** between C and Python —
  the dominant parity blocker, and it is upstream (LTS / dict / timing), not
  this lane.
- On matched sequences, this lane's |ΔF2| is small (22.6 Hz mean, much of it
  transition-edge timing — see §4). The orchestrator's ~70 Hz sits *between*
  the matched-lane mean (22.6) and the contaminated mean (104) — it is the
  diluted average, not a lane bias.

Signed steady-state ΔF2 on matched vowel mid-frames: **mean +16, median
+0.5 Hz**. Per-vowel signed means are mostly within ±20 Hz with both signs
(AA +1, AO 0, OW −5, RR +1); the only large skew is front vowels (IY +85,
AY +37), which §4 shows is a transition-rate artifact, not a plateau offset.

### 4. The IY "+85" is a 1-frame transition-rate difference, not an offset

`see` (S→IY), per-frame F2:

```
     C            Py
...  1551         1584
     1968         2032     <- Py reaches the IY F2 plateau ~1 frame ahead
     2032 (peak)  2032
     2032         2032     <- both plateau at 2032 (ΔF2 = 0)
     2032         2032
```

The IY F2 **plateau is identical (2032 = 2032)**. The transient +64 Hz is
the rising edge arriving ~1 frame early on the Python side — a `durtran` /
`phdraw` timing nuance, sub-7 %, not a target or steady-state error.

## What this lane is *not* responsible for (handoff)

| symptom | real root cause | lane |
|---|---|---|
| F2 "stuck 440 Hz high" on pa/ta/ka/calm/la/spa | LTS final-open-`a` → AE1 (should be AA) | `lts/rules_us.py` |
| ~70 Hz "steady-state F2 offset" | corpus-avg dilution of the above; no uniform bias | n/a |
| 89 % phone-sequence mismatch | LTS / dict / `ph_timng` divergences | lts / dict / timing |
| ±1-frame transition-rate on front vowels | `durtran` / `phdraw` | ph draw/smooth |

## Reproducers

```bash
# Shared C oracle (build once, read-only):
scripts/setup_c_oracle.sh           # -> /tmp/dectalk-binary-stable

# C per-frame dump (cols: phone AP F1 .. TLT F0 AV F2 F3 FZ B1 B2 B3):
cd /tmp/dectalk-binary-stable && LD_LIBRARY_PATH=$PWD/lib \
  ./say -a "[:debug 2200]pa" -fo /dev/null

# Python LTS check:
uv run python -c "from dectalk.lts import lts; print(lts('pa'), lts('ah'))"
#   -> ['P', 'AE1'] ['AA1']

# Diph-dip values (both transcribed correctly):
uv run python -c "from dectalk.ph.rom_tables import us_maltar, us_maldip; \
  print('AA', us_maltar[63], us_maldip[92:97]); \
  print('AE', us_maltar[62], us_maldip[68:73])"
```

The per-frame comparison + corpus-scan scripts used for this note live in
the worker scratch tree (`/tmp/{perframe,scan,bigscan,steady}.py`); they
re-derive every number above from the C oracle and the Python pipeline.
