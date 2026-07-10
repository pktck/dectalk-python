#!/usr/bin/env python3
"""Full-corpus WAV bit-parity sweep: pure-Python pipeline vs the C binary.

Byte-compares ``dectalk.to_wav`` (under ``DECTALK_DISABLE_CAPI=1`` +
FULL+VTM1 — the byte-exact-capable pure-Python path) against the
shipped ``say`` binary for every prompt in ``tests/parity/_corpus.py``
(~133K prompts). This is the collect-all companion to the goalpost test
``tests/parity/test_binary_wav_parity.py``, whose stop-hook fail-fast
gate halts on the FIRST mismatch: one sweep run enumerates the WHOLE
residual tail so the burn-down can be batched by divergence cluster
(issue #311).

Design mirrors ``scripts/corpus_phoneme_sweep.py``: the corpus is
walked in slices, each slice in a **fresh subprocess**, with
crash-victim resume. The Python side here never touches the in-process
C library (the segfault driver behind the phoneme sweep's design), but
the same shape buys parallelism, isolation from any pipeline crash or
runaway render, and a resumable walk for free. The C side is one
``say`` subprocess per prompt (byte-exact reference by definition).

Usage::

    export DECTALK_SRC=/tmp/dectalk-oracle-src DECTALK_BIN=/tmp/dectalk-oracle-bin
    uv run python scripts/corpus_wav_sweep.py                 # full sweep
    uv run python scripts/corpus_wav_sweep.py --sample 2000   # strided subsample
    uv run python scripts/corpus_wav_sweep.py --from-list /tmp/residuals.txt

``--from-list FILE`` re-sweeps only the prompts listed in FILE (one per
line) — the post-fix re-verification loop. Mismatch rows land in
``<out-dir>/mismatches.txt`` (prompt text) and the per-prompt JSONL
rows (sample counts, first divergent sample) in
``<out-dir>/results_w*.jsonl`` for clustering.

Runtime: ~2 h for the full corpus with the default 4 workers (~5
prompts/s/worker; the pure-Python render dominates at ~200 ms).
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import threading
import time
import wave
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


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
    per prompt so the driver can locate the victim if this process dies.

    The parity env (``DECTALK_DISABLE_CAPI=1`` + FULL+VTM1) is set
    before ``import dectalk`` — the PARITY-METHOD §4 capture rule.
    """
    import os  # noqa: PLC0415

    os.environ["DECTALK_DISABLE_CAPI"] = "1"
    os.environ["DECTALK_FULL_PIPELINE"] = "1"
    os.environ["DECTALK_USE_VTM1"] = "1"

    import tempfile  # noqa: PLC0415

    import dectalk  # noqa: PLC0415

    bin_root = Path(os.environ.get("DECTALK_BIN", "/tmp/dectalk-binary-stable"))
    say = bin_root / "say"

    indices = [int(line) for line in Path(idx_file).read_text(encoding="utf-8").split()]
    corpus = _load_corpus()
    with open(out_path, "a", encoding="utf-8") as out:
        for i in indices:
            text = corpus[i]
            row: dict[str, object]
            try:
                with tempfile.TemporaryDirectory(prefix="wav-sweep-") as td:
                    py_path = Path(td) / "py.wav"
                    bin_path = Path(td) / "bin.wav"
                    dectalk.to_wav(text, py_path)
                    subprocess.run(
                        [str(say), "-a", text, "-fo", str(bin_path)],
                        cwd=str(bin_root),
                        check=True,
                        capture_output=True,
                        timeout=60,
                    )
                    py_b = py_path.read_bytes()
                    bin_b = bin_path.read_bytes()
                if py_b == bin_b:
                    row = {"i": i, "ok": 1}
                else:
                    row = {"i": i, "text": text, **_mismatch_stats(py_b, bin_b)}
            except Exception as exc:  # worker must survive any prompt
                row = {"i": i, "text": text, "error": f"{type(exc).__name__}: {exc}"}
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(f"DONE {i}", flush=True)


