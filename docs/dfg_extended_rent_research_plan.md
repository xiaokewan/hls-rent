# Dataflow Communication Scaling Research Plan

Goal: develop a communication scaling law for dataflow computation systems. The FPGA/HLS backend prediction problem is an important validation target, but it should not be the whole research framing.

The core research question is:

```text
Classical Rent's rule describes gate-level communication scaling in Moore-era netlists.
What is the corresponding communication scaling law for AI/HLS-era dataflow systems?
```

This is different from "using Rent's rule on a DFG". The latter sounds like applying an old netlist metric to a new graph. The stronger contribution is to identify what must replace the classical terminal count when computation becomes directed, bandwidth-dominated, streaming, temporal, and semantic.

## Central Mismatch

Classical Rentian analysis assumes a model close to gate-level netlists:

```text
undirected
unweighted
static
topological
terminal-count based
```

Modern HLS and AI accelerators look different:

```text
directed
bandwidth-dominated
streaming
temporal
semantic
memory- and movement-heavy
```

So the key claim should be:

```text
Classical Rent's rule is not directly applicable to dataflow systems because its
communication observable is the wrong one.
```

The reusable part of Rentian analysis is not the exact terminal-count formula. The reusable part is the idea of measuring how external communication demand scales as a system is recursively grouped into larger computational regions.

## Research Position

A good high-level framing:

```text
We propose Dataflow Rentian Analysis: a generalized communication scaling
framework for directed, weighted, temporal dataflow systems.
```

The classical rule:

```text
T = k * B^p
```

becomes a family of scaling laws:

```text
C(S) = k_c * B(S)^alpha
```

where `S` is a computational region, `B(S)` is the amount of computation inside the region, and `C(S)` is not just terminal count. It is a communication demand observable chosen for dataflow systems.

## Communication Observables

For a dataflow graph edge:

```text
e = (src, dst, width, rate, kind, lifetime, semantic)
```

Possible edge attributes:

```text
width       bits per token
rate        tokens per cycle, tokens per iteration, or normalized throughput demand
kind        data, control, memory, stream, reduction, broadcast
lifetime    transient, buffered, persistent, recurrent
semantic    tensor, scalar, index, address, predicate, activation, weight
```

For a partition or computational region `S`, define:

```text
cut(S) = edges crossing the boundary of S
```

Baseline observable:

```text
T_plain(S) = number of crossing edges
```

This is included only as the classical baseline.

Bitwidth-weighted observable:

```text
C_bit(S) = sum(width(e)) for e in cut(S)
```

Bandwidth observable:

```text
C_bw(S) = sum(width(e) * rate(e)) for e in cut(S)
```

Streaming/storage pressure observable:

```text
C_buf(S) = sum(width(e) * fifo_depth(e)) for streaming or buffered crossing edges
```

Semantic observables:

```text
C_mem(S)     = bandwidth demand of memory/address/load/store edges crossing S
C_tensor(S)  = bandwidth demand of tensor/activation/weight edges crossing S
C_ctrl(S)    = communication demand of predicate/control edges crossing S
C_reduce(S)  = demand from reduction/all-to-all/broadcast style edges crossing S
```

The first version can use `C_bit`. The mature version should use `C_bw`, because dataflow systems are dominated by bandwidth, not just topology.

## Scaling Exponents

Instead of saying there is one Rent exponent, define a set of communication scaling exponents:

```text
alpha_plain:  T_plain(S) ~ B(S)^alpha_plain
alpha_bit:    C_bit(S)   ~ B(S)^alpha_bit
alpha_bw:     C_bw(S)    ~ B(S)^alpha_bw
alpha_mem:    C_mem(S)   ~ B(S)^alpha_mem
alpha_tensor: C_tensor(S)~ B(S)^alpha_tensor
```

For the first implementation:

```text
alpha_plain = classical baseline
alpha_bit   = first dataflow-aware extension
```

