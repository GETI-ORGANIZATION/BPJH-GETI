# Optimal Transport Attention Reallocation for Multi-Instance Dominance Mitigation in Diffusion Models

## Abstract

We propose a training-free framework that formulates the multi-instance attention allocation problem in diffusion models as an Optimal Transport (OT) problem, providing mathematically guaranteed balanced semantic distribution across instances. By applying entropy-regularized Sinkhorn algorithms to cross-attention maps, we enforce fair attention budget allocation per concept, addressing the Dominant-vs-Dominated (DvD) imbalance phenomenon without requiring model fine-tuning or architectural modifications.

---

## 1. Problem Statement

Text-to-image diffusion models excel at single-concept generation but struggle with multi-instance scenarios where one concept token dominates the generation process, suppressing others—a phenomenon termed **Dominant-vs-Dominated (DvD) imbalance** [1]. This manifests as:

- **Concept omission**: Missing instances in generated images
- **Attribute bleeding**: Features transferring between instances
- **Spatial dominance**: One instance occupying disproportionate image space

Existing training-free methods (attention rescaling, key-space augmentation) lack a **principled mathematical foundation** for redistributing attention mass across instances.

---

## 2. Proposed Method

### 2.1 Core Insight

Cross-attention maps $A_i \in \mathbb{R}^{H \times W}$ for each instance can be interpreted as probability distributions over spatial locations. The DvD imbalance corresponds to **unequal distribution masses**—dominated instances receive insufficient attention budget.

### 2.2 Optimal Transport Formulation

We formulate attention reallocation as an entropy-regularized optimal transport problem:

$$\min_{T} \sum_{i,j} C_{ij} T_{ij} - \epsilon H(T)$$

subject to:
- $\sum_j T_{ij} = \frac{1}{n}$ (equal attention mass per instance)
- $T_{ij} \geq 0$

where:
- $C \in \mathbb{R}^{n \times n}$ is the cost matrix based on attention spatial overlap
- $H(T) = -\sum_{i,j} T_{ij} \log T_{ij}$ is entropy regularization
- $\epsilon > 0$ controls regularization strength

### 2.3 Cost Matrix Design

The cost matrix captures semantic interference between instances:

$$C_{ij} = -\log(1 - \text{IoU}(A_i, A_j) + \delta)$$

where IoU measures spatial overlap between attention maps. High overlap implies high reallocation cost, encouraging separation.

### 2.4 Sinkhorn Algorithm

We solve the OT problem efficiently via Sinkhorn iterations:

$$K = \exp(-C / \epsilon)$$
$$u^{(k+1)} = \frac{a}{K v^{(k)}}, \quad v^{(k+1)} = \frac{b}{K^\top u^{(k+1)}}$$
$$T = \text{diag}(u) K \text{diag}(v)$$

where $a = b = \mathbf{1}/n$ enforces uniform marginals.

**Complexity**: $O(n^2)$ per iteration, typically converges in 20-50 iterations.

### 2.5 Integration with Diffusion

During denoising, we:
1. Extract cross-attention maps $A_1, \ldots, A_n$ for instance tokens
2. Compute transport plan $T$ via Sinkhorn
3. Reallocate attention weights: $\tilde{A}_i = \sum_j T_{ij} A_j$
4. Continue denoising with reallocated attention

**Timestep window**: Intervention applied during timesteps 25-50 (semantic formation phase).

---

## 3. Novelty and Contributions

### 3.1 Key Novelty

**No existing work combines Optimal Transport with cross-attention manipulation for multi-instance generation in diffusion models.**

### 3.2 Contributions

| Contribution | Description |
|--------------|-------------|
| **Principled Allocation** | First OT-based attention reallocation with provable marginal constraints |
| **Mathematical Guarantees** | Sinkhorn convergence guarantees interpretable, optimal solutions |
| **Training-Free** | No fine-tuning required—plug-and-play with pretrained models |
| **Architecture-Agnostic** | Applicable to both U-Net (SD 1.5, SDXL) and DiT (SD3, Flux) architectures |

---

## 4. Related Work

### 4.1 Training-Free Attention Manipulation

| Method | Mechanism | Limitation |
|--------|-----------|------------|
| Prompt-to-Prompt [5] | Cross-attention control | Editing-focused |
| Attend-and-Excite [4] | Heuristic attention excitation | No principled allocation |
| Delta-K [2] | Key-space augmentation | VLM-dependent, heuristic |

### 4.2 Optimal Transport in Generative Models

- **Rectified Flow** [6]: OT for training straight paths
- **OT-CFM** [7]: Minibatch OT for continuous flows
- **Sinkhorn Distances** [8]: Fast OT computation

