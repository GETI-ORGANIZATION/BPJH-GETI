# Research Request

## Query
Multi-instance image generation in diffusion models with training-free attention mechanisms

## Requirements
- Novel and with good math properties
- Low-cost experiments

## Notes
- Prefer papers after 2024

## Selected Idea
**Optimal Transport Attention Reallocation for Multi-Instance Dominance Mitigation**

### Description
A training-free framework that formulates the multi-instance attention allocation problem as an Optimal Transport (OT) problem to mathematically guarantee balanced semantic distribution. Applies Sinkhorn algorithms to solve an entropy-regularized OT problem between the spatial distribution of attention maps and a uniform target distribution across multiple instances.

### Key Innovation
- Sinkhorn-based optimal transport for attention reallocation
- Marginal constraints ensure equal attention budget per concept
- Training-free, architecture-agnostic (works on U-Net and DiT)
- Mathematically principled vs. heuristic methods

### Mathematical Formulation
Let $A_i \in \mathbb{R}^{H \times W}$ denote the attention map for instance $i$:

$$\min_{T} \sum_{i,j} C_{ij} T_{ij} - \epsilon H(T)$$

Constraints:
- $\sum_j T_{ij} = \frac{1}{n}$ (equal attention mass per instance)
- $T_{ij} \geq 0$

Solver: Sinkhorn iterations with $K = \exp(-C/\epsilon)$

### Evidence Sources
1. [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models
   - Introduces DominanceBench
   - Identifies DvD imbalance phenomenon

2. [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation
   - Key-space intervention approach
   - Backbone-agnostic framework

3. [2602.08749] Shifting the Breaking Point of Flow Matching for Multi-Instance Editing
   - Instance-Disentangled Attention
   - Joint attention partitioning

## Competitor Analysis

### Training-Free Methods
| Method | Year | Mechanism | Code |
|--------|------|-----------|------|
| Prompt-to-Prompt | 2022 | Cross-attention control | Available |
| Attend-and-Excite | 2023 | Attention excitation | Available |
| Delta-K | 2026 | Key-space augmentation | TBD |

### Key Gap
No existing work combines Optimal Transport (Sinkhorn) with cross-attention manipulation for multi-instance generation.

## Timeline
- Idea discovery: 2026-03-19
- Experiment planning: TBD
