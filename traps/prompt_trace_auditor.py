#!/usr/bin/env python3
"""
Prompt Traceability & Executable-Footprint Auditor (traps/prompt_trace_auditor.py)
==================================================================================
Audits prompt files in codex/AGENTS.md, codex/TEXT_DOMAIN.md, and codex/prompts/*.md
(or a specified root directory). Extracts normative directives and classifies them
into:
  1. ENFORCED_TRACE (with 'current_mechanism')
  2. ACTIONABLE_TRACE_CANDIDATE (with 'recommended_trace')
  3. SEMANTIC_UNVERIFIABLE (with 'mitigation_strategy')

Provides:
  - audit_prompt_file(file_path: Path) -> List[Dict[str, Any]]
  - audit_repository_prompts(root_dir: Path) -> Dict[str, Any]
  - format_markdown_report(report: Dict[str, Any]) -> str
  - main() CLI supporting --root, --json-out, --markdown-out
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# Pattern to identify directives in markdown bullet points or numbered lists
DIRECTIVE_PATTERN = re.compile(
    r"^(?:[\*\-\+]|\d+\.)\s+(.*)",
    re.MULTILINE,
)

# Normative trigger words
NORMATIVE_KEYWORDS = [
    "ALLOWED",
    "FORBIDDEN",
    "MUST",
    "NEVER",
    "PROHIBITED",
    "ASSERT",
    "static_assert",
    "TODO(KEEPER-DEBT",
    "Strictly",
    "strictly",
    "Zero",
    "zero",
    "Reject",
    "reject",
]


def _is_normative_line(line: str) -> bool:
    """Checks whether a line has normative directive strength."""
    stripped = line.strip()
    if not stripped:
        return False
    for kw in NORMATIVE_KEYWORDS:
        if kw in stripped:
            return True
    return False


def _classify_directive(raw_text: str, file_path: Path) -> Dict[str, Any]:
    """
    Classifies an extracted directive text into:
      ENFORCED_TRACE, ACTIONABLE_TRACE_CANDIDATE, or SEMANTIC_UNVERIFIABLE.
    Assigns current_mechanism, recommended_trace, or mitigation_strategy accordingly.
    """
    text = raw_text.strip()
    clean = text.replace("**", "").replace("`", "").strip()

    # 1. AGENTS.md Constitution checks
    if "never be authored in the same context window" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "KeeperRunner isolated subagent dispatch and keeper_hook.py role boundary interceptor.",
        }

    if "composed strictly in English" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "UTF-8 character script check verifying zero non-English prose in formal artifacts and code.",
        }

    # 2. Cartographer metric verifications
    if "0.0000% deviation" in clean or "Compare glyph IDs, cluster mappings, float advances" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "traps/cartographer_delta.py structural float metric comparison against baseline.",
        }

    # 3. Scavenger licensing and static analysis
    if "SPDX Whitelist" in clean or any(lic in clean for lic in ["GPL", "AGPL", "LGPL"]) or "-Wunreachable-code" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "License classifier and compiler -Wunreachable-code diagnostic check.",
        }

    # 4. Oracle clearance and debt tracking
    if "deferred unit test case in tests/" in clean or "zero drift against canonical upstream codex" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "scan_debt.py deferred trap verifier and test_codex_integrity.py.",
        }

    # 5. Inquisitor Mechanical Git Triplet
    if "Mechanical Git Triplet" in clean or ("atomically modify:" in clean and "INVARIANTS.md" in clean):
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Git commit/diff check verifying bugfix commits atomically touch src/**, tests/**, and INVARIANTS.md.",
        }

    # 6. Quartermaster zero-allocation hot paths and spans
    if "Zero-Allocation Hot Path" in clean or "malloc, new, or std::vector" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "traps/performance_auditor.py allocation budget gate and KeeperRunner.check_code_traces.",
        }

    if "std::span" in clean and "std::vector" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Header return-type scanner verifying functions return std::span instead of heap std::vector.",
        }

    # 7. Mimic mutation rules
    if (
        "No assert(false)" in clean
        or "No premature early return" in clean
        or "No syntax corruptions" in clean
        or "Boundary Flips" in clean
        or "Coordinate & Spatial Inversions" in clean
        or "Off-by-One Boundary Shifts" in clean
        or "Topological Inversions" in clean
    ):
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "traps/mutation_gate.py AST semantic mutator and kill matrix.",
        }

    # 8. Operational Boundaries (ALLOWED / FORBIDDEN)
    if clean.startswith("ALLOWED:") or clean.startswith("FORBIDDEN:") or "Operational Boundaries" in clean:
        # Check if backed by KeeperRunner scope guard / breakers / rollback
        if any(target in clean for target in [
            "src/**",
            "include/**",
            "tests/**",
            "fuzz/**",
            "AGENTS.md",
            "INVARIANTS.md",
            "commit mutations to git",
            "reverted after test execution",
            "modifying, softening, or pruning constitutional rules",
        ]):
            return {
                "text": text,
                "category": "ENFORCED_TRACE",
                "current_mechanism": "KeeperRunner.check_forbidden_paths scope guard, _rollback_working_tree, and keeper_hook.py pre_tool_use interceptor.",
            }
        elif "BUILD.gn" in clean and "sources" in clean:
            return {
                "text": text,
                "category": "ACTIONABLE_TRACE_CANDIDATE",
                "recommended_trace": "Git diff patch AST checker verifying that any modification to BUILD.gn strictly appends to the 'sources' list.",
            }
        elif "BUILD.gn" in clean:
            return {
                "text": text,
                "category": "ENFORCED_TRACE",
                "current_mechanism": "KeeperRunner.check_forbidden_paths scope guard for BUILD.gn flag tampering.",
            }
        else:
            return {
                "text": text,
                "category": "ACTIONABLE_TRACE_CANDIDATE",
                "recommended_trace": f"Operational boundary checker enforcing rule: '{clean[:80]}...'",
            }

    # 9. Disallowed code constructs
    if "reinterpret_cast" in clean or "#pragma" in clean or "goto" in clean or "malloc" in clean or "free(" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "KeeperRunner.check_code_traces disallowed construct regex scanner.",
        }

    if "TODO(KEEPER-DEBT" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "KeeperRunner.check_code_traces unmarked TODO scanner and keeper-debt-audit skill.",
        }

    if ("for (" in clean or "while (" in clean or "iteration loops" in clean) and ("header" in clean.lower() or "include" in clean.lower()):
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "KeeperRunner.check_code_traces header iteration loop check.",
        }

    if "SKIP_IF" in clean or "GTEST_SKIP" in clean or "#define private public" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "KeeperRunner.check_code_traces test-skip and private-hack filter.",
        }

    if "compile cleanly" in clean.lower() or "compiles cleanly" in clean.lower() or "-Werror" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "Automated build gate checking compiler return code 0 under -Werror.",
        }

    if "FAILS" in clean and "defect" in clean.lower():
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "KeeperRunner.evaluate_gate Gate A defect pinning exit code verification.",
        }

    if "PASSES" in clean or "pass cleanly" in clean.lower() or "all target unit tests pass" in clean.lower():
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "KeeperRunner.evaluate_gate Gate B unit test runner verification.",
        }

    if "Anti-Regression Corpus Mandate" in clean or "regression seed" in clean or "fuzz/corpus" in clean:
        return {
            "text": text,
            "category": "ENFORCED_TRACE",
            "current_mechanism": "Corpus check in init_keeper.sh and traps/fuzz_gate.py executing all seeds in fuzz/corpus/.",
        }

    # 10. Actionable Trace Candidates
    if "loop_guard" in clean or ("while" in clean and "guard" in clean.lower()):
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Static analysis check (Clang-Tidy or AST scanner) asserting that all while loops declare and increment a loop_guard watchdog variable.",
        }

    if "is_aggregate_v" in clean or "Strict Type Bifurcation" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Header type contract scanner verifying static_assert(std::is_aggregate_v<T>) for struct DTOs and static_assert(!std::is_aggregate_v<T>) for class entities.",
        }

    if "Zero raw owning pointers" in clean or "raw owning pointers" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Clang-Tidy modernize-use-auto/smart-ptr check or AST grep verifying zero unadorned owning raw pointer declarations in header/source fields.",
        }

    if "Ghost Tests" in clean or "Dual-Contract" in clean or "State and Geometry Co-Verification" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Mutation gate (traps/mutation_gate.py) and AST assertion inspector verifying tests assert both logical indices and spatial bounding boxes.",
        }

    if "Zero Silent Degradation" in clean or "No-Tofu Law" in clean or ".notdef" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Text rendering test assertion verifying glyph ID != 0 (.notdef) across all printable UTF-8 codepoints in input runs.",
        }

    if "Control Code Zero-Width" in clean or "Control characters" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Layout pipeline unit test asserting that U+200B-U+200F and control characters produce advance width == 0.0.",
        }

    if "Atomic Grapheme Cluster Unification" in clean or "combining marks" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "UAX #29 boundary compliance test verifying directional navigation steps across full extended grapheme clusters.",
        }

    if "Single-Keystroke Atomic Navigation" in clean or "Hit-Testing Affinity" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Deterministic navigation matrix test asserting caret index jumps whole grapheme byte lengths per navigation event.",
        }

    if "Soft-Wrap Boundary Singularity" in clean or "Geometric Affinity" in clean or "Step-Through Horizontal Navigation" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Soft-wrap boundary test verifying upstream/downstream affinity caret coordinates at shared line break indices.",
        }

    if "Differential Reference Invariant" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Differential fuzz harness comparing optimized structure against naive reference implementation.",
        }

    if "Crash Minimization" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Automated crash minimizer trap invoking -minimize_crash=1 upon libFuzzer artifact discovery.",
        }

    if "Indivisible Boundary Bombardment" in clean or "Bounded Execution & Determinism" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": "Fuzz harness property assertion verifying deterministic execution within iteration timeout limit.",
        }

    # 11. Semantic unverifiable directives
    if any(phrase in clean.lower() for phrase in [
        "peer-engineering",
        "sycophancy",
        "overgod axiom",
        "intent",
        "aesthetic",
        "architectural elegance",
        "realistic ingress",
        "comprehension",
        "pros and cons",
        "balanced evaluation",
        "definition of done",
        "safe refactoring",
        "internal private members",
        "zero unneeded dynamic heap allocations",
        "external abi freeze",
    ]):
        return {
            "text": text,
            "category": "SEMANTIC_UNVERIFIABLE",
            "mitigation_strategy": "Adversarial cross-agent Inquisitor review, Overgod architectural sign-off, or strict encapsulation limiting public API exposure.",
        }

    # Catch-all
    if "FORBIDDEN" in clean or "NEVER" in clean or "PROHIBITED" in clean:
        return {
            "text": text,
            "category": "ACTIONABLE_TRACE_CANDIDATE",
            "recommended_trace": f"Automated AST or regex trace scanner enforcing rule: '{clean[:80]}...'",
        }

    return {
        "text": text,
        "category": "SEMANTIC_UNVERIFIABLE",
        "mitigation_strategy": "Subject to Overgod review and adversarial prompt auditing.",
    }


def audit_prompt_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parses a single prompt markdown file and extracts categorized directives.
    Tracks fenced code blocks (skipping all code lines) and skips bare title-only bullets ending with ':'.
    """
    if not file_path.exists():
        return []

    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    directives = []
    in_relevant_section = False
    in_code_block = False
    current_section = ""

    for line in lines:
        stripped = line.strip()

        # Track fenced code blocks and skip all lines inside
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            # Sections that inherently specify directives
            if any(h in current_section.lower() for h in [
                "boundary", "boundaries", "invariant", "invariants", "standard", "standards",
                "law", "laws", "constitution", "mandate", "mission", "definition of done",
                "rules", "directives"
            ]):
                in_relevant_section = True
            else:
                in_relevant_section = False
            continue

        # Check list item / bullet
        m = DIRECTIVE_PATTERN.match(stripped)
        if m:
            item_text = m.group(1).strip()
            clean_item = item_text.replace("**", "").replace("`", "").strip()

            # Skip bare title-only bullets ending with ':' and having fewer than 6 words
            if clean_item.endswith(":") and len(clean_item.split()) < 6:
                continue

            if in_relevant_section or _is_normative_line(item_text):
                classified = _classify_directive(item_text, file_path)
                classified["source_file"] = str(file_path)
                classified["section"] = current_section
                directives.append(classified)
        elif in_relevant_section and _is_normative_line(stripped):
            clean_item = stripped.replace("**", "").replace("`", "").strip()
            if clean_item.endswith(":") and len(clean_item.split()) < 6:
                continue
            classified = _classify_directive(stripped, file_path)
            classified["source_file"] = str(file_path)
            classified["section"] = current_section
            directives.append(classified)

    return directives


