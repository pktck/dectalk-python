#!/usr/bin/env bash
#
# Run the local quality gate: ruff lint + format, pyright, pytest, shellcheck.
# Intended for pre-push verification.
#
# Modes:
#   (no args)   Full check: ruff, ruff format, pyright (all), pytest (all).
#   --changed   Fast check: ruff + pyright on files changed vs origin/dev
#               (falls back to HEAD~1), pytest with -n auto excluding c_oracle.
#   --smoke     Tightest loop: ruff + last-failed pytest only. <5s when green.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_ROOT

run_step() {
  local step_name="$1"
  shift
  printf '\n=== %s ===\n' "${step_name}"
  "$@"
}

run_shellcheck() {
  if command -v shellcheck >/dev/null 2>&1; then
    if compgen -G "scripts/*.sh" >/dev/null; then
      run_step "shellcheck" shellcheck scripts/*.sh
    fi
  else
    printf '\nshellcheck not installed locally; skipping.\n'
  fi
}

changed_python_files() {
  local base
  base="$(git merge-base HEAD origin/dev 2>/dev/null || echo HEAD~1)"
  git diff --name-only "${base}"...HEAD -- '*.py' 2>/dev/null || true
}

main_full() {
  cd "${REPO_ROOT}"
  run_step "ruff lint" uv run ruff check .
  run_step "ruff format check" uv run ruff format --check .
  run_step "pyright strict" uv run pyright
  run_step "pytest" uv run pytest -n auto
  run_shellcheck
  printf '\nAll checks passed.\n'
}

main_changed() {
  cd "${REPO_ROOT}"
  local files
  files="$(changed_python_files)"
  if [[ -n "${files}" ]]; then
    # shellcheck disable=SC2086  # intentional word splitting on filenames
    run_step "ruff (changed)" uv run ruff check ${files}
    # shellcheck disable=SC2086
    run_step "pyright (changed)" uv run pyright ${files}
  else
    printf '\nNo changed .py files vs origin/dev (or HEAD~1).\n'
  fi
  run_step "pytest" uv run pytest -n auto -m "not c_oracle and not slow"
  run_shellcheck
  printf '\nChanged-file checks passed.\n'
}

main_smoke() {
  cd "${REPO_ROOT}"
  run_step "ruff" uv run ruff check .
  run_step "pytest --lf" uv run pytest -n auto -m "not c_oracle and not slow" --lf --last-failed-no-failures=all
  printf '\nSmoke checks passed.\n'
}

case "${1:-}" in
  --changed) main_changed ;;
  --smoke)   main_smoke ;;
  -h|--help)
    cat <<'EOF'
Usage: scripts/dev_check.sh [--changed | --smoke]

  (no args)   Full quality gate (ruff + pyright + pytest + shellcheck).
  --changed   Only ruff+pyright on changed .py files; pytest excluding c_oracle.
  --smoke     Ruff + last-failed pytest (tight inner-loop).
EOF
    ;;
  *) main_full ;;
esac
