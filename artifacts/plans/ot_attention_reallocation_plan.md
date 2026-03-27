# Experimental Plan: Optimal Transport Attention Reallocation for Multi-Instance Dominance Mitigation

## Overview

**Goal**: Develop and validate a training-free method using Sinkhorn Optimal Transport to reallocate attention for balanced multi-instance generation in diffusion models.

**Key Innovation**: Mathematically principled attention reallocation via entropy-regularized Optimal Transport, providing guaranteed marginal constraints for fair instance representation.

**Research Problem**: Dominant-vs-Dominated (DvD) imbalance where one concept suppresses others during multi-instance generation.

---

## 1. Assumptions & Scope

### Assumptions
- Cross-attention maps $A_i \in \mathbb{R}^{H \times W}$ can be extracted from pretrained diffusion models without modification
- Sinkhorn algorithm converges within acceptable iteration budget (<50 iterations)
- Equal marginal constraint ($\frac{1}{n}$ per instance) is appropriate default; instance-specific weights can be added
- Dominance patterns manifest in attention map spatial overlap

### Scope
- **In-scope**: 
  - Training-free attention manipulation
  - U-Net architectures (SD 1.5, SDXL)
  - DiT architectures (SD3-base if accessible)
  - Multi-instance prompts (2-5 instances)
  - Instance Success Rate, attention entropy metrics
  
- **Out-of-scope**:
  - Training or fine-tuning diffusion models
  - Single-instance prompts
  - Video generation
  - Real-time inference optimization

### Key Mathematical Formulation
```
min_T  Σ_{i,j} C_{ij} T_{ij} - ε H(T)

subject to:
  Σ_j T_{ij} = 1/n  (equal attention mass per instance)
  T_{ij} ≥ 0

where:
  C = cost matrix based on attention overlap
  H(T) = entropy regularization
  K = exp(-C/ε) for Sinkhorn kernel
```

---

## 2. Stages

### Stage 1: Baseline Establishment

**Goal**: Establish baseline performance of vanilla Stable Diffusion and Attend-and-Excite on multi-instance prompts.

**Success Signals**:
- ISR (Instance Success Rate) baseline for SD 1.5 vanilla: expected ~30-50%
- ISR for Attend-and-Excite: expected ~50-70%
- Attention entropy baseline values
- CLIP score per instance baseline
- Qualitative: identify failure modes (dominated instance patterns)

**What to Run**:

1. **Environment Setup**
```bash
# Install dependencies
pip install torch torchvision diffusers transformers accelerate
pip install git+https://github.com/yuval-alaluf/Attend-and-Excite.git
pip install clip-interrogator ftfy

# Verify GPU
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f}GB')"
```

2. **Vanilla SD 1.5 Inference**
```bash
python scripts/baseline_inference.py \
  --model "runwayml/stable-diffusion-v1-5" \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage1/vanilla_sd15 \
  --num_samples 10 \
  --seed 42
```

3. **Attend-and-Excite Inference**
```bash
python scripts/attend_and_excite_inference.py \
  --model "runwayml/stable-diffusion-v1-5" \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage1/attend_and_excite \
  --num_samples 10 \
  --threshold 0.2 \
  --seed 42
```

4. **Extract and Analyze Attention Maps**
```bash
python scripts/extract_attention_maps.py \
  --model "runwayml/stable-diffusion-v1-5" \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage1/attention_analysis \
  --layers "up_blocks.1.attentions.1" "up_blocks.2.attentions.0"
```

**Expected Artifacts**:
- `outputs/stage1/vanilla_sd15/`: 100+ generated images
- `outputs/stage1/attend_and_excite/`: 100+ generated images
- `outputs/stage1/attention_analysis/attention_maps.pt`: Saved attention tensors
- `tables/baseline_isr.csv`: Instance Success Rate per prompt
- `plots/attention_entropy_distribution.png`: Entropy comparison
- `logs/baseline_metrics.json`: Quantitative metrics

**Dependencies**:
- Pretrained SD 1.5 (~4GB)
- Attend-and-Excite codebase
- Custom prompt dataset (create from COCO-style multi-object descriptions)

