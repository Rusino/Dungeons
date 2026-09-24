// =============================================================================
// KEEPER GATE A DEFECT PINNING TRAP (The Trapsmith)
// =============================================================================
// Targets:
//   1. Multi-byte UTF-8 increment corruption (1-byte slicing defect).
//   2. Silent buffer overflow truncation (should return std::nullopt).
// Enforces Axiom 4 (Anti-Ghost Test Rule) and Axiom 11 (Dimensional Matrix).
// =============================================================================

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <vector>
#include "text_shaper.hpp"

#define KEEPER_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "\n[KEEPER TRAP FIRED] " << msg \
                      << " at " << __FILE__ << ":" << __LINE__ << "\n"; \
            std::exit(1); \
        } \
    } while (0)

using namespace dungeons::text;

// Test 1: 0D Boundary - Empty buffers
void test_0d_degenerate_buffers() {
    TextShaper shaper;
    std::array<PositionedGlyph, 8> out_buffer;

    auto res = shaper.shape_cluster({}, out_buffer);
    KEEPER_ASSERT(res.has_value() && *res == 0, "Empty input must return 0 glyphs");

    std::array<std::byte, 1> input{std::byte{'A'}};
    auto res2 = shaper.shape_cluster(input, {});
    KEEPER_ASSERT(!res2.has_value(), "Zero-capacity output buffer must return nullopt");
}

// Test 2: 1D Standard - ASCII Linear Sequence
void test_1d_ascii_sequence() {
    TextShaper shaper;
    std::array<PositionedGlyph, 8> out_buffer;
    std::array<std::byte, 3> input{std::byte{'A'}, std::byte{'B'}, std::byte{'C'}};

    auto res = shaper.shape_cluster(input, out_buffer);
    KEEPER_ASSERT(res.has_value() && *res == 3, "3 ASCII characters must produce 3 glyphs");
    KEEPER_ASSERT(out_buffer[0].cluster_index == 0, "Cluster index 0 mismatch");
    KEEPER_ASSERT(out_buffer[1].cluster_index == 1, "Cluster index 1 mismatch");
    KEEPER_ASSERT(out_buffer[2].cluster_index == 2, "Cluster index 2 mismatch");
}

// Test 3: 2D Complex - Multi-byte UTF-8 Codepoint (Fire Emoji: 0xF0 0x9F 0x94 0xA5)
// PINS DEFECT 1: Current code slices 4-byte UTF-8 into 4 individual bytes!
void test_2d_multibyte_utf8() {
    TextShaper shaper;
    std::array<PositionedGlyph, 8> out_buffer;

    // Single 4-byte UTF-8 codepoint: 🔥 U+1F525 (0xF0, 0x9F, 0x94, 0xA5)
    std::vector<std::byte> emoji_bytes = {
        std::byte{0xF0}, std::byte{0x9F}, std::byte{0x94}, std::byte{0xA5}
    };

    auto res = shaper.shape_cluster(emoji_bytes, out_buffer);
    KEEPER_ASSERT(res.has_value(), "Valid UTF-8 emoji must not fail parsing");
    KEEPER_ASSERT(*res == 1, "Single 4-byte UTF-8 codepoint must produce exactly 1 glyph, not multiple fragmented bytes");
    KEEPER_ASSERT(out_buffer[0].cluster_index == 0, "Emoji glyph cluster index must be 0");
}

// Test 4: Adversarial / Capacity Overflow
// PINS DEFECT 2: Current code silently truncates and returns partial count instead of nullopt!
void test_overflow_fail_fast() {
    TextShaper shaper;
    std::array<PositionedGlyph, 2> tiny_buffer; // Only room for 2 glyphs

    // Input has 4 distinct ASCII characters: 'A', 'B', 'C', 'D'
    std::array<std::byte, 4> input{
        std::byte{'A'}, std::byte{'B'}, std::byte{'C'}, std::byte{'D'}
    };

    auto res = shaper.shape_cluster(input, tiny_buffer);
    KEEPER_ASSERT(!res.has_value(), "Insufficient output buffer must fail-fast with std::nullopt (silent truncation prohibited)");
}

int main() {
    std::cout << "=== Running KEEPER Dimensional Test Suite ===\n";
    std::cout << "[1/4] Testing 0D Degenerate Buffers... ";
    test_0d_degenerate_buffers();
    std::cout << "PASSED\n";

    std::cout << "[2/4] Testing 1D ASCII Sequence... ";
    test_1d_ascii_sequence();
    std::cout << "PASSED\n";

    std::cout << "[3/4] Testing 2D Multi-byte UTF-8 (Trap 1)... ";
    test_2d_multibyte_utf8();
    std::cout << "PASSED\n";

    std::cout << "[4/4] Testing Overflow Fail-Fast (Trap 2)... ";
    test_overflow_fail_fast();
    std::cout << "PASSED\n";

    std::cout << "=== All Tests Passed Successfully ===\n";
    return 0;
}
