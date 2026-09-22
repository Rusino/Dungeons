#!/usr/bin/env bash
# ==============================================================================
# Project KEEPER: Automated Project Bootstrapper
# ==============================================================================
# Equips a new or existing repository with Project KEEPER operational rules,
# subagent prompt templates, and domain invariants.
#
# Defaults:
#   - Target Directory: . (current working directory if omitted)
#   - Linking:          --link (symlinks AGENTS.md and prompts for live updates)
#   - Domain Codex:     --domain text (deploys Universal Text Domain as INVARIANTS.md)
#
# Can be run from ANY directory:
#   cd ~/Sources/my-project && ~/Sources/Dungeons/init_keeper.sh
# ==============================================================================

set -euo pipefail

# Deterministically resolve the directory where this script and codex reside
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEX_DIR="${SCRIPT_DIR}/codex"

usage() {
    cat << EOF
==============================================================================
Project KEEPER Bootstrapper (init_keeper.sh)
==============================================================================

Equips any target repository or subsystem with Project KEEPER's Master Constitution,
subagent system prompts, domain invariants, and local harness configuration.

USAGE:
  $0 [target_directory] [options]

ARGUMENTS:
  target_directory    Path to the project or subsystem to equip.
                      Can be a standalone repository root OR a subsystem/folder
                      inside a larger monorepo (e.g. ~/Sources/skia/tools/text_editor).
                      Defaults to "." (current working directory) if omitted.

OPTIONS:
  --link              (DEFAULT) Create symbolic links to Dungeons for AGENTS.md
                      and .antigravity/prompts/. Any updates pushed to Dungeons
                      propagate automatically to this project.
  --copy              Copy AGENTS.md and prompts instead of symlinking (useful
                      if sharing the project with external collaborators).
  --domain <name>     Deploy a Tier-2 domain codex to <target>/INVARIANTS.md.
                      Options: 'text' (default), 'none'.
                      Note: INVARIANTS.md is ALWAYS copied (never linked) so it
                      can evolve locally and be committed to project history.
  --no-domain         Skip creating INVARIANTS.md.
  --help              Display this detailed help screen.

WHERE CAN THIS SCRIPT BE RUN FROM?
  You can run this script from ANY folder on your machine.
  It uses BASH_SOURCE to deterministically locate the Dungeons codex directory,
  regardless of your current working directory.

MONOREPO & SUBSYSTEM ISOLATION:
  When working in a large monorepo (e.g. Chromium, Skia, Android), you should NOT
  pollute the monorepo root with KEEPER files. Pass the specific subsystem path
  as target_directory. Antigravity discovers rules hierarchically, so placing
  AGENTS.md and .antigravity/prompts inside the subsystem activates KEEPER strictly
  when working on that tool, leaving the monorepo root completely untouched.

EXAMPLES:
  1. Bootstrap the project/directory you are currently in:
     cd ~/Sources/my-text-editor
     ~/Sources/Dungeons/init_keeper.sh

  2. Bootstrap a specific subsystem inside a monorepo (Client Zero pattern):
     ~/Sources/Dungeons/init_keeper.sh ~/Sources/skia/tools/text_editor

  3. Bootstrap a non-text project (e.g. database/compiler) with no text invariants:
     ~/Sources/Dungeons/init_keeper.sh ~/Sources/my-db --no-domain

  4. Bootstrap a standalone project with full standalone copies (no symlinks):
     ~/Sources/Dungeons/init_keeper.sh ~/Sources/my-project --copy

==============================================================================
EOF
    exit 0
}

TARGET_DIR=""
DOMAIN="text"
USE_LINK=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --domain)
            if [[ $# -lt 2 || "$2" =~ ^-- ]]; then
                echo "Error: --domain requires a value (e.g. --domain text or --domain none)."
                exit 1
            fi
            DOMAIN="$2"
            shift 2
            ;;
        --no-domain)
            DOMAIN="none"
            shift
            ;;
        --link)
            USE_LINK=true
            shift
            ;;
        --copy|--no-link)
            USE_LINK=false
            shift
            ;;
        --help|-h)
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

# Default to current working directory if target is not specified
if [ -z "${TARGET_DIR}" ]; then
    TARGET_DIR="."
fi

if [ ! -d "${TARGET_DIR}" ]; then
    echo "==> Target directory does not exist. Creating: ${TARGET_DIR}..."
    mkdir -p "${TARGET_DIR}"
fi

TARGET_DIR="$(cd "${TARGET_DIR}" && pwd)"

echo "=================================================================="
echo "🛡️  Bootstrapping Project KEEPER in: ${TARGET_DIR}"
echo "    Mode: $([ "${USE_LINK}" = true ] && echo "Live Symlinks (--link)" || echo "Standalone Copy (--copy)")"
echo "    Domain Codex: ${DOMAIN}"
echo "=================================================================="

# 1. Deploy Master Constitution (Tier 1)
CONSTITUTION_DEST="${TARGET_DIR}/AGENTS.md"
if [ "${USE_LINK}" = true ]; then
    echo "==> Symlinking Master Constitution (codex/AGENTS.md -> AGENTS.md)..."
    ln -sf "${CODEX_DIR}/AGENTS.md" "${CONSTITUTION_DEST}"
else
    echo "==> Copying Master Constitution (codex/AGENTS.md -> AGENTS.md)..."
    cp "${CODEX_DIR}/AGENTS.md" "${CONSTITUTION_DEST}"
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

# 3. Deploy Domain Invariants (Tier 2, always an independent copy)
if [ "${DOMAIN}" = "text" ]; then
    INVARIANTS_DEST="${TARGET_DIR}/INVARIANTS.md"
    if [ -f "${INVARIANTS_DEST}" ]; then
        echo "==> [NOTICE] Existing INVARIANTS.md detected. Preserving existing local invariants."
    else
        echo "==> Deploying Tier-2 Universal Text Domain Codex (-> INVARIANTS.md copy)..."
        cp "${CODEX_DIR}/TEXT_DOMAIN.md" "${INVARIANTS_DEST}"
    fi
fi

# 4. Generate Local Build Configuration Template if missing
CONFIG_FILE="${TARGET_DIR}/KEEPER_CONFIG.md"
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "==> Generating KEEPER_CONFIG.md template..."
    cat << 'EOF' > "${CONFIG_FILE}"
# Project KEEPER: Local Harness Configuration

Please fill in project-specific execution commands so AI subagents can build and test deterministically:

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
echo "   - Tier 1 Constitution: ${TARGET_DIR}/AGENTS.md $([ "${USE_LINK}" = true ] && echo "(symlinked to Dungeons)" || echo "(copied)")"
echo "   - Subagent Prompts:    ${PROMPTS_DEST}/ $([ "${USE_LINK}" = true ] && echo "(symlinked to Dungeons)" || echo "(copied)")"
if [ "${DOMAIN}" = "text" ]; then
echo "   - Tier 2 Domain Codex: ${TARGET_DIR}/INVARIANTS.md (local copy)"
fi
echo "   - Local Config:        ${CONFIG_FILE}"
echo "=================================================================="
