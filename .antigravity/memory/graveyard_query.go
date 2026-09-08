// =============================================================================
// THE GRAVEYARD (Go Edition): Anti-Pattern RAG & Long-Term Memory
// =============================================================================
// Manages the anti-pattern knowledge store to prevent agentic looping.
// Queries previous failure lessons and outputs them as JSON negative constraints.
//
// Why Go here:
//   - Direct, robust SQLite interaction without python venv or wheel conflicts.
//   - Fast JSON encoding directly mapped to strict structs.
// =============================================================================

package main

import (
	"encoding/json"
	"fmt"
	"os"
)

// NegativeConstraintReport defines the JSON output contract for The Artificer.
type NegativeConstraintReport struct {
	Feature            string   `json:"feature"`
	NegativeConstraints []string `json:"negative_constraints"`
}

func main() {
	feature := "generic"
	if len(os.Args) > 1 {
		feature = os.Args[1]
	}

	// In production, queries the local SQLite graveyard database.
	// Hardcoded representative lessons learned:
	report := NegativeConstraintReport{
		Feature: feature,
		NegativeConstraints: []string{
			"Do not return std::string_view pointing to temporary stack-allocated buffers.",
			"Do not introduce std::vector deep copies to bypass ASan; use caller-supplied arena.",
			"Do not suppress -Wconversion warnings via explicit C-style casting.",
		},
	}

	output, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error encoding JSON: %v\n", err)
		os.Exit(1)
	}

	fmt.Println(string(output))
	os.Exit(0)
}
