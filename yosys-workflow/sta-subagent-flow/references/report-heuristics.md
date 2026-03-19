# Report Heuristics

Use these heuristics when the flow succeeds but the reports are incomplete or noisy.

## SDC assumptions

The generated default SDC is intentionally minimal:
- single-clock only
- one primary clock
- reset-like ports excluded from data input delay constraints
- all non-clock outputs constrained with a default output delay

If the RTL is multi-clock, CDC-heavy, or contains asynchronous interfaces, call out that the generated SDC is only a bootstrap file.

## Clock inference

Prefer these names in order:
- `clk`
- `clock`
- `aclk`
- ports ending in `_clk`
- ports containing `clk`

If multiple plausible clocks exist, do not guess silently. Either use the user-specified clock or state the ambiguity.

## Reset inference

Treat these as reset-like by default:
- `reset`
- `rst`
- `rst_n`
- `resetn`
- `aresetn`
- names containing `reset` or `rst`

Exclude reset-like ports from default input delay constraints.

## Recommendation mapping

Use these mappings:

- `unconstrained` in `sta.log`
  Action: add missing I/O timing exceptions or interface delays.

- negative setup slack or negative max TNS
  Action: reduce frequency target or shorten the critical path by pipelining, retiming, logic simplification, or gate sizing.

- negative hold slack or negative min TNS
  Action: add hold buffers, adjust short-path structure, or fix incorrect min-delay assumptions.

- negative slew slack in `.trans`
  Action: buffer the net, upsize the driver, or reduce fanout.

- negative capacitance slack in `.cap`
  Action: reduce net load, repartition sinks, or increase drive strength.

- negative fanout slack in `.fanout`
  Action: duplicate the source or insert a buffer tree.

- `Found and reported N problems` with `N > 0`
  Action: fix synthesis structural issues before trusting timing numbers.
