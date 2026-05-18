# Glossary: DFG and HLS

## HLS

High-level synthesis. A compilation process that converts behavioral descriptions into RTL hardware.

## RTL

Register-transfer level. A hardware representation describing registers, combinational logic, and transfers between registers per clock cycle.

## DFG

Data-flow graph. A graph where nodes are operations and edges are data dependencies or value transfers.

Classical HLS often treats DFGs as static DAGs inside basic blocks. Modern dataflow systems may include cycles, streams, rates, buffers, and memory channels.

## CFG

Control-flow graph. A graph describing branches, loops, and possible execution paths.

## CDFG

Control/data-flow graph. A combined representation that includes both control-flow and data-flow information.

## FSMD

Finite state machine with datapath. A common HLS implementation model: the datapath performs operations, while the FSM controls when operations happen.

## Single-Assignment Form

A representation where each variable version is assigned once. This makes dependencies explicit and simplifies DFG construction.

## Allocation

The decision of how many hardware resources exist. Example: one multiplier vs. four multipliers.

## Binding

The mapping from operations or values to concrete hardware resources. Example: operation `mul_3` runs on `multiplier_0`.

## Scheduling

The mapping from operations to time slots or clock cycles.

## Control Step

A time step in a schedule where a set of micro-operations executes.

## Resource Sharing

Using the same hardware unit for multiple operations at different times. It saves area but can add muxes, control, and communication pressure.

## Steering Logic

Muxes, buses, control signals, and related logic that route values into shared functional units or storage.

## Chaining

Executing multiple dependent operations within one clock cycle, if the combined delay fits the clock period.

## Pipelining

Overlapping multiple operations or loop iterations across cycles to improve throughput.

## FIFO

First-in-first-out buffer. Important in streaming/dataflow systems because it stores tokens and decouples producer/consumer timing.

## Guarded Atomic Action

A rule-based hardware behavior model where a condition guards an atomic state update. This idea is associated with Bluespec and term rewriting systems.

## Dataflow Communication Scaling

The project framing used here: measure how communication demand grows as computational regions become larger.

Classical baseline:

```text
T_plain = number of crossing edges
```

Dataflow-aware observables:

```text
C_bit = sum(width of crossing edges)
C_bw  = sum(width * rate of crossing edges)
```

