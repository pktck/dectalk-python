#!/usr/bin/env python3
r"""Cluster WAV-sweep divergences into scoped classes (issue #316).

Reads one or more ``scripts/corpus_wav_sweep.py`` result directories,
enriches every mismatching prompt with a **phoneme-stream comparison**
(pure-Python front end vs the patched C library), and buckets the
divergences:

- ``front-end/*`` — the phoneme streams already differ, so the WAV
  divergence originates in text processing / dictionary / LTS. Bucketed
  by the word-level diff signature (common prefix/suffix stripped).
- ``back-end-timing`` — phoneme streams byte-identical but the sample
  counts differ: PH orchestration / timing divergence.
- ``back-end-content`` — phoneme streams and sample counts identical,
  bytes differ: per-frame parameter divergence.
- ``render-error/*`` — one side failed to render (worker exception).
- ``phoneme-oracle-error`` — the C phoneme oracle crashed on the
  prompt (retryable; counted separately, not classified).

The C phoneme calls run in **sliced fresh subprocesses** (the patched
library segfaults after sustained in-process use — same design as
``scripts/corpus_phoneme_sweep.py``), with crash victims recorded and
skipped.

Usage::

    export DECTALK_SRC=/tmp/dectalk-oracle-src DECTALK_BIN=/tmp/dectalk-oracle-bin
    uv run python scripts/cluster_wav_divergences.py \\
        --sweep-dir /tmp/wav-sweep-dict-bare /tmp/wav-sweep-commands \\
        --out /tmp/discovery-census.md

Writes the census (markdown) to ``--out`` and an enriched JSONL
(``<out>.jsonl``) with one row per divergent prompt for downstream
issue-filing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

Row = dict[str, object]

# ---------------------------------------------------------------------------
# Worker mode: phoneme-compare a batch of texts in a fresh process.
# ---------------------------------------------------------------------------


def _worker(job_file: str, out_path: str) -> None:
    """Phoneme-compare every text in ``job_file`` (JSON list of strings).

    Appends ``{"t": text, "py": ..., "c": ...}`` JSONL rows to
    ``out_path`` with a ``DONE <i>`` marker per text so the driver can
    resume past a segfault victim.
    """
    import os  # noqa: PLC0415

    os.environ["DECTALK_DISABLE_CAPI"] = "1"
    os.environ["DECTALK_FULL_PIPELINE"] = "1"

    import dectalk  # noqa: PLC0415
    from dectalk._capi import CAPI  # noqa: PLC0415

    texts: list[str] = json.loads(Path(job_file).read_text(encoding="utf-8"))
    capi = CAPI()
    with open(out_path, "a", encoding="utf-8") as out:
        for i, text in enumerate(texts):
            row: dict[str, object] = {"t": text}
            try:
                row["c"] = capi.convert_to_phonemes(text).decode("latin-1")
            except Exception as exc:
                row["c_error"] = f"{type(exc).__name__}: {exc}"
            try:
                row["py"] = dectalk.text_to_dectalk_phonemes(text).decode("latin-1")
            except Exception as exc:
                row["py_error"] = f"{type(exc).__name__}: {exc}"
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(f"DONE {i}", flush=True)


def _phoneme_compare(
    texts: list[str], work_dir: Path, batch_size: int = 150
) -> dict[str, Row]:
    """{text: worker row} for every text, via sliced fresh subprocesses.

    A batch whose worker dies resumes one text past the victim; the
    victim gets a ``phoneme-oracle-error`` marker row.
    """
    out_path = work_dir / "phoneme_rows.jsonl"
    out_path.unlink(missing_ok=True)
    job_file = work_dir / "phoneme_job.json"
    pos = 0
    while pos < len(texts):
        batch = texts[pos : pos + batch_size]
        job_file.write_text(json.dumps(batch), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, __file__, "--worker", str(job_file), str(out_path)],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        last_done = -1
        for line in proc.stdout.splitlines():
            if line.startswith("DONE "):
                last_done = int(line.split()[1])
        if proc.returncode == 0 or last_done == len(batch) - 1:
            pos += len(batch)
            continue
        victim = batch[last_done + 1]
        with open(out_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": victim, "c_error": "oracle crash"}) + "\n")
        pos += last_done + 2
    rows: dict[str, Row] = {}
    with open(out_path, encoding="utf-8") as fh:
        for line in fh:
            row: Row = json.loads(line)
            rows[str(row["t"])] = row
    return rows


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _diff_signature(c_stream: str, py_stream: str, max_len: int = 60) -> str:
    """Word-level middle diff of the two phoneme streams."""
    c_toks = c_stream.split()
    py_toks = py_stream.split()
    pre = 0
    while pre < len(c_toks) and pre < len(py_toks) and c_toks[pre] == py_toks[pre]:
        pre += 1
    suf = 0
    while (
        suf < len(c_toks) - pre
        and suf < len(py_toks) - pre
        and c_toks[-1 - suf] == py_toks[-1 - suf]
    ):
        suf += 1
    c_mid = " ".join(c_toks[pre : len(c_toks) - suf]) or "(nothing)"
    py_mid = " ".join(py_toks[pre : len(py_toks) - suf]) or "(nothing)"
    sig = f"C[{c_mid}] vs Py[{py_mid}]"
    return sig if len(sig) <= max_len else sig[: max_len - 1] + "…"


def _text_features(text: str) -> str:
    """Coarse input-shape tag to aid manual grouping."""
    if "[:" in text:
        return "cmd"
    stripped = text.strip()
    if stripped and not any(ch.isalnum() for ch in stripped):
        return "punct-only"
    if any(ch.isdigit() for ch in stripped):
        return "digit"
    last = stripped.rstrip(".!?,;: ").rsplit(" ", 1)[-1].lower()
    for suf in ("ed", "ing", "est", "er", "s"):
        if last.endswith(suf):
            return f"suffix-{suf}"
    return "plain"


def _classify(row: Row, ph: Row | None) -> tuple[str, str]:
    """(bucket, detail) for one divergent sweep row."""
    if "error" in row:
        exc = str(row["error"]).split(":", 1)[0]
        return f"render-error/{exc}", str(row.get("error", ""))
    if ph is None or "c_error" in ph or "py_error" in ph:
        detail = "" if ph is None else str(ph.get("c_error") or ph.get("py_error"))
        return "phoneme-oracle-error", detail
    if ph["c"] != ph["py"]:
        return "front-end", _diff_signature(str(ph["c"]), str(ph["py"]))
    delta = row.get("delta_samples")
    if delta == 0:
        return "back-end-content", f"first_div_sample={row.get('first_div_sample')}"
    return "back-end-timing", f"delta_samples={delta}"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _load_fail_rows(
    sweep_dirs: list[Path],
) -> tuple[dict[str, Row], dict[str, list[str]], int]:
    """(text -> row, text -> [set labels], total swept) over all dirs."""
    fails: dict[str, Row] = {}
    origin: dict[str, list[str]] = defaultdict(list)
    total = 0
    for d in sweep_dirs:
        for path in sorted(d.glob("results_w*.jsonl")):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row: Row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    total += 1
                    if row.get("ok"):
                        continue
                    text = str(row.get("text", f"#index-{row.get('i')}"))
                    fails.setdefault(text, row)
                    if d.name not in origin[text]:
                        origin[text].append(d.name)
    return fails, origin, total


def main(argv: list[str] | None = None) -> int:
    """Drive the census (or run one phoneme worker with ``--worker``)."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--worker", nargs=2, metavar=("JOB", "OUT"), help=argparse.SUPPRESS)
    parser.add_argument(
        "--sweep-dir",
        type=Path,
        nargs="+",
        default=None,
        help="one or more corpus_wav_sweep.py --out-dir directories",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("/tmp/discovery-census.md"),
        help="markdown census output (enriched rows land in <out>.jsonl)",
    )
    parser.add_argument(
        "--reps", type=int, default=8, help="representatives shown per cluster (default 8)"
    )
    args = parser.parse_args(argv)

    if args.worker:
        _worker(args.worker[0], args.worker[1])
        return 0
    if not args.sweep_dir:
        parser.error("--sweep-dir is required outside --worker mode")

    fails, origin, total = _load_fail_rows(args.sweep_dir)
    print(f"{total} sweep rows, {len(fails)} unique divergent prompts")

    needs_phonemes = sorted(t for t, r in fails.items() if "error" not in r)
    work_dir = args.out.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    ph_rows = _phoneme_compare(needs_phonemes, work_dir) if needs_phonemes else {}

    clusters: dict[tuple[str, str], list[str]] = defaultdict(list)
    enriched: list[Row] = []
    for text, row in sorted(fails.items()):
        bucket, detail = _classify(row, ph_rows.get(text))
        key_detail = detail if bucket == "front-end" else ""
        clusters[(bucket, key_detail)].append(text)
        enriched.append(
            {
                "text": text,
                "sets": origin[text],
                "bucket": bucket,
                "detail": detail,
                "feature": _text_features(text),
                **{k: v for k, v in row.items() if k not in ("i", "text")},
                **{
                    k: v
                    for k, v in (ph_rows.get(text) or {}).items()
                    if k in ("c", "py", "c_error", "py_error")
                },
            }
        )

    jsonl_path = args.out.with_suffix(args.out.suffix + ".jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for row in enriched:
            fh.write(json.dumps(row) + "\n")

    lines = [
        "# WAV divergence census",
        "",
        f"Sweep dirs: {', '.join(d.name for d in args.sweep_dir)}",
        f"Rows swept: {total}; unique divergent prompts: {len(fails)}",
        "",
        "| bucket | signature | count | representatives |",
        "|---|---|---:|---|",
    ]
    by_size = sorted(clusters.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for (bucket, detail), texts in by_size:
        reps = "; ".join(f"`{t}`" for t in texts[: args.reps])
        sig = detail.replace("|", "\\|") or "-"
        lines.append(f"| {bucket} | {sig} | {len(texts)} | {reps} |")
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"census written to {args.out} (+ {jsonl_path.name})")

    bucket_totals: dict[str, int] = defaultdict(int)
    for (bucket, _), texts in clusters.items():
        bucket_totals[bucket] += len(texts)
    for bucket, count in sorted(bucket_totals.items(), key=lambda kv: -kv[1]):
        print(f"  {count:6d}  {bucket}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
