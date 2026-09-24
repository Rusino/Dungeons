# Universal Text Domain Codex (Tier 2 Standard Reference)
## Domain Invariants for Interactive Text, Typography, and Layout Systems

This document defines the universal domain-specific invariants governing interactive text processing, complex typography, bidirectional (BiDi) layout, cursor navigation, selection geometry, and text editing.

It is independent of any specific UI framework, engine architecture, or class naming convention. Any text rendering, layout, or editing subsystem (e.g. GUI text boxes, terminal emulators, word processors, web engine text controls) operating under Project KEEPER is constitutionally bound to satisfy every invariant specified herein.

---

### Invariant 1: Dual-Contract Typography (Logical Index $\longleftrightarrow$ Spatial Geometry)

1. **State and Geometry Co-Verification**:
   Any test or operational contract asserting text state, mutation, insertion, deletion, or cursor navigation must assert BOTH:
   - **The Logical State**: Exact buffer content (UTF-8 bytes / Unicode scalar values) and caret logical position $(\text{index}, \text{affinity})$.
   - **The Spatial Geometry**: The resulting caret rectangle bounds must be valid and non-empty ($\text{height} > 0$), positioned at valid baseline coordinates, and reflecting directional displacement across navigation steps.
2. **Empty Document Metric Fallback**:
   When the text buffer is empty, line layout containers contain zero character boxes. The engine must compute a valid fallback caret rectangle directly from the active font metrics ($\text{height} = |\text{Ascent}| + |\text{Descent}|$) at the document origin, rather than collapsing to a zero-height or zero-width coordinate.
3. **Caret Position Retention Across Mutations**:
   Deleting characters (backward or forward) or replacing text spans must preserve the active visual cursor position corresponding to the remaining character boundary. Under no circumstances may a deletion operation reset horizontal caret coordinates ($\Delta X \to 0$ or line origin) unless the deletion removes all characters preceding the cursor on that line.

---

### Invariant 2: Multi-Script Font Fallback & The No-Tofu Law

1. **Zero Silent Degradation (`.notdef` Tofu Prohibition)**:
   The rendering engine must never draw glyph ID 0 (`.notdef` / empty replacement box) for any printable Unicode character in any script supported by installed system fonts.
2. **Dynamic Character-Level Font Fallback**:
   Layout must not assume a single static font for an entire paragraph or style span. If the primary font lacks glyph coverage for a codepoint, the engine must partition the run and query font fallback mechanisms to resolve a script-capable font (e.g., Latin, Arabic, Hebrew, CJK, Indic, emoji).
3. **Control Code Zero-Width Filtering**:
   Control characters (line breaks, tab characters, and Unicode formatting controls $\text{U+200B}$–$\text{U+200F}$) must have zero visual advance and MUST BE FILTERED OUT prior to glyph rendering. Control codes must never render as visual tofu boxes.

---

### Invariant 3: Extended Grapheme Cluster Atomicity (Unicode UAX #29)

1. **Atomic Grapheme Cluster Unification**:
   Zero-width combining marks (e.g., stacked diacritics, Arabic harakat/tashkeel, Hebrew niqqud, combining accents) and emoji ZWJ sequences must NEVER produce standalone, navigable character boundaries. All combining marks must merge into the preceding base cluster, extending its byte span and expanding its vertical ink bounds.
2. **Single-Keystroke Atomic Navigation**:
   Horizontal directional navigation (Arrow Left / Arrow Right) must step across the entire extended grapheme cluster in a single user action. Caret movement must never require multiple keystrokes that leave the cursor visually stranded at intermediate zero-width diacritics.
3. **Hit-Testing Affinity & Internal Snapping**:
   Hit-testing on a base character with attached combining marks must resolve either to the leading boundary of the cluster or past the entire cluster to its trailing boundary, never landing at an internal zero-width mark boundary. If programmatic mutation sets an index inside a multi-codepoint grapheme cluster, the next navigation step must snap to the outer cluster boundary.

---

### Invariant 4: Soft-Wrap Boundary Singularity & Geometric Affinity

1. **Soft-Wrap Boundary Singularity**:
   In soft-wrapped text, the transition from line $k$ to line $k+1$ occurs without a hard newline character (`\n`). The scalar index $I = \text{line}_k.\text{end} = \text{line}_{k+1}.\text{start}$ is topologically shared between two distinct geometric screen coordinates: the end of line $k$ and the start of line $k+1$.
