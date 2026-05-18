# Lecture 9 Notes: High Level Synthesis

Source: EE 382V SoC Design, Fall 2009, J. A. Abraham, Lecture 9, High Level Synthesis.

PDF: https://users.ece.utexas.edu/~gerstl/ee382v-ics_f09/lectures/lecture_9.pdf

## One-Line Summary

This lecture explains the classical HLS flow: convert behavioral descriptions into RTL by building CDFG/DFG representations, then performing scheduling, allocation, binding, datapath generation, and controller generation under area and timing constraints.

## Slide-Level Structure

1. HLS overview
   - HLS converts a high-level behavior into an RTL netlist.
   - Inputs may be C, behavioral HDL, state diagrams, or logic networks.
   - Outputs include operation schedules, resource bindings, control logic, and interconnect.

2. Design abstraction levels
   - HLS sits above RTL and logic synthesis.
   - It transforms algorithmic or behavioral descriptions toward structural RTL.

3. Essential issues in HLS
   - Behavioral language.
   - Target architecture.
   - Intermediate representation.
   - Operation scheduling.
   - Allocation and binding.
   - Control generation.

4. Target architecture choices
   - Bus-based, mux-based, register-file based, pipelined, RISC/VLIW-like, or protocol-based.
   - Architecture choice changes the cost model for interconnect and storage.

5. FSMD model
   - HLS commonly outputs a finite state machine with datapath.
   - A design can also be viewed as communicating FSMDs.
   - This is important because control and data are separated in the implementation, even if they were mixed in the source code.

6. CDFG and DFG
   - A CDFG combines control-flow and data-flow information.
   - A DFG captures data dependencies between operations.
   - In the classical lecture framing, a DFG is usually for a basic block and has no conditionals.
   - Single-assignment form is used so each produced value has a unique definition.

7. Scheduling, allocation, and binding
   - Scheduling maps operations to cycles or control steps.
   - Allocation decides available resources such as adders, multipliers, registers, memories, buses, and muxes.
   - Binding maps operations and values onto actual resource instances.
   - Resource sharing saves area but serializes operations and adds steering logic.

8. Datapath-controller generation
   - A scheduled CDFG plus an allocated datapath is converted into micro-operations.
   - The controller triggers those micro-operations each control step.
   - Registers sit at clock boundaries; muxes select inputs when resources are shared.

9. Quality metrics
   - Performance.
   - Area.
   - Power.
   - Testability.
   - Reusability.

10. Hardware variations
   - Functional units can be pipelined, multi-cycle, chained, or multi-function.
   - Storage may be registers, register files, multi-port memories, RAMs, ROMs, FIFOs, or distributed storage.
   - Interconnect may be bus-based, segmented, mux-based, or protocol-based.

11. Behavioral optimization
   - Software compiler optimizations can apply, such as common subexpression elimination, propagation, dead-code elimination, and strength reduction.
   - Hardware-specific transforms include conditional expansion and loop expansion.
   - These transforms expose parallelism but can increase area and communication demand.

12. Architectural synthesis
   - Treats behavior as a sequencing/dependency graph.
   - Treats hardware resources as library elements with delays.
   - Searches for solutions satisfying timing and resource constraints.
   - Objective examples: maximize performance under area constraint or minimize area under latency constraint.

13. Temporal and spatial domains
   - Temporal scheduling labels operations with time slots.
   - Spatial binding groups operations onto physical resources.
   - Resource sharing can be represented as hyperedges or vertex partitions.
   - Scheduling and binding are mutually dependent: a schedule affects what can share a resource, and binding affects achievable schedule and cycle time.

14. Interconnect and congestion
   - The lecture explicitly raises how scheduling and binding affect wires, input selection, congestion, and steering logic.
   - This is the direct bridge to our communication-scaling research: communication is not only a graph property; it also depends on resource sharing, timing, and datapath realization.

15. Coprocessor synthesis example
   - The lecture discusses a BCH encoder/decoder acceleration example.
   - The main lesson is that a small number of hot loops can dominate execution time and become candidates for hardware acceleration.

16. Why classical HLS adoption was limited
   - Static scheduling.
   - Black-box tool behavior.
   - Low-level structuring primitives.
   - Artificial control/data-flow separation.
   - C is convenient but not always a good hardware behavior language.

17. Term rewriting and Bluespec
   - The lecture introduces guarded atomic actions and Bluespec as an alternative way to describe hardware behavior.
   - State is explicit, behavior is written as rules, and interfaces carry readiness/enabling conditions.
   - This is a useful conceptual bridge toward modern dataflow and protocol-aware systems.

## Key Takeaways

1. Classical DFG in HLS is not the same as modern streaming dataflow.
   - Lecture DFG: static dependencies, basic block, usually DAG, no conditionals.
   - Modern dataflow: streams, rates, buffers, memory channels, control tokens, and semantic data movement.

2. Scheduling and binding are not secondary details.
   - They change resource sharing, muxing, wires, congestion, and cycle time.
   - A communication model that ignores time and binding is incomplete.

3. Interconnect already appears as a hard HLS problem in the classical flow.
   - The lecture names wires, input selection, congestion, steering logic, buses, muxes, FIFOs, and register files.
   - This supports our argument that communication scaling is a first-class problem, not just a backend artifact.

4. DFG extraction alone is not enough for our research.
   - We need edge width, edge type, direction, rate, fanout, memory relation, and possibly buffer depth.
   - We also need to record whether a graph is pre-schedule, post-schedule, or post-binding.

5. Classical HLS gives us vocabulary; our project generalizes the communication observable.
   - Classical baseline: count crossing DFG edges.
   - Dataflow-aware metric: weighted crossing communication demand.
   - Later metric: bandwidth-weighted, semantic, temporal communication demand.

## Connection To Dataflow Communication Scaling

The lecture's DFG model is a good starting point, but it exposes why classical Rent-style counting is insufficient:

```text
DFG edge count != communication pressure
```

Two designs may have the same number of crossing dependencies, but very different hardware difficulty:

```text
1-bit predicate edge vs. 512-bit tensor stream
single-use scalar edge vs. high-fanout broadcast
static operation dependency vs. continuous FIFO traffic
compute-to-compute edge vs. HBM/memory edge
```

For this project, the lecture motivates three layers of analysis:

```text
Layer 1: classical HLS DFG dependency graph
Layer 2: scheduled/bound datapath communication graph
Layer 3: dataflow communication scaling graph with width, rate, direction, and semantics
```

## Questions To Keep While Studying

1. At what IR level is the DFG extracted: source-level, CDFG, scheduled graph, or bound datapath?
2. Are edges just dependencies, or do they represent actual transferred values?
3. Is bitwidth known?
4. Is transfer rate known?
5. Are memory, stream, control, and compute edges distinguishable?
6. Does the representation include FIFOs, buffers, register files, or muxes?
7. Does scheduling change the communication graph or only the time labels?
8. Does binding introduce new communication through muxes, buses, or shared resources?

## Practical Notes For Implementation

When building a dataflow graph JSON from HLS IR, try to capture:

```text
node.id
node.op
node.kind
node.resource_type
node.schedule_time
node.binding
edge.src
edge.dst
edge.width
edge.rate
edge.kind
edge.semantic
edge.lifetime
edge.fanout
edge.buffer_depth
```

Minimum useful subset:

```text
node.id
edge.src
edge.dst
edge.width
edge.kind
```

The most important missing field for true dataflow systems is `rate`.

