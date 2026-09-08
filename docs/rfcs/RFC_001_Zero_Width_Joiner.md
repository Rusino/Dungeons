# RFC 001: Zero-Width Joiner (ZWJ) Complex Text Layout

- **Author**: The Overgod
- **Status**: Draft / Pending The Architect
- **Module**: `src/engine/text_shaper`

## 1. Problem Statement
The text rendering pipeline must correctly identify and shape Unicode emoji clusters involving Zero-Width Joiners (U+200D), combining diacritical marks, and skin tone modifiers into unified glyph clusters without fallback splitting or intermediate heap allocations.

## 2. Constraints & Invariants
1. **Zero Allocation Hot Path**: Text cluster shaping must operate using either caller-supplied monotonic memory or an arena-backed `std::span` buffer.
2. **Deterministic Advances**: Cluster bounding boxes and advances must calculate float coordinates without drift across compilation passes.
3. **Robustness**: Ill-formed UTF-8, trailing ZWJs, and nested combinations up to 16 graphemes must not throw uncaught exceptions or cause buffer over-reads.

## 3. Success Metrics
- 100% of Trapsmith adversarial tests pass under AddressSanitizer, UBSan, and MemorySanitizer.
- Mull Mutation Score >= 90%.
- Zero heap allocations during `shape_cluster()`.
