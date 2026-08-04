<!-- SPDX-FileCopyrightText: 2026 Sebastien Rousseau -->
<!-- SPDX-License-Identifier: MIT -->

# AgtMLS — Agent Multiple Listing Service

**The universal agent skills registry.**

`agtmls` is the central nervous system for LLM prompts, skills, and
system instructions across a polyglot ecosystem (Python, Rust, C++,
Go, JS). By acting as a single source of truth, it ensures that
whether you use Claude Code, Aider, GitHub Copilot CLI, or Codex,
the AI behaves consistently, adheres to strict security standards,
and writes idiomatic code for the target language.

## Directory structure

```
agtmls/
├── scripts/
│   ├── setup-workspace.sh       # Links AgtMLS into your active repos
│   ├── agtmls-doctor.py         # Local health checks for the registry
│   └── generate-skill-index.py  # Builds index.json for discovery
├── system-prompts/              # Global behavioural rules → repo-root CLAUDE.md/AGENTS.md/CONVENTIONS.md
│   ├── _base.md                 # Universal engineering standards
│   └── <lang>.md                # Per-language idiom profiles: rust, python,
│                                # go, cpp, swift, typescript, javascript,
│                                # ruby, bash (all authored)
├── skills/                      # FLAT: every skill is skills/<name>/SKILL.md
│   ├── writing-plans/           # Discipline skills: plan → test → debug →
│   ├── test-driven-development/ #   verify → review → hand off. Apply in
│   ├── systematic-debugging/    #   any repo, any language
│   ├── verification-before-completion/
│   ├── receiving-code-review/
│   ├── handoff/
│   ├── cross-language-port/     # Porting logic between polyglot repos
│   └── noyalib-*/               # Project skills; bundle is a metadata field
├── references/
│   └── noyalib-bundle.md        # Routing index for the 14 noyalib skills
├── commands/                    # Interactive slash commands (author here)
├── evals/                       # Routing + behavioral skill checks
├── lifecycle.json               # Skill proposal -> publication lifecycle
├── profiles.json                # Named install/export profiles
├── providers.json               # Native agent + plugin + export target matrix
├── CHANGELOG.md                 # Human-readable changes
├── RELEASE.md                   # Release checklist
├── CATALOG.md                   # Generated human-readable registry catalog
└── index.json                   # Generated skill registry metadata
```

## Install

No clone required:

```bash
uvx agtmls install rust claude --skills-only --bundle noyalib   # one-shot
pipx install agtmls && agtmls install rust claude               # persistent
```

The package bundles the whole registry and is **dependency-free** — every
script is stdlib-only, so `uvx` is a single fast download with nothing to
resolve. Browsing works the same way:

```bash
uvx agtmls list
uvx agtmls search yaml
uvx agtmls show cross-language-port
uvx agtmls stats
```

Installing from a package defaults to `--copy` rather than symlinks: the
wheel lives in an ephemeral uvx/pipx cache, and linking into a cache that is
about to be collected would leave the target repo full of dangling links.
Pass `--copy` explicitly to get the same behaviour from a checkout.

Repository-maintenance commands (`check`, `release-*`, `bump-version`,
`diff`, `next-version`, `verify-release-assets`) need a real checkout and
refuse to run from a package. Point `AGTMLS_HOME` at a checkout to run the
installed CLI against your own working tree:

```bash
AGTMLS_HOME=~/dev/agtmls agtmls check
```

## Install as a plugin

AgtMLS reaches agents three ways, and `providers.json` records all three:

| Section | Mechanism | Runtimes |
|---|---|---|
| `native_agents` | symlink install via `setup-workspace.sh` | Claude Code, Codex, Aider |
| `plugin_targets` | the runtime's own plugin manifest | Antigravity, Codex, Cursor, Gemini CLI, Kimi, OpenCode |
| `export_targets` | provider-adapted Markdown bundle | 13 targets, see below |

Plugin installs need no clone:

