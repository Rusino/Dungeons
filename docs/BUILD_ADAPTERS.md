# Project KEEPER: Build System Adaptation Guide
## Binding Abstract Gauntlet Verification to Concrete Build Toolchains

Project KEEPER's Master Constitution mandates strict verification gauntlets:
- **Fast Unit Tests**: Bound by $\le 10\text{s}$ timeout.
- **Incremental Compilation**: Bound by $\le 60\text{s}$ timeout with `-Werror`.
- **Multi-Pass Sanitizer Matrix**: AddressSanitizer (ASan), UndefinedBehaviorSanitizer (UBSan), ThreadSanitizer (TSan), and MemorySanitizer (MSan) bound by $\le 120\text{s}$.
- **Resource Profiling**: Zero dynamic allocations in hot loops.

This guide provides the standard adapters for binding these requirements to the major build systems: **GN/Ninja**, **CMake**, **Cargo (Rust)**, and **Bazel**.

---

## 1. Project Build Configuration (`KEEPER_CONFIG.md`)

When bootstrapping KEEPER in an existing project, define a `KEEPER_CONFIG.md` (or declare a `## Build & Test Commands` section at the top of `INVARIANTS.md`). This eliminates agent guessing and ensures deterministic command execution:

```markdown
# KEEPER Local Harness Configuration

- **Build Command**: `ninja -C out/Debug dm`
- **Unit Test Command**: `out/Debug/dm --match <SuiteName>`
- **Compilation Timeout**: `60s`
- **Test Timeout**: `10s`
- **Sanitizer Matrix**:
  - ASan Target: `out/ASan/dm --match <SuiteName>`
  - TSan Target: `out/TSan/dm --match <SuiteName>`
  - MSan Target: `out/MSan/dm --match <SuiteName>`
```

---

## 2. GN / Ninja (Skia, Chromium, Fuchsia)

### Compilation & Tests
```bash
# Incremental build
timeout 60s ninja -C out/Debug <target>

# Fast unit test run
timeout 10s out/Debug/<test_binary> --match <SuiteFilter>
```

### Multi-Pass Sanitizer Matrix Configuration
Clang prohibits linking conflicting sanitizers simultaneously. Configure separate output directories:

```bash
# Pass A: AddressSanitizer + UndefinedBehaviorSanitizer (Fast Gate)
gn gen out/ASan --args='is_debug=true is_asan=true is_ubsan=true'
timeout 60s ninja -C out/ASan <target>
timeout 120s out/ASan/<test_binary> --match <SuiteFilter>

# Pass B: ThreadSanitizer (Concurrency Gate)
gn gen out/TSan --args='is_debug=false is_tsan=true'
timeout 60s ninja -C out/TSan <target>
timeout 120s out/TSan/<test_binary> --match <SuiteFilter>

# Pass C: MemorySanitizer (Uninitialized Memory Gate)
gn gen out/MSan --args='is_debug=false is_msan=true'
timeout 60s ninja -C out/MSan <target>
timeout 120s out/MSan/<test_binary> --match <SuiteFilter>
```

---

## 3. CMake / Ninja

### Compilation & Tests
```bash
# Configure debug build
cmake -B build/Debug -S . -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

# Incremental build
timeout 60s cmake --build build/Debug -j

# Fast unit test run via CTest
timeout 10s ctest --test-dir build/Debug --output-on-failure -R <SuiteFilter>
```

### Multi-Pass Sanitizer Configuration
```bash
# Pass A: ASan + UBSan
cmake -B build/ASan -S . -G Ninja \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer -g -O1"
timeout 60s cmake --build build/ASan -j
timeout 120s ctest --test-dir build/ASan --output-on-failure -R <SuiteFilter>

# Pass B: TSan
cmake -B build/TSan -S . -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_CXX_FLAGS="-fsanitize=thread -fno-omit-frame-pointer -g -O1"
timeout 60s cmake --build build/TSan -j
timeout 120s ctest --test-dir build/TSan --output-on-failure -R <SuiteFilter>

# Pass C: MSan
cmake -B build/MSan -S . -G Ninja \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_CXX_FLAGS="-fsanitize=memory -fsanitize-memory-track-origins -g -O1"
timeout 60s cmake --build build/MSan -j
timeout 120s ctest --test-dir build/MSan --output-on-failure -R <SuiteFilter>
```

---

## 4. Cargo (Rust)

### Compilation & Tests
```bash
# Incremental build
timeout 60s cargo check --tests

# Fast unit test run
timeout 10s cargo test <test_filter> -- --nocapture
```

### Sanitizer & Undefined Behavior Verification
```bash
# AddressSanitizer (nightly required)
RUSTFLAGS="-Zsanitizer=address" timeout 120s cargo +nightly test --target x86_64-unknown-linux-gnu <test_filter>

# ThreadSanitizer
RUSTFLAGS="-Zsanitizer=thread" timeout 120s cargo +nightly test --target x86_64-unknown-linux-gnu <test_filter>

# Miri (Undefined Behavior Evaluation)
timeout 120s cargo miri test <test_filter>
```

---

## 5. Bazel

### Compilation & Tests
```bash
# Incremental build
timeout 60s bazel build //...

# Fast unit test run
timeout 10s bazel test //... --test_filter=<SuiteFilter> --test_output=errors
```

### Sanitizer Configuration
In `.bazelrc`:
```bash
build:asan --copt=-fsanitize=address,undefined --linkopt=-fsanitize=address,undefined
build:tsan --copt=-fsanitize=thread --linkopt=-fsanitize=thread
build:msan --copt=-fsanitize=memory --linkopt=-fsanitize=memory
```

Execution:
```bash
timeout 120s bazel test --config=asan //... --test_filter=<SuiteFilter>
timeout 120s bazel test --config=tsan //... --test_filter=<SuiteFilter>
```

---

## 6. Continuous & Bounded Fuzz Testing Adapters (The Beholder Gate)

Fuzz targets must link against coverage-guided fuzz engines (typically `libFuzzer` via `-fsanitize=fuzzer`) with ASan and UBSan enabled.

### GN / Ninja (Skia / Chromium)
```bash
# Configure LibFuzzer + AddressSanitizer
gn gen out/Fuzz --args='is_debug=false is_asan=true is_ubsan=true use_libfuzzer=true'
ninja -C out/Fuzz <fuzzer_target>

# Execute Fuzz Gate
python3 traps/fuzz_gate.py --target out/Fuzz/<fuzzer_target> --timeout 15
```

### CMake / Ninja
In `CMakeLists.txt`:
```cmake
if (ENABLE_FUZZING)
    add_executable(fuzzer_beholder fuzz/fuzzer_target.cpp)
    target_link_libraries(fuzzer_beholder PRIVATE <my_engine>)
    target_compile_options(fuzzer_beholder PRIVATE -fsanitize=fuzzer,address,undefined)
    target_link_options(fuzzer_beholder PRIVATE -fsanitize=fuzzer,address,undefined)
endif()
```
Compilation & Execution:
```bash
cmake -B build/Fuzz -S . -G Ninja -DENABLE_FUZZING=ON -DCMAKE_CXX_COMPILER=clang++
cmake --build build/Fuzz --target fuzzer_beholder
python3 traps/fuzz_gate.py --target build/Fuzz/fuzzer_beholder --timeout 15
```

### Cargo (Rust)
Using `cargo-fuzz` / `libfuzzer-sys`:
```bash
# Initialize fuzzing harness
cargo fuzz init

# Run bounded fuzz gate
python3 traps/fuzz_gate.py --target "cargo fuzz run <fuzz_target> fuzz/corpus -- -max_total_time=15"
```

