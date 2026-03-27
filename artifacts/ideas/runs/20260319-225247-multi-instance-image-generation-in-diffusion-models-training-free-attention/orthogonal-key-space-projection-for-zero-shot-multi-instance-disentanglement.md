# Orthogonal Key-Space Projection for Zero-Shot Multi-Instance Disentanglement

## Idea Description
A training-free method that enforces geometric orthogonality in the cross-attention Key space to prevent instance confusion, complementing existing differential key approaches.

## Research Request
- Query: multi-instance image generation in diffusion models, training-free attention
- Requirements: novel and with good math properties, low-cost experiments
- Notes: prefer papers after 2024

## Relevant Evidence And Research Results
### Evidence 1: [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation
- URL: https://arxiv.org/abs/2603.10210
- Source Type: webpage
- Relevance Score: 0.0
- Summary: [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation We gratefully acknowledge support from the Simons Foundation, , and all contributors. arXiv:2603.10210 | All fields Title Author Abstract Comments Journal reference ACM classification MSC classification Report number arXiv identifier DOI ORCID arXiv author ID Help pages Full text Search open search GO open navigation menu quick links Computer Science > Computer Vision and Pattern Recognition ========================================================== arXiv:2603.10210** (cs) [Submitted on 10 Mar 2026] Title:Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation ================================================================================== Authors: , , , , View a PDF of the paper titled Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation, by Zitong Wang and 4 other authors Abstract:While Diffusion Models excel in text-to-image synthesis, they often suffer from concept omission when synthesizing complex multi-instance scenes. Existing training-free methods attempt to resolve this by rescaling attention maps, which merely exacerbates unstructured noise without establishing coherent semantic representations.
- Research Results:
  - [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation We gratefully acknowledge support from the Simons Foundation, , and all contributors.
  - To address this, we propose Delta-K, a backbone-agnostic and plug-and-play inference framework that tackles omission by operating directly in the shared cross-attention Key space.
  - Specifically, with Vision-language model, we extract a differential key $\Delta K$ that encodes the semantic signature of missing concepts.
  - Extensive experiments demonstrate the generality of our approach: Delta-K consistently improves compositional alignment across both modern DiT models and classical U-Net architectures, without requiring spatial masks, additional training, or architectural modifications.
  - Data provided by: Bookmark Bibliographic Tools Bibliographic and Citation Tools ================================ Bibliographic Explorer Toggle Bibliographic Explorer *( )* Connected Papers Toggle Connected Papers *( )* Litmaps Toggle Litmaps *( )* scite.ai Toggle scite Smart Citations *( )* Code, Data, Media Code, Data and Media Associated with this Article ================================================= alphaXiv Toggle alphaXiv *( )* Links to Code Toggle CatalyzeX Code Finder for Papers *( )* DagsHub Toggle DagsHub *( )* GotitPub Toggle Gotit.pub *( )* Huggingface Toggle Hugging Face *( )* Links to Code Toggle Papers with Code *( )* ScienceCast Toggle ScienceCast *( )* Demos Demos ===== Replicate Toggle Replicate *( )* Spaces Toggle Hugging Face Spaces *( )* Spaces Toggle TXYZ.AI *( )* Related Papers Recommenders and Search Tools ============================= Link to Influence Flower Influence Flower *( )* Core recommender toggle CORE Recommender *( )* Author Venue Institution Topic About arXivLabs arXivLabs: experimental projects with community collaborators ============================================================= arXivLabs is a framework that allows collaborators to develop and share new arXiv features directly on our website.

### Evidence 2: [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models
- URL: https://arxiv.org/abs/2512.20666
- Source Type: webpage
- Relevance Score: 0.0
- Summary: [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models We gratefully acknowledge support from the Simons Foundation, , and all contributors. arXiv:2512.20666 | All fields Title Author Abstract Comments Journal reference ACM classification MSC classification Report number arXiv identifier DOI ORCID arXiv author ID Help pages Full text Search open search GO open navigation menu quick links Computer Science > Machine Learning =================================== arXiv:2512.20666** (cs) [Submitted on 19 Dec 2025] Title:Dominating vs.
- Research Results:
  - Dominated: Generative Collapse in Diffusion Models We gratefully acknowledge support from the Simons Foundation, , and all contributors.
  - However, when generating from multi-concept prompts, one concept token often dominates the generation, suppressing the others-a phenomenon we term the Dominant-vs-Dominated (DvD) imbalance.
  - To systematically analyze this imbalance, we introduce DominanceBench and examine its causes from both data and architectural perspectives.
  - Through various experiments, we show that the limited instance diversity in training data exacerbates the inter-concept interference.
  - In addition, head ablation studies show that the DvD behavior arises from distributed attention mechanisms across multiple heads.

## Open Questions
- What is the strongest novelty claim compared with existing work?
- Which experiments would most directly validate this idea?
- What assumptions or risks still need to be checked?

## Sources
- [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation: https://arxiv.org/abs/2603.10210
- [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models: https://arxiv.org/abs/2512.20666
