---
name: keeper-prompt-trace-audit
description: >-
  Audits repository and subagent prompt specifications for physical traceability, verifies mapping of prose rules to deterministic compilers/traps/hooks, and outputs the Executable-Footprint Dossier. Use when verifying agent prompt integrity or detecting untracked semantic drift.
---

# KEEPER Prompt Traceability & Executable-Footprint Audit Runbook

This skill enforces Axiom 4 (**Zero-Trust Physical Verification**) and Axiom 10 (**Subagent Prompt Isolation & Containment**) of Project KEEPER.

## Objectives
1. Extract all normative directives from `codex/AGENTS.md`, `codex/TEXT_DOMAIN.md`, and `codex/prompts/*.md`.
2. Classify directives into:
   - `ENFORCED_TRACE`: Backed by compiler checks, exit codes, circuit breakers, or lifecycle hooks.
   - `ACTIONABLE_TRACE_CANDIDATE`: Prose instructions that should be transformed into physical disk checks.
   - `SEMANTIC_UNVERIFIABLE`: High-level semantic invariants requiring cross-agent review or Overgod arbitration.
3. Validate metadata completeness (`current_mechanism`, `recommended_trace`, `mitigation_strategy`).
4. Generate the **Prompt Traceability Dossier**.

---

## Operational Steps

### 1. Execute the Prompt Trace Auditor
Run the auditor from the repository root:

```bash
python3 traps/prompt_trace_auditor.py --root . --json-out .keeper/prompt_trace_report.json --markdown-out .keeper/prompt_trace_report.md
```

Or via the state machine runner:
```bash
./keeper --audit-prompts
```

### 2. Review Actionable Candidates
Inspect `.keeper/prompt_trace_report.md` for `ACTIONABLE_TRACE_CANDIDATE` directives. Prioritize converting high-frequency prose boundaries into deterministic regex or AST checks in `keeper_runner.py` or `traps/keeper_hook.py`.

### 3. Report Structure
Ensure the markdown output satisfies the standard three-category structure:
- `## 1. ENFORCED_TRACE Directives`
- `## 2. ACTIONABLE_TRACE_CANDIDATE Directives`
- `## 3. SEMANTIC_UNVERIFIABLE Directives`
