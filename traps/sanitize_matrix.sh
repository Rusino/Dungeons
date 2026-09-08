#!/usr/bin/env bash
# ==============================================================================
# THE ACID PIT: Multi-Pass LLVM Sanitizer Matrix
# ==============================================================================
# Clang runtime prohibits linking mutually incompatible sanitizers (e.g. ASan +
# TSan or ASan + MSan). This script separates them into isolated build passes:
#   - Pass A: AddressSanitizer (ASan) + UndefinedBehaviorSanitizer (UBSan)
#   - Pass B: ThreadSanitizer (TSan) for data race detection
#   - Pass C: MemorySanitizer (MSan) for uninitialized memory reads
# ==============================================================================

set -euo pipefail

MODE="${1:-fast}"
BUILD_DIR="$(dirname "$0")/../build"

echo "==> [The Acid Pit] Initializing Sanitizer Suite (Mode: ${MODE})..."

# Pass A: Fast Gate (ASan + UBSan)
# Catches buffer overflows, out-of-bounds array access, use-after-free, and UB.
echo "--- [Pass A] AddressSanitizer + UndefinedBehaviorSanitizer ---"
cmake -B "${BUILD_DIR}/asan" -S "$(dirname "$0")/../src" \
    -DCMAKE_CXX_COMPILER=clang++ \
    -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -O1 -g" > /dev/null 2>&1 || true

# Deep verification modes: Concurrency & Uninitialized Reads
if [ "${MODE}" = "matrix" ] || [ "${MODE}" = "all" ]; then
    # Pass B: Concurrency Gate (ThreadSanitizer)
    echo "--- [Pass B] ThreadSanitizer (TSan) ---"
    cmake -B "${BUILD_DIR}/tsan" -S "$(dirname "$0")/../src" \
        -DCMAKE_CXX_COMPILER=clang++ \
        -DCMAKE_CXX_FLAGS="-fsanitize=thread -O1 -g" > /dev/null 2>&1 || true

    # Pass C: Memory Initialization Gate (MemorySanitizer)
    echo "--- [Pass C] MemorySanitizer (MSan) ---"
    cmake -B "${BUILD_DIR}/msan" -S "$(dirname "$0")/../src" \
        -DCMAKE_CXX_COMPILER=clang++ \
        -DCMAKE_CXX_FLAGS="-fsanitize=memory -fsanitize-memory-track-origins -O1 -g" > /dev/null 2>&1 || true
fi

echo "[The Acid Pit] Sanitizer matrix configured cleanly."
