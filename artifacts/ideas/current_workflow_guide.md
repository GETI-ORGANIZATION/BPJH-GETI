# EvoScientist Idea Workflow Guide

## What You Can Do Now

The current stable Feishu entrypoint is `/idea start`.

The bot will:
1. Parse your request.
2. Collect sources from your seed URLs and optional search results.
3. Read source content.
4. Extract evidence and research results.
5. Generate candidate ideas.
6. Publish process documents to Feishu.
7. Ask you to choose one idea with `A/B/C/...`.
8. Build and publish the final Idea Brief.

## Supported Command Format

Use this format in Feishu:

```text
@BOT
/idea start
query: multimodal agents for scientific discovery
max_ideas: 5
max_sources: 6
requirements:
- novel
- interesting
- low-cost experiments
urls:
- https://arxiv.org/abs/2308.12345
- https://arxiv.org/abs/2402.01234
notes:
- focus on practical validation
- prefer papers after 2023
```

## Supported Fields

- `query`: required in practice, your research topic.
- `max_ideas`: optional, how many candidate ideas to generate.
  - Current supported range: `1` to `8`.
  - Default: `3`.
- `max_sources`: optional, how many sources to read deeply.
  - Current supported range: `1` to `12`.
  - Default: `4`.
- `requirements`: optional constraints for idea generation.
- `urls` / `seed_urls` / `seeds`: optional source URLs to prioritize.
- `notes`: optional extra instructions.

## Interaction Modes In Feishu

### Idea Selection
After candidate generation, the bot sends a multiple-choice question.
Reply with `A`, `B`, `C`, etc. to choose one idea.

### Recovery Prompts
If a publish or pipeline step fails, the bot can ask:
- `A`: retry
- `B`: skip
- `C`: cancel

### Approval Prompts
If an action requires approval, the bot can ask:
- `A`: approve once
- `B`: reject
- `C`: approve all similar actions

## Documents Published To Feishu

For each run, the bot can publish:
- `Source Index`
- `Evidence Report`
- `Idea Candidates`
- `Idea Pipeline Log`
- Final `Idea Brief`

## Multi-Run History Management

Each idea exploration now gets its own run folder locally:
- `artifacts/ideas/runs/<run_id>/`

A persistent history index is maintained at:
- `artifacts/ideas/runs/index.json`
- `artifacts/ideas/runs/index.md`

The latest run pointer is stored at:
- `artifacts/ideas/last_run.json`

This means new runs do not overwrite previous runs.

## Local Data Retention

The system still keeps a small local cache because the runtime needs local state.
However, it now minimizes leftover data by:
- storing each run in its own lightweight run folder
- keeping a latest pointer and run history index
- removing downloaded source files from `artifacts/lit_review/sources/` after the pipeline run when possible

## Recommended Test Command

```text
@BOT
/idea start
query: multimodal agents
max_ideas: 4
max_sources: 3
urls:
- https://arxiv.org/abs/2308.12345
```

## Current Limits

- `/idea start` is the mature hard-routed workflow.
- `/paper plan` is not yet hard-routed.
- Feishu documents are created successfully, but the local cache still exists in minimized form.
