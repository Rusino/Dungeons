# RFC 002: Dead Code Elimination in SkParagraph

- **Author**: The Overgod
- **Status**: Active / In Gauntlet Execution
- **Target Repository**: `~/Sources/skia/` (Branch: `keeper/skparagraph-audit`)
- **Module**: `modules/skparagraph/src/`

## 1. Problem Statement & Objective
Audit `modules/skparagraph/src/` for dead lines of code (dead stores, unreachable branches, redundant assignments) inside function bodies, and eliminate verified dead code without introducing behavioral or metric regressions.

## 2. Hard Invariants & Constraints
1. **Preserve External Consumer Callers (The JetBrains Invariant)**:
   - **ZERO** deletions or modifications of method signatures, functions, or class member variables (even private ones).
   - Only dead statements strictly *inside* function bodies may be considered for elimination.
2. **Mandatory Pre-Flight Pinning (Characterization Testing)**:
   - The Trapsmith MUST write characterization/pinning tests covering target functions *before* any code is modified or deleted.
   - Tests must capture exact baseline outputs and confirm 100% pass on unmodified code.
3. **Zero Delta Enforcement**:
   - Post-deletion execution must produce 0.0000% delta in layout metrics, glyph positions, and return states.
4. **Local Execution Only**:
   - Zero remote git pushes. All work remains local to the `keeper/skparagraph-audit` branch.

## 3. Agents in Action
- **The Scavenger**: Audit `modules/skparagraph/src/` for candidate dead lines.
- **The Architect**: Formulate the Safe Refactoring Specification.
- **The Trapsmith**: Generate and execute pre-flight pinning tests.
- **The Artificer**: Surgically remove verified dead lines.
- **The Gauntlet (Acid Pit & Cartographer)**: Compile and verify zero regressions.
- **The Overgod**: Final diff review and approval.
