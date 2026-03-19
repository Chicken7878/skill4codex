`timescale 1ns/1ps

module example_block (
  input wire clk,
  input wire rst_n,
  input wire in_valid,
  input wire [7:0] in_data,
  output reg out_valid,
  output reg [7:0] out_data
);

  reg [7:0] data_q;

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      data_q <= 8'h00;
      out_valid <= 1'b0;
      out_data <= 8'h00;
    end else begin
      out_valid <= 1'b0;

      if (in_valid) begin
        data_q <= in_data;
        out_valid <= 1'b1;
        out_data <= in_data;
      end
    end
  end

endmodule
