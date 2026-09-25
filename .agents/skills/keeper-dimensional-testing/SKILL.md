---
name: keeper-dimensional-testing
description: >-
  Guides authoring and verification of red-team unit tests, defect pinning traps, and 0D/1D/2D test matrices under the Anti-Ghost Test Rule. Use when writing new tests, verifying bug reproductions before fixing code, or enforcing dimensional boundary assertions.
---

# KEEPER Dimensional Testing & Defect Pinning Runbook

This skill enforces Axiom 4 (**The Anti-Ghost Test Rule**) and Axiom 11 (**The Fail-Fast & Dimensional Honesty Protocol**) of Project KEEPER.

---

## 1. Core Principles

### The Anti-Ghost Test Rule (Axiom 4)
A test that has not been proven to **FAIL** on broken code is a "ghost test" and has zero evidential value. 
- **Gate A (Pinning)**: You MUST run the test against the current, un-fixed code. It MUST fail (exit code $\neq 0$ or assertion failure). If it passes immediately, the test is invalid or testing the wrong invariant.
- **Gate B (Verification)**: Only after the implementation fix is applied may the test pass.

### The Mandatory Dimensional Matrix (Axiom 11)
When testing contracts, author test cases across all dimensional degrees of freedom:
1. **0D (Degenerate / Boundary)**:
   - Empty input buffer (`size == 0`).
   - Saturated / zero-capacity output buffer (`out_buffer.size() == 0`).
   - Null spans and point boundaries.
2. **1D (Linear / Standard)**:
   - Single ASCII codepoints (`'A'`, `'Z'`).
   - Standard 1-to-1 linear advances.
3. **2D (Complex / Multi-Entity)**:
   - Multi-byte UTF-8 sequences (2-byte Latin/Cyrillic, 3-byte Asian, 4-byte Emoji).
   - Composite clusters (Zero-Width Joiner `U+200D` sequences, combining diacritics).
4. **Adversarial / Overflow**:
   - Truncated multi-byte UTF-8 (e.g., lead byte followed by end of stream).
   - Insufficient output buffer capacity (buffer size < required glyph count). Must fail-fast (`std::nullopt`) rather than silently truncating.

---

## 2. Fast Standalone Test Scaffolding

For zero-dependency, ultra-fast compilation under C++20:

```cpp
#include <cassert>
#include <iostream>

#define KEEPER_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "[KEEPER TRAP FIRED] " << msg \
                      << " at " << __FILE__ << ":" << __LINE__ << "\n"; \
            std::exit(1); \
        } \
    } while (0)

#define KEEPER_TEST(name) void name()
#define RUN_TEST(name) do { \
    std::cout << "[RUNNING] " << #name << "... "; \
    name(); \
    std::cout << "PASSED\n"; \
} while(0)
```

---

## 3. Two-Gate Execution Protocol

### Gate A: Defect Pinning
1. Author the adversarial reproduction test inside `tests/`.
2. Compile and run against the **unmodified** production code using the project's configured build and test commands (from `KEEPER_CONFIG.md` or `keeper.yaml`):
   ```bash
   # Via deterministic state machine runner:
   ./keeper --phase 4

   # Or directly via project build/test harness:
   <build_cmd> && <test_cmd>
   ```
3. **Receipt Requirement**: Confirm compilation succeeds (`0`) and test execution fails (`!= 0`), proving defect sensitivity.

### Gate B: Implementation Resolution
1. Apply the production fix in `src/`.
2. Recompile and run the test suite:
   ```bash
   # Via deterministic state machine runner:
   ./keeper --phase 6

   # Or directly via project build/test harness:
   <build_cmd> && <test_cmd>
   ```
3. **Receipt Requirement**: Confirm exit code `0` across all test matrix dimensions.

