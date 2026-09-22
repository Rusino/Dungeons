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

| File / Folder | Tier | Description |
| :--- | :---: | :--- |
| **[`codex/AGENTS.md`](codex/AGENTS.md)** | **Tier 1** | **The Master Constitution**. Copy this file to any project root as `AGENTS.md` to instantly equip it with Project KEEPER rules. |
| **[`codex/TEXT_DOMAIN.md`](codex/TEXT_DOMAIN.md)** | **Tier 2** | **Universal Text Domain Codex**. Standardized invariants for interactive text, complex typography, BiDi selection, and layout. Copy to a text subsystem root as `INVARIANTS.md`. |
| **[`codex/prompts/`](codex/prompts/)** | **Roles** | **Canonical Subagent System Prompts**. The 13 frozen system prompts for all Legislative, Judicial, and Executive roles. |

---

## How to Adopt KEEPER in a New or Existing Project

### Option A: Automated 1-Command Bootstrap (Recommended)
Use the included [`init_project.sh`](init_project.sh) script to deploy the constitution, subagent prompts, and domain invariants in one step:

```bash
# Standard bootstrap:
~/Sources/Dungeons/init_project.sh /path/to/my-project

# Bootstrap with Text Domain invariants:
~/Sources/Dungeons/init_project.sh /path/to/my-project --domain text

# Bootstrap with live symlinks (auto-updates from Dungeons):
~/Sources/Dungeons/init_project.sh /path/to/my-project --domain text --link
```

### Option B: Manual Adoption
1. **Copy the Master Constitution**:
   ```bash
   cp ~/Sources/Dungeons/codex/AGENTS.md <your_project_root>/AGENTS.md
   ```
2. **Copy the Subagent Prompts**:
   ```bash
   mkdir -p <your_project_root>/.antigravity/prompts
   cp ~/Sources/Dungeons/codex/prompts/*.md <your_project_root>/.antigravity/prompts/
   ```
3. **Add Domain Invariants (if applicable)**:
   For text, typography, or editor projects:
   ```bash
   cp ~/Sources/Dungeons/codex/TEXT_DOMAIN.md <your_subsystem>/INVARIANTS.md
   ```
4. **Configure Local Build Toolchain**:
   See [`docs/BUILD_ADAPTERS.md`](docs/BUILD_ADAPTERS.md) for instructions on wiring GN/Ninja, CMake, Cargo, or Bazel into KEEPER's test gauntlet.

---

## Repository Structure

```
~/Sources/Dungeons/
├── README.md                                     # Project overview, adoption guide, directory map
├── KEEPER_INSTRUCTIONS_FOR_AGENTS.md             # Master Constitution (Root Copy)
├── init_project.sh                               # 1-command automated project bootstrapper
│
├── codex/                                        # Canonical Distribution Hub
│   ├── AGENTS.md                                 # Tier 1 Master Constitution
│   ├── TEXT_DOMAIN.md                            # Tier 2 Universal Text Domain Codex
│   └── prompts/                                  # Canonical Subagent System Prompts (13 roles)
│
├── docs/                                         # Architectural Documentation & RFCs
│   ├── BUILD_ADAPTERS.md                         # Wiring GN, CMake, Cargo, Bazel into Gauntlet
│   ├── architecture/
│   │   └── zero_trust_cpp_gauntlet_architecture.md # Foundational Gauntlet Whitepaper
│   └── rfcs/                                     # Architectural Proposals (RFCs)
│
├── .antigravity/                                 # Orchestration & Agent Tooling
│   ├── gauntlet_graph.py                         # Master execution graph
│   └── prompts/                                  # Canonical subagent role prompts
│
├── traps/                                        # Reference Verification Traps (CMake sample)
│   ├── sanitize_matrix.sh                        # Multi-pass sanitizer runner (ASan, TSan, MSan)
│   ├── mutation_gate.py                          # Mutation testing auditor
│   └── cartographer_delta.py                     # Metric delta comparator
│
├── src/                                          # Reference C++ HarfBuzz Engine (CMake sample)
└── tests/                                        # Reference Test Suites
```
