# hls-rent

Rent-aware dataflow communication scaling for early HLS routability prediction.

This project extends classical Rent-style analysis from undirected netlists to
directed, weighted, streaming dataflow graphs. The goal is to predict future
physical routability earlier in the HLS flow and explain the risk back to C
source constructs such as loops, arrays, and pragmas.

## Flowchart

```mermaid
flowchart TD
    A["C/C++ kernel<br/>HLS pragmas"] --> B["Open HLS / IR extractor<br/>Dynamatic, HLSyn, future Vitis/XLS"]
    B --> C["Normalized DFG/CDFG JSON<br/>nodes, edges, width, rate, provenance"]
    A --> D["C pragma annotation<br/>#pragma HLS -> pragma_ids"]
    C --> D
    D --> E["Dataflow communication scaling<br/>recursive partitioning"]
    E --> F["Rent-like exponents<br/>alpha_plain, alpha_bit, alpha_bw,<br/>alpha_mem, alpha_tensor"]
    E --> G["Hierarchical region features<br/>node path + partition context"]
    D --> H["GNN feature fusion<br/>node, edge, graph features"]
    F --> H
    G --> H
    B --> I["Backend implementation<br/>Vivado / VPR"]
    I --> J["Physical labels<br/>routing congestion, routed fraction,<br/>WNS/TNS, channel width"]
    H --> K["GNN training / ablation<br/>raw vs edge vs Rent vs hierarchy"]
    J --> K
    K --> L["Early routability prediction<br/>kernel and region risk"]
    L --> M["Root-cause attribution<br/>region -> edge/node -> source line -> pragma"]
    D --> M
```

## Current Pipeline

```text
source kernel + pragmas
  -> normalized dataflow graph
  -> pragma provenance annotation
  -> dataflow/Rent communication features
  -> PyG-ready GNN graph
  -> backend routability labels
  -> prediction and pragma-level attribution
```

Main code lives in [`dataflow_comm_scaling/`](dataflow_comm_scaling/README.md).
