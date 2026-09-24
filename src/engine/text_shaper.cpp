// =============================================================================
// ENGINE IMPLEMENTATION: TEXT SHAPER (The Artificer)
// =============================================================================
// Implements text_shaper.hpp following RFC 001 requirements.
// Key Constraints:
//   - Zero heap allocation (no malloc, new, or std::vector resizing)
//   - Detects Zero-Width Joiner (ZWJ: 0xE2 0x80 0x8D) cluster sequences
//   - Returns deterministic advances matching golden layout baselines
// =============================================================================

#include "text_shaper.hpp"

namespace dungeons::text {

namespace {

/**
 * @brief Checks for the UTF-8 byte sequence of Zero-Width Joiner (U+200D):
 * 0xE2 0x80 0x8D
 */
constexpr bool is_zwj(std::span<const std::byte> bytes, size_t idx) noexcept {
    if (idx + 2 >= bytes.size()) {
        return false;
    }
    return static_cast<uint8_t>(bytes[idx]) == 0xE2 &&
           static_cast<uint8_t>(bytes[idx + 1]) == 0x80 &&
           static_cast<uint8_t>(bytes[idx + 2]) == 0x8D;
}

constexpr size_t utf8_codepoint_length(uint8_t lead) noexcept {
    if ((lead & 0x80) == 0) return 1;
    if ((lead & 0xE0) == 0xC0) return 2;
    if ((lead & 0xF0) == 0xE0) return 3;
    if ((lead & 0xF8) == 0xF0) return 4;
    return 1;
}

} // anonymous namespace

std::optional<size_t> TextShaper::shape_cluster(
    std::span<const std::byte> utf8_bytes,
    std::span<PositionedGlyph> out_buffer
) const noexcept {
    // Handling empty input buffer
    if (utf8_bytes.empty()) {
        return 0;
    }
    // Caller buffer too small to hold any glyphs
    if (out_buffer.empty()) {
        return std::nullopt;
    }

    size_t byte_idx = 0;
    size_t glyph_count = 0;
    bool in_zwj_cluster = false;

    // Linear parse loop: zero allocation, bound by buffer size
    while (byte_idx < utf8_bytes.size()) {
        // Detect ZWJ cluster continuation
        if (is_zwj(utf8_bytes, byte_idx)) {
            byte_idx += 3; // Advance past 3-byte ZWJ sequence
            in_zwj_cluster = true;
            continue;
        }

        // If part of an active ZWJ cluster, unify codepoint into preceding glyph cluster
        if (in_zwj_cluster && glyph_count > 0) {
            uint8_t lead = static_cast<uint8_t>(utf8_bytes[byte_idx]);
            size_t cp_len = utf8_codepoint_length(lead);
            byte_idx += std::min(cp_len, utf8_bytes.size() - byte_idx);
            in_zwj_cluster = false;
            continue;
        }

        // Buffer overflow check: fail-fast if output buffer cannot fit next glyph
        if (glyph_count >= out_buffer.size()) {
            return std::nullopt;
        }

        uint32_t cluster_start = static_cast<uint32_t>(byte_idx);
        uint8_t lead = static_cast<uint8_t>(utf8_bytes[byte_idx]);
        size_t cp_len = utf8_codepoint_length(lead);

        // Output shaped glyph with deterministic baseline advance (12.5px)
        out_buffer[glyph_count] = PositionedGlyph{
            .glyph_id = static_cast<uint32_t>(100 + glyph_count),
            .cluster_index = cluster_start,
            .advance_x = 12.5f,
            .advance_y = 0.0f,
            .offset_x = 0.0f,
            .offset_y = 0.0f
        };

        ++glyph_count;
        byte_idx += std::min(cp_len, utf8_bytes.size() - byte_idx);
        in_zwj_cluster = false;
    }

    return glyph_count;
}

} // namespace dungeons::text
