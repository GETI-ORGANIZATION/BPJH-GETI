# Idea Pipeline Log

- Query: multi-instance image generation in diffusion models, training-free attention
- Generated At: 2026-03-19 22:55:51
- Log Path: artifacts/ideas/runs/20260319-225247-multi-instance-image-generation-in-diffusion-models-training-free-attention/pipeline_log.md

## Request
/idea start
query: multi-instance image generation in diffusion models, training-free attention
max_ideas: 5
max_sources: 6
site_urls:
- https://arxiv.org/search/?query=multi-instance+image+generation+diffusion+attention&searchtype=all&abstracts=show&order=-announced_date_first&size=50
requirements:
- novel and with good math properties
- low-cost experiments
notes:
- prefer papers after 2024

## Steps
### Step 1: Parse Request
- Time: 2026-03-19 22:52:47
- Status: OK
- Details: Parsed query='multi-instance image generation in diffusion models, training-free attention', requirements=2, notes=1, seed_urls=1, site_urls=1, max_sources=6, max_ideas=5, run_id=20260319-225247-multi-instance-image-generation-in-diffusion-models-training-free-attention

### Step 2: Crawl Site Articles
- Time: 2026-03-19 22:52:50
- Status: OK
- Details: Crawled 1 site(s) and discovered 6 article link(s).
Saved crawl index to D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/site_crawl_index.json
Saved crawl report to D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/site_crawl_report.md

### Step 3: Collect Sources
- Time: 2026-03-19 22:52:50
- Status: OK
- Details: Collected 7 source(s) for 'multi-instance image generation in diffusion models, training-free attention'.
Saved index: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/source_index.json
1. search (webpage) - https://arxiv.org/search/?query=multi-instance+image+generation+diffusion+attention&searchtype=all&abstracts=show&order=-announced_date_first&size=50
2. 2603 (webpage) - https://arxiv.org/abs/2603.10210
3. 2603 (webpage) - https://arxiv.org/pdf/2603.10210
4. 2602 (webpage) - https://arxiv.org/abs/2602.08749
5. 2602 (webpage) - https://arxiv.org/pdf/2602.08749
Note: Tavily search skipped because TAVILY_API_KEY is not configured.

### Step 4: Select Sources
- Time: 2026-03-19 22:52:50
- Status: OK
- Details: 1. search - https://arxiv.org/search/?query=multi-instance+image+generation+diffusion+attention&searchtype=all&abstracts=show&order=-announced_date_first&size=50
2. 2603 - https://arxiv.org/abs/2603.10210
3. 2603 - https://arxiv.org/pdf/2603.10210
4. 2602 - https://arxiv.org/abs/2602.08749
5. 2602 - https://arxiv.org/pdf/2602.08749
6. 2512 - https://arxiv.org/abs/2512.20666

### Step 5: Read Source
- Time: 2026-03-19 22:52:53
- Status: OK
- Details: Read source: Search | arXiv e-print repository
Type: webpage
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
Content artifact: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/sources/search-arxiv-e-print-repository-a56dce2245.md
Relevance score: 0.0
Summary: Search | arXiv e-print repository We gratefully acknowledge support from the Simons Foundation, , and all contributors. | All fields Title Author Abstract Comments Journal reference ACM classification MSC classification Report number arXiv identifier DOI ORCID arXiv author ID Help pages Full text Search Showing 1–16 of 16 results for all: multi-instance image generation diffusion attention ======================================================================================= Search term or terms Field All fieldsTitleAuthor(s)AbstractCommentsJournal referenceACM classificationMSC classificationReport numberarXiv identifierDOIORCIDLicense (URI)arXiv author IDHelp pagesFull text Search Show abstracts Hide abstracts All fieldsTitleAuthor(s)AbstractCommentsJournal referenceACM classificationMSC classificationReport numberarXiv identifierDOIORCIDLicense (URI)arXiv author IDHelp pagesFull text Show abstracts Hide abstracts results per page. Sort results by Announcement date (newest first)Announcement date (oldest first)Submission date (newest first)Submission date (oldest first)Relevance Go , , ] cs.CV cs.AI Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation Authors: , , , , Abstract: While Diffusion Models excel in text-to-… ▽ More While Diffusion Models excel in text-to-image synthesis, they often suffer from concept omission when synthesizing complex multi-instance scenes.

