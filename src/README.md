# Reference C++ Engine Implementation

This directory (`src/`), along with `tests/` and `traps/`, contains a **reference implementation** demonstrating how Project KEEPER operates in a greenfield C++ project built with CMake and Clang.

### Key Components

- `engine/text_shaper.hpp`: The Architect's C++20 contract specifying `TextShapingBuffer` concepts, RAII spans, and `[[nodiscard]]` constraints.
- `engine/text_shaper.cpp`: The Artificer's zero-heap implementation.
- `fuzz/fuzzer_target.cpp`: Continuous libFuzzer fuzzing entry point.
- `CMakeLists.txt`: Hardened build configuration with `-Werror` and Clang multi-pass sanitizer flags.

---

> [!NOTE]
> **Adoption Notice**: When adopting Project KEEPER in an existing or separate project, you do NOT need this code. Your own codebase, repository structure, and build system (GN/Ninja, Cargo, Bazel) take the place of `src/`. See [`docs/BUILD_ADAPTERS.md`](../docs/BUILD_ADAPTERS.md) for instructions on wiring your project's build toolchain into the KEEPER gauntlet.