def audit_repository_prompts(root_dir: Path) -> Dict[str, Any]:
    """
    Audits codex/AGENTS.md, codex/TEXT_DOMAIN.md, and codex/prompts/*.md in root_dir.
    Returns counts and directives list.
    """
    root_path = Path(root_dir).resolve()
    target_files = []

    # Check canonical locations
    agents_md = root_path / "codex" / "AGENTS.md"
    if not agents_md.exists():
        agents_md = root_path / "AGENTS.md"
    if agents_md.exists():
        target_files.append(agents_md)

    text_domain_md = root_path / "codex" / "TEXT_DOMAIN.md"
    if not text_domain_md.exists():
        text_domain_md = root_path / "INVARIANTS.md"
    if text_domain_md.exists():
        target_files.append(text_domain_md)

    prompts_dir = root_path / "codex" / "prompts"
    if not prompts_dir.exists():
        prompts_dir = root_path / ".antigravity" / "prompts"
    if prompts_dir.exists():
        target_files.extend(sorted(prompts_dir.glob("*.md")))

    all_directives: List[Dict[str, Any]] = []
    for tf in target_files:
        all_directives.extend(audit_prompt_file(tf))

    enforced_count = sum(1 for d in all_directives if d.get("category") == "ENFORCED_TRACE")
    actionable_count = sum(1 for d in all_directives if d.get("category") == "ACTIONABLE_TRACE_CANDIDATE")
    semantic_count = sum(1 for d in all_directives if d.get("category") == "SEMANTIC_UNVERIFIABLE")

    return {
        "enforced_count": enforced_count,
        "actionable_count": actionable_count,
        "semantic_count": semantic_count,
        "total_count": len(all_directives),
        "directives": all_directives,
    }