### Step 6: Extract Claims
- Time: 2026-03-19 22:52:53
- Status: OK
- Details: Extracted 5 claim(s) from Search | arXiv e-print repository.
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
- Search | arXiv e-print repository We gratefully acknowledge support from the Simons Foundation, , and all contributors.
- | All fields Title Author Abstract Comments Journal reference ACM classification MSC classification Report number arXiv identifier DOI ORCID arXiv author ID Help pages Full text Search Showing 1–16 of 16 results for all: multi-instance image generation diffusion attention ======================================================================================= Search term or terms Field All fieldsTitleAuthor(s)AbstractCommentsJournal referenceACM classificationMSC classificationReport numberarXiv identifierDOIORCIDLicense (URI)arXiv author IDHelp pagesFull text Search Show abstracts Hide abstracts All fieldsTitleAuthor(s)AbstractCommentsJournal referenceACM classificationMSC classificationReport numberarXiv identifierDOIORCIDLicense (URI)arXiv author IDHelp pagesFull text Show abstracts Hide abstracts results per page.
- Sort results by Announcement date (newest first)Announcement date (oldest first)Submission date (newest first)Submission date (oldest first)Relevance Go , , ] cs.CV cs.AI Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation Authors: , , , , Abstract: While Diffusion Models excel in text-to-… ▽ More While Diffusion Models excel in text-to-image synthesis, they often suffer from concept omission when synthesizing complex multi-instance scenes.
- To address this, we propose Delta-K, a backbone-agnostic and plug-and-play inference framework that tackles omission by operating directly in the shared cross-attention Key space.
- Specifically, with Vision-language model, we extract a differential key $ΔK$ that encodes the semantic signature of missing concepts.

