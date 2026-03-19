---
name: verilog-rtl-workflow
description: "Use this skill when the user describes hardware behavior in natural language and needs a strict RTL delivery flow: derive a structured spec, plan the architecture, implement RTL, run lint, write a testbench, and complete behavioral simulation. Trigger it for module-level digital design tasks, interface/protocol decomposition, combinational or sequential RTL coding, TB scaffolding, waveform-driven debug, and regression-style validation with tools such as iverilog, verilator, or vvp."
---

# Verilog RTL Workflow

## When to use

Use this skill when the user starts from a natural-language hardware requirement and wants a strict delivery flow:

1. Structured design contract
2. Architecture plan
3. RTL
4. Lint
5. Testbench
6. Behavioral simulation

Do not skip or reorder stages unless the user explicitly asks to do so.

## Global rules

- Language choice is mandatory: use the user-specified language exactly; if unspecified, default to plain Verilog and state that assumption explicitly
- Do not write final RTL before the design contract and architecture plan are internally consistent
- Do not move to TB authoring while unresolved lint findings still indicate likely RTL correctness issues
- Default waveform output path is `build/<tb_module>.vcd`
- Prefer the smallest correct implementation that satisfies the requirement

Read extra references only when needed:

- [analysis checklist](./references/analysis-checklist.md)
- [architecture plan](./references/architecture-plan.md)
- [language rules](./references/language-rules.md)
- [simulation conventions](./references/simulation-conventions.md)
- [contract template](./references/stage-1-contract-template.md)
- [architecture template](./references/stage-2-architecture-template.md)
- [testbench patterns](./references/testbench-patterns.md)
- [Verilog RTL template](./references/verilog-rtl-template.v)
- [Verilog TB template](./references/verilog-testbench-template.v)

## Stage flow

### Stage 1. Structured design contract

Convert the natural-language request into a structured spec before writing code.

Required output:

- Functional summary
- Interface summary
- Selected language
- Assumptions
- Corner cases and priority rules
- Verification targets

Exit condition:

- Module boundary, reset behavior, timing intent, corner cases, and language choice are explicit enough to review

### Stage 2. Architecture plan

Produce a compact architecture plan before writing RTL.

Required output:

- Block type: combinational or sequential
- Main datapath and control structure
- State list when FSMs exist
- Latency/throughput intent
- Reset and idle behavior
- Rationale for tricky choices

Exit condition:

- Every user-visible behavior from Stage 1 is mapped to a concrete implementation strategy

### Stage 3. RTL

Implement synthesizable RTL that matches the architecture plan.

Required output:

- Final RTL source
- File naming and syntax aligned with the selected language

Exit condition:

- RTL is ready for lint and does not rely on exploratory placeholders

### Stage 4. Lint

Run lint before expanding TB effort.

Required output:

- Exact lint command
- Findings summary
- Fixes applied, if any

Exit condition:

- No unresolved lint findings that plausibly indicate RTL correctness issues

### Stage 5. Testbench

Write a self-checking TB tied to Stage 1 verification targets.

Required output:

- TB source
- Stable stimulus/checking strategy
- Default wave dump to `build/<tb_module>.vcd`

Exit condition:

- TB covers reset, nominal path, boundary cases, and defined corner cases

### Stage 6. Simulation

Run behavioral simulation and debug until the target checks pass.

Required output:

- Exact simulation command
- Pass/fail result
- Waveform output path
- Remaining risk, if any

Exit condition:

- Targeted scenarios pass, or the remaining blocker is explicitly identified

## Deliverable shape

Unless the user asks otherwise, final delivery should include:

- Structured requirement summary
- Architecture summary
- RTL
- TB
- Lint command and result
- Simulation command and result
- Waveform path
- Assumptions and remaining risk
