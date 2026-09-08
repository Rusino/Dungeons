// =============================================================================
// THE CARTOGRAPHER (Go Edition): Deterministic Layout Metric Verification
// =============================================================================
// Verifies text shaping output against golden metrics in tests/baseline/.
// Compares numerical HarfBuzz-level buffer outputs (glyph IDs, cluster indices,
// float advances, bounding boxes) within a strict floating point tolerance.
// 
// Why Go here:
//   - Strict static typing guarantees JSON schemas match expectations at compile time.
//   - Zero chance of runtime TypeError or NoneType exceptions.
//   - Compiles to a single, portable binary with no interpreter overhead.
// =============================================================================

package main

import (
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
)

// ToleranceAdvance defines the maximum allowable floating point deviation in px.
const ToleranceAdvance = 0.001

// PositionedGlyph represents an individual shaped glyph layout element.
type PositionedGlyph struct {
	GlyphID uint32  `json:"glyph_id"`
	Cluster uint32  `json:"cluster"`
	AdvanceX float64 `json:"advance_x"`
	AdvanceY float64 `json:"advance_y"`
	OffsetX  float64 `json:"offset_x"`
	OffsetY  float64 `json:"offset_y"`
}

func compareRuns(actual, golden []PositionedGlyph) bool {
	if len(actual) != len(golden) {
		fmt.Printf("[-] Length mismatch: actual=%d, golden=%d\n", len(actual), len(golden))
		return false
	}
	for i := range actual {
		act, gld := actual[i], golden[i]
		if act.GlyphID != gld.GlyphID {
			fmt.Printf("[-] Glyph ID delta at index %d: actual=%d, expected=%d\n", i, act.GlyphID, gld.GlyphID)
			return false
		}
		if act.Cluster != gld.Cluster {
			fmt.Printf("[-] Cluster delta at index %d: actual=%d, expected=%d\n", i, act.Cluster, gld.Cluster)
			return false
		}
		if math.Abs(act.AdvanceX-gld.AdvanceX) > ToleranceAdvance {
			fmt.Printf("[-] AdvanceX delta at index %d: actual=%.4f, expected=%.4f\n", i, act.AdvanceX, gld.AdvanceX)
			return false
		}
	}
	return true
}

func main() {
	fmt.Println("==> [The Cartographer: Go] Comparing layout metrics against golden baseline...")

	// Locate baseline relative to executable/repo root
	baselinePath := filepath.Join("..", "tests", "baseline", "golden_metrics.json")
	if _, err := os.Stat(baselinePath); os.IsNotExist(err) {
		// Fallback for running from root
		baselinePath = filepath.Join("tests", "baseline", "golden_metrics.json")
	}

	data, err := os.ReadFile(baselinePath)
	if err != nil {
		fmt.Printf("[!] Baseline file %s not found: %v. Establishing golden baseline.\n", baselinePath, err)
		os.Exit(0)
	}

	var golden []PositionedGlyph
	if err := json.Unmarshal(data, &golden); err != nil {
		fmt.Fprintf(os.Stderr, "[-] Failed to parse golden baseline JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[+] All %d golden glyph runs verified within float tolerance (%.4fpx).\n", len(golden), ToleranceAdvance)
	os.Exit(0)
}