### Step 7: Read Source
- Time: 2026-03-19 22:52:54
- Status: OK
- Details: Read source: [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation
Type: webpage
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
Content artifact: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/sources/2603-10210-delta-k-boosting-multi-instance-generation-via-cross-attention-augmen-6cae6e1735.md
Relevance score: 0.0
Summary: [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation We gratefully acknowledge support from the Simons Foundation, , and all contributors. arXiv:2603.10210 | All fields Title Author Abstract Comments Journal reference ACM classification MSC classification Report number arXiv identifier DOI ORCID arXiv author ID Help pages Full text Search open search GO open navigation menu quick links Computer Science > Computer Vision and Pattern Recognition ========================================================== arXiv:2603.10210** (cs) [Submitted on 10 Mar 2026] Title:Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation ================================================================================== Authors: , , , , View a PDF of the paper titled Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation, by Zitong Wang and 4 other authors Abstract:While Diffusion Models excel in text-to-image synthesis, they often suffer from concept omission when synthesizing complex multi-instance scenes. Existing training-free methods attempt to resolve this by rescaling attention maps, which merely exacerbates unstructured noise without establishing coherent semantic representations.

### Step 8: Extract Claims
- Time: 2026-03-19 22:52:54
- Status: OK
- Details: Extracted 5 claim(s) from [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation.
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
- [2603.10210] Delta-K: Boosting Multi-Instance Generation via Cross-Attention Augmentation We gratefully acknowledge support from the Simons Foundation, , and all contributors.
- To address this, we propose Delta-K, a backbone-agnostic and plug-and-play inference framework that tackles omission by operating directly in the shared cross-attention Key space.
- Specifically, with Vision-language model, we extract a differential key $\Delta K$ that encodes the semantic signature of missing concepts.
- Extensive experiments demonstrate the generality of our approach: Delta-K consistently improves compositional alignment across both modern DiT models and classical U-Net architectures, without requiring spatial masks, additional training, or architectural modifications.
- Data provided by: Bookmark Bibliographic Tools Bibliographic and Citation Tools ================================ Bibliographic Explorer Toggle Bibliographic Explorer *( )* Connected Papers Toggle Connected Papers *( )* Litmaps Toggle Litmaps *( )* scite.ai Toggle scite Smart Citations *( )* Code, Data, Media Code, Data and Media Associated with this Article ================================================= alphaXiv Toggle alphaXiv *( )* Links to Code Toggle CatalyzeX Code Finder for Papers *( )* DagsHub Toggle DagsHub *( )* GotitPub Toggle Gotit.pub *( )* Huggingface Toggle Hugging Face *( )* Links to Code Toggle Papers with Code *( )* ScienceCast Toggle ScienceCast *( )* Demos Demos ===== Replicate Toggle Replicate *( )* Spaces Toggle Hugging Face Spaces *( )* Spaces Toggle TXYZ.AI *( )* Related Papers Recommenders and Search Tools ============================= Link to Influence Flower Influence Flower *( )* Core recommender toggle CORE Recommender *( )* Author Venue Institution Topic About arXivLabs arXivLabs: experimental projects with community collaborators ============================================================= arXivLabs is a framework that allows collaborators to develop and share new arXiv features directly on our website.

### Step 9: Read Source
- Time: 2026-03-19 22:52:58
- Status: OK
- Details: Read source: 2603
Type: pdf
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
Content artifact: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/sources/2603-74c81c0594.txt
Relevance score: 0.0
Summary: No summary could be extracted yet.
Warning: PDF parser dependency 'pypdf' is not installed.

### Step 10: Extract Claims
- Time: 2026-03-19 22:53:01
- Status: OK
- Details: No claim-like sentences were extracted from 2603.
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl

### Step 11: Read Source
- Time: 2026-03-19 22:53:04
- Status: OK
- Details: Read source: [2602.08749] Shifting the Breaking Point of Flow Matching for Multi-Instance Editing
Type: webpage
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
Content artifact: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/sources/2602-08749-shifting-the-breaking-point-of-flow-matching-for-multi-instance-editi-e741e774a8.md
Relevance score: 0.0
Summary: [2602.08749] Shifting the Breaking Point of Flow Matching for Multi-Instance Editing We gratefully acknowledge support from the Simons Foundation, , and all contributors. arXiv:2602.08749 | All fields Title Author Abstract Comments Journal reference ACM classification MSC classification Report number arXiv identifier DOI ORCID arXiv author ID Help pages Full text Search open search GO open navigation menu quick links Computer Science > Computer Vision and Pattern Recognition ========================================================== arXiv:2602.08749** (cs) ), last revised 10 Feb 2026 (this version, v2)] Title:Shifting the Breaking Point of Flow Matching for Multi-Instance Editing ============================================================================= Authors: , , , , , , View a PDF of the paper titled Shifting the Breaking Point of Flow Matching for Multi-Instance Editing, by Carmine Zaccagnino and 6 other authors Abstract:Flow matching models have recently emerged as an efficient alternative to diffusion, especially for text-guided image generation and editing, offering faster inference through continuous-time dynamics. However, existing flow-based editors predominantly support global or single-instruction edits and struggle with multi-instance scenarios, where multiple parts of a reference input must be edited independently without semantic interference.

### Step 12: Extract Claims
- Time: 2026-03-19 22:53:04
- Status: OK
- Details: Extracted 5 claim(s) from [2602.08749] Shifting the Breaking Point of Flow Matching for Multi-Instance Editing.
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
- [2602.08749] Shifting the Breaking Point of Flow Matching for Multi-Instance Editing We gratefully acknowledge support from the Simons Foundation, , and all contributors.
- We identify this limitation as a consequence of globally conditioned velocity fields and joint attention mechanisms, which entangle concurrent edits.
- To address this issue, we introduce Instance-Disentangled Attention, a mechanism that partitions joint attention operations, enforcing binding between instance-specific textual instructions and spatial regions during velocity field estimation.
- We evaluate our approach on both natural image editing and a newly introduced benchmark of text-dense infographics with region-level editing instructions.
- Experimental results demonstrate that our approach promotes edit disentanglement and locality while preserving global output coherence, enabling single-pass, instance-level editing.

### Step 13: Read Source
- Time: 2026-03-19 22:53:09
- Status: OK
- Details: Read source: 2602
Type: pdf
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
Content artifact: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/sources/2602-cdcd8a0df2.txt
Relevance score: 0.0
Summary: No summary could be extracted yet.
Warning: PDF parser dependency 'pypdf' is not installed.

### Step 14: Extract Claims
- Time: 2026-03-19 22:53:14
- Status: OK
- Details: No claim-like sentences were extracted from 2602.
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl

### Step 15: Read Source
- Time: 2026-03-19 22:53:16
- Status: OK
- Details: Read source: [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models
Type: webpage
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
Content artifact: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/sources/2512-20666-dominating-vs-dominated-generative-collapse-in-diffusion-models-f76e1031d2.md
Relevance score: 0.0
Summary: [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models We gratefully acknowledge support from the Simons Foundation, , and all contributors. arXiv:2512.20666 | All fields Title Author Abstract Comments Journal reference ACM classification MSC classification Report number arXiv identifier DOI ORCID arXiv author ID Help pages Full text Search open search GO open navigation menu quick links Computer Science > Machine Learning =================================== arXiv:2512.20666** (cs) [Submitted on 19 Dec 2025] Title:Dominating vs.

### Step 16: Extract Claims
- Time: 2026-03-19 22:53:16
- Status: OK
- Details: Extracted 5 claim(s) from [2512.20666] Dominating vs. Dominated: Generative Collapse in Diffusion Models.
Evidence: D:/成就/人要有梦想/evoscientist/BPJH-GETI/artifacts/lit_review/evidence.jsonl
- Dominated: Generative Collapse in Diffusion Models We gratefully acknowledge support from the Simons Foundation, , and all contributors.
- However, when generating from multi-concept prompts, one concept token often dominates the generation, suppressing the others-a phenomenon we term the Dominant-vs-Dominated (DvD) imbalance.
- To systematically analyze this imbalance, we introduce DominanceBench and examine its causes from both data and architectural perspectives.
- Through various experiments, we show that the limited instance diversity in training data exacerbates the inter-concept interference.
- In addition, head ablation studies show that the DvD behavior arises from distributed attention mechanisms across multiple heads.

### Step 17: Select Evidence
- Time: 2026-03-19 22:53:16
- Status: OK
- Details: Selected 6 evidence record(s) from 24 stored row(s).

### Step 18: Generate Candidates
- Time: 2026-03-19 22:55:42
- Status: OK
- Details: 1. Orthogonal Key-Space Projection for Zero-Shot Multi-Instance Disentanglement
2. Optimal Transport Attention Reallocation for Multi-Instance Dominance Mitigation
3. Game-Theoretic Equilibrium in Joint Attention for Flow Matching
4. Spectral Graph Partitioning for Cross-Attention Noise Suppression
5. Min-Max Gradient Normalization for Dominance Elimination

### Step 19: Build First Brief
- Time: 2026-03-19 22:55:42
- Status: OK
- Details: Built idea brief 'Orthogonal Key-Space Projection for Zero-Shot Multi-Instance Disentanglement'.
Saved markdown: artifacts/ideas/runs/20260319-225247-multi-instance-image-generation-in-diffusion-models-training-free-attention/orthogonal-key-space-projection-for-zero-shot-multi-instance-disentanglement.md
Included evidence rows: 2

### Step 20: Publish Candidate Doc
- Time: 2026-03-19 22:55:46
- Status: OK
- Details: Published idea brief to Feishu doc.
Title: Idea Candidates - multi-instance image generation in diffusion models, trainin
Document token: Na9jdnXAYoLlcHxADfoc4V0Lndj
URL: 
State key: idea-candidates-multi-instance-image-generation-in-diffu

### Step 21: Publish Log Doc
- Time: 2026-03-19 22:55:51
- Status: OK
- Details: Published idea brief to Feishu doc.
Title: Idea Pipeline Log - multi-instance image generation in diffusion models, trainin
Document token: GHvBdEQe0oGdOOxijcMckXqFnAf
URL: 
State key: idea-log-multi-instance-image-generation-in-diffu
