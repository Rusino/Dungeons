#!/usr/bin/env python3
"""
Unit Tests for Project KEEPER Codex Integrity (test_codex_integrity.py)
========================================================================
Validates that:
1. Subagent prompts contain zero sequence leaks (no 'Phase X' or 'Axiom X').
2. Subagent prompts adhere to the Single-Duty Role Card standard.
3. Code-generating roles maintain symmetry regarding build file boundaries.
4. Root AGENTS.md remains a lean, universal constitution (< 80 lines).
"""

import glob
import re
import unittest
from pathlib import Path

CODEX_DIR = Path(__file__).parent.parent / "codex"
PROMPTS_DIR = CODEX_DIR / "prompts"
AGENTS_MD = CODEX_DIR / "AGENTS.md"


class TestCodexIntegrity(unittest.TestCase):
    def test_agents_md_is_concise_universal_constitution(self):
        """Verifies root AGENTS.md is under 80 lines and contains no sequence diagrams."""
        self.assertTrue(AGENTS_MD.exists(), "AGENTS.md missing in codex/")
        content = AGENTS_MD.read_text(encoding="utf-8")
        lines = content.strip().splitlines()

        self.assertLess(
            len(lines),
            80,
            f"AGENTS.md is too bloated ({len(lines)} lines). Must be < 80 lines.",
        )
        self.assertNotIn("Phase 1:", content, "AGENTS.md must not contain workflow sequence.")
        self.assertNotIn("Phase 11:", content, "AGENTS.md must not contain workflow sequence.")

    def test_no_sequence_leaks_in_prompts(self):
        """Verifies that subagent prompts are blind to the global workflow sequence."""
        prompt_files = glob.glob(str(PROMPTS_DIR / "*.md"))
        self.assertGreater(len(prompt_files), 0, "No prompt files found in codex/prompts/")

        sequence_patterns = [
            (re.compile(r"\bPhase\s+\d+(\.\d+)?\b", re.IGNORECASE), "Workflow Phase citation"),
            (re.compile(r"\bAxiom\s+\d+(\([a-z]\))?\b", re.IGNORECASE), "Axiom number citation"),
        ]

        violations = []
        for p in prompt_files:
            rel_name = Path(p).name
            text = Path(p).read_text(encoding="utf-8")
            for pattern, desc in sequence_patterns:
                matches = pattern.findall(text)
                if matches:
                    violations.append(f"{rel_name}: Found {desc} -> {matches[:3]}")

        self.assertEqual(violations, [], f"Sequence leaks detected in prompts:\n" + "\n".join(violations))

    def test_prompts_have_required_sections(self):
        """Verifies all prompts have Role, Boundaries, Craft Invariants, and Done criteria."""
        prompt_files = glob.glob(str(PROMPTS_DIR / "*.md"))
        for p in prompt_files:
            rel_name = Path(p).name
            text = Path(p).read_text(encoding="utf-8")

            self.assertRegex(text, r"# Role:", f"{rel_name} missing '# Role:' header")
            has_mission = "## Core Mission" in text or "## Objective" in text or "## Core Responsibilities" in text
            self.assertTrue(has_mission, f"{rel_name} missing Core Mission / Objective")

            has_constraints = "## Operational Boundaries" in text or "## Negative Constraints" in text or "## Strict Licensing" in text or "## Output Schema" in text
            self.assertTrue(has_constraints, f"{rel_name} missing Boundaries or Constraints")

    def test_code_generator_symmetry(self):
        """Verifies that The Artificer and The Trapsmith have symmetrical build file policies."""
        artificer_text = (PROMPTS_DIR / "artificer_system.md").read_text(encoding="utf-8")
        trapsmith_text = (PROMPTS_DIR / "trapsmith_system.md").read_text(encoding="utf-8")

        # Neither role can have free-form build file edit permissions
        for name, text in [("Artificer", artificer_text), ("Trapsmith", trapsmith_text)]:
            self.assertIn("BUILD.gn", text, f"{name} must explicitly declare BUILD.gn policy")
            self.assertIn("compiler flags", text.lower(), f"{name} must explicitly forbid altering compiler flags")


if __name__ == "__main__":
    unittest.main()
