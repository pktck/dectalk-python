#!/usr/bin/env bash
#
# Run the full local quality gate: ruff lint + format, pyright, pytest, shellcheck.
# Intended for pre-push verification. Mirrors the CI matrix but runs once on the
# host's Python.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_ROOT

run_step() {
  # Print a banner and run a command, exiting on first failure.
  local step_name="$1"
  shift
  printf '\n=== %s ===\n' "${step_name}"
  "$@"
}

main() {
  cd "${REPO_ROOT}"

  run_step "ruff lint" uv run ruff check .
  run_step "ruff format check" uv run ruff format --check .
  run_step "pyright strict" uv run pyright
  run_step "pytest" uv run pytest -v

  if command -v shellcheck >/dev/null 2>&1; then
    if compgen -G "scripts/*.sh" >/dev/null; then
      run_step "shellcheck" shellcheck scripts/*.sh
    fi
  else
    printf '\nshellcheck not installed locally; skipping. Install via your package manager.\n'
  fi

  printf '\nAll checks passed.\n'
}

main "$@"
