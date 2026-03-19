---
name: sta-subagent-flow
description: Generate a default `constraint/default.sdc` for a specified RTL top module by inspecting the RTL interface, run `make sta` in a Yosys/iEDA style synthesis and STA project, then analyze `result/` reports and produce key timing, area, power, and constraint findings with concrete timing-closure suggestions. Use when Codex is asked to prepare SDC for an RTL module, execute the local `make sta` flow, summarize STA results, or propose synthesis/STA remediation actions.
---

# STA Flow

Use this skill to drive a local RTL synthesis and STA loop with the repository's `make sta` entry.

Keep the workflow strict:
1. Confirm the design root and top module.
2. Inspect `rtl/` and infer the top-level interface before writing SDC.
3. Generate `constraint/default.sdc` with explicit assumptions.
4. Run `make sta`.
5. Read `result/` artifacts and report key metrics, violations, and next actions.

## Workflow

### 1. Confirm inputs

Prefer these inputs from the user:
- design root
- top module name
- clock port name
- target frequency in MHz

If some inputs are missing, infer them locally:
- Read the local `Makefile` first.
- If the top module is missing, inspect `DESIGN` in the make variables.
- If the clock port is missing, inspect the RTL top interface and choose the most likely clock port.
- If the frequency is missing, use the flow default from the environment or `Makefile`.

Always state inferred assumptions explicitly in the response.

### 2. Use subagents when available

If the current session explicitly permits subagents, prefer splitting the work:
- Use one subagent to inspect the RTL top module and identify clock, reset, input, and output ports.
- Use another subagent to inspect `result/` artifacts after `make sta` and extract key metrics and violations.

Keep ownership disjoint. Do not ask one subagent to both infer constraints and interpret reports if the work can be split cleanly.

### 3. Generate SDC

Use the bundled script:

```bash
python3 scripts/run_sta_flow.py --design-home <design-root> --top <top-module>
```

The script:
- scans `rtl/` for the target module
- supports ANSI and common non-ANSI top-level port declarations
- infers interface directions and bus widths
- detects likely clock, reset, test, and async-style ports
- writes `constraint/default.sdc`
- runs `make sta`
- parses `result/` reports
- emits a Markdown summary

Use script flags when needed:

```bash
python3 scripts/run_sta_flow.py \
  --design-home <design-root> \
  --top <top-module> \
  --clock-port <clk_name> \
  --clock-freq-mhz <freq> \
  --io-delay-ratio 0.2 \
  --async-inputs rst_n,irq \
  --input-delay-exclude scan_en,test_mode \
  --output-delay-exclude debug_bus
```

### 4. Review generated constraints

Check that the generated SDC matches the RTL intent:
- The chosen clock port must be a real top-level input.
- Reset ports must not be treated as synchronous data ports by default.
- Test, scan, debug, and user-marked async inputs should usually not receive default input delay constraints.
- All non-clock outputs should receive output delay constraints unless the interface is intentionally unconstrained.

If the interface is protocol-heavy or multi-clock, do not pretend the default SDC is complete. Say that the generated SDC is only a safe starting point and list what is still missing.

### 5. Analyze reports

Prioritize these files under `result/<design>-<freq>MHz/`:
- `<design>.rpt`
- `sta.log`
- `synth_stat.txt`
- `synth_check.txt`
- `<design>.pwr`
- `<design>.fanout`
- `<design>.trans`
- `<design>.cap`

Always report:
- selected top module, clock port, and target frequency
- which ports were treated as reset, async, test, data input, and unconstrained output
- setup WNS and TNS
- hold WNS and TNS if present
- top critical endpoint for setup and hold
- best reported achievable frequency if present
- total cell count and chip area
- sequential area ratio if present
- total power if present
- unconstrained ports or synthesis check problems

### 6. Give remediation advice

Map findings to actions:
- Unconstrained ports: add `set_input_delay`, `set_output_delay`, false paths, or multicycle paths based on interface intent.
- Suspected bootstrap-only constraints: call out that the current SDC is only a first-pass model.
- Negative setup slack: reduce target frequency, pipeline long combinational cones, restructure arithmetic/control, or resize/buffer the path.
- Negative hold slack: add delay cells, revisit clock gating and short paths, or constrain min-delay intent correctly.
- Slew/cap/fanout issues: buffer, duplicate drivers, or reduce fanout/load.
- Large sequential area ratio: check over-pipelining or unnecessary state duplication.
- Synthesis check problems: fix RTL structural issues before iterating timing.

Do not give generic advice only. Tie each recommendation to a concrete report symptom.

## Files To Read

Read these only when needed:
- [report-heuristics.md](references/report-heuristics.md) for advice mapping and assumptions

## Output Contract

In the final response:
- state whether SDC was generated or updated
- state whether `make sta` completed successfully
- if it failed, name the failure stage explicitly, such as `rtl_discovery`, `rtl_parse`, `constraint_inference`, `synthesis`, or `sta_runtime`
- cite the summary file path
- list the key metrics
- list concrete remediation actions
- call out assumptions and residual risk
