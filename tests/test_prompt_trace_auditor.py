#!/usr/bin/env python3
"""
Unit Tests for Prompt Traceability & Executable-Footprint Auditor
(tests/test_prompt_trace_auditor.py)
=================================================================
Gate A defect-pinning unit tests enforcing:
1. Extraction and classification of prompt directives across codex/prompts.
2. Directives correctly partitioned into ENFORCED_TRACE, ACTIONABLE_TRACE_CANDIDATE,
   and SEMANTIC_UNVERIFIABLE.
3. Every ENFORCED_TRACE has non-empty 'current_mechanism'.
4. Every ACTIONABLE_TRACE_CANDIDATE has non-empty 'recommended_trace'.
5. Every SEMANTIC_UNVERIFIABLE has non-empty 'mitigation_strategy'.
6. format_markdown_report contains required category section markers.
"""

from pathlib import Path
import unittest

from traps.prompt_trace_auditor import (
    audit_prompt_file,
    audit_repository_prompts,
    format_markdown_report,
)


class TestPromptTraceAuditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent

    def test_audit_repository_prompts_counts_and_structure(self):
        """Verifies repository prompts auditing classifies directives into 3 non-empty categories."""
        report = audit_repository_prompts(self.repo_root)

        self.assertIn("enforced_count", report)
        self.assertIn("actionable_count", report)
        self.assertIn("semantic_count", report)
        self.assertIn("directives", report)

        self.assertGreater(
            report["enforced_count"],
            0,
            "Expected at least one ENFORCED_TRACE directive in repo prompts",
        )
        self.assertGreater(
            report["actionable_count"],
            0,
            "Expected at least one ACTIONABLE_TRACE_CANDIDATE directive in repo prompts",
        )
        self.assertGreater(
            report["semantic_count"],
            0,
            "Expected at least one SEMANTIC_UNVERIFIABLE directive in repo prompts",
        )

    def test_directive_fields_integrity(self):
        """Verifies each categorized directive has its mandatory traceability metadata."""
        report = audit_repository_prompts(self.repo_root)
        directives = report.get("directives", [])
        self.assertGreater(len(directives), 0, "No directives extracted from repository")

        for d in directives:
            category = d.get("category")
            self.assertIn(
                category,
                ("ENFORCED_TRACE", "ACTIONABLE_TRACE_CANDIDATE", "SEMANTIC_UNVERIFIABLE"),
                f"Invalid directive category: {category}",
            )

            if category == "ENFORCED_TRACE":
                current_mechanism = d.get("current_mechanism", "").strip()
                self.assertTrue(
                    bool(current_mechanism),
                    f"ENFORCED_TRACE missing non-empty 'current_mechanism': {d}",
                )
            elif category == "ACTIONABLE_TRACE_CANDIDATE":
                recommended_trace = d.get("recommended_trace", "").strip()
                self.assertTrue(
                    bool(recommended_trace),
                    f"ACTIONABLE_TRACE_CANDIDATE missing non-empty 'recommended_trace': {d}",
                )
            elif category == "SEMANTIC_UNVERIFIABLE":
                mitigation_strategy = d.get("mitigation_strategy", "").strip()
                self.assertTrue(
                    bool(mitigation_strategy),
                    f"SEMANTIC_UNVERIFIABLE missing non-empty 'mitigation_strategy': {d}",
                )

    def test_audit_single_prompt_file(self):
        """Verifies auditing an individual prompt file extracts structured directives."""
        trapsmith_file = self.repo_root / "codex" / "prompts" / "trapsmith_system.md"
        self.assertTrue(trapsmith_file.exists(), "trapsmith_system.md not found")

        directives = audit_prompt_file(trapsmith_file)
        self.assertIsInstance(directives, list)
        self.assertGreater(len(directives), 0, "Failed to extract directives from trapsmith_system.md")

        categories = {d.get("category") for d in directives}
        self.assertTrue(
            categories.issubset({"ENFORCED_TRACE", "ACTIONABLE_TRACE_CANDIDATE", "SEMANTIC_UNVERIFIABLE"})
        )

    def test_format_markdown_report_contains_categories(self):
        """Verifies markdown report string contains sections for all three categories."""
        report = audit_repository_prompts(self.repo_root)
        md = format_markdown_report(report)

        self.assertIsInstance(md, str)
        self.assertIn("ENFORCED_TRACE", md)
        self.assertIn("ACTIONABLE_TRACE_CANDIDATE", md)
        self.assertIn("SEMANTIC_UNVERIFIABLE", md)


if __name__ == "__main__":
    unittest.main()
