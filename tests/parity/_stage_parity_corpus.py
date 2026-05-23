"""Focused corpus for per-stage parity tests.

The full :mod:`tests.parity._corpus` corpus is ~133K prompts — far too
many for per-stage tests that each invoke the C oracle (one ``dump_pipeline``
call ≈ 100-300 ms). For divergence-localization monitoring we want a
small representative subset that exercises:

- a plain short utterance ("hello world"),
- punctuation handling ("yes, and no."),
- numbers (which trigger CMD-side number expansion),
- inline commands ("[:rate 250] testing"),
- a stretchier sentence (longer LTS / PH workload).

Each entry is intended to surface a different class of divergence
between the Python and C pipelines. Add prompts here when a new
class of bug crops up; otherwise keep the list small.
"""

from __future__ import annotations

STAGE_PARITY_CORPUS: tuple[str, ...] = (
    "hello world",
    "yes, and no.",
    "the answer is 42",
    "[:rate 250] testing one two three",
    "the quick brown fox jumps over the lazy dog",
)
