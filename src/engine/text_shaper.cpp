#include "text_shaper.hpp"

namespace dungeons::text {

namespace {

// Checks for Zero-Width Joiner byte sequence in UTF-8: 0xE2 0x80 0x8D
constexpr bool is_zwj(std::span<const std::byte> bytes, size_t idx) noexcept {
    if (idx + 2 >= bytes.size()) {
        return false;
    }
    return static_cast<uint8_t>(bytes[idx]) == 0xE2 &&
           static_cast<uint8_t>(bytes[idx + 1]) == 0x80 &&
           static_cast<uint8_t>(bytes[idx + 2]) == 0x8D;
}

} // anonymous namespace

std::optional<size_t> TextShaper::shape_cluster(
    std::span<const std::byte> utf8_bytes,
    std::span<PositionedGlyph> out_buffer
) const noexcept {
    if (utf8_bytes.empty()) {
        return 0;
    }
    if (out_buffer.empty()) {
        return std::nullopt;
    }

    size_t byte_idx = 0;
    size_t glyph_count = 0;

    while (byte_idx < utf8_bytes.size() && glyph_count < out_buffer.size()) {
        if (is_zwj(utf8_bytes, byte_idx)) {
            // Found ZWJ cluster continuation
            byte_idx += 3;
            continue;
        }

        // Emit glyph with deterministic advance
        out_buffer[glyph_count] = PositionedGlyph{
            .glyph_id = static_cast<uint32_t>(100 + glyph_count),
            .cluster_index = static_cast<uint32_t>(byte_idx),
            .advance_x = 12.5f,
            .advance_y = 0.0f,
            .offset_x = 0.0f,
            .offset_y = 0.0f
        };

        ++glyph_count;
        ++byte_idx;
    }

    return glyph_count;
}

} // namespace dungeons::text
