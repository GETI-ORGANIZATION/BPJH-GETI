# Optimal Transport Attention Reallocation for Multi-Instance Dominance Mitigation

## Idea Description
A training-free framework that formulates the multi-instance attention allocation problem as an Optimal Transport (OT) problem to mathematically guarantee balanced semantic distribution. Applies Sinkhorn algorithms to solve an entropy-regularized OT problem between the spatial distribution of attention maps and a uniform target distribution across multiple instances, ensuring fair generation and addressing the Dominant-vs-Dominated (DvD) imbalance.

## Research Request
- Query: multi-instance image generation in diffusion models, training-free attention
- Requirements: novel and with good math properties, low-cost experiments
- Notes: prefer papers after 2024

## Motivation
The 'Dominant-vs-Dominated' phenomenon suggests an uneven distribution of 'attention mass' among instances. Current rescaling methods lack a rigorous mathematical basis for redistributing this mass globally.

## Novelty
Applies Sinkhorn algorithms to solve an entropy-regularized Optimal Transport problem between the spatial distribution of attention maps and a uniform target distribution across multiple instances, ensuring fair generation.

## Proposed Method
Compute attention maps $A_1, ..., A_n$ for $n$ instances. Define a cost matrix based on spatial overlap. Use an OT solver to find a transport plan that redistributes attention probabilities to minimize overlap and maximize uniform coverage, correcting the DvD imbalance without retraining.

### Mathematical Formulation
Let $A_i \in \mathbb{R}^{H \times W}$ denote the attention map for instance $i$. We formulate the reallocation as:

$$\min_{T} \sum_{i,j} C_{ij} T_{ij} - \epsilon H(T)$$

subject to:
- $\sum_j T_{ij} = \frac{1}{n}$ (each instance gets equal total attention mass)
- $T_{ij} \geq 0$

where $C_{ij}$ is the cost of moving attention mass, and $H(T)$ is the entropy regularization term.

The Sinkhorn algorithm solves this efficiently with iterations:
- $u^{(k+1)} = \frac{a}{K v^{(k)}}$
- $v^{(k+1)} = \frac{b}{K^\top u^{(k+1)}}$

where $K = \exp(-C/\epsilon)$.

## Validation Plan
1. Experiments on COCO dataset prompts with multiple objects
2. Compare the entropy of attention distributions
3. Measure Instance Success Rate (ISR)
4. Visualize the transport maps to show how dominance is suppressed

## Key Metrics
- **Instance Success Rate (ISR)**: Fraction of prompts where all instances appear correctly
- **Attention Entropy**: Measure of balanced attention distribution
- **CLIP Score per Instance**: Semantic alignment for each instance
- **Object Detection mAP**: Verifying instance presence

## Risks
- The iterative Sinkhorn algorithm may introduce computational overhead during inference
- Need to balance regularization strength $\epsilon$ for stability vs. sharpness

## Relevant Evidence And Research Results

### Evidence 1: [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models
- URL: https://arxiv.org/abs/2512.20666
- Key Findings:
  - DvD imbalance is a significant issue where one token suppresses others
  - DominanceBench introduced to systematically analyze these imbalances
  - Limited instance diversity in training data exacerbates inter-concept interference
  - DvD behavior arises from distributed attention mechanisms across multiple heads

### Evidence 2: [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation
- URL: https://arxiv.org/abs/2603.10210
- Key Findings:
  - Concept omission is a frequent failure mode in complex scenes
  - Existing training-free rescaling methods exacerbate unstructured noise
  - Operating in cross-attention Key space is promising for resolving conflicts
  - Backbone-agnostic and plug-and-play inference possible

### Evidence 3: [2602.08749] Shifting the Breaking Point of Flow Matching for Multi-Instance Editing
- URL: https://arxiv.org/abs/2602.08749
- Key Findings:
  - Globally conditioned velocity fields and joint attention entangle concurrent edits
  - Instance-Disentangled Attention partitions joint attention operations
  - Enforces binding between instance-specific textual instructions and spatial regions

## Open Questions
1. What is the optimal cost matrix design for attention reallocation?
2. How many Sinkhorn iterations are needed for convergence without significant overhead?
3. Does OT reallocation complement or conflict with Delta-K's key-space intervention?
4. How to handle varying instance sizes/complexities while maintaining fairness?

## Competitor Analysis

### Training-Free Methods (Baselines)
| Method | Year | Mechanism | Code | Limitation |
|--------|------|-----------|------|------------|
| Prompt-to-Prompt | 2022 | Cross-attention control | Available | Editing-focused |
| Attend-and-Excite | 2023 | Heuristic attention excitation | Available | No principled allocation |
| Delta-K | 2026 | Key-space augmentation | TBD | VLM-dependent, heuristic |
| Instance-Disentangled | 2026 | Attention partitioning | TBD | Flow-matching only |

### Key Novelty Gap
**No existing work combines Optimal Transport (Sinkhorn) with cross-attention manipulation for multi-instance generation.**

Our OT Attention Reallocation fills this gap by providing:
1. **Principled vs Heuristic**: Sinkhorn provides mathematically optimal transport plan
2. **Token-to-Spatial Matching**: Formulate attention as OT between concepts and pixels
3. **Fair Marginal Constraints**: Enforce equal attention budget per concept via OT
4. **Theoretical Guarantees**: Convergence proofs and interpretable solutions

## Experiment Plan
See: `/artifacts/plans/ot_attention_reallocation_plan.md`

### Stage Overview
| Stage | Goal | Success Signal |
|-------|------|----------------|
| 1. Baseline | Establish vanilla SD + A&E performance | ISR baseline 30-70% |
| 2. OT Prototype | Implement Sinkhorn reallocation | ISR +15-25% over vanilla |
| 3. DominanceBench | Systematic DvD evaluation | ISR ≥65%, FID ≤25 |
| 4. Ablation | Validate design choices | Identify critical components |

## Sources
- [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models: https://arxiv.org/abs/2512.20666
- [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation: https://arxiv.org/abs/2603.10210
- [2602.08749] Shifting the Breaking Point of Flow Matching for Multi-Instance Editing: https://arxiv.org/abs/2602.08749
- [2301.13826] Attend-and-Excite: https://arxiv.org/abs/2301.13826
- [2208.01626] Prompt-to-Prompt: https://arxiv.org/abs/2208.01626
- [1803.00567] Computational Optimal Transport: https://arxiv.org/abs/1803.00567
