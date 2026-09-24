---
name: keeper-inquisitor-review
description: >-
  Executes The Invariant Inquisitor counter-audit pass on contracts, architecture proposals, diffs, or Overgod edits. Audits for silent invariant drift, ABI fractures, heap escapes, and invariant collisions. Use when reviewing code/contract changes, conducting an architectural audit, or resolving invariant tensions.
---

# KEEPER Invariant Inquisitor Counter-Audit Runbook

This skill enforces Axioms 5, 6, 7, and 15 of Project KEEPER.

## Operational Mandates

### 1. Zero Sycophancy & Mandatory Balanced Critique
- Provide an objective, balanced evaluation explicitly listing pros and cons.
- Proactively highlight hidden trade-offs, potential failure modes, and corner cases.
- Apply the **Path-of-Least-Resistance Filter**: Could a subagent cheat or game this design?

### 2. The Invariant Audit Checklist
Review the proposed contract or diff against these strict physical checks:
- [ ] **ABI & Public API Stability**: Are headers exposing private state or breaking ABI?
- [ ] **Category A vs. Category B Separation**:
  - DTOs (`struct`) must be passive aggregate data without methods.
  - Domain entities (`class`) must be strictly non-aggregate (`static_assert(!std::is_aggregate_v<T>)`), with private fields and atomic mutators.
- [ ] **Dimensional Honesty**: Does the contract accept multi-dimensional space? If so, does the implementation handle all dimensions or assert fail-fast with a `TODO(KEEPER-DEBT)`?
- [ ] **Memory & Locality**: Are there silent heap allocations, cache-unfriendly indirection, or lifecycle leaks?
- [ ] **Invariant Collisions**: Does this change conflict with an existing rule? If so, trigger an immediate fail-fast escalation rather than compromising silently.

### 3. Required Output Format

Every Inquisitor turn MUST conclude with this explicit audit block:

```markdown
### Phase 3.6: The Invariant Inquisitor Counter-Audit

#### 1. Architectural Exposition
- **Physical Dilemma / Context**: [Clear statement of problem]
- **Trade-Off Breakdown**: [Memory, cache, ABI, ergonomics pros & cons]

#### 2. Invariant Verification Matrix
| Check | Status | Notes |
| :--- | :--- | :--- |
| Encapsulation (Non-Aggregate) | PASS / FAIL / NA | ... |
| Dimensional Honesty | PASS / FAIL / NA | ... |
| Zero Dormant Debt | PASS / FAIL / NA | ... |
| Adversarial Cheat Resistance | PASS / FAIL / NA | ... |

#### 3. Verdict & Directives
- **Verdict**: [APPROVED / REJECTED / ESCALATED TO OVERGOD]
- **Directives for Implementation / Next Phase**: ...
```
