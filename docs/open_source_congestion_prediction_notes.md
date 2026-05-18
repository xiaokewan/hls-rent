# Open-Source Congestion Prediction Notes

This note tracks papers and codebases relevant to testing whether dataflow/Rentian communication features improve congestion or post-route QoR prediction.

## DATE 2019 Zhao et al.

Paper:

- J. Zhao, T. Liang, S. Sinha, W. Zhang, "Machine Learning Based Routing Congestion Prediction in FPGA High-Level Synthesis," DATE 2019.
- arXiv: https://arxiv.org/abs/1905.03852
- Author PDF: https://zjru.github.io/camera_ready/zhao_DATE19.pdf

Status:

- The paper is openly available through arXiv.
- I did not find an official public code repository for this DATE 2019 work.
- CatalyzeX lists the paper with "Request Code", which suggests code is not directly available from a linked repository.

Useful ideas to emulate:

- Predict routing congestion early from HLS-level information.
- Map predicted congestion back to high-level source code.
- Use vertical/horizontal congestion labels from implementation.

Gap for our work:

- Their work predates modern GNN-based HLS graph models.
- It does not appear to use dataflow/Rentian communication scaling features.

## Open Codebases To Emulate

### HLSyn

Source: https://github.com/ZongyueQin/HLSyn

Why useful:

- Includes C kernels, pragma-augmented ProGraML graphs, and design-point QoR labels.
- Good first source for real HLS CDFG/DFG-like graphs.

Limitation:

- Labels are performance/resource QoR, not routing congestion.

Current integration:

- `dataflow_comm_scaling/extractors/hlsyn_gexf_to_dataflow.py`
- Converts HLSyn `.gexf` graphs to our normalized dataflow JSON.

### Hierarchical GNN for HLS

Source: https://github.com/sjtu-zhao-lab/hierarchical-gnn-for-hls

Paper: "Hierarchical Source-to-Post-Route QoR Prediction in High-Level Synthesis with GNNs", DATE 2024.

Why useful:

- Open implementation of source-to-post-route HLS QoR prediction with graph construction and pragmas.
- Strong baseline for our feature-level fusion story.

Limitation:

- Targets post-route QoR metrics, not explicitly routing congestion maps.

Potential experiment:

```text
baseline H-GNN features
baseline + dataflow/Rentian communication scaling features
```

### FPGA Heterogeneous Congestion Prediction

Source: https://github.com/AIPnR/FPGA_Hetero_Congestion_Prediction

Paper: "FPGA Routing Congestion Prediction via Graph Learning-Aided Conditional GAN".

Why useful:

- Open code for FPGA routing congestion prediction using VTR-derived graph/layout data.
- Provides scripts for VTR benchmark execution and graph dataset construction.

Limitation:

- Dataset is not uploaded due to size; it must be regenerated with VTR.
- It is not HLS/source-level, but it is useful for physical congestion label generation.

## Recommended Baseline Plan

1. Use HLSyn for real HLS graph extraction and feature fusion.
2. Use HLSyn labels first for QoR/resource smoke tests.
3. Use hierarchical-gnn-for-hls as a post-route QoR GNN baseline.
4. For true congestion labels:
   - commercial path: Vitis/Vivado HLS + Vivado implementation congestion reports;
   - open path: VTR/VPR labels using BLIF/netlist benchmarks, then later bridge HLS-generated RTL/netlists into VTR.
5. Run ablation:

```text
GNN raw graph features
GNN raw + width/rate/semantic edge features
GNN raw + width/rate + dataflow/Rentian scaling features
```

Claim to test:

```text
Dataflow/Rentian communication scaling features improve congestion/QoR prediction
because they inject explicit multi-scale communication pressure into the GNN.
```