**Resource Estimate**:
- GPU: 8GB VRAM minimum, 12GB recommended
- Time: ~2-4 hours for 100 prompts × 10 samples
- Disk: ~2GB for outputs

---

### Stage 2: OT Attention Reallocation Prototype

**Goal**: Implement and validate Sinkhorn-based attention reallocation mechanism.

**Success Signals**:
- Sinkhorn algorithm converges in ≤50 iterations
- ISR improvement over vanilla SD: +15-25% absolute
- Attention entropy increase: ≥0.2 nats
- Per-instance CLIP score variance reduction: ≥30%
- Qualitative: visible reduction in DvD patterns

**What to Run**:

1. **Implement Core OT Module**
```python
# core/ot_attention.py - Key implementation
import torch
from geomloss import SamplesLoss

def compute_cost_matrix(attention_maps):
    """
    Compute cost matrix based on spatial overlap.
    C_ij = -log(1 - IoU(A_i, A_j)) for overlapping regions
    """
    n_instances = len(attention_maps)
    C = torch.zeros(n_instances, n_instances)
    for i in range(n_instances):
        for j in range(n_instances):
            if i != j:
                overlap = (attention_maps[i] * attention_maps[j]).sum()
                union = attention_maps[i].sum() + attention_maps[j].sum() - overlap
                iou = overlap / (union + 1e-8)
                C[i, j] = -torch.log(1 - iou + 1e-8)
    return C

def sinkhorn_reallocate(attention_maps, epsilon=0.1, n_iter=50):
    """
    Sinkhorn iterations for attention reallocation.
    Returns transport plan T for reallocation weights.
    """
    C = compute_cost_matrix(attention_maps)
    K = torch.exp(-C / epsilon)
    n = len(attention_maps)
    
    # Uniform marginals
    a = torch.ones(n) / n
    b = torch.ones(n) / n
    
    u = torch.ones(n)
    for _ in range(n_iter):
        v = b / (K.T @ u)
        u = a / (K @ v)
    
    T = torch.diag(u) @ K @ torch.diag(v)
    return T
```

2. **Install OT Dependencies**
```bash
pip install geomloss pot  # Python Optimal Transport library
```

3. **Run OT Prototype**
```bash
python scripts/ot_attention_inference.py \
  --model "runwayml/stable-diffusion-v1-5" \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage2/ot_prototype \
  --epsilon 0.1 \
  --sinkhorn_iters 50 \
  --intervention_timesteps "25-50" \
  --num_samples 10
```

4. **Hyperparameter Search (Epsilon)**
```bash
python scripts/hyperparam_search.py \
  --param epsilon \
  --values 0.05 0.1 0.2 0.5 1.0 \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage2/hyperparam_epsilon
```

**Expected Artifacts**:
- `core/ot_attention.py`: Core OT implementation
- `outputs/stage2/ot_prototype/`: Generated images
- `outputs/stage2/transport_maps/`: Visualized transport plans
- `tables/ot_vs_baseline.csv`: Comparison metrics
- `plots/sinkhorn_convergence.png`: Iteration convergence curves
- `plots/epsilon_sensitivity.png`: Epsilon parameter analysis

**Dependencies**:
- POT (Python Optimal Transport) or geomloss
- Stage 1 baseline results for comparison

**Resource Estimate**:
- GPU: 8GB VRAM
- Time: ~3-5 hours (including hyperparameter search)
- Disk: ~3GB

---

### Stage 3: DominanceBench Evaluation

**Goal**: Systematic evaluation on DominanceBench to measure DvD mitigation effectiveness.

**Success Signals**:
- Average ISR on DominanceBench: ≥65% (vs. ~45% baseline)
- Dominance Ratio reduction: ≥40% (metric from DvD paper)
- FID score: ≤25 (maintaining image quality)
- Inference overhead: ≤2× vanilla SD

**What to Run**:

1. **Prepare DominanceBench Dataset**
```bash
# Download or create DominanceBench-style prompts
python scripts/prepare_dominancebench.py \
  --output data/dominancebench_prompts.json \
  --categories 2obj 3obj 4obj 5obj \
  --prompts_per_category 50
```