```
# Claude Code
/plugin marketplace add sebastienrousseau/agtmls
/plugin install agtmls@agtmls

# Antigravity
agy plugin install https://github.com/sebastienrousseau/agtmls

# Gemini CLI
gemini extensions install https://github.com/sebastienrousseau/agtmls

# Codex CLI      /plugins  -> search agtmls -> Install Plugin
# Cursor         /add-plugin agtmls
# Kimi Code      /plugins install https://github.com/sebastienrousseau/agtmls
# OpenCode       see .opencode/INSTALL.md
```

Every plugin manifest is **generated** from `.claude-plugin/plugin.json` and
the skill tree, so a version bump or a new bundle cannot leave one runtime
behind:

```bash
python3 scripts/agtmls.py plugin-manifests --write   # regenerate
python3 scripts/agtmls.py plugin-manifests --check   # CI: fail on drift
```

The manifests are `plugin.json` (Antigravity, at the repo root — it does not
read `.claude-plugin/`), `.codex-plugin/plugin.json` plus
`.agents/plugins/marketplace.json` (Codex), `.cursor-plugin/plugin.json`,
`.kimi-plugin/plugin.json`, `gemini-extension.json` with `GEMINI.md`, and
`.opencode/INSTALL.md`. OpenCode has no skill-bundle manifest, so it is
wired through the `instructions` array in the user's `opencode.json`.

Use the hub-and-spoke setup below instead when you want editable symlinks,
per-language system prompts, or a native Aider install.

## Hub-and-spoke setup

Do NOT copy these files into your application repositories. Use the
provided script to symlink them so hub updates propagate instantly.

1. Clone this hub: `~/dev/agtmls` (or wherever you keep it).
2. Navigate to an application repo: `cd ~/dev/my-rust-microservice`.
3. Link the rules:

    ```bash
    ~/dev/agtmls/scripts/setup-workspace.sh rust aider
    ```

The script assembles the system prompt from `_base.md` + the language
profile and writes it to the **repo-root file the tool auto-loads**
(`CLAUDE.md` for Claude Code, `AGENTS.md` for Codex, `CONVENTIONS.md`
for Aider — the latter also registered in `.aider.conf.yml`). It then
symlinks every in-scope skill and command into the tool's dot-dir
(`.claude/`, `.aider/`, `.codex/`, or `.agent/`), one level deep
(`<cli>/skills/<skill>/`) where the tool can discover it. Re-run it any
time you add a language profile or a skill.

