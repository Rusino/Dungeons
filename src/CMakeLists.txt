# ==============================================================================
# HARDENED BUILD CONFIGURATION (The Acid Pit)
# ==============================================================================
# Locked build settings for the Gauntlet C++ rendering engine.
# Strictly enforces C++20, -Werror, and all warnings.
# AI agents are denied write access to this file by safety_policies.json.
# ==============================================================================

cmake_minimum_required(VERSION 3.20)
project(DungeonsEngine CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# The Acid Pit Hardened Compiler Flags
add_compile_options(
    -Wall
    -Wextra
    -Wpedantic
    -Werror
    -Wconversion
    -Wshadow
    -Wnon-virtual-dtor
)

include_directories(engine)

# Engine Static Library
add_library(dungeons_engine STATIC
    engine/text_shaper.cpp
)

# The Beholder: Optional Continuous Fuzzing Binary
if (ENABLE_FUZZING)
    add_executable(fuzzer_beholder
        fuzz/fuzzer_target.cpp
    )
    target_link_libraries(fuzzer_beholder PRIVATE dungeons_engine)
    target_compile_options(fuzzer_beholder PRIVATE -fsanitize=fuzzer,address,undefined)
    target_link_options(fuzzer_beholder PRIVATE -fsanitize=fuzzer,address,undefined)
endif()