2. **Run Full Evaluation Suite**
```bash
# Vanilla SD
python scripts/evaluate_dominancebench.py \
  --method vanilla \
  --output_dir outputs/stage3/vanilla_dominancebench

# Attend-and-Excite
python scripts/evaluate_dominancebench.py \
  --method attend_and_excite \
  --output_dir outputs/stage3/a_e_dominancebench

# OT Reallocation (Ours)
python scripts/evaluate_dominancebench.py \
  --method ot_reallocation \
  --epsilon 0.1 \
  --output_dir outputs/stage3/ot_dominancebench
```

3. **Compute Dominance Metrics**
```bash
python scripts/compute_dominance_metrics.py \
  --results_dir outputs/stage3 \
  --output tables/dominancebench_results.csv
```

4. **Cross-Architecture Evaluation (DiT)**
```bash
# If SD3 or FLUX accessible
python scripts/evaluate_dit.py \
  --model "stabilityai/stable-diffusion-3-medium" \
  --prompts data/dominancebench_prompts.json \
  --output_dir outputs/stage3/sd3_ot
```

**Expected Artifacts**:
- `tables/dominancebench_results.csv`: Full benchmark results
- `tables/per_category_breakdown.csv`: Results by instance count
- `plots/isr_comparison.png`: Bar chart comparing methods
- `plots/dominance_ratio_reduction.png`: DvD mitigation visualization
- `plots/fid_vs_isr.png`: Quality-diversity tradeoff
- `logs/evaluation_summary.json`: Aggregate metrics

**Dependencies**:
- DominanceBench prompt set (create if not publicly available)
- Object detector for ISR computation (OWL-ViT or GroundingDINO)
- CLIP model for semantic alignment scores
- FID computation (clean-fid package)

**Resource Estimate**:
- GPU: 12GB VRAM for SDXL/SD3
- Time: ~8-12 hours for full benchmark
- Disk: ~10GB for all outputs

---

### Stage 4: Ablation Studies

**Goal**: Understand component contributions and validate design choices.

**Success Signals**:
- Identify critical vs. non-critical components
- Understand sensitivity to hyperparameters
- Validate cost matrix design choices
- Confirm Sinkhorn iteration budget sufficiency

**What to Run**:

1. **Cost Matrix Ablation**
```bash
python scripts/ablation_cost_matrix.py \
  --cost_types iou overlap_area kl_divergence learned \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage4/ablation_cost
```

2. **Sinkhorn Iterations Ablation**
```bash
python scripts/ablation_sinkhorn_iters.py \
  --iterations 10 20 30 50 100 200 \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage4/ablation_iters
```

3. **Epsilon (Regularization) Ablation**
```bash
# Already done in Stage 2, but extend with finer grid
python scripts/ablation_epsilon.py \
  --epsilon_values 0.01 0.02 0.05 0.1 0.2 0.5 1.0 2.0 \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage4/ablation_epsilon
```

4. **Timestep Intervention Window**
```bash
python scripts/ablation_timesteps.py \
  --intervention_windows "0-25" "25-50" "50-75" "0-50" "25-75" \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage4/ablation_timesteps
```

5. **Marginal Constraint Ablation**
```bash
# Uniform vs. weighted marginals
python scripts/ablation_marginals.py \
  --marginal_types uniform proportional inverse_size \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage4/ablation_marginals
```

6. **Architecture Ablation (U-Net vs DiT)**
```bash
# Compare behavior across architectures
python scripts/ablation_architecture.py \
  --models sd15 sdxl sd3 \
  --prompts data/multi_instance_prompts_2obj.json \
  --output_dir outputs/stage4/ablation_arch
```

**Expected Artifacts**:
- `tables/ablation_summary.csv`: All ablation results
- `plots/cost_matrix_comparison.png`: ISR by cost type
- `plots/sinkhorn_iters_curve.png`: Convergence analysis
- `plots/epsilon_tradeoff.png`: Regularization vs. performance
- `plots/timestep_window.png`: Optimal intervention period
- `plots/marginal_types.png`: Uniform vs. weighted comparison
- `plots/architecture_comparison.png`: U-Net vs DiT behavior

