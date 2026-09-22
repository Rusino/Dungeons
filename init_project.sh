#!/usr/bin/env bash
# ==============================================================================
# Project KEEPER: Automated Project Bootstrapper
# ==============================================================================
# Equips a new or existing repository with Project KEEPER operational rules,
# subagent prompt templates, and domain invariants.
#
# Usage:
#   ./init_project.sh <target_dir> [--domain text] [--link]
#
# Options:
#   --domain text    Copies the Universal Text Domain Codex as INVARIANTS.md
#   --link           Symlinks AGENTS.md and prompts instead of copying
#   --help           Show this message
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_DIR="${SCRIPT_DIR}/codex"

usage() {
    echo "Usage: $0 <target_directory> [--domain text] [--link]"
    echo ""
    echo "Options:"
    echo "  --domain text    Deploy Tier-2 Universal Text Domain Codex to <target>/INVARIANTS.md"
    echo "  --link           Symlink AGENTS.md and prompts to Dungeons (auto-updating)"
    echo "  --help           Show this help message"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

TARGET_DIR=""
DOMAIN=""
USE_LINK=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --link)
            USE_LINK=true
            shift
            ;;
        --help)
            usage
            ;;
        *)
            if [ -z "${TARGET_DIR}" ]; then
                TARGET_DIR="$1"
                shift
            else
                echo "Error: Unexpected argument: $1"
                usage
            fi
            ;;
    esac
done

if [ -z "${TARGET_DIR}" ]; then
    echo "Error: Target directory is required."
    usage
fi

if [ ! -d "${TARGET_DIR}" ]; then
    echo "==> Target directory does not exist. Creating: ${TARGET_DIR}..."
    mkdir -p "${TARGET_DIR}"
fi

TARGET_DIR="$(cd "${TARGET_DIR}" && pwd)"

echo "=================================================================="
echo "🛡️  Bootstrapping Project KEEPER in: ${TARGET_DIR}"
echo "=================================================================="

# 1. Deploy Master Constitution (Tier 1)
if [ "${USE_LINK}" = true ]; then
    echo "==> Symlinking Master Constitution (codex/AGENTS.md -> AGENTS.md)..."
    ln -sf "${CODEX_DIR}/AGENTS.md" "${TARGET_DIR}/AGENTS.md"
else
    echo "==> Copying Master Constitution (codex/AGENTS.md -> AGENTS.md)..."
    cp "${CODEX_DIR}/AGENTS.md" "${TARGET_DIR}/AGENTS.md"
fi

# 2. Deploy Subagent System Prompts
PROMPTS_DEST="${TARGET_DIR}/.antigravity/prompts"
mkdir -p "${PROMPTS_DEST}"

if [ "${USE_LINK}" = true ]; then
    echo "==> Symlinking subagent prompts (.antigravity/prompts/*)..."
    for prompt_file in "${CODEX_DIR}/prompts/"*.md; do
        filename="$(basename "${prompt_file}")"
        ln -sf "${prompt_file}" "${PROMPTS_DEST}/${filename}"
    done
else
    echo "==> Copying subagent prompts (.antigravity/prompts/*)..."
    cp -r "${CODEX_DIR}/prompts/"*.md "${PROMPTS_DEST}/"
fi

# 3. Deploy Domain Invariants (Tier 2, always a copy)
if [ "${DOMAIN}" = "text" ]; then
    INVARIANTS_DEST="${TARGET_DIR}/INVARIANTS.md"
    if [ -f "${INVARIANTS_DEST}" ]; then
        echo "==> [NOTICE] Existing INVARIANTS.md detected. Preserving existing local invariants."
    else
        echo "==> Deploying Tier-2 Universal Text Domain Codex (-> INVARIANTS.md)..."
        cp "${CODEX_DIR}/TEXT_DOMAIN.md" "${INVARIANTS_DEST}"
    fi
fi

# 4. Generate Local Build Configuration Template if missing
CONFIG_FILE="${TARGET_DIR}/KEEPER_CONFIG.md"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "==> Generating KEEPER_CONFIG.md template..."
    cat << 'EOF' > "${CONFIG_FILE}"
# Project KEEPER: Local Harness Configuration

Please fill in the project-specific execution commands so AI subagents can build and test deterministically:

- **Build Command**: `ninja -C out/Debug <target>` # Or: cargo check, cmake --build, bazel build
- **Unit Test Command**: `out/Debug/<test_binary> --match <Suite>` # Or: ctest, cargo test, bazel test
- **Incremental Build Timeout**: `60s`
- **Fast Unit Test Timeout**: `10s`
- **Sanitizer Matrix**:
  - ASan+UBSan Command: `out/ASan/<test_binary>`
  - TSan Command: `out/TSan/<test_binary>`
  - MSan Command: `out/MSan/<test_binary>`

See `docs/BUILD_ADAPTERS.md` in Dungeons for examples on wiring GN/Ninja, CMake, Cargo, and Bazel.
EOF
fi

echo "=================================================================="
echo "✅ Project KEEPER successfully bootstrapped in: ${TARGET_DIR}"
echo "   - Tier 1 Constitution: ${TARGET_DIR}/AGENTS.md"
echo "   - Subagent Prompts:    ${PROMPTS_DEST}/"
if [ -n "${DOMAIN}" ]; then
echo "   - Tier 2 Domain Codex: ${TARGET_DIR}/INVARIANTS.md"
fi
echo "   - Local Config:        ${CONFIG_FILE}"
echo "=================================================================="
