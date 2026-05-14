#!/usr/bin/env bash
#
# Set up the DECtalk C-oracle environment for tests that need it.
#
# Idempotent: clones the source if missing, applies our patches, builds the
# US English shared library + sample binary, and assembles a stable-binary
# reference directory laid out exactly like the shipped DECtalk release.
#
# After running this, the tests can be invoked with:
#     DECTALK_SRC=/tmp/dectalk-src \
#     DECTALK_BIN=/tmp/dectalk-binary-stable \
#     uv run pytest
#
# This script is what GitHub Actions runs to enable the parity tests; local
# devs can use it too instead of building by hand.

set -euo pipefail

DECTALK_SRC="${DECTALK_SRC:-/tmp/dectalk-src}"
DECTALK_BIN="${DECTALK_BIN:-/tmp/dectalk-binary-stable}"
DECTALK_REPO="${DECTALK_REPO:-https://github.com/dectalk/dectalk.git}"
DECTALK_BRANCH="${DECTALK_BRANCH:-develop}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() {
  printf '\n=== %s ===\n' "$*"
}

# --- 1. Clone the DECtalk C source -----------------------------------------

if [[ ! -d "${DECTALK_SRC}/.git" ]]; then
  log "Cloning ${DECTALK_REPO} @ ${DECTALK_BRANCH} into ${DECTALK_SRC}"
  git clone --depth 1 --branch "${DECTALK_BRANCH}" "${DECTALK_REPO}" "${DECTALK_SRC}"
else
  log "Source tree already present at ${DECTALK_SRC} (skipping clone)"
fi

# --- 2. Apply our C-source patches and build -------------------------------
# apply_c_patches.py iterates every `.patch` file under
# tests/parity/c_patches/ in sorted order. Currently:
#   0001-expose-convert-to-phonemes-on-linux.patch
#   0002-stage-boundary-dumps.patch   (kernel stage; cmd/lts/ph/vtm TODO)

log "Applying C-source patches and building libtts_us.so + samples"
uv run python "${REPO_ROOT}/scripts/apply_c_patches.py" --src-root "${DECTALK_SRC}"

# --- 3. Locate the build artefacts (path includes uname -r) ----------------

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

# --- 4. Assemble the stable-binary reference directory --------------------
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

# --- 5. Sanity check ------------------------------------------------------

log "Verifying the assembled fixture"
cd "${DECTALK_BIN}"
./say -a "hello world" -fo /tmp/oracle-smoke.wav
test -s /tmp/oracle-smoke.wav
echo "  say -a 'hello world' produced $(stat -c%s /tmp/oracle-smoke.wav) bytes — OK"
rm -f /tmp/oracle-smoke.wav

log "C oracle ready"
echo "  DECTALK_SRC=${DECTALK_SRC}"
echo "  DECTALK_BIN=${DECTALK_BIN}"