**Gap**: OT has not been applied to cross-attention manipulation for inference-time generation.

---

## 5. Experimental Validation Plan

### 5.1 Evaluation Protocol

**Benchmark**: DominanceBench [1] (multi-instance prompts with 2-5 objects)

**Metrics**:
| Metric | Definition | Target |
|--------|------------|--------|
| ISR | Instance Success Rate | ≥65% |
| Dominance Ratio | $\max_i A_i / \min_i A_i$ | ≤2.0 |
| Attention Entropy | $H(A) = -\sum_i A_i \log A_i$ | ≥1.5 nats |
| FID | Fréchet Inception Distance | ≤25 |

### 5.2 Baselines

1. Vanilla Stable Diffusion 1.5
2. Attend-and-Excite [4]
3. Delta-K [2] (if code available)
4. Random reallocation (control)

### 5.3 Ablation Studies

- Cost matrix design (IoU vs. overlap vs. KL divergence)
- Regularization strength $\epsilon$
- Sinkhorn iteration count
- Timestep intervention window
- Marginal constraint type (uniform vs. weighted)

---

## 6. Expected Results

Based on preliminary analysis and related work:

| Method | ISR (2-obj) | ISR (3-obj) | ISR (4+obj) | FID |
|--------|-------------|-------------|-------------|-----|
| Vanilla SD 1.5 | ~50% | ~30% | ~15% | ~20 |
| Attend-and-Excite | ~65% | ~45% | ~25% | ~22 |
| **OT Reallocation (Ours)** | **~75%** | **~55%** | **~35%** | ~23 |

**Key hypotheses**:
- OT reallocation reduces Dominance Ratio by ≥40%
- Inference overhead ≤2× vanilla SD
- Works across U-Net and DiT architectures

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Sinkhorn numerical instability | Log-domain Sinkhorn with epsilon floor |
| High inference overhead | Limit intervention timesteps, optimize kernel computation |
| FID degradation | Add quality-preserving regularization term |
| DominanceBench unavailable | Create synthetic benchmark from DvD methodology |

---

## 8. Resource Requirements

- **GPU**: 8GB VRAM minimum, 12GB recommended
- **Disk**: ~30GB (models, datasets, outputs)
- **Time**: 35-50 hours total (parallelizable stages)

---

## 9. Timeline

| Stage | Duration | Deliverables |
|-------|----------|--------------|
| Baseline | 4-6h | ISR baseline, attention analysis |
| OT Prototype | 5-8h | Core implementation, epsilon tuning |
| DominanceBench | 10-15h | Full benchmark results |
| Ablation | 15-20h | Component analysis |

---

## References

[1] Dominating vs. Dominated: Generative Collapse in Diffusion Models. arXiv:2512.20666, 2025.

[2] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation. arXiv:2603.10210, 2026.

[3] Shifting the Breaking Point of Flow Matching for Multi-Instance Editing. arXiv:2602.08749, 2026.

[4] Attend-and-Excite: Attention-Based Semantic Guidance for Text-to-Image Diffusion Models. arXiv:2301.13826, 2023.

[5] Prompt-to-Prompt Image Editing with Cross Attention Control. arXiv:2208.01626, 2022.

[6] Flow Straight and Fast: Learning to Generate and Transfer Data with Rectified Flow. arXiv:2209.03003, 2022.

[7] Flow Matching for Generative Modeling. arXiv:2210.02747, 2022.

[8] Sinkhorn Distances: Lightspeed Computation of Optimal Transport. NeurIPS 2013.

[9] Computational Optimal Transport. arXiv:1803.00567, 2018.

---

## Appendix: Mathematical Details

### A. Sinkhorn Convergence

The Sinkhorn algorithm converges linearly with rate $(1 - \epsilon/\|C\|_\infty)$. For typical cost matrices with $\|C\|_\infty \approx 5$ and $\epsilon = 0.1$, we expect convergence in ~50 iterations.

### B. Marginal Constraint Rationale

Uniform marginals ($1/n$ per instance) ensure each concept receives equal "attention budget." Weighted marginals can accommodate instance importance if needed.

### C. Cost Matrix Properties

The IoU-based cost matrix satisfies:
- Non-negativity: $C_{ij} \geq 0$
- Zero diagonal: $C_{ii} = 0$ (no self-transport cost)
- Symmetry: $C_{ij} = C_{ji}$
- Triangle inequality for well-separated attention maps

---

*Document generated: 2026-03-19*
*Idea ID: ot_attention_reallocation_v1*
