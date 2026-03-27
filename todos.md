# Experiment Todo List

## Project: Optimal Transport Attention Reallocation for Multi-Instance Dominance Mitigation

### Completed Tasks
- [x] Idea discovery and selection
- [x] Competitor/baseline research
- [x] Research request documentation
- [x] Experiment plan creation

### Pending Tasks

#### Stage 1: Baseline Establishment
- [ ] Set up environment (diffusers, transformers, POT)
- [ ] Create multi-instance prompt dataset
- [ ] Run vanilla SD 1.5 inference
- [ ] Run Attend-and-Excite baseline
- [ ] Extract and analyze attention maps
- [ ] Compute baseline ISR, entropy, CLIP scores
- **Success Signals**: ISR baseline 30-70%, attention entropy recorded

#### Stage 2: OT Attention Reallocation Prototype
- [ ] Implement `core/ot_attention.py` (Sinkhorn algorithm)
- [ ] Design cost matrix (IoU-based)
- [ ] Integrate OT with SD cross-attention hooks
- [ ] Run hyperparameter search (epsilon)
- [ ] Compare against Stage 1 baselines
- **Success Signals**: ISR +15-25% over vanilla, Sinkhorn convergence ≤50 iters

#### Stage 3: DominanceBench Evaluation
- [ ] Prepare DominanceBench-style prompts
- [ ] Run full evaluation suite (vanilla, A&E, OT)
- [ ] Compute dominance ratio metrics
- [ ] Cross-architecture evaluation (DiT if accessible)
- **Success Signals**: ISR ≥65%, Dominance Ratio reduction ≥40%

#### Stage 4: Ablation Studies
- [ ] Cost matrix ablation (IoU, overlap, KL)
- [ ] Sinkhorn iterations ablation
- [ ] Epsilon (regularization) ablation
- [ ] Timestep intervention window ablation
- [ ] Marginal constraint ablation
- [ ] Architecture ablation (U-Net vs DiT)
- **Success Signals**: Identify critical components

#### Final Report
- [ ] Compile results tables
- [ ] Generate comparison plots
- [ ] Write final report

---

## Resource Estimates
- **GPU**: 8GB minimum, 12GB recommended
- **Disk**: ~30GB total
- **Time**: 35-50 hours

## Key Files
- Plan: `/artifacts/plans/ot_attention_reallocation_plan.md`
- Research Request: `/research_request_ot_attention.md`
- Idea Brief: `/artifacts/ideas/.../optimal-transport-attention-reallocation.md`