**Dependencies**:
- All previous stages completed
- Extended compute for multiple ablation runs

**Resource Estimate**:
- GPU: 12GB VRAM
- Time: ~12-16 hours for all ablations
- Disk: ~15GB

---

## 3. Dependencies

### Data Dependencies
| Dataset | Source | Size | Purpose |
|---------|--------|------|---------|
| Multi-instance prompts | Custom/COCO-derived | 100+ prompts | Stage 1-2 development |
| DominanceBench | Create based on DvD paper | 200+ prompts | Stage 3 evaluation |

### Model Dependencies
| Model | Size | Download Source | Purpose |
|-------|------|-----------------|---------|
| SD 1.5 | ~4GB | HuggingFace | Primary architecture |
| SDXL | ~6GB | HuggingFace | High-quality baseline |
| CLIP ViT-L/14 | ~600MB | OpenAI | Semantic scoring |
| OWL-ViT | ~600MB | Google | Object detection for ISR |

### Code Dependencies
| Repository | Purpose |
|------------|---------|
| Attend-and-Excite | Baseline comparison |
| diffusers | Diffusion model inference |
| transformers | Tokenizer, CLIP |
| POT/geomloss | Optimal Transport solvers |
| clean-fid | FID computation |

### Environment Requirements
```bash
# requirements.txt
torch>=2.0.0
torchvision>=0.15.0
diffusers>=0.25.0
transformers>=4.35.0
accelerate>=0.24.0
pot>=0.9.0
geomloss>=0.2.6
clip-interrogator>=0.5.0
clean-fid>=0.1.35
ftfy>=6.1.0
opencv-python>=4.8.0
numpy>=1.24.0
pandas>=2.0.0
matplotlib>=3.7.0
seaborn>=0.12.0
tqdm>=4.66.0
```

---

## 4. Iteration Triggers

### When to Change Dataset
- ISR variance across prompts is too high (>30% std)
- Prompts don't cover diverse instance combinations
- Missing edge cases (similar instances, varying sizes)

### When to Change Model/Objective
- OT method shows no improvement over baseline after epsilon tuning
- FID degradation is unacceptable (>30)
- Inference overhead exceeds 3× baseline

### When to Pivot Approach
- Sinkhorn fails to converge within 100 iterations
- Attention reallocation introduces artifacts
- Cost matrix design doesn't capture dominance patterns

---

## 5. Evaluation Protocol

### Data Splits
- **Development set**: 30 prompts for method development
- **Validation set**: 50 prompts for hyperparameter tuning
- **Test set**: 100+ prompts for final evaluation (DominanceBench)

### Primary Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **ISR** | Instance Success Rate: % of instances correctly generated | ≥65% |
| **Attention Entropy** | $H(A) = -\sum_i A_i \log A_i$ | ≥1.5 nats |
| **CLIP Score/Instance** | CLIP similarity per instance | ≥0.25 |
| **Dominance Ratio** | $\max_i A_i / \min_i A_i$ | ≤2.0 |
| **FID** | Fréchet Inception Distance | ≤25 |

### Secondary Metrics
- Inference time overhead
- Sinkhorn convergence iterations
- Per-category ISR (by instance count: 2, 3, 4, 5+)

### Baselines for Comparison
1. **Vanilla SD 1.5**: No intervention
2. **Attend-and-Excite**: Heuristic attention excitation
3. **Delta-K** (if code available): Key-space augmentation
4. **Random reallocation**: Control for OT benefit

### Data Quality Checks
```python
def validate_prompts(prompts):
    """Ensure prompts have correct structure for multi-instance evaluation."""
    for p in prompts:
        assert 'text' in p, "Missing text field"
        assert 'instances' in p, "Missing instances list"
        assert len(p['instances']) >= 2, "Need at least 2 instances"
        assert len(p['instances']) <= 5, "Max 5 instances for tractability"
```

---

## 6. Environment Preflight

