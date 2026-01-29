---
name: find-skills
description: Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", or express interest in extending capabilities. Uses a non-interactive installer script suitable for automated agents.
---

# Find Skills

This skill helps you discover and install skills from the open agent skills ecosystem.

## When to Use This Skill

Use this skill when the user:

- Asks "how do I do X" where X might be a common task with an existing skill
- Says "find a skill for X" or "is there a skill for X"
- Wants to search for tools, templates, or workflows
- Expresses interest in extending agent capabilities
- Mentions they wish they had help with a specific domain (design, testing, deployment, etc.)

## Step 1: Search for Skills

Use `npx -y skills find` with a relevant keyword to search the ecosystem:

```bash
npx -y skills find [query]
```

Examples:
- User asks "help me with React performance" → `npx -y skills find react performance`
- User asks "is there a skill for PR reviews?" → `npx -y skills find pr review`
- User asks "I need to create a changelog" → `npx -y skills find changelog`

The search results will show installable skills like:

```
vercel-labs/agent-skills@vercel-react-best-practices
└ https://skills.sh/vercel-labs/agent-skills/vercel-react-best-practices
```

Browse all available skills at: https://skills.sh/

## Step 2: Present Options

When you find relevant skills, present them to the user with:
1. The skill name and what it does
2. A link to learn more on skills.sh

Ask the user which skill(s) they want to install. All skills are installed to `./skills/` in the current working directory.

## Step 3: Install with the Script

**IMPORTANT: Do NOT use `npx -y skills add` for installation** — it requires interactive prompts.

Use the bundled installer script instead:

```bash
python /skills/find-skills/scripts/install_skill.py --url <github_url>
```

### Install Commands

**From a GitHub URL** (most common — copy the URL from search results):
```bash
python /skills/find-skills/scripts/install_skill.py \
  --url https://github.com/owner/repo/tree/main/skill-name
```

**From skills.sh shorthand** (owner/repo@skill):
```bash
python /skills/find-skills/scripts/install_skill.py \
  --url vercel-labs/agent-skills@vercel-react-best-practices
```

**From repo + path** (install specific skills from a multi-skill repo):
```bash
# Single skill
python /skills/find-skills/scripts/install_skill.py \
  --repo owner/repo --path skill-name

# Multiple skills from same repo
python /skills/find-skills/scripts/install_skill.py \
  --repo owner/repo --path skill-a --path skill-b
```

**With a specific git branch or tag**:
```bash
python /skills/find-skills/scripts/install_skill.py \
  --repo owner/repo --path skill-name --ref v2.0
```

### Installer Options

| Option | Description |
|--------|-------------|
| `--url` | GitHub URL or owner/repo@skill shorthand |
| `--repo` | GitHub repo (owner/repo format) |
| `--path` | Path to skill inside repo (repeatable) |
| `--ref` | Git branch or tag |
| `--dest` | Custom destination directory (default: `./skills`) |

## Step 4: Confirm Installation

After installation, verify by listing the skills directory:

```bash
ls /skills/   # all skills (system + user merged)
```

Then read the installed skill's SKILL.md to confirm it loaded correctly:

```bash
read_file /skills/<skill-name>/SKILL.md
```

## Common Skill Categories

| Category | Example Queries |
|----------|----------------|
| Web Development | react, nextjs, typescript, css, tailwind |
| Testing | testing, jest, playwright, e2e |
| DevOps | deploy, docker, kubernetes, ci-cd |
| Documentation | docs, readme, changelog, api-docs |
| Code Quality | review, lint, refactor, best-practices |
| Design | ui, ux, design-system, accessibility |
| Productivity | workflow, automation, git |

## When No Skills Are Found

If no relevant skills exist:

1. Acknowledge that no existing skill was found
2. Offer to help with the task directly using your general capabilities
3. Mention the user could create their own skill with `npx -y skills init`