2. **Geometric Affinity Disambiguation**:
   Resolving a cursor position at index $I$ without explicit `Affinity` is mathematically undefined:
   - $\text{Affinity::kUpstream}$: Places the caret strictly at the trailing edge of line $k$ ($(X_{\text{end}}, Y_k)$). It must NEVER jump down to line $k+1$.
   - $\text{Affinity::kDownstream}$: Places the caret strictly at the leading edge of line $k+1$ ($(X_{\text{start}}, Y_{k+1})$).
3. **Step-Through Horizontal Navigation**:
   Horizontal caret movement across a soft-wrap boundary must transition sequentially through both geometric positions via affinity toggling ($(\text{line}_k.\text{end}, \text{kUpstream}) \longleftrightarrow (\text{line}_{k+1}.\text{start}, \text{kDownstream})$) without skipping screen locations.

---

### Invariant 5: Continuous Physical Selection across Discontinuous BiDi Runs

1. **Physical Selection Bounds Dominance**:
   During an interactive pointer drag across mixed LTR/RTL text, the visual selection must strictly illuminate the physical horizontal interval $[X_{\text{anchor}}, X_{\text{focus}}]$ on the active line. Crossing a directionality boundary must NEVER cause the selection to prematurely expand across unselected portions of the run or invert unselected characters.
2. **Discontinuous Logical Mapping**:
   In bidirectional text, physically contiguous intervals map to topologically discontinuous byte ranges. The selected text must be represented as a canonical set of sorted, non-overlapping logical byte ranges $\{R_1, R_2, \dots, R_m\}$, containing exclusively the codepoints physically falling within the visual drag interval.
3. **2D Multi-Line Drag Continuity & Saturation**:
   When an interactive drag spans multiple lines:
   - On the starting line: Clusters intersecting from the anchor coordinate to the trailing line edge are selected.
   - On intermediate lines: 100% of clusters across the entire line bounds are selected.
   - On the ending line: Clusters intersecting from the leading line edge to the focus coordinate are selected.
   Silently collapsing multi-line drag to a single line or dropping intermediate lines is strictly prohibited.

---

### Invariant 6: Reverse Topological Mutation & Deletion Order

1. **Inverted Byte Deletion Order**:
   When mutating or deleting a discontinuous selection (such as a cross-directional BiDi selection), deletions must execute strictly in reverse logical offset order (from highest byte offset down to lowest byte offset).
2. **Prevention of Index Drift**:
   Executing deletions forward (from lowest to highest offset) shifts the byte positions of downstream ranges, corrupting subsequent slices and leaving document text in an invalid state.

---

### Invariant 7: BiDi Coordinate Mapping & Cut-Boundary Retention

1. **BiDi Caret Coordinate Inversion**:
   In right-to-left (RTL) runs, cluster coordinate mapping is inverted relative to LTR runs: the logical start boundary of a cluster resides at its visual right edge ($\text{bounds.fRight}$), and the logical end boundary resides at its visual left edge ($\text{bounds.fLeft}$). Caret resolution must invert geometric calculations accordingly.
2. **Physical Cut-Boundary Retention**:
   When deleting text within or across BiDi runs, the resulting caret must remain at the exact physical visual cut boundary where the deletion occurred. It must never teleport to the opposite visual boundary of an adjacent RTL run or line origin.
3. **Insertion Upstream Affinity**:
   Upon text insertion, the caret must maintain $\text{Affinity::kUpstream}$, positioning strictly at the trailing edge (for LTR: right boundary; for RTL: left boundary) of the newly inserted character in that run's direction.

---

### Invariant 8: Typographic Metrics vs. Visual Ink Bounds Separation

1. **Typographic Height Invariant**:
   The vertical height and position of the caret and line baselines must be strictly computed from the active typographic font metrics ($|\text{Ascent}| + |\text{Descent}| + \text{LineGap}$). Caret bounds must NEVER expand vertically to encompass stacked diacritics, combining marks, or tall glyphs.
2. **Ink Bounds Isolation**:
   Dynamic diacritic expansion (e.g. Zalgo stacked marks) belongs strictly to ink bounds for visual redraw invalidation and clipping. It must never leak into caret geometry or alter paragraph line spacing.

---

