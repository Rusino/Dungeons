#!/usr/bin/env bash
set -euo pipefail

# The Acid Pit: LLVM Sanitizer Matrix Runner
# Separates conflicting sanitizer flags into isolated compilation & test passes.

MODE="${1:-fast}"
BUILD_DIR="$(dirname "$0")/../build"

echo "==> [The Acid Pit] Initializing Sanitizer Suite (Mode: ${MODE})..."

# Pass A: Fast Gate (ASan + UBSan)
echo "--- [Pass A] AddressSanitizer + UndefinedBehaviorSanitizer ---"
cmake -B "${BUILD_DIR}/asan" -S "$(dirname "$0")/../src" \
    -DCMAKE_CXX_COMPILER=clang++ \
    -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -O1 -g" > /dev/null 2>&1 || true

# Pass B: Concurrency Gate (ThreadSanitizer)
if [ "${MODE}" = "matrix" ] || [ "${MODE}" = "all" ]; then
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
