# Architecture Plan Checklist

Use this reference after the natural-language requirement has been converted into a structured contract and before any RTL is written.

## Minimum architecture output

- One-sentence description of the block purpose
- Why the design is combinational or sequential
- List of main internal registers or state variables
- List of main combinational decisions or datapath transforms
- Reset behavior
- Latency/throughput summary

## FSM-oriented blocks

- Enumerate each state
- State entry condition
- State exit condition
- Outputs or control actions associated with each state
- Priority rules when multiple transitions are possible

## Datapath-oriented blocks

- Input capture point
- Arithmetic or logical transforms
- Output register point, if any
- Overflow/underflow/sign-extension policy
- Pipeline stage intent when latency is more than one cycle

## Interface-oriented blocks

- Handshake type: valid/ready, request/ack, start/done, or custom
- Backpressure behavior
- Idle behavior
- Illegal input handling
- Simultaneous event priority

## Consistency checks before RTL

- Every user-visible output is accounted for in the plan
- Every corner case from the requirement has a stated behavior
- Timing assumptions are explicit
- Reset behavior is unambiguous
- Verification targets can be mapped to concrete TB scenarios
