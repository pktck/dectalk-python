#!/usr/bin/env python3
"""Full-corpus phoneme parity sweep vs the C oracle (issue #281 tooling).

Byte-compares ``dectalk.text_to_dectalk_phonemes`` against the patched C
library's ``TextToSpeechConvertToPhonemes`` for every prompt in
``tests/parity/_corpus.py`` (~133K prompts).

Why this exists instead of ``pytest -m c_oracle`` with a full-corpus
sample: the patched C library reliably **segfaults after ~45-60 seconds
of in-process use** (a few thousand ``convert_to_phonemes`` calls),
regardless of ``TextToSpeechStartup`` handle recycling. This driver
therefore walks the corpus in small slices, each in a **fresh
subprocess**, and resumes past crashes: when a slice dies, the crash
victim's index is recorded and the walk restarts one prompt later.
Recorded victims and mismatches are then **re-verified against a fresh
oracle** — mid-run library-state corruption otherwise produces
truncated/empty C outputs that read as false mismatches (~0.05% of
prompts in practice).

Usage::

    export DECTALK_SRC=/tmp/dectalk-src DECTALK_BIN=/tmp/dectalk-binary-stable
    uv run python scripts/corpus_phoneme_sweep.py                # full sweep
    uv run python scripts/corpus_phoneme_sweep.py --sample 2000  # strided subsample
    uv run python scripts/corpus_phoneme_sweep.py --update-known-list

``--update-known-list`` rewrites
``tests/parity/data/corpus_phoneme_known_divergent.txt`` (the xfail
allowlist consumed by ``tests/parity/test_python_phonemes_vs_c_parity.py``)
from the verified mismatch set and prints the delta.

Runtime: ~10-15 minutes for the full corpus with the default 4 workers
(~60-70 prompts/s/worker; the C call dominates).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_KNOWN_LIST = _REPO_ROOT / "tests" / "parity" / "data" / "corpus_phoneme_known_divergent.txt"

_KNOWN_LIST_HEADER = """\
# Corpus prompts whose Python phoneme stream is a known divergence from the
# C oracle (issue #281 burn-down list). One prompt per line, sorted.
# Regenerate: uv run python scripts/corpus_phoneme_sweep.py --update-known-list
"""


def _load_corpus() -> tuple[str, ...]:
    sys.path.insert(0, str(_REPO_ROOT))
    from tests.parity._corpus import CORPUS  # noqa: PLC0415

    return CORPUS


# --------------------------------------------------------------------------
# Worker mode: compare one batch of corpus indices inside a fresh process.
# --------------------------------------------------------------------------


def _worker(idx_file: str, out_path: str) -> None:
    """Compare the corpus indices listed in ``idx_file`` (one per line).

    Appends JSONL rows to ``out_path`` and prints a ``DONE <i>`` marker
    per prompt so the driver can locate the victim when this process is
    killed by the C library's segfault.
    """
    import dectalk  # noqa: PLC0415
    from dectalk._capi import CAPI  # noqa: PLC0415

    indices = [int(line) for line in Path(idx_file).read_text(encoding="utf-8").split()]
    corpus = _load_corpus()
    capi = CAPI()
    with open(out_path, "a", encoding="utf-8") as out:
        for i in indices:
            text = corpus[i]
            try:
                expected = capi.convert_to_phonemes(text)
            except Exception as exc:
                out.write(json.dumps({"i": i, "error": f"C: {exc}"}) + "\n")
                out.flush()
                print(f"DONE {i}", flush=True)
                continue
            actual = dectalk.text_to_dectalk_phonemes(text)
            if actual == expected:
                out.write(json.dumps({"i": i, "ok": 1}) + "\n")
            else:
                row = {
                    "i": i,
                    "text": text,
                    "c": expected.decode("latin-1"),
                    "py": actual.decode("latin-1"),
                }
                out.write(json.dumps(row) + "\n")
            out.flush()
            print(f"DONE {i}", flush=True)


# --------------------------------------------------------------------------
# Driver mode: banded, sliced, crash-resuming walk + verification pass.
# --------------------------------------------------------------------------


def _run_batch(indices: list[int], idx_file: Path, out_path: str) -> tuple[int, int]:
    """Run one worker subprocess over ``indices``; return (rc, last_done_pos).

    ``last_done_pos`` is the position within ``indices`` of the last
    prompt the worker completed (-1 when none were).
    """
    idx_file.write_text("\n".join(map(str, indices)) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, __file__, "--worker", str(idx_file), out_path],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    last_done = -1
    for line in proc.stdout.splitlines():
        if line.startswith("DONE "):
            last_done = int(line.split()[1])
    return proc.returncode, indices.index(last_done) if last_done >= 0 else -1


def _run_band(
    indices: list[int], wid: int, out_dir: Path, crash_victims: list[int], slice_size: int
) -> None:
    """Walk ``indices`` in ``slice_size`` batches, resuming past crashes."""
    out_path = str(out_dir / f"results_w{wid}.jsonl")
    idx_file = out_dir / f"batch_w{wid}.txt"
    pos = 0
    while pos < len(indices):
        batch = indices[pos : pos + slice_size]
        rc, last_done_pos = _run_batch(batch, idx_file, out_path)
        if rc == 0 or last_done_pos == len(batch) - 1:
            # clean exit, or the crash happened after the last prompt
            pos += len(batch)
            continue
        # the prompt after the last completed one is the crash victim
        crash_victims.append(batch[last_done_pos + 1])
        pos += last_done_pos + 2  # resume one prompt past the victim
    idx_file.unlink(missing_ok=True)


def _verify(
    indices: list[int], out_dir: Path, batch_size: int = 40
) -> dict[int, dict[str, object]]:
    """Re-run ``indices`` in small fresh batches; return {index: row}.

    A batch that crashes falls back to per-prompt subprocesses so a
    genuine crasher is pinned to its index instead of poisoning its
    batch-mates.
    """
    verify_path = out_dir / "verify.jsonl"
    verify_path.unlink(missing_ok=True)
    idx_file = out_dir / "batch_verify.txt"
    for k in range(0, len(indices), batch_size):
        chunk = indices[k : k + batch_size]
        rc, _ = _run_batch(chunk, idx_file, str(verify_path))
        if rc == 0:
            continue
        for idx in chunk:
            rc, _ = _run_batch([idx], idx_file, str(verify_path))
            if rc != 0:
                with open(verify_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"i": idx, "error": f"SEGV rc={rc}"}) + "\n")
    idx_file.unlink(missing_ok=True)
    result: dict[int, dict[str, object]] = {}
    if verify_path.exists():
        with open(verify_path, encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                result[row["i"]] = row
    return result


def _classify(c: str, py: str) -> str:
    """Coarse divergence class for the summary table."""
    strip_stress = re.sub(r"[\s'`*]+", "", c) == re.sub(r"[\s'`*]+", "", py)
    if strip_stress:
        return "stress-marks-only"
    markers = r"[\s'`*()^,.!?#@_\[\]-]+"
    if re.sub(markers, "", c) == re.sub(markers, "", py):
        return "phrase/POS-markers"
    return "word-pronunciation/other"


def main(argv: list[str] | None = None) -> int:
    """Drive the sweep (or run one worker slice with ``--worker``)."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--worker", nargs=2, metavar=("IDX_FILE", "OUT"), help=argparse.SUPPRESS)
    parser.add_argument(
        "--sample", type=int, default=0, help="strided subsample size (0 = full corpus)"
    )
    parser.add_argument("--workers", type=int, default=4, help="parallel band workers (default 4)")
    parser.add_argument(
        "--slice",
        type=int,
        default=500,
        dest="slice_size",
        help="prompts per subprocess slice (default 500)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/tmp/corpus-phoneme-sweep"),
        help="result directory",
    )
    parser.add_argument(
        "--update-known-list",
        action="store_true",
        help="rewrite the known-divergent allowlist from the verified mismatch set",
    )
    args = parser.parse_args(argv)

    if args.worker:
        _worker(args.worker[0], args.worker[1])
        return 0

    corpus = _load_corpus()
    n = len(corpus)
    if args.sample and args.sample < n:
        step = -(-n // args.sample)
        indices = list(range(0, n, step))
    else:
        indices = list(range(n))

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("results_w*.jsonl"):
        old.unlink()

    t0 = time.time()
    band = -(-len(indices) // args.workers)
    crash_victims: list[int] = []
    threads: list[threading.Thread] = []
    for wid in range(args.workers):
        chunk = indices[wid * band : (wid + 1) * band]
        if not chunk:
            continue
        t = threading.Thread(
            target=_run_band, args=(chunk, wid, out_dir, crash_victims, args.slice_size)
        )
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    rows: dict[int, dict[str, object]] = {}
    for path in out_dir.glob("results_w*.jsonl"):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                rows[row["i"]] = row

    # Verification pass: crash victims + raw mismatches get a fresh oracle.
    suspects = sorted(
        set(crash_victims)
        | {i for i in indices if i not in rows}
        | {i for i, r in rows.items() if "error" in r or "c" in r}
    )
    print(f"sweep pass done in {time.time() - t0:.0f}s; verifying {len(suspects)} suspects...")
    rows.update(_verify(suspects, out_dir))

    return _report(corpus, rows, out_dir, update_known_list=args.update_known_list)


def _report(
    corpus: tuple[str, ...],
    rows: dict[int, dict[str, object]],
    out_dir: Path,
    *,
    update_known_list: bool,
) -> int:
    """Print the pass-rate/class summary; optionally rewrite the allowlist."""
    n_pass = sum(1 for r in rows.values() if r.get("ok"))
    fails = {i: r for i, r in rows.items() if not r.get("ok")}
    classes = Counter(_classify(str(r.get("c", "")), str(r.get("py", ""))) for r in fails.values())
    total = len(rows)
    print(f"\ncorpus phoneme parity: {n_pass}/{total} pass ({100 * n_pass / total:.3f}%)")
    for cls, cnt in classes.most_common():
        print(f"  {cnt:6d}  {cls}")

    mismatch_texts = sorted({corpus[i] for i in fails})
    (out_dir / "mismatches.txt").write_text(
        "\n".join(mismatch_texts) + ("\n" if mismatch_texts else ""), encoding="utf-8"
    )
    print(f"mismatch prompts written to {out_dir / 'mismatches.txt'}")

    if update_known_list:
        old_set: set[str] = set()
        if _KNOWN_LIST.exists():
            old_set = {
                line
                for line in _KNOWN_LIST.read_text(encoding="utf-8").splitlines()
                if line and not line.startswith("#")
            }
        _KNOWN_LIST.write_text(
            _KNOWN_LIST_HEADER + "\n".join(mismatch_texts) + ("\n" if mismatch_texts else ""),
            encoding="utf-8",
        )
        new_set = set(mismatch_texts)
        print(
            f"known-divergent list updated: {len(old_set)} -> {len(new_set)} "
            f"(+{len(new_set - old_set)} added, -{len(old_set - new_set)} removed)"
        )

    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
