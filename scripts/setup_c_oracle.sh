#!/usr/bin/env bash
#
# Set up the DECtalk C-oracle environment for tests that need it.
#
# Idempotent: clones the source if missing, applies our patches, builds the
# US English shared library + sample binary, and assembles a stable-binary
# reference directory laid out exactly like the shipped DECtalk release.
#
# Fast path: if a prebuilt oracle release matching the current source/patch
# hash exists on GitHub Releases, fetch + untar it (~5 s) instead of building.
# The release is produced by .github/workflows/build-c-oracle.yml whenever
# scripts/setup_c_oracle.sh, scripts/apply_c_patches.py, or
# tests/parity/c_patches/** change. See docs/PLAN-CI-STRATEGY.md §2.
#
# After running this, the tests can be invoked with:
#     DECTALK_SRC=/tmp/dectalk-src \
#     DECTALK_BIN=/tmp/dectalk-binary-stable \
#     uv run pytest
#
# This script is what GitHub Actions runs to enable the parity tests; local
# devs and parallel agents can use it too. Agents that need /tmp isolation
# should `eval "$(scripts/agent_oracle_env.sh)"` to get unique DECTALK_SRC /
# DECTALK_BIN paths before invoking this script.

set -euo pipefail

DECTALK_SRC="${DECTALK_SRC:-/tmp/dectalk-src}"
DECTALK_BIN="${DECTALK_BIN:-/tmp/dectalk-binary-stable}"
DECTALK_REPO="${DECTALK_REPO:-https://github.com/dectalk/dectalk.git}"
# Pinned SHA on dectalk/dectalk@develop as of 2026-05-15. Bump deliberately
# and run `gh workflow run build-c-oracle.yml` to republish the release
# tarball under the new hash.
DECTALK_REF="${DECTALK_REF:-32efa30ef2e216b3ad091c41abf5b502498a19aa}"
ORACLE_RELEASE_REPO="${ORACLE_RELEASE_REPO:-pktck/dectalk-python}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '\n=== %s ===\n' "$*"
}

# --- 0. Compute a deterministic content hash for the oracle ---------------
# Inputs: the pinned upstream SHA, every patch under tests/parity/c_patches,
# and this script + apply_c_patches.py themselves. Used as the release tag.
oracle_hash() {
  {
    printf '%s\n' "${DECTALK_REF}"
    find "${REPO_ROOT}/tests/parity/c_patches" -name '*.patch' \
      -exec sha256sum {} \; | sort
    sha256sum \
      "${REPO_ROOT}/scripts/setup_c_oracle.sh" \
      "${REPO_ROOT}/scripts/apply_c_patches.py"
  } | sha256sum | cut -c1-16
}

# --- 1. Fast path: fetch the prebuilt oracle tarball from GitHub Releases -

ORACLE_TAG="c-oracle-$(oracle_hash)"
ORACLE_URL="https://github.com/${ORACLE_RELEASE_REPO}/releases/download/${ORACLE_TAG}/c-oracle.tar.zst"

# Skip the fetch path entirely if either output is already populated (idempotent).
if [[ -d "${DECTALK_BIN}" && -x "${DECTALK_BIN}/say" && -d "${DECTALK_SRC}/.git" ]]; then
  log "C oracle already populated; skipping fetch + build"
  echo "  DECTALK_SRC=${DECTALK_SRC}"
  echo "  DECTALK_BIN=${DECTALK_BIN}"
  exit 0
fi

if command -v curl >/dev/null 2>&1 && command -v zstd >/dev/null 2>&1; then
  tarball="$(mktemp -u /tmp/c-oracle.XXXXXX.tar.zst)"
  if curl -fsSL "${ORACLE_URL}" -o "${tarball}" 2>/dev/null; then
    log "Restoring prebuilt C oracle from release ${ORACLE_TAG}"
    rm -rf "${DECTALK_SRC}" "${DECTALK_BIN}"
    mkdir -p "$(dirname "${DECTALK_SRC}")" "$(dirname "${DECTALK_BIN}")"
    # Tarball layout: dectalk-src/ and dectalk-binary-stable/ as siblings at
    # archive root. We extract to a tempdir and move into place so callers
    # can use non-default DECTALK_SRC / DECTALK_BIN paths.
    extract_dir="$(mktemp -d /tmp/c-oracle-extract.XXXXXX)"
    tar --use-compress-program=unzstd -xf "${tarball}" -C "${extract_dir}"
    mv "${extract_dir}/dectalk-src" "${DECTALK_SRC}"
    mv "${extract_dir}/dectalk-binary-stable" "${DECTALK_BIN}"
    rm -rf "${tarball}" "${extract_dir}"
    log "C oracle restored from prebuilt tarball"
    echo "  DECTALK_SRC=${DECTALK_SRC}"
    echo "  DECTALK_BIN=${DECTALK_BIN}"
    exit 0
  fi
  rm -f "${tarball}"
  log "Prebuilt release ${ORACLE_TAG} not available — falling back to source build"
