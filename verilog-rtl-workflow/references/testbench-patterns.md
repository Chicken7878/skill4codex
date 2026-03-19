# Testbench Patterns

The example below uses SystemVerilog syntax for readability. If the user requests plain Verilog, rewrite the TB using Verilog-compatible constructs such as `reg`, `wire`, and plain `always`/`initial`.

Waveforms should be dumped by default to `build/<tb_module>.vcd`. Prefer supporting a `+wave_path=<path>` plusarg and falling back to the default build path when the plusarg is absent.

## Minimal self-checking TB skeleton

```systemverilog
`timescale 1ns/1ps

module example_tb;
  logic clk;
  logic rst_n;
  logic in_valid;
  logic [7:0] in_data;
  logic out_valid;
  logic [7:0] out_data;

  example dut (
    .clk(clk),
    .rst_n(rst_n),
    .in_valid(in_valid),
    .in_data(in_data),
    .out_valid(out_valid),
    .out_data(out_data)
  );

  initial clk = 1'b0;
  always #5 clk = ~clk;

  string wave_path;

  initial begin
    wave_path = "build/example_tb.vcd";
    if (!$value$plusargs("wave_path=%s", wave_path)) begin
      wave_path = "build/example_tb.vcd";
    end
    $dumpfile(wave_path);
    $dumpvars(0, example_tb);
  end

  task automatic expect_eq(input [7:0] actual, input [7:0] expected, input string msg);
    if (actual !== expected) begin
      $error("%s actual=%0h expected=%0h", msg, actual, expected);
      $finish(1);
    end
  endtask

  initial begin
    rst_n = 1'b0;
    in_valid = 1'b0;
    in_data = '0;

    repeat (3) @(posedge clk);
    rst_n = 1'b1;

    @(negedge clk);
    in_valid <= 1'b1;
    in_data <= 8'h12;

    @(posedge clk);
    @(negedge clk);
    in_valid <= 1'b0;
    in_data <= '0;

    wait (out_valid === 1'b1);
    expect_eq(out_data, 8'h12, "single transfer");

    repeat (2) @(posedge clk);
    $display("TB PASS");
    $finish;
  end
endmodule
```

## Recommended TB structure

- One clock generator per synchronous domain unless the test explicitly studies CDC behavior
- Reset sequence at the beginning of simulation
- Stimulus phase separated from checking logic when possible
- Reusable tasks for repeated transactions
- Immediate fail on deterministic mismatch
- Prefer a stable phase convention: drive on `negedge`, sample after the relevant `posedge` has completed
- Treat same-edge drive/check against sequential RTL as suspicious unless the protocol explicitly demands it
- If using nonblocking assignments in the DUT, avoid checking registered outputs in the same simulation region as the capturing edge
- Default wave dump path should live under `build/`, not the source tree root

## Debug habits

- Print cycle counts or timestamps near the first failure
- Dump waves only when text logs are insufficient
- Keep expected-value logic simpler than the DUT
- If latency is configurable, derive the checker from the parameter instead of hardcoding one cycle
- When a nominal test fails unexpectedly, inspect TB event ordering before assuming the RTL is wrong
- Missing `` `timescale `` directives can create noisy or confusing simulator output; add them to both DUT and TB
