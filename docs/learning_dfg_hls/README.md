# Learning DFG and HLS

This folder collects notes for learning data-flow graphs, high-level synthesis, and how classical HLS concepts connect to the dataflow communication scaling project.

## Current Source

- Lecture 9, EE 382V SoC Design, Fall 2009, J. A. Abraham: High Level Synthesis
  - PDF: https://users.ece.utexas.edu/~gerstl/ee382v-ics_f09/lectures/lecture_9.pdf
  - Local notes: [lecture_9_high_level_synthesis.md](lecture_9_high_level_synthesis.md)

## Learning Map

1. HLS problem definition
   - Input: behavioral C/HDL/state model.
   - Output: scheduled, bound RTL with datapath and control.
   - Constraints: area, latency, resource availability, clock period.

2. Intermediate representation
   - CFG captures control.
   - DFG captures data dependencies inside a basic block.
   - CDFG combines control and data dependencies.
   - Single-assignment form is needed to make data dependencies explicit.

3. Scheduling, allocation, and binding
   - Scheduling maps operations to time slots.
   - Allocation decides how many hardware resources exist.
   - Binding maps operations, values, and transfers to concrete resources.
   - These choices change area, latency, muxing, wiring, and congestion.

4. Datapath and controller generation
   - The datapath contains functional units, registers, muxes, buses, memories, FIFOs, and wires.
   - The controller sequences micro-operations across control steps.
   - Even a DFG with no conditionals may need a sequencer when operations span multiple cycles.

5. Research bridge to this project
   - Classical HLS DFGs are often static, DAG-like, basic-block representations.
   - Modern dataflow systems add streams, rates, bitwidths, memory traffic, buffering, semantic edge types, and temporal behavior.
   - This motivates a dataflow communication scaling law rather than just applying classical Rent's rule to DFGs.

## Folder Convention

- `lecture_*`: notes for a specific course lecture or PDF.
- `glossary.md`: stable terminology used across notes.
- Future additions can include `exercises/`, `figures/`, and `paper_notes/`.

