---
name: keeper-debt-audit
description: >-
  Audits codebase for defensive debt markers, validates TODO(KEEPER-DEBT) syntax, verifies accompanying deferred traps, and formats the formal Defensive Debt Ledger. Use when performing milestone clearance, pre-handoff verification, or checking for dormant debt.
---

# KEEPER Defensive Debt Audit Runbook

This skill enforces Axiom 12 (**The Defensive Debt & TODO Resolution Protocol / Prohibition of Dormant Debt**) of Project KEEPER.

## Objectives
1. Ensure **Zero Dormant Debt**: No unformatted or anonymous `TODO` stubs exist in modified packages.
2. Validate semantic formatting of all explicit debt markers: `TODO(KEEPER-DEBT: Invariant-<ID>): <statement>`.
3. Verify the **Deferred Trap Requirement**: Every debt marker must have an accompanying deferred test in the test suite documenting expected behavior and failure conditions.
4. Generate the formal **Active Defensive Debt Ledger** and populate the **Forward Backlog** for The Overgod.

---

## Operational Steps

### 1. Execute the Debt Scanner
Run the deterministic debt audit script from the repository root:

```bash
python3 .agents/skills/keeper-debt-audit/scripts/scan_debt.py
```

Optional flags:
- `--staged-only`: Restrict scan to git staged files.
- `--fail-on-anonymous`: Exit with code 1 if anonymous `// TODO:` or `// FIXME:` comments are detected.

### 2. Manual Verification Checklist
If inspecting files manually or reviewing script output:
- [ ] **Check Marker Syntax**: Every debt comment must strictly match:
  `TODO(KEEPER-DEBT: Invariant-<ID>): <Precise statement of deferred capability>`
- [ ] **Detect Illegal Debt**: Flag any occurrences of `// TODO: fix later`, `// HACK`, or unstructured comments. These constitute an immediate protocol violation.
- [ ] **Verify Deferred Traps**: For each identified `TODO(KEEPER-DEBT)`, locate the corresponding test case in `tests/` or `traps/` that explicitly tests the boundary condition or assertion.

### 3. Generate the Active Defensive Debt Ledger
Format findings using this exact markdown table in the dialogue:

```markdown
### Active Defensive Debt Ledger

| Invariant ID | File:Line | Deferred Capability | Accompanying Trap / Test | Status |
| :--- | :--- | :--- | :--- | :--- |
| Invariant-11 | `src/model.cpp:142` | Multi-line span selection support | `tests/test_selection.cpp:88` | Active (Tracked) |
```

### 4. Milestone Clearance Criteria
- A subsystem **cannot** be declared feature-complete or milestone-ready if unresolved debt markers exist without an approved Overgod exemption.
- Inject all active debt items into the **Forward Backlog** presented to The Overgod during Phase 10 (Interactive Hand-off).