For the main research argument:

```text
alpha_bw is the real dataflow communication scaling exponent.
```

`alpha_bit` is useful when rate information is unavailable.

## Direction Is Not A Separate Rent Rule

Direction should not be split into independent input and output Rent exponents as the main result. Direction should explain flow structure:

```text
in_bw(S)      = bandwidth entering S
out_bw(S)     = bandwidth leaving S
flow_balance  = abs(out_bw(S) - in_bw(S)) / max(in_bw(S) + out_bw(S), 1)
source_skew   = concentration of outgoing traffic around a few producer nodes
sink_skew     = concentration of incoming traffic around a few consumer nodes
```

This captures whether communication is producer-heavy, consumer-heavy, memory-centric, reduction-like, broadcast-like, or locally balanced.

## What Counts As Compute Size

Classical Rent uses block count. In dataflow systems, region size can be measured several ways:

```text
B_node(S)     = number of DFG operations
B_area(S)     = estimated operator area or resource cost
B_ops(S)      = operations per iteration
B_throughput(S)= operations per cycle under a schedule
B_state(S)    = registers, buffers, or local memory state
```

MVP:

```text
B_node(S)
```

Next:

```text
B_area(S)
```

Later:

```text
B_throughput(S)
```

This matters because unrolling and systolic transformations change compute replication and communication demand together.

## Why This Is Bigger Than Backend Prediction

Backend routability is a strong validation target because routing failure is a visible symptom of communication pressure. But the broader problem appears in many systems:

```text
FPGA routing congestion
NoC traffic
chiplet links
multi-die FPGA crossings
HBM bandwidth pressure
systolic array data movement
attention all-to-all communication
tensor movement in AI accelerators
```

The project should therefore be framed as:

```text
communication scaling law for dataflow systems
```

with:

```text
HLS/FPGA routability prediction as the first experimental application
```

## Tool Shortlist

### Priority A: best fit for dataflow extraction

1. Dynamatic
   - Source: https://dynamatic.epfl.ch/ and https://epfl-lap.github.io/dynamatic/DeveloperGuide/IntroductoryMaterial/DynamaticHLSFlow.html
   - Why it matters: MLIR-based HLS flow with affine, SCF, CF, and Handshake IR. The Handshake dialect is close to directed dataflow computation.
   - Best use: extract directed edges, bitwidths, memory edges, control edges, and possibly buffering structure.
   - Risk: dynamic HLS/dataflow semantics differ from conventional static HLS.

2. CIRCT HLS / Handshake
   - Source: https://circt.llvm.org/docs/HLS/
   - Why it matters: compiler infrastructure for MLIR/CIRCT HLS flows, useful for writing custom analysis passes.
   - Best use: stable IR-level dataflow communication extraction.
   - Risk: research-tool integration work may be nontrivial.

3. XLS
   - Source: https://github.com/google/xls and https://google.github.io/xls/
   - Why it matters: explicit bitwidths and a clean dataflow-like IR.
   - Best use: controlled experiments where `width` is reliable and extraction is straightforward.
   - Risk: less representative of conventional C-to-FPGA HLS flows.

### Priority B: transformation and benchmark flows

4. ScaleHLS
   - Source: https://github.com/UIUC-ChenLab/scalehls
   - Why it matters: MLIR-based HLS framework with transformations and DSE.
   - Best use: compare communication scaling before and after HLS-oriented transformations.

5. TAPA
   - Source: https://github.com/UCLA-VAST/tapa and https://tapa.readthedocs.io/
   - Why it matters: task-parallel HLS dataflow framework with physical-design-aware related work.
   - Best use: task-level dataflow communication scaling.

6. PandA-bambu
   - Source: https://github.com/ferrandi/PandA-bambu
   - Why it matters: mature open C-based HLS framework.
   - Best use: alternate HLS flow after the extractor concept is stable.