else
  log "curl or zstd not installed; using source-build path"
fi

# --- 2. Clone the DECtalk C source (SHA-pinned shallow fetch) ------------

if [[ ! -d "${DECTALK_SRC}/.git" ]]; then
  log "Cloning ${DECTALK_REPO} @ ${DECTALK_REF} into ${DECTALK_SRC}"
  mkdir -p "${DECTALK_SRC}"
  git -C "${DECTALK_SRC}" init -q
  git -C "${DECTALK_SRC}" remote add origin "${DECTALK_REPO}"
  git -C "${DECTALK_SRC}" fetch --depth 1 origin "${DECTALK_REF}"
  git -C "${DECTALK_SRC}" checkout -q "${DECTALK_REF}"
else
  log "Source tree already present at ${DECTALK_SRC} (skipping clone)"
fi

# --- 3. Apply our C-source patches and build -----------------------------
# apply_c_patches.py iterates every `.patch` file under
# tests/parity/c_patches/ in sorted order.

log "Applying C-source patches and building libtts_us.so + samples"
uv run python "${REPO_ROOT}/scripts/apply_c_patches.py" --src-root "${DECTALK_SRC}"

# --- 4. Locate the build artefacts (path includes uname -r) --------------

LIBTTS_US_DIR=$(find "${DECTALK_SRC}/src/dapi/build/dectalk" -name "libtts_us.so" -printf "%h\n" | head -n1)
LIBTTS_DIR=$(find "${DECTALK_SRC}/src/dtalkml/build" -name "libtts.so" -printf "%h\n" | head -n1)
SAY_PATH=$(find "${DECTALK_SRC}/src/samplosf/build/dtsamples" -name "say" -type f -executable | head -n1)
DIC_PATH=$(find "${DECTALK_SRC}/src/dapi/build/dic" -name "dtalk_us.dic" | head -n1)

if [[ -z "${LIBTTS_US_DIR}" || -z "${LIBTTS_DIR}" || -z "${SAY_PATH}" || -z "${DIC_PATH}" ]]; then
  echo "ERROR: missing build artefacts:" >&2
  echo "  libtts_us dir: ${LIBTTS_US_DIR:-MISSING}" >&2
  echo "  libtts dir:    ${LIBTTS_DIR:-MISSING}" >&2
  echo "  say binary:    ${SAY_PATH:-MISSING}" >&2
  echo "  dtalk_us.dic:  ${DIC_PATH:-MISSING}" >&2
  exit 1
fi

# --- 5. Assemble the stable-binary reference directory -------------------
# Layout mirrors the shipped DECtalk release so the `say` binary can find
# its libraries (RUNPATH=$ORIGIN/lib/) and dictionaries (configured by
# DECtalk.conf using relative paths).

log "Assembling stable-binary fixture at ${DECTALK_BIN}"
rm -rf "${DECTALK_BIN}"
mkdir -p "${DECTALK_BIN}/lib" "${DECTALK_BIN}/dic"

cp "${SAY_PATH}" "${DECTALK_BIN}/say"
cp "${LIBTTS_DIR}/libtts.so" "${DECTALK_BIN}/lib/libtts.so"
cp "${LIBTTS_US_DIR}/libtts_us.so" "${DECTALK_BIN}/lib/libtts_us.so"
cp "${DIC_PATH}" "${DECTALK_BIN}/dic/dtalk_us.dic"

# Minimal DECtalk.conf: just enough for the runtime to find the US dictionary.
cat > "${DECTALK_BIN}/DECtalk.conf" <<'EOF'
US_dict:dic/dtalk_us.dic
US_udict:udict_us.dic
Default_lang:us
LANG:us,US English
EOF

# --- 6. Sanity check -----------------------------------------------------

log "Verifying the assembled fixture"
cd "${DECTALK_BIN}"
./say -a "hello world" -fo /tmp/oracle-smoke.wav
test -s /tmp/oracle-smoke.wav
echo "  say -a 'hello world' produced $(stat -c%s /tmp/oracle-smoke.wav) bytes — OK"
rm -f /tmp/oracle-smoke.wav

log "C oracle ready (tag ${ORACLE_TAG})"
echo "  DECTALK_SRC=${DECTALK_SRC}"
echo "  DECTALK_BIN=${DECTALK_BIN}"