def _mismatch_stats(py_b: bytes, bin_b: bytes) -> dict[str, object]:
    """Sample counts + first divergent sample index for a mismatch row."""
    stats: dict[str, object] = {"py_bytes": len(py_b), "c_bytes": len(bin_b)}
    try:
        with wave.open(io.BytesIO(py_b)) as fh:
            py_pcm = fh.readframes(fh.getnframes())
        with wave.open(io.BytesIO(bin_b)) as fh:
            c_pcm = fh.readframes(fh.getnframes())
    except Exception:  # header-mangled output still wants a row
        stats["wav_parse"] = "failed"
        return stats
    n_py, n_c = len(py_pcm) // 2, len(c_pcm) // 2
    stats["py_samples"] = n_py
    stats["c_samples"] = n_c
    stats["delta_samples"] = n_py - n_c
    n = min(len(py_pcm), len(c_pcm))
    first = next(
        (k for k in range(0, n, 2) if py_pcm[k : k + 2] != c_pcm[k : k + 2]),
        None,
    )
    stats["first_div_sample"] = first // 2 if first is not None else min(n_py, n_c)
    return stats


# --------------------------------------------------------------------------
# Driver mode: banded, sliced, crash-resuming walk (corpus_phoneme_sweep.py).
# --------------------------------------------------------------------------


def _run_batch(indices: list[int], idx_file: Path, out_path: str) -> tuple[int, int]:
    """Run one worker subprocess over ``indices``; return (rc, last_done_pos)."""
    idx_file.write_text("\n".join(map(str, indices)) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, __file__, "--worker", str(idx_file), out_path],
        capture_output=True,
        text=True,
        timeout=3600,
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
            pos += len(batch)
            continue
        crash_victims.append(batch[last_done_pos + 1])
        pos += last_done_pos + 2  # resume one prompt past the victim
    idx_file.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:  # noqa: PLR0912 — sweep-driver arg dispatch
    """Drive the sweep (or run one worker slice with ``--worker``)."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--worker", nargs=2, metavar=("IDX_FILE", "OUT"), help=argparse.SUPPRESS)
    parser.add_argument(
        "--sample", type=int, default=0, help="strided subsample size (0 = full corpus)"
    )
    parser.add_argument(
        "--from-list",
        type=Path,
        default=None,
        help="sweep only the prompts listed in this file (one per line)",
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
        default=Path("/tmp/corpus-wav-sweep"),
        help="result directory",
    )
    args = parser.parse_args(argv)

    if args.worker:
        _worker(args.worker[0], args.worker[1])
        return 0

    corpus = _load_corpus()
    n = len(corpus)
    if args.from_list is not None:
        wanted = {
            line
            for line in args.from_list.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")
        }
        indices = [i for i, text in enumerate(corpus) if text in wanted]
        missing = wanted - {corpus[i] for i in indices}
        if missing:
            print(f"WARNING: {len(missing)} prompts from --from-list not in corpus")
    elif args.sample and args.sample < n:
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

    for idx in crash_victims:
        rows.setdefault(idx, {"i": idx, "text": corpus[idx], "error": "worker crash"})
    for idx in indices:
        rows.setdefault(idx, {"i": idx, "text": corpus[idx], "error": "no result"})

    print(f"sweep done in {time.time() - t0:.0f}s")
    return _report(corpus, rows, out_dir)


def _report(
    corpus: tuple[str, ...],
    rows: dict[int, dict[str, object]],
    out_dir: Path,
) -> int:
    """Print the pass-rate summary; write the mismatch prompt list."""
    n_pass = sum(1 for r in rows.values() if r.get("ok"))
    fails = {i: r for i, r in rows.items() if not r.get("ok")}
    total = len(rows)
    print(f"\ncorpus WAV parity: {n_pass}/{total} byte-exact ({100 * n_pass / max(total, 1):.3f}%)")

    classes: Counter[str] = Counter()
    for r in fails.values():
        if "error" in r:
            classes["error"] += 1
        elif r.get("delta_samples", None) == 0:
            classes["same-count-content-diff"] += 1
        else:
            classes["sample-count-diff"] += 1
    for cls, cnt in classes.most_common():
        print(f"  {cnt:6d}  {cls}")

    mismatch_texts = sorted({str(r.get("text", corpus[i])) for i, r in fails.items()})
    (out_dir / "mismatches.txt").write_text(
        "\n".join(mismatch_texts) + ("\n" if mismatch_texts else ""), encoding="utf-8"
    )
    print(f"mismatch prompts written to {out_dir / 'mismatches.txt'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
