# Project KEEPER: Keeping End-to-End Paranoia in Engine Reliability

Project KEEPER is an autonomous, zero-trust engineering framework designed for mission-critical software engines. It shifts the human engineer to the role of **Architectural Arbitrator ("The Overgod")**, while adversarial AI subagents and deterministic verification gauntlets autonomously write specifications, implement logic, attack boundary conditions, and enforce system invariants.

---

## The Two-Tier Invariant Architecture

Project KEEPER operates under a strict two-tier governance model:

1. **Tier 1: Master Constitution ([`codex/AGENTS.md`](codex/AGENTS.md))**:
   - Universal, domain-agnostic operational laws governing agent containment, zero-trust separation of concerns, the Tripartite Governance Model (Executive, Judicial, Legislative branches), verification gates (Gate A / Gate B), dynamic investigation budgets, and execution watchdogs.
2. **Tier 2: Local Domain Codices (`INVARIANTS.md` in Subsystems)**:
   - Specific domain invariants for specialized engineering areas (e.g. typography, GPU pipelines, audio synchronization, database engines).
   - A standardized template for text and typography engines is provided at [`codex/TEXT_DOMAIN.md`](codex/TEXT_DOMAIN.md).

---

## The Distribution Hub (`codex/`)

The [`codex/`](codex/) directory contains the canonical operational codices ready to be deployed to target repositories:

| File | Tier | Description |
| :--- | :---: | :--- |
| **[`codex/AGENTS.md`](codex/AGENTS.md)** | **Tier 1** | **The Master Constitution**. Copy this file to any project root as `AGENTS.md` to instantly equip it with Project KEEPER rules. |
| **[`codex/TEXT_DOMAIN.md`](codex/TEXT_DOMAIN.md)** | **Tier 2** | **Universal Text Domain Codex**. Standardized invariants for interactive text, complex typography, BiDi selection, and layout. Copy to a text subsystem root as `INVARIANTS.md`. |

---

## How to Adopt KEEPER in a New Project

1. **Copy the Master Constitution**:
   ```bash
   cp ~/Sources/Dungeons/codex/AGENTS.md <your_project_root>/AGENTS.md
   ```
2. **Add Domain Invariants (if applicable)**:
   For text, typography, or editor projects:
   ```bash
   cp ~/Sources/Dungeons/codex/TEXT_DOMAIN.md <your_subsystem>/INVARIANTS.md
   ```
3. **Engage with The Overgod**:
   AI agents operating in that repository will immediately bind to the Two-Tier Invariant Architecture and follow the 21 Core Axioms.

---

## Repository Structure

```
~/Sources/Dungeons/
├── README.md                                     # Project overview, adoption guide, directory map
├── KEEPER_INSTRUCTIONS_FOR_AGENTS.md             # Master Constitution (Root Copy)
│
├── codex/                                        # Canonical Distribution Hub
│   ├── AGENTS.md                                 # Tier 1 Master Constitution
│   └── TEXT_DOMAIN.md                            # Tier 2 Universal Text Domain Codex
│
├── docs/                                         # Architectural Documentation & RFCs
│   ├── architecture/
│   │   └── zero_trust_cpp_gauntlet_architecture.md # Foundational Gauntlet Whitepaper
│   └── rfcs/                                     # Architectural Proposals (RFCs)
│
├── .antigravity/                                 # Orchestration & Agent Tooling
│   ├── gauntlet_graph.py                         # Master execution graph
│   └── prompts/                                  # Canonical subagent role prompts
│
├── traps/                                        # Deterministic Verification Traps
│   ├── sanitize_matrix.sh                        # Multi-pass sanitizer runner (ASan, TSan, MSan)
│   ├── mutation_gate.py                          # Mutation testing auditor
│   └── cartographer_delta.py                     # Metric delta comparator
│
├── src/                                          # Prototype C++ Engine Components
└── tests/                                        # Verification Test Suites
```
