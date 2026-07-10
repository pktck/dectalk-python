#!/usr/bin/env python3
"""Build out-of-corpus discovery prompt sets (issue #316).

The 133K-prompt parity corpus is 100% byte-exact end-to-end but is not
all of English: #310's ``stopped`` family had zero corpus coverage and
was found only by a lucky probe. This generator emits deterministic
prompt files that target the corpus's known blind spots, for
``scripts/corpus_wav_sweep.py --prompts``:

- ``dict_bare.txt`` / ``dict_carrier.txt`` — every runtime-dictionary
  key (``$DECTALK_SRC/src/dapi/src/dic/Dic_us.txt``) that never occurs
  in ``tests/parity/_corpus.py``, spoken bare and inside a fixed
  carrier sentence.
- ``inflect_bare.txt`` / ``inflect_carrier.txt`` — regular
  -ed/-ing/-s/-er/-est inflections generated over a final-consonant
  stem grid (the #310 family shape: doubled finals, silent-e drops,
  y→i mutations, sibilant -es, agentive -er).
- ``commands.txt`` — ``[:cmd]`` grids over the active
  ``command_table`` (``c_us_cde.h``) at documented option values,
  plus combination/malformed edges.
- ``digits.txt`` — digit shapes: cardinals, ordinals, decimals,
  currency, percentages, times, dates, phone numbers, fractions,
  versions, grouping and mixed alphanumerics (bare + carrier).
- ``punctuation.txt`` — multi-sentence terminator mixes, symbol
  spellouts, abbreviations, apostrophes, case edges. (Punctuation-only
  prompts overlap issue #315's silence-clause lane by design — the
  census attributes those rather than re-filing.)

Usage::

    export DECTALK_SRC=/tmp/dectalk-oracle-src
    uv run python scripts/build_discovery_prompts.py --out-dir /tmp/discovery-prompts

Everything is deterministic: fixed tables, sorted dictionary output,
no randomness — re-running over the same oracle tree and corpus
reproduces the sets byte-for-byte.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

# The carrier sentence wraps a target token in a known-good clause so
# divergences that only fire in sentence context (stress, timing,
# clause-final lengthening) are exercised too.
_CARRIER = "Say {} again."

# ---------------------------------------------------------------------------
# Dictionary vocabulary set
# ---------------------------------------------------------------------------


def _split_dic_fields(line: str) -> list[str]:
    r"""Split a ``Dic_us.txt`` entry on unescaped commas.

    ``\,`` / ``\;`` escape literal characters inside a field (e.g. the
    dictionary key for the comma word itself).
    """
    fields: list[str] = []
    cur: list[str] = []
    esc = False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ",":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields


def _load_dictionary_keys(dic_path: Path) -> list[str]:
    """All entry keys from ``Dic_us.txt`` (latin-1, ``;`` comment lines)."""
    keys: list[str] = []
    for raw in dic_path.read_text(encoding="latin-1").splitlines():
        if not raw or raw.startswith(";"):
            continue
        key = _split_dic_fields(raw)[0]
        if key:
            keys.append(key)
    return keys


def _corpus_token_set() -> set[str]:
    """Lowercased token vocabulary of the parity corpus.

    Two tokenizations, unioned, so both plain words and
    punctuation-glued occurrences count as coverage: whitespace split
    and an alphanumeric-run scan.
    """
    sys.path.insert(0, str(_REPO_ROOT))
    from tests.parity._corpus import CORPUS  # noqa: PLC0415

    tokens: set[str] = set()
    for text in CORPUS:
        low = text.lower()
        tokens.update(low.split())
        tokens.update(re.findall(r"[a-z0-9']+", low))
    return tokens


def _dictionary_sets(dic_path: Path) -> tuple[list[str], list[str], dict[str, int]]:
    """(bare prompts, carrier prompts, stats) for uncovered dict keys."""
    keys = _load_dictionary_keys(dic_path)
    tokens = _corpus_token_set()
    ascii_keys = [k for k in keys if k.isascii() and k.isprintable()]
    uncovered = sorted(
        {k for k in ascii_keys if k.lower() not in tokens},
        key=lambda k: (k.lower(), k),
    )
    stats = {
        "dict_entries": len(keys),
        "dict_ascii": len(ascii_keys),
        "dict_uncovered": len(uncovered),
    }
    bare = list(uncovered)
    carrier = [_CARRIER.format(k) for k in uncovered]
    return bare, carrier, stats


# ---------------------------------------------------------------------------
# Inflection grid (the #310 family shape)
# ---------------------------------------------------------------------------

# Regular verb stems as (stem, doubles_final_consonant). Grouped by the
# stem-final sound class so the -ed/-ing/-s allomorph grid (/t/ vs /d/
# vs /ihd/; /s/ vs /z/ vs /ihz/) and the orthographic doubling rule are
# both walked systematically. Only stems whose regular inflections are
# real English words are listed.
_VERB_STEMS: tuple[tuple[str, bool], ...] = (
    # voiceless stop finals /p/
    ("stop", True),
    ("hop", True),
    ("skip", True),
    ("drop", True),
    ("wrap", True),
    ("clap", True),
    ("whip", True),
    ("snap", True),
    ("trip", True),
    ("dip", True),
    ("mop", True),
    ("tap", True),
    ("tip", True),
    ("pop", True),
    ("zip", True),
    ("flip", True),
    ("strip", True),
    ("grip", True),
    ("slip", True),
    ("step", True),
    ("shop", True),
    ("help", False),
    ("jump", False),
    ("camp", False),
    ("pump", False),
    ("bump", False),
    ("limp", False),
    ("gasp", False),
    ("grasp", False),
    # /t/
    ("chat", True),
    ("pat", True),
    ("plot", True),
    ("knit", True),
    ("spot", True),
    ("trot", True),
    ("submit", True),
    ("admit", True),
    ("permit", True),
    ("regret", True),
    ("commit", True),
    ("wait", False),
    ("want", False),
    ("count", False),
    ("paint", False),
    ("lift", False),
    ("rent", False),
    ("start", False),
    ("visit", False),
    ("edit", False),
    ("limit", False),
    ("plant", False),
    ("print", False),
    ("hunt", False),
    ("shout", False),
    ("doubt", False),
    ("treat", False),
    ("heat", False),
    ("melt", False),
    ("halt", False),
    ("insist", False),
    ("list", False),
    ("test", False),
    ("rest", False),
    ("trust", False),
    ("twist", False),
    ("dust", False),
    ("post", False),
    ("toast", False),
    ("boast", False),
    ("roast", False),
    # /k/
    ("walk", False),
    ("talk", False),
    ("look", False),
    ("cook", False),
    ("kick", False),
    ("lock", False),
    ("pick", False),
    ("park", False),
    ("work", False),
    ("ask", False),
    ("bark", False),
    ("mark", False),
    ("pack", False),
    ("lick", False),
    ("rock", False),
    ("knock", False),
    ("block", False),
    ("check", False),
    ("click", False),
    ("crack", False),
    ("track", False),
    ("wreck", False),
    ("risk", False),
    ("thank", False),
    ("blink", False),
    ("wink", False),
    # voiced stop finals /b/
    ("grab", True),
    ("rub", True),
    ("sob", True),
    ("stab", True),
    ("rob", True),
    ("throb", True),
    ("scrub", True),
    ("jab", True),
    ("nab", True),
    ("absorb", False),
    ("disturb", False),
    ("curb", False),
    ("climb", False),
    ("comb", False),
    # /d/
    ("nod", True),
    ("pad", True),
    ("plod", True),
    ("prod", True),
    ("need", False),
    ("load", False),
    ("fold", False),
    ("add", False),
    ("end", False),
    ("land", False),
    ("mend", False),
    ("hand", False),
    ("head", False),
    ("avoid", False),
    ("record", False),
    ("reward", False),
    ("guard", False),
    ("demand", False),
    ("expand", False),
    ("sound", False),
    ("pound", False),
    # /g/
    ("jog", True),
    ("beg", True),
    ("hug", True),
    ("shrug", True),
    ("plug", True),
    ("drag", True),
    ("wag", True),
    ("tug", True),
    ("lag", True),
    ("log", True),
    ("flag", True),
    ("brag", True),
    ("sag", True),
    ("nag", True),
    ("belong", False),
    ("bang", False),
    # sibilant finals (-es allomorph)
    ("kiss", False),
    ("miss", False),
    ("pass", False),
    ("press", False),
    ("guess", False),
    ("toss", False),
    ("cross", False),
    ("dress", False),
    ("bless", False),
    ("stress", False),
    ("focus", False),
    ("fix", False),
    ("mix", False),
    ("box", False),
    ("relax", False),
    ("tax", False),
    ("wax", False),
    ("flex", False),
    ("buzz", False),
    ("fizz", False),
    ("wish", False),
    ("wash", False),
    ("push", False),
    ("brush", False),
    ("crash", False),
    ("flash", False),
    ("finish", False),
    ("polish", False),
    ("publish", False),
    ("punish", False),
    ("vanish", False),
    ("watch", False),
    ("march", False),
    ("touch", False),
    ("reach", False),
    ("search", False),
    ("fetch", False),
    ("pitch", False),
    ("switch", False),
    ("scratch", False),
    ("stretch", False),
    ("launch", False),
    ("munch", False),
    ("crunch", False),
    ("preach", False),
    ("coach", False),
    ("attach", False),
    ("quiz", True),
    # silent-e finals
    ("bake", False),
    ("like", False),
    ("poke", False),
    ("hike", False),
    ("joke", False),
    ("smoke", False),
    ("glide", False),
    ("fade", False),
    ("trade", False),
    ("decide", False),
    ("live", False),
    ("love", False),
    ("save", False),
    ("wave", False),
    ("move", False),
    ("dive", False),
    ("dance", False),
    ("race", False),
    ("place", False),
    ("notice", False),
    ("judge", False),
    ("change", False),
    ("manage", False),
    ("doze", False),
    ("sneeze", False),
    ("amaze", False),
    ("smile", False),
    ("file", False),
    ("rule", False),
    ("fire", False),
    ("share", False),
    ("stare", False),
    ("care", False),
    ("compare", False),
    ("hope", False),
    ("note", False),
    ("vote", False),
    ("quote", False),
    ("taste", False),
    ("waste", False),
    ("phone", False),
    ("close", False),
    ("cause", False),
    ("pause", False),
    ("raise", False),
    ("praise", False),
    ("refuse", False),
    ("use", False),
    ("blame", False),
    ("frame", False),
    ("name", False),
    ("time", False),
    ("type", False),
    ("hate", False),
    ("date", False),
    ("gaze", False),
    ("giggle", False),
    ("juggle", False),
    ("struggle", False),
    ("sparkle", False),
    ("whistle", False),
    ("settle", False),
    ("handle", False),
    ("sample", False),
    ("cycle", False),
    ("circle", False),
    ("battle", False),
    ("bathe", False),
    ("breathe", False),
    ("soothe", False),
    # fricative finals
    ("laugh", False),
    ("cough", False),
    ("sniff", False),
    ("stuff", False),
    ("huff", False),
    ("puff", False),
    ("bluff", False),
    ("surf", False),
    ("golf", False),
    ("smooth", False),
    # nasal finals
    ("plan", True),
    ("pin", True),
    ("grin", True),
    ("scan", True),
    ("ban", True),
    ("stun", True),
    ("skin", True),
    ("slam", True),
    ("jam", True),
    ("trim", True),
    ("drum", True),
    ("hum", True),
    ("skim", True),
    ("cram", True),
    ("strum", True),
    ("rain", False),
    ("seem", False),
    ("dream", False),
    ("clean", False),
    ("open", False),
    ("happen", False),
    ("listen", False),
    ("learn", False),
    ("turn", False),
    ("burn", False),
    ("warn", False),
    ("sign", False),
    ("join", False),
    ("gain", False),
    ("moan", False),
    ("groan", False),
    ("lean", False),
    ("scream", False),
    ("claim", False),
    ("aim", False),
    ("form", False),
    ("harm", False),
    ("farm", False),
    ("storm", False),
    ("zoom", False),
    ("bloom", False),
    ("roam", False),
    # liquid finals
    ("call", False),
    ("pull", False),
    ("fill", False),
    ("roll", False),
    ("spell", False),
    ("smell", False),
    ("travel", False),
    ("cancel", False),
    ("label", False),
    ("model", False),
    ("level", False),
    ("stir", True),
    ("blur", True),
    ("occur", True),
    ("prefer", True),
    ("refer", True),
    ("star", True),
    ("scar", True),
    ("spur", True),
    ("pour", False),
    ("repair", False),
    ("offer", False),
    ("answer", False),
    ("remember", False),
    ("wonder", False),
    ("cover", False),
    ("order", False),
    ("color", False),
    ("favor", False),
    ("honor", False),
    ("enter", False),
    ("deliver", False),
    ("discover", False),
    ("gather", False),
    ("bother", False),
    ("hammer", False),
    ("whisper", False),
    ("appear", False),
    ("cheer", False),
    ("steer", False),
    ("roar", False),
    ("soar", False),
    ("fear", False),
    # vowel / glide finals
    ("play", False),
    ("stay", False),
    ("pray", False),
    ("spray", False),
    ("delay", False),
    ("obey", False),
    ("enjoy", False),
    ("destroy", False),
    ("employ", False),
    ("annoy", False),
    ("follow", False),
    ("borrow", False),
    ("swallow", False),
    ("snow", False),
    ("glow", False),
    ("flow", False),
    ("allow", False),
    # consonant+y finals (y -> ied/ies mutation)
    ("cry", False),
    ("try", False),
    ("fry", False),
    ("dry", False),
    ("spy", False),
    ("carry", False),
    ("hurry", False),
    ("study", False),
    ("marry", False),
    ("copy", False),
    ("empty", False),
    ("worry", False),
    ("bury", False),
    ("tidy", False),
    ("envy", False),
    ("pity", False),
    ("vary", False),
    ("apply", False),
    ("reply", False),
    ("supply", False),
    ("deny", False),
    ("rely", False),
    ("defy", False),
    ("multiply", False),
    ("satisfy", False),
    ("qualify", False),
    ("notify", False),
)

# Adjective stems (comparative -er / superlative -est), same doubling flag.
_ADJ_STEMS: tuple[tuple[str, bool], ...] = (
    ("big", True),
    ("hot", True),
    ("thin", True),
    ("flat", True),
    ("sad", True),
    ("wet", True),
    ("red", True),
    ("fit", True),
    ("dim", True),
    ("slim", True),
    ("mad", True),
    ("tan", True),
    ("grim", True),
    ("nice", False),
    ("late", False),
    ("wide", False),
    ("safe", False),
    ("ripe", False),
    ("cute", False),
    ("brave", False),
    ("close", False),
    ("large", False),
    ("simple", False),
    ("gentle", False),
    ("pale", False),
    ("rude", False),
    ("fine", False),
    ("strange", False),
    ("dense", False),
    ("loose", False),
    ("happy", False),
    ("easy", False),
    ("busy", False),
    ("funny", False),
    ("heavy", False),
    ("tiny", False),
    ("ugly", False),
    ("angry", False),
    ("lazy", False),
    ("noisy", False),
    ("dirty", False),
    ("lucky", False),
    ("pretty", False),
    ("silly", False),
    ("early", False),
    ("hungry", False),
    ("wealthy", False),
    ("healthy", False),
    ("windy", False),
    ("cloudy", False),
    ("rainy", False),
    ("messy", False),
    ("fancy", False),
    ("curly", False),
    ("dusty", False),
    ("foggy", False),
    ("fuzzy", False),
    ("juicy", False),
    ("shiny", False),
    ("tall", False),
    ("short", False),
    ("fast", False),
    ("slow", False),
    ("old", False),
    ("young", False),
    ("small", False),
    ("cheap", False),
    ("deep", False),
    ("dark", False),
    ("light", False),
    ("strong", False),
    ("weak", False),
    ("rich", False),
    ("poor", False),
    ("clean", False),
    ("warm", False),
    ("cool", False),
    ("kind", False),
    ("hard", False),
    ("soft", False),
    ("loud", False),
    ("smart", False),
    ("sweet", False),
    ("thick", False),
    ("sharp", False),
    ("plain", False),
    ("proud", False),
    ("calm", False),
    ("new", False),
    ("high", False),
    ("low", False),
    ("bright", False),
    ("tight", False),
    ("smooth", False),
    ("rough", False),
    ("tough", False),
    ("fresh", False),
    ("quick", False),
    ("long", False),
    ("full", False),
    ("dull", False),
    ("great", False),
    ("near", False),
    ("mild", False),
    ("bold", False),
    ("cold", False),
    ("neat", False),
    ("steep", False),
    ("clear", False),
    ("quiet", False),
    ("narrow", False),
    ("shallow", False),
)

# Noun stems for the plural -s/-es allomorph grid.
_NOUN_STEMS: tuple[str, ...] = (
    "cat",
    "dog",
    "church",
    "box",
    "glass",
    "maze",
    "path",
    "month",
    "book",
    "tree",
    "car",
    "horse",
    "bridge",
    "prize",
    "rose",
    "fox",
    "bus",
    "class",
    "brush",
    "badge",
    "page",
    "lake",
    "gate",
    "cup",
    "hat",
    "map",
    "bed",
    "egg",
    "pig",
    "hand",
    "arm",
    "ear",
    "eye",
    "boy",
    "day",
    "key",
    "toy",
    "city",
    "baby",
    "lady",
    "story",
    "party",
    "army",
    "fly",
    "sky",
    "cliff",
    "chief",
    "bench",
    "branch",
    "bush",
    "dish",
    "lens",
    "waltz",
    "roof",
)

# Explicit irregular-orthography extras the rules above cannot generate.
_EXTRA_FORMS: tuple[str, ...] = (
    # o + -es plurals
    "echoes",
    "heroes",
    "potatoes",
    "tomatoes",
    "vetoes",
    # agentive -er over the doubling / silent-e / sibilant classes
    "stopper",
    "shopper",
    "wrapper",
    "jogger",
    "planner",
    "scanner",
    "winner",
    "runner",
    "swimmer",
    "drummer",
    "beginner",
    "robber",
    "teacher",
    "worker",
    "player",
    "dancer",
    "driver",
    "baker",
    "smoker",
    "trader",
    "mover",
    "diver",
    "racer",
    "manager",
    "mixer",
    "boxer",
    "washer",
    "watcher",
    "catcher",
    "preacher",
    "printer",
    "speaker",
)

_SIBILANT_ENDINGS = ("s", "x", "z", "ch", "sh")
_VOWELS = "aeiou"


def _ends_consonant_y(stem: str) -> bool:
    prev = stem[-2:-1]
    return stem.endswith("y") and bool(prev) and prev not in _VOWELS


def _suffix_base(stem: str, doubles: bool) -> str:
    """Stem adjusted for a vowel-initial suffix (-ed/-ing/-er/-est)."""
    if doubles:
        return stem + stem[-1]
    if stem.endswith("e") and not stem.endswith("ee"):
        return stem[:-1]
    return stem


def _inflect_ed(stem: str, doubles: bool) -> str:
    if _ends_consonant_y(stem):
        return stem[:-1] + "ied"
    return _suffix_base(stem, doubles) + "ed"


def _inflect_ing(stem: str, doubles: bool) -> str:
    if _ends_consonant_y(stem):
        return stem + "ing"
    return _suffix_base(stem, doubles) + "ing"


def _inflect_s(stem: str) -> str:
    if stem.endswith(_SIBILANT_ENDINGS):
        return stem + "es"
    if _ends_consonant_y(stem):
        return stem[:-1] + "ies"
    return stem + "s"


def _inflect_er(stem: str, doubles: bool) -> str:
    if _ends_consonant_y(stem):
        return stem[:-1] + "ier"
    return _suffix_base(stem, doubles) + "er"


def _inflect_est(stem: str, doubles: bool) -> str:
    if _ends_consonant_y(stem):
        return stem[:-1] + "iest"
    return _suffix_base(stem, doubles) + "est"


def _inflection_forms() -> list[str]:
    """All grid forms (stems included), deduplicated, insertion order."""
    forms: dict[str, None] = {}
    for stem, doubles in _VERB_STEMS:
        for form in (
            stem,
            _inflect_ed(stem, doubles),
            _inflect_ing(stem, doubles),
            _inflect_s(stem),
        ):
            forms[form] = None
    for stem, doubles in _ADJ_STEMS:
        for form in (stem, _inflect_er(stem, doubles), _inflect_est(stem, doubles)):
            forms[form] = None
    for stem in _NOUN_STEMS:
        for form in (stem, _inflect_s(stem)):
            forms[form] = None
    for form in _EXTRA_FORMS:
        forms[form] = None
    return list(forms)


def _inflection_sets() -> tuple[list[str], list[str]]:
    forms = _inflection_forms()
    return forms, [_CARRIER.format(f) for f in forms]


# ---------------------------------------------------------------------------
# [:cmd] grid
# ---------------------------------------------------------------------------


_RATE_VALUES = (
    75,
    90,
    100,
    120,
    150,
    180,
    200,
    225,
    250,
    300,
    350,
    400,
    450,
    500,
    550,
    600,
    50,
    700,
)
_VOICE_COMMANDS = ("np", "nb", "nh", "nf", "nd", "nk", "nu", "nr", "nw", "nv")
_VOICE_NAMES = (
    "paul",
    "betty",
    "harry",
    "frank",
    "dennis",
    "kit",
    "ursula",
    "rita",
    "wendy",
    "val",
)
_MODE_OPTIONS = (
    "math",
    "europe",
    "spell",
    "name",
    "homograph",
    "citation",
    "latin",
    "table",
    "email",
)


def _command_value_grids() -> list[str]:
    """Per-command value grids over the active command_table options."""
    base = "testing one two three"
    short = "hello world"
    out: list[str] = []
    # rate span (75..600 documented) + clamp edges
    out += [f"[:rate {r}] {base}" for r in _RATE_VALUES]
    # voice short commands and [:name X]
    out += [f"[:{v}] {short}" for v in _VOICE_COMMANDS]
    out += [f"[:name {name}] {short}" for name in _VOICE_NAMES]
    # volume options
    for opt, val in (
        ("set", 0),
        ("set", 10),
        ("set", 25),
        ("set", 50),
        ("set", 75),
        ("set", 90),
        ("set", 100),
        ("up", 10),
        ("down", 10),
        ("att", 50),
        ("lset", 50),
        ("rset", 50),
        ("sset", 50),
    ):
        out.append(f"[:volume {opt} {val}] {short}")
    # comma / period pause scaling
    for cmd in ("comma", "cp"):
        out += [f"[:{cmd} {v}] one, two, three, four." for v in (0, 40, 100, 250, 500)]
    for cmd in ("period", "pp"):
        out += [f"[:{cmd} {v}] First. Second. Third." for v in (0, 100, 250, 500, 750)]
    # explicit pause command
    out += [f"before [:pause {v}] after" for v in (0, 1, 10, 100, 1000)]
    # pitch (stress rise)
    out += [f"[:pitch {v}] {short}" for v in (0, 10, 35, 50, 100, 200)]
    # say modes
    say_opts = ("clause", "word", "letter", "filtered_letter", "line", "syllable")
    out += [f"[:say {m}] hello world one." for m in say_opts]
    # punctuation modes
    punct_text = "Stop, look; listen: now (please) - go!"
    out += [f"[:punctuation {m}] {punct_text}" for m in ("none", "some", "all", "pass")]
    # skip modes
    skip_text = "Dr. Smith's e-mail is test@example.com!"
    out += [f"[:skip {m}] {skip_text}" for m in ("none", "email", "punct", "rule", "all", "cpg")]
    # text-processing modes, on and off
    for m in _MODE_OPTIONS:
        out += [f"[:mode {m} {onoff}] read 3 + 4 = 7 to Dr. Wind" for onoff in ("on", "off")]
    # error handling modes (paired with a deliberate bad command)
    out += [f"[:error {m}] [:bogus] hello" for m in ("ignore", "text", "escape", "speak", "tone")]
    # tone generator + DTMF dialing
    out += [f"[:tone {f} {d}] done" for f, d in ((440, 100), (1000, 50), (100, 500), (2000, 10))]
    out += [f"[:dial {num}] done" for num in ("5551212", "18005550199", "0", "911")]
    # gender remap
    out += [f"[:gender {g}] {short}" for g in ("masculine", "feminine", "neuter")]
    # voice-definition parameters at documented extremes
    for p, v in (
        ("ap", 90),
        ("ap", 200),
        ("pr", 0),
        ("pr", 200),
        ("hs", 80),
        ("hs", 120),
        ("as", 0),
        ("as", 100),
        ("br", 40),
        ("ri", 0),
        ("sm", 100),
        ("sr", 0),
        ("bf", 20),
        ("qu", 0),
        ("gv", 55),
    ):
        out.append(f"[:dv {p} {v}] {short}")
    return out


def _command_edges() -> list[str]:
    """Phonemic input, stacked/mid-text switches, malformed commands."""
    base = "testing one two three"
    short = "hello world"
    return [
        # phonemic input mode + inline phonemic text
        "[:phoneme on] hello",
        "[:phoneme off] hello",
        "[:phoneme arpabet on] hello",
        "[hxehlow] world",
        "say [dhihs] now",
        # index marks, sync, resume
        f"[:index mark 1] {short}",
        "hello [:index mark 42] world",
        f"[:sync] {short}",
        "hello [:sync]",
        f"[:resume] {short}",
        # stacking / mid-text switches / trailing commands
        f"[:np][:rate 300][:volume set 80] {base}",
        f"[:np] [:rate 300] [:volume set 80] {base}",
        "start [:rate 300] speed up [:rate 100] slow down",
        "voice [:nb] betty now [:np] paul again",
        "[:nh] [:pitch 50] harry low",
        "text before [:rate 300]",
        "[:rate 300]",
        "[:np]",
        "[:volume set 50]",
        # malformed / unknown command edges
        "[:bogus] hello",
        "[:rate] hello",
        "[:rate abc] hello",
        "[: rate 200] hello",
        "[:rate 200 hello",
        "[] hello",
        "[:] hello",
        "hello [:",
    ]


def _command_prompts() -> list[str]:
    """Grids over the active command_table (c_us_cde.h) + edges."""
    return _command_value_grids() + _command_edges()


# ---------------------------------------------------------------------------
# Digit / number-shape grid
# ---------------------------------------------------------------------------


def _digit_shapes() -> list[str]:
    shapes: list[str] = []
    shapes += [str(n) for n in range(26)]
    shapes += [
        "30",
        "33",
        "40",
        "44",
        "50",
        "55",
        "60",
        "66",
        "70",
        "77",
        "80",
        "88",
        "90",
        "99",
        "100",
        "101",
        "110",
        "111",
        "123",
        "200",
        "222",
        "300",
        "456",
        "500",
        "789",
        "900",
        "999",
        "1000",
        "1001",
        "1024",
        "1100",
        "1234",
        "1776",
        "1900",
        "1999",
        "2000",
        "2001",
        "2026",
        "5000",
        "9999",
        "10000",
        "12345",
        "65536",
        "99999",
        "100000",
        "123456",
        "999999",
        "1000000",
        "1000001",
        "12345678",
        "123456789",
        "1000000000",
        "4294967295",
    ]
    # ordinals (incl. date-style and awkward teens)
    shapes += [
        "1st",
        "2nd",
        "3rd",
        "4th",
        "5th",
        "8th",
        "9th",
        "11th",
        "12th",
        "13th",
        "20th",
        "21st",
        "22nd",
        "23rd",
        "24th",
        "30th",
        "31st",
        "40th",
        "42nd",
        "53rd",
        "99th",
        "100th",
        "101st",
        "111th",
        "1000th",
    ]
    # decimals
    shapes += [
        "0.5",
        ".5",
        "3.14",
        "3.14159",
        "0.001",
        "123.456",
        "100.00",
        "0.0",
        "1.5",
        "2.25",
        "99.99",
        "1234.5678",
    ]
    # currency
    shapes += [
        "$1",
        "$5",
        "$1.50",
        "$0.99",
        "$100",
        "$1,000",
        "$1,234.56",
        "$1000000",
        "$19.95",
        "$0.01",
    ]
    # percentages
    shapes += ["5%", "3.5%", "100%", "0.1%", "50%"]
    # clock times
    shapes += ["1:00", "12:30", "9:05", "23:59", "12:00", "3:45", "11:11", "0:30"]
    # dates
    shapes += [
        "7/4/1776",
        "12/25/2025",
        "1/2/2026",
        "01/02/2026",
        "2026-07-10",
        "July 4, 1776",
        "the 4th of July",
    ]
    # phone numbers
    shapes += ["555-1212", "(800) 555-0199", "1-800-555-0199"]
    # negatives
    shapes += ["-40", "-3.5", "-1", "-100"]
    # fractions and ratios
    shapes += ["1/2", "3/4", "22/7", "1/100", "2/3", "24/7", "9/11"]
    # ranges and scores
    shapes += ["1-10", "10-20", "3-2", "7-0"]
    # versions
    shapes += ["6.2.0", "1.2.3.4", "2.0", "10.04"]
    # mixed alphanumerics
    shapes += [
        "A1",
        "3M",
        "B2B",
        "42nd Street",
        "Route 66",
        "Boeing 747",
        "Area 51",
        "Catch-22",
        "7-Eleven",
    ]
    # leading zeros
    shapes += ["007", "0001", "08", "09", "000", "0.007"]
    # digit grouping (well- and ill-formed)
    shapes += ["1,000", "12,345", "12,345,678", "1,23", "12,34,56"]
    # scientific-ish
    shapes += ["6.02e23", "1E10", "2e-5"]
    # roman numerals
    shapes += ["IV", "XIV", "MMXXVI", "Chapter IV", "Henry VIII"]
    # units
    shapes += ["5 km", "10 mm", "100 mph", "72 degrees", "98.6 degrees"]
    return shapes


def _digit_prompts() -> list[str]:
    shapes = _digit_shapes()
    prompts = list(dict.fromkeys(shapes))
    prompts += [_CARRIER.format(s) for s in shapes]
    return prompts


# ---------------------------------------------------------------------------
# Punctuation / multi-sentence grid
# ---------------------------------------------------------------------------


def _punctuation_prompts() -> list[str]:
    out: list[str] = []
    # terminator pair grid across a sentence boundary
    firsts = (".", "!", "?", "...")
    seconds = (".", "!", "?")
    for a in firsts:
        for b in seconds:
            out.append(f"One{a} Two{b}")
    # mid-clause separators and symbol spellouts
    for mid in (
        ",",
        ";",
        ":",
        " -",
        " --",
        " ---",
        "/",
        "&",
        "@",
        "#",
        "%",
        "$",
        "*",
        "+",
        "=",
        "_",
        "~",
        "|",
        "^",
        "<",
        ">",
    ):
        out.append(f"one{mid} two")
    out.append("one (two) three")
    out.append("one {two} three")
    out.append('he said "stop" now')
    out.append("he said 'stop' now")
    # repeated terminators
    out += ["stop!!", "what??", "really?!", "wait--", "hmm...", "so...", "!!!", "???"]
    # punctuation-only inputs (issue #315's silence-clause lane)
    out += ["...", "..", ".", "!", "?", ",", ";", ":", "-", "()", '""']
    # abbreviations and title periods
    out += [
        "Dr. Smith lives on St. Paul Street.",
        "Mr. and Mrs. Jones met Ms. Lee.",
        "e.g. apples, i.e. fruit, etc.",
        "the U.S.A. and the U.K.",
        "at 9 a.m. or 9 p.m.",
        "Prof. Brown, Jr. and Sgt. Green, Sr.",
        "No. 5 vs. no. 6",
    ]
    # apostrophes and contractions
    out += [
        "don't stop",
        "it's John's book",
        "the '90s",
        "five o'clock",
        "we'll they've I'd you're",
        "'twas the night",
        "the dogs' bones",
    ]
    # case edges
    out += [
        "HELLO WORLD",
        "NASA and IBM",
        "MiXeD CaSe words",
        "camelCaseWord here",
        "ALLCAPS then lower",
    ]
    # hyphenation
    out += [
        "well-known state-of-the-art re-enter",
        "twenty-one thirty-two",
        "a so-called know-it-all",
        "x-ray e-mail t-shirt",
    ]
    # whitespace edges
    out += [
        "double  space",
        "   leading spaces",
        "trailing spaces   ",
        "tab\there",
    ]
    # multi-sentence stress
    out += [
        "First. Second? Third! Fourth.",
        "Stop! Go? Wait. Now!",
        "A, b; c: d - e (f) g.",
        "One. Two. Three. Four. Five. Six.",
    ]
    # email / URL shapes
    out += [
        "user@example.com",
        "http://example.com",
        "www.example.com",
        "name at example dot com",
    ]
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _write_set(out_dir: Path, name: str, prompts: list[str]) -> None:
    deduped = list(dict.fromkeys(prompts))
    (out_dir / name).write_text("\n".join(deduped) + ("\n" if deduped else ""), encoding="utf-8")
    print(f"  {name:22s} {len(deduped):6d} prompts")


def main(argv: list[str] | None = None) -> int:
    """Generate every discovery prompt set into ``--out-dir``."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/tmp/discovery-prompts"),
        help="directory for the generated prompt files",
    )
    parser.add_argument(
        "--dic",
        type=Path,
        default=None,
        help="Dic_us.txt path (default $DECTALK_SRC/src/dapi/src/dic/Dic_us.txt)",
    )
    args = parser.parse_args(argv)

    dic_path = args.dic or (
        Path(os.environ.get("DECTALK_SRC", "/tmp/dectalk-src"))
        / "src"
        / "dapi"
        / "src"
        / "dic"
        / "Dic_us.txt"
    )
    if not dic_path.is_file():
        print(f"ERROR: dictionary not found at {dic_path}; set DECTALK_SRC or --dic")
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"writing discovery prompt sets to {args.out_dir}")

    dict_bare, dict_carrier, stats = _dictionary_sets(dic_path)
    print(
        f"  dictionary: {stats['dict_entries']} entries, "
        f"{stats['dict_ascii']} ascii, {stats['dict_uncovered']} uncovered by corpus"
    )
    _write_set(args.out_dir, "dict_bare.txt", dict_bare)
    _write_set(args.out_dir, "dict_carrier.txt", dict_carrier)

    inflect_bare, inflect_carrier = _inflection_sets()
    _write_set(args.out_dir, "inflect_bare.txt", inflect_bare)
    _write_set(args.out_dir, "inflect_carrier.txt", inflect_carrier)

    _write_set(args.out_dir, "commands.txt", _command_prompts())
    _write_set(args.out_dir, "digits.txt", _digit_prompts())
    _write_set(args.out_dir, "punctuation.txt", _punctuation_prompts())
    return 0


if __name__ == "__main__":
    sys.exit(main())