def format_markdown_report(report: Dict[str, Any]) -> str:
    """
    Formats the audit report as a structured Markdown document.
    """
    enforced = [d for d in report.get("directives", []) if d.get("category") == "ENFORCED_TRACE"]
    actionable = [d for d in report.get("directives", []) if d.get("category") == "ACTIONABLE_TRACE_CANDIDATE"]
    semantic = [d for d in report.get("directives", []) if d.get("category") == "SEMANTIC_UNVERIFIABLE"]

    md_lines = [
        "# Project KEEPER: Prompt Traceability & Executable-Footprint Dossier",
        "",
        "## Executive Summary",
        f"- **Total Directives Audited**: {report.get('total_count', 0)}",
        f"- **ENFORCED_TRACE**: {report.get('enforced_count', 0)} (backed by physical compilers/hooks/gates)",
        f"- **ACTIONABLE_TRACE_CANDIDATE**: {report.get('actionable_count', 0)} (prose rules convertible to disk checks)",
        f"- **SEMANTIC_UNVERIFIABLE**: {report.get('semantic_count', 0)} (inherently semantic or design evaluations)",
        "",
        "---",
        "",
        "## 1. ENFORCED_TRACE Directives",
        "Directives guaranteed by physical circuit breakers, exit codes, or disk checks:",
        "",
        "| Source | Section | Directive | Current Mechanism |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for d in enforced:
        src = Path(d.get("source_file", "")).name
        sec = d.get("section", "")
        txt = d.get("text", "").replace("|", "\\|")
        mech = d.get("current_mechanism", "").replace("|", "\\|")
        md_lines.append(f"| `{src}` | {sec} | {txt} | {mech} |")

    md_lines.extend([
        "",
        "---",
        "",
        "## 2. ACTIONABLE_TRACE_CANDIDATE Directives",
        "Normative prose directives that can and should be hardened into physical disk checks:",
        "",
        "| Source | Section | Directive | Recommended Trace Implementation |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for d in actionable:
        src = Path(d.get("source_file", "")).name
        sec = d.get("section", "")
        txt = d.get("text", "").replace("|", "\\|")
        trace = d.get("recommended_trace", "").replace("|", "\\|")
        md_lines.append(f"| `{src}` | {sec} | {txt} | {trace} |")

    md_lines.extend([
        "",
        "---",
        "",
        "## 3. SEMANTIC_UNVERIFIABLE Directives",
        "Directives not reducible to syntax checks, mitigated via adversarial audits or Overgod review:",
        "",
        "| Source | Section | Directive | Mitigation Strategy |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for d in semantic:
        src = Path(d.get("source_file", "")).name
        sec = d.get("section", "")
        txt = d.get("text", "").replace("|", "\\|")
        strat = d.get("mitigation_strategy", "").replace("|", "\\|")
        md_lines.append(f"| `{src}` | {sec} | {txt} | {strat} |")

    md_lines.append("")
    return "\n".join(md_lines)


def main():
    parser = argparse.ArgumentParser(description="KEEPER Prompt Traceability Auditor")
    parser.add_argument("--root", default=".", help="Root directory of repository")
    parser.add_argument("--json-out", default=None, help="Output JSON path")
    parser.add_argument("--markdown-out", default=None, help="Output Markdown path")
    args = parser.parse_args()

    root_dir = Path(args.root).resolve()
    report = audit_repository_prompts(root_dir)
    md_report = format_markdown_report(report)

    if args.json_out:
        out_p = Path(args.json_out).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.markdown_out:
        out_m = Path(args.markdown_out).resolve()
        out_m.parent.mkdir(parents=True, exist_ok=True)
        out_m.write_text(md_report, encoding="utf-8")

    print(md_report)


if __name__ == "__main__":
    main()