7. Stream-HLS / AutoSA
   - Sources: https://github.com/UCLA-VAST/Stream-HLS and https://github.com/UCLA-VAST/AutoSA
   - Why they matter: dataflow and systolic transformations directly change communication scaling.
   - Best use: case studies for AI/dataflow transformations.

## Benchmark and Dataset Shortlist

### Priority A: first experiments

1. HLSFactory
   - Source: https://github.com/sharc-lab/HLSFactory
   - Why it matters: organizes PolyBench, MachSuite, CHStone, Rosetta, PP4FPGA kernels, and Vitis HLS examples.
   - Best use: benchmark orchestration and metadata organization.

2. MachSuite
   - Source: https://github.com/breagen/MachSuite
   - Why it matters: accelerator-centric kernels with diverse structures: AES, BFS, FFT, GEMM, KMP, MD, NW, sort, SpMV, stencil, Viterbi.
   - Best use: first diverse kernel set.

3. PolyBench/C
   - Source: https://www.cs.colostate.edu/~pouchet/software/polybench/polybench.html
   - Why it matters: loop-heavy numerical kernels with static control flow.
   - Best use: controlled loop transformations: pipeline, unroll, tiling, interchange, array partition.

4. CHStone
   - Source: https://github.com/ferrandi/CHStone
   - Why it matters: standard C-based HLS benchmark suite.
   - Best use: conventional HLS baseline.

5. Rosetta
   - Source: https://github.com/cornell-zhang/rosetta
   - Why it matters: realistic HLS applications with unoptimized and optimized versions.
   - Best use: compare communication scaling across realistic optimization stages.

### Priority B: later scaling

6. Vitis HLS Introductory Examples / Vitis Accel Examples
   - Sources: https://github.com/Xilinx/Vitis-HLS-Introductory-Examples and https://github.com/Xilinx/Vitis_Accel_Examples
   - Best use: microbenchmarks for known dataflow, stream, memory widening, array partition, and systolic patterns.

7. HLSDataset
   - Source: https://github.com/UT-LCA/ML4Accel-Dataset/tree/main/fpga_ml_dataset
   - Best use: compare with existing HLS/implementation report-level ML features.

8. ForgeHLS
   - Source: https://github.com/zedong-peng/ForgeHLS
   - Best use: large-scale QoR and pragma exploration after the core metric is stable.

## Normalized Dataflow Graph Schema

Use a normalized JSON schema so different frontends can map into the same analysis:

```json
{
  "nodes": [
    {
      "id": "n0",
      "op": "mul",
      "kind": "compute",
      "area": 3
    }
  ],
  "edges": [
    {
      "src": "n0",
      "dst": "n1",
      "width": 32,
      "rate": 1.0,
      "kind": "data",
      "semantic": "tensor"
    }
  ]
}
```

Minimum fields:

```text
node.id
edge.src
edge.dst
edge.width
```

Preferred fields:

```text
node.op
node.kind
node.area
edge.rate
edge.kind
edge.semantic
edge.fanout
edge.fifo_depth
edge.memory_bank
```

## MVP Implementation

Add:

```text
post_process/dataflow_comm_scaling.py
post_process/dataflow_scaling2csv.py
post_process/dataflow_scaling2viz.py
examples/dataflow/*.json
```

The first implementation should:

1. Read normalized dataflow JSON.
2. Use recursive partitioning to generate regions at multiple scales.
3. Partition with an undirected projection only as a practical heuristic.
4. Score each region with directed, weighted, semantic communication metrics.
5. Fit log-log scaling exponents.

Per-region output:

```text
B_node
B_area
T_plain
C_bit
C_bw
in_bw
out_bw
flow_balance
source_skew
sink_skew
C_mem
C_tensor
C_ctrl
fanout_weighted_cut
```

Per-design output:

```text
alpha_plain
alpha_bit
alpha_bw
alpha_mem
alpha_tensor
k_plain
k_bit
k_bw
mean_flow_balance
max_flow_balance
memory_fraction
semantic_mix
```

If `rate` is missing:

```text
C_bw = C_bit
```

and the result should be labeled as bitwidth-weighted rather than true bandwidth-weighted.

## First Experiments

Start with:

```text
MachSuite: gemm, fft, stencil, spmv, bfs, aes
PolyBench: gemm, 2mm, 3mm, atax, bicg, syrk, covariance
CHStone: aes, jpeg, sha, mips
Rosetta: optical flow, spam filter, digit recognition, 3d rendering if setup is manageable
```

Generate variants:

```text
baseline
pipeline
unroll factor 2/4/8 where legal
array partition factor 2/4/complete where legal
dataflow/function split where legal
tiling/interchange where legal
manual dataflow transformation where available
```

Collect validation labels:

```text
HLS: latency, II, LUT, FF, DSP, BRAM, URAM, estimated clock
Implementation: route runtime, wirelength, congestion, WNS/TNS, routed yes/no
Architecture: NoC traffic, HBM bandwidth, inter-SLR or inter-die crossings where available
```

Backend labels validate the scaling law. They should not define the whole method.

## Analysis Questions

1. Does `alpha_bit` or `alpha_bw` separate bandwidth-dominated kernels from control-dominated kernels better than `alpha_plain`?
2. Do unroll and array partition transformations increase communication scaling faster than compute scaling?
3. Do tiling and locality transformations reduce `alpha_bw` or the communication constant `k_bw`?
4. Do systolic/dataflow transformations change the exponent, the constant, or only the semantic mix?
5. Does memory communication scale differently from compute-to-compute communication?
6. Does all-to-all, broadcast, or reduction traffic produce identifiable scaling signatures?
7. Does high communication scaling correlate with backend routability, NoC pressure, HBM pressure, or timing failure?

## Paper-Level Claims To Test

Claim 1:

```text
Classical terminal-count Rent exponents understate communication pressure in
bandwidth-dominated dataflow systems.
```

Claim 2:

```text
Bitwidth- and bandwidth-weighted communication scaling exponents better capture
the structural difficulty of HLS/AI accelerator designs.
```

Claim 3:

```text
Different dataflow transformations alter communication scaling in distinguishable
ways: some change the exponent, some change the constant, and some only change
the semantic composition of communication.
```

Claim 4:

```text
Backend routing congestion is one observable consequence of poor dataflow
communication scaling, but the same framework also applies to NoC, HBM,
chiplet, and systolic/tensor movement pressure.
```

## Immediate Next Steps

1. Rename the conceptual framing from `DFG-level Rent` to `dataflow communication scaling`.
2. Implement the normalized dataflow JSON reader and region scoring.
3. Keep `T_plain` only as the classical baseline.
4. Implement `C_bit` first and design the code so `C_bw` is a drop-in extension when rates are available.
5. Create synthetic examples for:
   - narrow scalar chain
   - wide streaming pipeline
   - broadcast/fanout
   - reduction tree
   - memory-centric stencil
   - all-to-all attention-like block
6. Use these examples to show where classical Rent gives the wrong intuition.
7. Then move to MachSuite/PolyBench through HLSFactory or MLIR/XLS extraction.

## Current Recommendation

Use this order:

```text
1. Build the dataflow communication scaling metric on synthetic graphs.
2. Validate against known communication patterns.
3. Extract real graphs from Dynamatic Handshake MLIR or XLS IR.
4. Use HLSFactory/MachSuite/PolyBench for benchmark organization.
5. Use FPGA backend metrics as one validation axis.
```

The first milestone should prove the conceptual mismatch:

```text
same or similar T_plain,
very different C_bit / C_bw,
very different dataflow communication difficulty.
```

That is the cleanest way to show why classical Rent is insufficient and why a dataflow communication scaling law is needed.