### GPU/CUDA Check
```bash
# Check CUDA availability and VRAM
python -c "
import torch
print(f'PyTorch: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'Device: {torch.cuda.get_device_name(0)}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
"
```

### Disk Space Check
```bash
# Ensure sufficient disk space
df -h .
# Recommend: ≥50GB free for models, datasets, outputs
```

### Model Download Preflight
```bash
# Pre-download models to avoid runtime delays
python scripts/preflight_download.py --models sd15 sdxl clip
```

### Quick Smoke Test
```bash
# Verify all components work
python scripts/smoke_test.py --quick
# Should complete in <5 minutes, verify:
# - Model loading
# - Attention extraction
# - Sinkhorn convergence
# - Image generation
```

---

## 7. Expected Timeline

| Stage | Duration | Parallelizable |
|-------|----------|----------------|
| Stage 1: Baseline | 4-6 hours | Partially (vanilla vs A&E) |
| Stage 2: OT Prototype | 5-8 hours | Partially (epsilon search) |
| Stage 3: DominanceBench | 10-15 hours | Yes (per-category) |
| Stage 4: Ablation | 15-20 hours | Yes (per-ablation) |
| **Total** | **35-50 hours** | |

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| DominanceBench not publicly available | Create synthetic benchmark based on DvD paper methodology |
| Sinkhorn numerical instability | Use log-domain Sinkhorn, add small epsilon floor |
| High inference overhead | Profile and optimize, limit intervention timesteps |
| FID degradation | Add quality-preserving regularization term |
| DiT incompatibility | Design attention hook to be architecture-agnostic |

---

## Plan Update JSON

