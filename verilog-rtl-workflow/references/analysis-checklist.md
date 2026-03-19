# Analysis Checklist

Use this checklist before RTL coding when the requirement is incomplete or the module is stateful.

## Interface contract

- What language did the user request: Verilog or SystemVerilog?
- What are the exact inputs, outputs, parameters, and widths?
- Which signals are synchronous to which clock?
- Is reset synchronous or asynchronous? Active high or active low?
- Are there enable, valid/ready, request/ack, or start/done semantics?
- Which outputs are combinational versus registered?

## Functional behavior

- What must happen after reset?
- What is the default or idle state?
- Are operations single-cycle, multi-cycle, or pipelined?
- Are simultaneous requests legal? If yes, what is the priority?
- What should happen on overflow, underflow, wrap, saturation, or illegal input?

## Timing and state

- What is the expected latency from input acceptance to output visibility?
- Can the block accept back-to-back transactions?
- Are stalls or backpressure possible?
- Is there any requirement for glitch-free outputs?
- Are there state transition restrictions?

## Codebase fit

- Does the repository already constrain file extensions or language version?
- Does the repository already define naming, reset, or FSM conventions?
- Are there nearby modules that imply protocol behavior not written in the prompt?
- Are there existing TB utilities or compile scripts to reuse?

## Verification targets

Minimum cases to cover:

- Reset behavior
- One nominal operation
- Boundary condition at each width or counter limit
- One negative or illegal case if behavior is defined
- Consecutive operations without idle gap