### Invariant 9: The Zero-Delta Phantom Navigation Law

1. **Prohibition of Zero-Delta Navigation**:
   Any navigational input that successfully increments or decrements the logical text buffer index must produce a non-zero visual displacement ($\Delta X \ne 0 \lor \Delta Y \ne 0$) on screen.
2. **Phantom Stalling as a Defect**:
   Advancing logical indices across zero-width characters, formatting marks, or unmerged combining marks while leaving the visual caret frozen in place is classified as a Phantom Navigation defect and constitutes an automatic test failure.

---

### Invariant 10: Input Ingestion Hygiene & Control Character Preservation

1. **Line Break Normalization**:
   External line break sequences (`\r\n` or single `\r`) must be normalized to canonical newlines (`\n`) immediately upon ingestion, before reaching layout or shaping engines.
2. **Destructive Control Code Sanitization**:
   C0 and C1 control characters (ASCII $0\text{x}00$–$0\text{x}1F$ other than `\n`, and $0\text{x}7F$ DEL) must be rejected or stripped upon ingestion to prevent shaping corruption and visual tofu.
3. **Unicode Formatting Control Preservation**:
   Unicode Format Controls (category `Cf`, including Zero-Width Joiner $\text{U+200D}$, Zero-Width Non-Joiner $\text{U+200C}$, Left-to-Right Mark $\text{U+200E}$, and Right-to-Left Mark $\text{U+200F}$) must be strictly preserved. They are mandatory typographical inputs for complex script shaping (HarfBuzz) and BiDi analysis.

---

### Invariant 11: Single-Source Presentation Projection (Passive Consumer Law)

1. **Presentation Layer Purity**:
   The visual presentation layer (canvas painter, widget renderer, terminal output) must be a pure, passive consumer of projected layout and cursor geometry.
2. **Prohibition of Consumer Arithmetic**:
   The presentation layer is strictly prohibited from recalculating glyph hit-testing, evaluating line wrapping, or constructing text spans internally. All visual coordinates (caret rect, selection highlights, glyph positions) must be queried directly from the layout/view model projection.

---

### Invariant 12: Deterministic Reversible Editing (Undo/Redo History)

1. **Symmetric Command Pair Invariant**:
   Every state mutation on document text must be captured as an invertible transaction pair:
   $$(\text{ForwardMutation}, \text{InverseMutation})$$
   recording exact byte offsets, inserted/deleted text payloads, and cursor selection states before and after the mutation $(\text{Selection}_{\text{before}}, \text{Selection}_{\text{after}})$.
2. **Typing Coalescing Determinism**:
   Continuous character typing may be coalesced into single undoable transactions if and only if:
   - Sequential keystrokes occur within a defined temporal threshold ($\le 750\text{ms}$);
   - Insertions are contiguous;
   - Keystrokes do not cross word boundaries (whitespace, punctuation, newline) or directionality boundaries.
   Non-typing commands (navigation, paste, cut, block selection) must never be coalesced.

---

### Invariant 13: Continuous Fuzzing & Invariant Verification Matrix

1. **Differential Buffer Model Equivalence**:
   Any optimized text storage engine (piece table, rope, gap buffer) must be continuously fuzzed against a naive sequential string/array reference model under randomized mutation streams ($\text{Insert}, \text{Delete}, \text{Replace}$). At every mutation step:
   $$\text{buffer.to_string}() == \text{reference_model.to_string}()$$
   $$\text{buffer.length}() == \text{reference_model.length}()$$
2. **Deterministic Reversibility Fuzzing**:
   Random sequences of $N$ edits followed by $N$ undos must restore the exact initial document state and cursor projection:
   $$\text{undo}^N(\text{apply}_N(\dots \text{apply}_1(\text{state}))) == \text{state}$$
3. **Malformed & Truncated Ingress Bombardment**:
   Shapers, parsers, and hit-testing engines must be continuously fuzzed with corrupted UTF-8 byte streams, unpaired surrogates, trailing joiners, and mixed line breaks. Under no input may the engine crash, panic, leak memory, or hang in an infinite loop.
4. **Indivisible Boundary Invariant**:
   Fuzz testing of cursor navigation and deletion over arbitrary Unicode text must assert that the caret NEVER rests inside a surrogate pair, between `\r` and `\n`, or inside an extended grapheme cluster.

