// =============================================================================
// CONTINUOUS FUZZING ENTRY POINT (The Beholder)
// =============================================================================
// Consumes randomized, corrupted byte streams via LLVMFuzzerTestOneInput
// to detect unhandled memory exceptions, crashes, and integer overflows 24/7.
// =============================================================================

#include <cstddef>
#include <cstdint>
#include <array>
#include "text_shaper.hpp"

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size == 0) {
        return 0;
    }

    dungeons::text::TextShaper shaper;
    std::array<dungeons::text::PositionedGlyph, 256> glyph_buffer;

    auto byte_span = std::span<const std::byte>(
        reinterpret_cast<const std::byte*>(data), size
    );

    // Continuous fuzzing bombardment against the text shaper
    (void)shaper.shape_cluster(byte_span, glyph_buffer);

    return 0;
}
