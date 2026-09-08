// =============================================================================
// THE GAUNTLET GRAPH ORCHESTRATOR (Go Edition - The Dungeon Master)
// =============================================================================
// Master state manager controlling the autonomous verification gauntlet:
//   1. Checks RFC specification existence.
//   2. Coordinates tier-by-tier execution of all verification gates:
//        - Tier 1: Fast Traps (Sanitizer compilation, Cartographer delta)
//        - Tier 2: Deep Sanitizer Matrix (TSan, MSan)
//        - Tier 3: The Mimic (Mutation testing >= 90%)
//        - Tier 4: The Quartermaster (Performance & allocation limits)
//   3. Handles retry loop (up to MaxRetries) before triggering Overgod escalation.
//
// Why Go here:
//   - os/exec and context provide rock-solid subprocess timeouts and signal handling.
//   - Single static binary orchestrator: zero python environment drift.
// =============================================================================

package main

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

const MaxRetries = 5

type StepResult struct {
	ExitCode int
	Stdout   string
	Stderr   string
}

func runCommand(ctx context.Context, description string, name string, args ...string) StepResult {
	fmt.Printf("==> [The Dungeon Master: Go] Running: %s (%s %v)\n", description, name, args)
	cmd := exec.CommandContext(ctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	code := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			code = exitErr.ExitCode()
		} else {
			code = 1
		}
	}
	return StepResult{
		ExitCode: code,
		Stdout:   stdout.String(),
		Stderr:   stderr.String(),
	}
}

func main() {
	rfcPath := filepath.Join("docs", "rfcs", "RFC_001_Zero_Width_Joiner.md")
	if len(os.Args) > 1 {
		rfcPath = os.Args[1]
	}

	fmt.Printf("=== Initiating The Gauntlet (Go Engine) for RFC: %s ===\n", rfcPath)

	if _, err := os.Stat(rfcPath); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "Error: RFC %s does not exist.\n", rfcPath)
		os.Exit(1)
	}

	fmt.Println("[1/5] Contract Generation: The Architect generates C++20 .hpp contracts.")
	fmt.Println("[2/5] Adversarial Testing: The Trapsmith lays edge-case tests.")

	ctx := context.Background()

	// Self-Healing Gauntlet Loop
	for iteration := 1; iteration <= MaxRetries; iteration++ {
		fmt.Printf("\n--- [The Gauntlet: Go] Iteration %d/%d ---\n", iteration, MaxRetries)

		// Tier 1: Fast Traps
		res := runCommand(ctx, "Tier 1: Fast Traps (ASan+UBSan)", "bash", "traps/sanitize_matrix.sh", "fast")
		if res.ExitCode != 0 {
			fmt.Printf("[!] Tier 1 Trap Triggered:\n%s\n", res.Stderr)
			continue
		}

		// Cartographer layout check
		res = runCommand(ctx, "The Cartographer: Layout Deltas", "traps/cartographer_delta")
		if res.ExitCode != 0 {
			// Try running via go run if binary not pre-built
			res = runCommand(ctx, "The Cartographer (Fallback)", "go", "run", "traps/cartographer_delta.go")
			if res.ExitCode != 0 {
				fmt.Println("[!] The Cartographer Detected Structural Layout Regression.")
				continue
			}
		}

		// Tier 2: Deep Sanitizers
		res = runCommand(ctx, "Tier 2: Concurrency & Deep Memory (TSan/MSan)", "bash", "traps/sanitize_matrix.sh", "matrix")
		if res.ExitCode != 0 {
			fmt.Println("[!] Tier 2 Trap Triggered.")
			continue
		}

		// Tier 3: The Mimic
		res = runCommand(ctx, "Tier 3: The Mimic (Mutation Score >= 90%)", "go", "run", "traps/mutation_gate.go")
		if res.ExitCode != 0 {
			fmt.Println("[!] The Mimic: Mutation score below threshold.")
			continue
		}

		// Tier 4: The Quartermaster
		res = runCommand(ctx, "Tier 4: The Quartermaster (Performance)", "go", "run", "traps/performance_auditor.go")
		if res.ExitCode != 0 {
			fmt.Println("[!] The Quartermaster: Budget exceeded.")
			continue
		}

		fmt.Println("\n*** SUCCESS: Code passed all Gauntlet traps! ***")
		fmt.Println("Waiting for The Overgod (Human) final elegance review and merge.")
		os.Exit(0)
	}

	fmt.Println("\n[DEADLOCK] Maximum retry iterations reached without passing all traps.")
	fmt.Println("Triggering Deadlock Diagnostic Analyst for The Overgod escalation...")
	os.Exit(2)
}
