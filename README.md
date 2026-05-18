# hls-rent

Rent-aware dataflow communication scaling for early HLS routability prediction.

This project extends classical Rent-style analysis from undirected netlists to
directed, weighted, streaming dataflow graphs. The goal is to predict future
physical routability earlier in the HLS flow and explain the risk back to C
source constructs such as loops, arrays, and pragmas.

## Implemented Flow

```mermaid
flowchart LR
    A["Implemented extractors<br/>synthetic JSON / HLSyn GEXF / Dynamatic MLIR"]:::done --> B["Normalized DFG/CDFG JSON<br/>directed edges + width/rate + provenance"]:::key
    C["C source pragmas<br/>PIPELINE / UNROLL / ARRAY_PARTITION"]:::done --> D["Pragma annotation<br/>adds pragma_ids / kinds / texts"]:::key
    B --> D
    D --> E["Dataflow Rent analysis<br/>alpha_plain / alpha_bit / alpha_bw / alpha_mem / alpha_tensor"]:::key
    E --> F["GNN feature graph<br/>node + edge + graph features"]:::key
    F --> G["Pragma attribution baseline<br/>region -> edge/node -> source line -> pragma"]:::key

    H["Vivado/VPR reports"]:::done --> I["Routability labels<br/>congestion / routed fraction / WNS / channel width"]:::label
    I -. "training target" .-> F

    classDef key fill:#e8f3ff,stroke:#1d4ed8,stroke-width:2px,color:#0f172a;
    classDef done fill:#f8fafc,stroke:#64748b,color:#0f172a;
    classDef label fill:#ecfdf5,stroke:#059669,color:#0f172a;
```

Highlighted path:

```text
normalized DFG/CDFG
  -> pragma annotation
  -> dataflow Rent features
  -> GNN feature graph
  -> pragma-level attribution
```

Implemented label path:

```text
Vivado/VPR reports -> routability labels -> supervised GNN target
```

Main code lives in [`dataflow_comm_scaling/`](dataflow_comm_scaling/README.md).
