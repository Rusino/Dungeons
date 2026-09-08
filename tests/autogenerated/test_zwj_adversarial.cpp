// =============================================================================
// ADVERSARIAL RED-TEAM UNIT TESTS (The Trapsmith)
// =============================================================================
// Target: text_shaper.hpp / text_shaper.cpp
// Explicitly written to test boundary failures:
//   - Empty and zero-sized buffers
//   - Zero-Width Joiner Unicode cluster continuation
//   - Truncated multi-byte UTF-8 sequences (verifying ASan doesn't over-read)
// =============================================================================

#include <gtest/gtest.h>
#include <array>
#include <vector>
#include <span>
#include "text_shaper.hpp"

using namespace dungeons::text;

// Test 1: Empty buffers should safely return 0 or nullopt without memory fault
TEST(TrapsmithTextShaperTest, HandlesEmptyBuffersWithoutCrashing) {
    TextShaper shaper;
    std::array<PositionedGlyph, 10> out_buffer;
    
    // Empty input byte span
    auto res = shaper.shape_cluster({}, out_buffer);
    ASSERT_TRUE(res.has_value());
    EXPECT_EQ(*res, 0);

    // Empty output buffer
    std::array<std::byte, 4> input{std::byte{0x61}, std::byte{0x62}, std::byte{0x63}, std::byte{0x64}};
    auto res2 = shaper.shape_cluster(input, {});
    EXPECT_FALSE(res2.has_value());
}

// Test 2: Valid ZWJ sequence should not split into fragmented glyphs
TEST(TrapsmithTextShaperTest, HandlesZeroWidthJoinerSequences) {
    TextShaper shaper;
    std::array<PositionedGlyph, 10> out_buffer;

    // Byte stream with ZWJ sequence: 'A' + 0xE2 0x80 0x8D + 'B'
    std::vector<std::byte> input = {
        std::byte{0x41},
        std::byte{0xE2}, std::byte{0x80}, std::byte{0x8D},
        std::byte{0x42}
    };

    auto res = shaper.shape_cluster(input, out_buffer);
    ASSERT_TRUE(res.has_value());
    EXPECT_GT(*res, 0);
}

// Test 3: Truncated UTF-8 must not cause an out-of-bounds read under AddressSanitizer
TEST(TrapsmithTextShaperTest, TruncatedUtf8DoesNotOverRead) {
    TextShaper shaper;
    std::array<PositionedGlyph, 10> out_buffer;

    // Truncated ZWJ prefix (2 bytes instead of 3)
    std::vector<std::byte> truncated = {
        std::byte{0xE2}, std::byte{0x80}
    };

    auto res = shaper.shape_cluster(truncated, out_buffer);
    ASSERT_TRUE(res.has_value());
}
