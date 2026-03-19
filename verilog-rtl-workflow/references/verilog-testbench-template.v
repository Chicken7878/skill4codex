`timescale 1ns/1ps

module example_tb;
  reg clk;
  reg rst_n;
  reg in_valid;
  reg [7:0] in_data;
  wire out_valid;
  wire [7:0] out_data;

  event_counter dut (
    .clk(clk),
    .rst_n(rst_n),
    .in_valid(in_valid),
    .in_data(in_data),
    .out_valid(out_valid),
    .out_data(out_data)
  );

  initial clk = 1'b0;
  always #5 clk = ~clk;

  initial begin
    if (!$test$plusargs("no_waves")) begin
      $dumpfile("build/example_tb.vcd");
      $dumpvars(0, example_tb);
    end
  end

  initial begin
    rst_n = 1'b0;
    in_valid = 1'b0;
    in_data = 8'h00;

    repeat (3) @(posedge clk);
    rst_n = 1'b1;

    @(negedge clk);
    in_valid = 1'b1;
    in_data = 8'h12;
    @(posedge clk);
    @(negedge clk);
    in_valid = 1'b0;

    wait (out_valid === 1'b1);
    if (out_data !== 8'h12) begin
      $display("TB FAIL actual=%0h expected=%0h", out_data, 8'h12);
      $finish(1);
    end

    $display("TB PASS");
    $finish;
  end
endmodule