```json
{
  "plan_id": "ot_attention_reallocation_v1",
  "created": "2026-03-20",
  "stages": [
    {
      "stage_id": 1,
      "title": "Baseline Establishment",
      "goal": "Establish baseline performance of vanilla SD and Attend-and-Excite",
      "success_signals": [
        "ISR baseline for SD 1.5 vanilla: ~30-50%",
        "ISR for Attend-and-Excite: ~50-70%",
        "Attention entropy baseline recorded",
        "DvD failure patterns identified"
      ],
      "what_to_run": [
        "Install dependencies: diffusers, transformers, Attend-and-Excite",
        "Run vanilla SD 1.5 inference on multi-instance prompts",
        "Run Attend-and-Excite inference",
        "Extract and analyze attention maps",
        "Compute baseline metrics (ISR, entropy, CLIP)"
      ],
      "expected_artifacts": [
        "outputs/stage1/vanilla_sd15/",
        "outputs/stage1/attend_and_excite/",
        "tables/baseline_isr.csv",
        "plots/attention_entropy_distribution.png"
      ],
      "dependencies": [
        "Pretrained SD 1.5 (~4GB)",
        "Attend-and-Excite codebase",
        "Custom prompt dataset"
      ],
      "resource_estimate": {
        "gpu_vram": "8GB minimum, 12GB recommended",
        "time_hours": "2-4",
        "disk_gb": 2
      }
    },
    {
      "stage_id": 2,
      "title": "OT Attention Reallocation Prototype",
      "goal": "Implement and validate Sinkhorn-based attention reallocation",
      "success_signals": [
        "Sinkhorn converges in ≤50 iterations",
        "ISR improvement over vanilla: +15-25%",
        "Attention entropy increase: ≥0.2 nats",
        "CLIP score variance reduction: ≥30%"
      ],
      "what_to_run": [
        "Implement core OT module with Sinkhorn solver",
        "Design cost matrix (IoU-based overlap)",
        "Run OT prototype inference",
        "Hyperparameter search for epsilon",
        "Compare with Stage 1 baselines"
      ],
      "expected_artifacts": [
        "core/ot_attention.py",
        "outputs/stage2/ot_prototype/",
        "tables/ot_vs_baseline.csv",
        "plots/sinkhorn_convergence.png",
        "plots/epsilon_sensitivity.png"
      ],
      "dependencies": [
        "POT or geomloss library",
        "Stage 1 baseline results"
      ],
      "resource_estimate": {
        "gpu_vram": "8GB",
        "time_hours": "3-5",
        "disk_gb": 3
      }
    },
    {
      "stage_id": 3,
      "title": "DominanceBench Evaluation",
      "goal": "Systematic evaluation on DominanceBench for DvD mitigation",
      "success_signals": [
        "Average ISR on DominanceBench: ≥65%",
        "Dominance Ratio reduction: ≥40%",
        "FID score: ≤25",
        "Inference overhead: ≤2× vanilla"
      ],
      "what_to_run": [
        "Prepare DominanceBench-style prompts (2-5 instances)",
        "Run vanilla, Attend-and-Excite, OT reallocation",
        "Compute ISR, dominance ratio, FID metrics",
        "Cross-architecture evaluation (SDXL, SD3 if available)",
        "Generate comparison tables and plots"
      ],
      "expected_artifacts": [
        "tables/dominancebench_results.csv",
        "plots/isr_comparison.png",
        "plots/dominance_ratio_reduction.png",
        "plots/fid_vs_isr.png"
      ],
      "dependencies": [
        "DominanceBench prompt set",
        "Object detector (OWL-ViT/GroundingDINO)",
        "CLIP for semantic scoring",
        "clean-fid for FID"
      ],
      "resource_estimate": {
        "gpu_vram": "12GB",
        "time_hours": "8-12",
        "disk_gb": 10
      }
    },
    {
      "stage_id": 4,
      "title": "Ablation Studies",
      "goal": "Understand component contributions and validate design choices",
      "success_signals": [
        "Identify critical vs non-critical components",
        "Determine optimal hyperparameter ranges",
        "Validate cost matrix design",
        "Confirm iteration budget sufficiency"
      ],
      "what_to_run": [
        "Cost matrix ablation (IoU, overlap, KL, learned)",
        "Sinkhorn iterations ablation (10-200)",
        "Epsilon regularization ablation (fine grid)",
        "Timestep intervention window ablation",
        "Marginal constraint ablation (uniform vs weighted)",
        "Architecture ablation (U-Net vs DiT)"
      ],
      "expected_artifacts": [
        "tables/ablation_summary.csv",
        "plots/cost_matrix_comparison.png",
        "plots/sinkhorn_iters_curve.png",
        "plots/epsilon_tradeoff.png",
        "plots/timestep_window.png",
        "plots/architecture_comparison.png"
      ],
      "dependencies": [
        "All previous stages completed",
        "Extended compute resources"
      ],
      "resource_estimate": {
        "gpu_vram": "12GB",
        "time_hours": "12-16",
        "disk_gb": 15
      }
    }
  ],
  "total_resource_estimate": {
    "gpu_vram_min": "8GB",
    "gpu_vram_recommended": "12GB",
    "total_time_hours": "35-50",
    "total_disk_gb": 30
  },
  "evaluation_protocol": {
    "primary_metrics": ["ISR", "Attention Entropy", "CLIP Score/Instance", "Dominance Ratio", "FID"],
    "baselines": ["Vanilla SD 1.5", "Attend-and-Excite", "Delta-K (if available)", "Random reallocation"],
    "target_isr": "≥65%",
    "target_fid": "≤25"
  },
  "iteration_triggers": {
    "change_dataset": "ISR variance >30% across prompts",
    "change_objective": "No improvement after epsilon tuning or FID >30",
    "pivot_approach": "Sinkhorn fails to converge in 100 iters or artifacts introduced"
  }
}
```

---

## Summary

This plan provides a structured approach to develop and validate OT Attention Reallocation for multi-instance dominance mitigation. Key strengths:

1. **Training-free**: Uses pretrained models, no GPU-intensive training
2. **Mathematically principled**: Sinkhorn OT provides guaranteed convergence and interpretable transport plans
3. **Architecture-agnostic**: Targets both U-Net and DiT via cross-attention abstraction
4. **Comprehensive evaluation**: DominanceBench + extensive ablations
5. **Resource-efficient**: All experiments feasible on single 12GB GPU

**Critical next step**: Execute Stage 1 baseline to establish performance benchmarks before OT implementation.