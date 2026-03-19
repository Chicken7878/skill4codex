# Language Rules

## Selection policy

- If the user explicitly asks for `Verilog`, use Verilog-compatible syntax only
- If the user explicitly asks for `SystemVerilog`, SystemVerilog syntax is allowed
- If the user does not specify, default to plain Verilog and state that assumption in Stage 1

## Verilog mode

Avoid SystemVerilog-only constructs such as:

- `logic`
- `always_ff`
- `always_comb`
- `typedef`
- `enum`
- packed structs/unions
- `string`

Prefer:

- `reg` and `wire`
- `always @(*)` and clocked `always @(posedge ... )`
- plain parameters and localparams
- See [verilog-rtl-template.v](./verilog-rtl-template.v) and [verilog-testbench-template.v](./verilog-testbench-template.v) for plain Verilog starting points

## SystemVerilog mode

Allowed when tool-compatible and useful:

- `logic`
- `always_ff`
- `always_comb`
- enums and typedefs
- stronger TB typing when supported by the simulator

## TB alignment

- By default, TB language should match the RTL language
- Mixed-language style is allowed only when the user explicitly asks for it
