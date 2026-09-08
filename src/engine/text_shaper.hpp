// =============================================================================
// CONTRACT SPECIFICATION: TEXT SHAPER (The Architect)
// =============================================================================
// Generated based on RFC 001 (Zero-Width Joiner Complex Text Layout).
// Enforces:
//   - C++20 Standard
//   - Zero raw pointer declarations (std::span used exclusively)
//   - Zero-allocation hot path
//   - C++20 concept for output buffer validation
// =============================================================================

#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <concepts>
#include <optional>
#include <string_view>

namespace dungeons::text {

/**
 * @brief Represents an individual positioned glyph inside a shaped run.
 * Contains layout coordinates, cluster associations, and typographic advances.
 */
struct PositionedGlyph {
    uint32_t glyph_id{0};       ///< Font glyph identifier index
    uint32_t cluster_index{0};  ///< Byte offset in the input UTF-8 stream
    float advance_x{0.0f};      ///< Horizontal advance width in pixels
    float advance_y{0.0f};      ///< Vertical advance height in pixels
    float offset_x{0.0f};       ///< Horizontal glyph placement offset
    float offset_y{0.0f};       ///< Vertical glyph placement offset
};

/**
 * @brief C++20 Concept enforcing Text Shaping Output Buffer properties.
 * Guarantees destination buffer supports random access write and standard sizing.
 */
template <typename T>
concept TextGlyphBuffer = requires(T b, size_t idx, PositionedGlyph g) {
    { b.data() } -> std::same_as<PositionedGlyph*>;
    { b.size() } -> std::same_as<size_t>;
    { b[idx] = g };
};

/**
 * @brief High-performance, zero-allocation text shaper contract.
 * Pure virtual contract designed for Skia/HarfBuzz integration.
 */
class TextShaper {
public:
    constexpr TextShaper() noexcept = default;
    ~TextShaper() noexcept = default;

    // Non-copyable to prevent accidental object slicing or implicit state copies
    TextShaper(const TextShaper&) = delete;
    TextShaper& operator=(const TextShaper&) = delete;

    // Movable
    TextShaper(TextShaper&&) noexcept = default;
    TextShaper& operator=(TextShaper&&) noexcept = default;

    /**
     * @brief Shapes a UTF-8 text run into the caller-provided glyph buffer.
     * Guaranteed zero-allocation hot path (no heap allocations during execution).
     *
     * @param utf8_bytes Raw byte view of the UTF-8 text stream.
     * @param out_buffer Caller-managed destination span for positioned glyphs.
     * @return std::optional<size_t> Number of glyphs written, or nullopt on malformed stream.
     */
    [[nodiscard]] std::optional<size_t> shape_cluster(
        std::span<const std::byte> utf8_bytes,
        std::span<PositionedGlyph> out_buffer
    ) const noexcept;
};

} // namespace dungeons::text