The assembled prompt is a per-machine artifact of the hub, not repo
content — so the script adds it (and the tool's dot-dir) to the target
repo's local `.git/info/exclude`. It stays **private and un-committed**,
sourced only from the hub, and re-running never dirties the working
tree. (This is a personal, local ignore; it doesn't touch the committed
`.gitignore`.)

### Skills only (no system prompt)

For repos that consume AgtMLS *skills* but source their system prompt
elsewhere (e.g. a global `~/.claude/CLAUDE.md`), pass `--skills-only`:

```bash
~/dev/agtmls/scripts/setup-workspace.sh rust claude --skills-only
```

It links the skills without writing a prompt, and cleans up any prompt a
previous non-`--skills-only` run generated (a hand-authored prompt with
no generated marker is left untouched). Use this flag on every run for
those repos so a future setup never re-creates the prompt.

### The discipline skills

Six skills cover ordinary engineering work in any repo and any language.
They are general (`"bundle": null`), so they install everywhere, and they
compose in phase order:

| Phase | Skill | The rule it enforces |
| --- | --- | --- |
| Decompose | `writing-plans` | A step is done when something observable changes |
| Build | `test-driven-development` | A test you have not seen fail proves nothing |
| Diagnose | `systematic-debugging` | No edit before an explanation |
| Finish | `verification-before-completion` | A claim you have not observed is a guess |
| Review | `receiving-code-review` | Every comment gets a decision and a reply |
| Pause | `handoff` | Can the reader act without asking you a question? |

Each hands off to the next — debugging produces the explanation a red test is
written from; that red-then-green is exactly the evidence the completion gate
demands. A project bundle's own rules override them on specifics.

Install just these with the `discipline` profile:

```bash
uvx agtmls install python claude --profile discipline
```

### General skills vs project bundles

The skill tree is **flat** — every skill is `skills/<name>/SKILL.md`, with no
nesting. That is not cosmetic: each agent runtime scans its skills path
*non-recursively*, so a nested skill is invisible to Codex, Cursor, Gemini
CLI, Antigravity, and anything else that does not support an array-valued
`skills` field.

Bundle membership is therefore the `bundle` field in each skill's
`metadata.json`, not a parent directory:

- **General skills** (`"bundle": null`) — `cross-language-port`,
  `using-agtmls`. These apply anywhere and are **always linked**.
- **Project skills** (`"bundle": "noyalib"`) — linked **only** when the
  bundle is named with `--bundle`, so a project's skills never land in an
  unrelated repo:

```bash
# a generic Python repo — general skills only, no project bundle
setup-workspace.sh python claude --skills-only

# a noyalib-family repo — general skills + the noyalib bundle
setup-workspace.sh rust claude --skills-only --bundle noyalib
```

All nine fleet languages have an authored profile — `rust`, `python`,
`go`, `cpp`, `swift`, `typescript`, `javascript`, `ruby`, `bash`. A
language without a profile falls back to `_base.md` alone.

## Adding a skill

Every skill lives in its own directory under `skills/` with at
minimum a `SKILL.md` file. The frontmatter's `name` and
`description` fields drive the router — write a description rich in
verb-form triggers so a model can decide whether to load the skill
from the description alone.

For a template, see `skills/cross-language-port/SKILL.md`, or scaffold one:

```bash
python3 scripts/agtmls.py scaffold-skill my-skill
```

Project-specific skills live beside every other skill and declare their
grouping with `"bundle": "<name>"` in `metadata.json`. Pass `--bundle` to
`scaffold-skill` to set it.

### The skill contract (CI-enforced)

`scripts/validate-skills.py` runs on every push/PR
(`.github/workflows/validate.yml`) and fails the build unless every
`SKILL.md` satisfies:

- a parseable YAML frontmatter block;
- **only the six keys the [Agent Skills spec][spec] allows** — `name`,
  `description`, `license`, `compatibility`, `metadata`, `allowed-tools`.
  Any other key fails validation here and in `skills-ref validate`;
- `name` present, ≤ 64 characters, kebab-case with no consecutive hyphens,
  and equal to the skill's directory name;
- `description` present, **≤ 1024 characters** (Claude Code truncates
  beyond this), and containing a trigger cue (a "when…" / "use for" /
  "load before" phrase telling the router when to load the skill);
- `compatibility` ≤ 500 characters, and `metadata` a flat map of string
  keys to string values, when either is present;
- a top-level `# ` heading in the body;
- **≤ 500 lines total**, so activation stays inside the
  progressive-disclosure budget. Detail belongs in `reference.md`.

Run it locally before pushing: `python3 scripts/validate-skills.py`.

[spec]: https://agentskills.io/specification.md

### Generated frontmatter

`compatibility`, `metadata`, and `allowed-tools` are **generated** from each
skill's `metadata.json` — do not hand-edit them:

```bash
python3 scripts/sync-skill-frontmatter.py --write   # regenerate
python3 scripts/sync-skill-frontmatter.py --check   # CI: fail on drift
```

`metadata.json` stays the source of truth, but it is an AgtMLS-private
sidecar that no other runtime reads. Mirroring it into the spec's fields is
what gives a Cursor, Gemini CLI, or marketplace consumer the same risk
signal a native install gets. `required_tools` becomes `compatibility`;
`safety_policy` becomes the namespaced `agtmls-*` keys under `metadata` and
the derived `allowed-tools` surface.

Note that `allowed-tools` is experimental and runtimes disagree on its
meaning — some read it as a pre-approval, others as a restriction. AgtMLS
declares the **full capability surface** the safety policy implies, which is
correct under the restriction reading and pre-approves under the other.
Switch `ALLOWED_TOOLS_MODE` in `sync-skill-frontmatter.py` to `"readonly"`
to declare only non-mutating tools instead.

### Full local health check

The full list lives in [docs/checks.md](docs/checks.md). Run them all with:

```bash
python3 scripts/agtmls.py check
```

The dispatcher wraps every registry operation; the full command reference is
in [docs/cli.md](docs/cli.md).

`index.json` is generated from the skill tree and committed so tools can
discover skills without reading every body. Rebuild it after changing skills:

```bash
python3 scripts/generate-skill-index.py --write
python3 scripts/generate-catalog.py --write
```

The generated schema is documented in
`references/registry-schema.md`; do not edit `index.json` by hand.

### Repository location

AgtMLS is intentionally a polyglot hub. It should not live under a
Python-only folder unless your local machine has a personal convention for all
automation repos. The repo contains Python tooling, but its product surface is
language-neutral skills, prompts, commands, and evals.

### Providers and profiles

AgtMLS has native symlink installers for Claude Code, Codex, and Aider. Other
AI providers are supported through provider-adapted Markdown exports generated
from the same registry source of truth. Each export includes `ADAPTERS.md` plus
a provider-specific file such as `adapters/openai/AGENTS.md`,
`adapters/anthropic/CLAUDE.md`,
`adapters/github-copilot/.github/copilot-instructions.md`, or
`adapters/cursor/.cursor/rules/agtmls.mdc`. `providers.json` records the native
agent layouts and export targets; `profiles.json` records named subsets such as
`minimal`, `polyglot`, `noyalib`, `security`, and `research`.

Use exports when a provider does not have a first-class local skills directory:

```bash
python3 scripts/agtmls.py export --provider generic --profile polyglot --out-dir dist
python3 scripts/agtmls.py export --provider anthropic --profile noyalib --out-dir dist
```

Optional live API smoke tests are available for configured model backends. They
skip cleanly when credentials are absent and probe only metadata/list endpoints
when present:

```bash
python3 scripts/smoke-live-providers.py
```

Supported credential variables are `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `QWEN_API_KEY`, and
`OLLAMA_BASE_URL` for a reachable local Ollama server.

### Safety metadata

Every metadata source must include `safety_policy` with explicit flags for
network access, file writes, command execution, secret handling, human-review
requirements, and risk level. The policy is validated by
`validate-skill-metadata.py` and published into `index.json` so agents can
route or gate skills before use.

### Import and release workflow

External skills should enter as drafts, not directly as hardened skills:

```bash
python3 scripts/agtmls.py import-skill /path/to/external/skill --name external-skill
python3 scripts/agtmls.py scaffold-skill follow-up-skill
python3 scripts/agtmls.py release-check
```

`import-skill` normalizes a Markdown skill into `skills/imported/<name>/`, adds
draft metadata, creates a reference stub when needed, and review-gates the
result. Publish it only after adding routing and behavioral eval cases, filling
out references, and passing `python3 scripts/agtmls.py check`.

### Static docs site

`site/index.html` is generated from the registry metadata and gives a browser-readable catalog with skill quality, risk, agent support, profiles, and export targets. Rebuild it after changing `index.json`, `profiles.json`, or `providers.json`:

```bash
python3 scripts/agtmls.py docs-site --write
```

### Release packs

`release-pack` creates provider export archives plus `SHA256SUMS` and `release-manifest.json`:

```bash
python3 scripts/agtmls.py release-pack --profile polyglot --out-dir dist/release
```

### Evolution and evidence

`evolve` creates a redacted local proposal from a transcript and requires human review before publication. `evidence` records per-skill invocation evidence with commands, touched files, outcome, and the skill safety policy. These files default to `.agtmls/` and are intentionally ignored.

### Interoperability artifacts

`agent-card.json` and `mcp-resources.json` are generated from the registry for A2A-style discovery and MCP-style resource publication. `SBOM.spdx.json` and `provenance.json` provide release supply-chain evidence.

## Versioning

AgtMLS follows the pre-1.0 patch-line policy in `VERSIONING.md`: public releases stay on `0.0.x` and increment by exactly `0.0.1`.

Published release assets can be verified after release with `python3 scripts/agtmls.py verify-release-assets --tag v0.0.1`.

Release tag protection is documented in `docs/tag-protection.md`.
