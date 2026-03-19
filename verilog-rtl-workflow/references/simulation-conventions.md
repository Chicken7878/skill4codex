# Simulation Conventions

## Default commands

Preferred order:

1. `verilator --lint-only`
2. `iverilog -g2012 -Wall`
3. `vvp`

Helper script:

```bash
./skills/verilog-rtl-workflow/scripts/verilog_flow.sh lint --top <top_module> --files "rtl/a.v rtl/b.v"
./skills/verilog-rtl-workflow/scripts/verilog_flow.sh sim --top <top_module> --tb <tb_module> --files "rtl/top.v tb/top_tb.v"
./skills/verilog-rtl-workflow/scripts/verilog_flow.sh sim --top <top_module> --tb <tb_module> --filelist sim.f --incdir rtl/include --define SIM=1
```

## Waveforms

- Default wave dump path is `build/<tb_module>.vcd`
- Prefer TBs that accept `+wave_path=<path>` and fall back to the default build path
- Do not dump waves into the source tree root unless the repository already requires it

## Debug order

When simulation fails:

1. Re-check the Stage 1 contract
2. Re-check TB event ordering and checker correctness
3. Re-check RTL against the Stage 2 plan
4. Re-run lint if RTL changed materially
5. Re-run simulation

## Common pitfalls

- Same-edge TB drive and DUT sampling races
- Reading registered outputs before NBA updates become visible
- Missing `` `timescale `` directives creating noisy timing diagnostics
