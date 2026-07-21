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
├── skills/                      # Autonomous, multi-step workflows (SKILL.md)
│   ├── cross-language-port/     # Porting logic between polyglot repos
│   └── noyalib/                 # Project-specific skills for noyalib
│       ├── README.md            # Routing index for the 14 noyalib skills
│       └── noyalib-*/           # Per-skill directory with SKILL.md + reference.md
├── commands/                    # Interactive slash commands (author here)
├── evals/                       # Routing + behavioral skill checks
├── lifecycle.json               # Skill proposal -> publication lifecycle
├── profiles.json                # Named install/export profiles
├── providers.json               # Native agent + export target compatibility matrix
├── CHANGELOG.md                 # Human-readable changes
├── RELEASE.md                   # Release checklist
├── CATALOG.md                   # Generated human-readable registry catalog
└── index.json                   # Generated skill registry metadata
```

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
symlinks every skill and command into the tool's dot-dir
(`.claude/`, `.aider/`, `.codex/`, or `.agent/`), flattening skill
bundles so each skill lands one level deep (`<cli>/skills/<skill>/`)
where the tool can discover it. Re-run it any time you add a language
profile or a skill.

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

### General skills vs project bundles

Two kinds of skill live under `skills/`:

- **General skills** — a top-level dir with its own `SKILL.md`
  (`cross-language-port`, `using-agtmls`). These apply anywhere and are
  **always linked**.
- **Project bundles** — a top-level dir that holds *other* skill dirs
  (e.g. `skills/noyalib/`). A bundle is **only** linked when named with
  `--bundle`, so a project's skills never land in an unrelated repo:

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

For a template, see `skills/cross-language-port/SKILL.md`.

Project-specific skills (like the noyalib bundle) live under a
project-named subdirectory to keep them from cluttering the
top-level namespace.

### The skill contract (CI-enforced)

`scripts/validate-skills.py` runs on every push/PR
(`.github/workflows/validate.yml`) and fails the build unless every
`SKILL.md` satisfies:

- a parseable YAML frontmatter block;
- `name` present, kebab-case, and equal to the skill's directory name;
- `description` present, **≤ 1024 characters** (Claude Code truncates
  beyond this), and containing a trigger cue (a "when…" / "use for" /
  "load before" phrase telling the router when to load the skill);
- a top-level `# ` heading in the body.

Run it locally before pushing: `python3 scripts/validate-skills.py`.

### Full local health check

Run the same high-signal checks CI runs:

```bash
python3 scripts/validate-skills.py
python3 scripts/validate-commands.py
python3 scripts/validate-plugin-manifest.py
python3 scripts/validate-providers.py
python3 scripts/validate-profiles.py
python3 scripts/validate-templates.py
python3 scripts/validate-doc-links.py
python3 scripts/validate-json-files.py
python3 scripts/validate-python-scripts.py
python3 scripts/validate-shell-syntax.py
python3 scripts/validate-secrets.py
python3 scripts/validate-gitignore.py
python3 scripts/validate-cli-surface.py
python3 scripts/validate-system-prompts.py
python3 scripts/check-skill-collisions.py
python3 scripts/validate-eval-cases.py
python3 scripts/run-trigger-evals.py
python3 scripts/run-behavioral-evals.py
python3 scripts/validate-skill-metadata.py
python3 scripts/generate-skill-index.py --check
python3 scripts/generate-catalog.py --check
python3 scripts/generate-docs-site.py --check
python3 scripts/validate-generated-artifacts.py
python3 scripts/validate-docs-site.py
python3 scripts/validate-skill-index.py
python3 scripts/validate-lifecycle.py
python3 scripts/validate-release.py
python3 scripts/validate-version-policy.py
python3 scripts/release-check.py
python3 scripts/smoke-release-pack.py
python3 scripts/smoke-next-version.py
python3 scripts/smoke-release-dry-run.py
python3 scripts/smoke-install.py
python3 scripts/smoke-install-profiles.py
python3 scripts/smoke-cli.py
python3 scripts/smoke-export.py
python3 scripts/smoke-import.py
python3 scripts/smoke-proposal.py
python3 scripts/smoke-scaffold.py
python3 scripts/run-unit-tests.py
python3 scripts/validate-check-manifest.py
python3 scripts/agtmls-doctor.py
```

The convenience dispatcher wraps the same operations:

```bash
python3 scripts/agtmls.py check
python3 scripts/agtmls.py list
python3 scripts/agtmls.py list commands
python3 scripts/agtmls.py search yaml
python3 scripts/agtmls.py show cross-language-port
python3 scripts/agtmls.py stats
python3 scripts/agtmls.py profiles
python3 scripts/agtmls.py providers
python3 scripts/agtmls.py export --provider openai --profile polyglot --out-dir dist
python3 scripts/agtmls.py docs-site --write
python3 scripts/agtmls.py release-pack --profile polyglot --out-dir dist/release
python3 scripts/agtmls.py next-version
python3 scripts/agtmls.py bump-version --check --version 0.0.2
python3 scripts/agtmls.py release-dry-run --version 0.0.1 --skip-check
python3 scripts/agtmls.py verify-release-assets --tag v0.0.1
python3 scripts/agtmls.py evolve transcript.txt --skill-name candidate-skill
python3 scripts/agtmls.py evidence --skill cross-language-port --command pytest --file src/example.py
python3 scripts/agtmls.py agent-card --write
python3 scripts/agtmls.py mcp-resources --write
python3 scripts/agtmls.py sbom --write
python3 scripts/agtmls.py provenance --write
python3 scripts/agtmls.py provider-install --provider cursor --target /path/to/repo --profile polyglot
python3 scripts/agtmls.py bench
python3 scripts/agtmls.py diff --from index.json --to index.json
python3 scripts/agtmls.py release-check
python3 scripts/agtmls.py import-skill /path/to/external/skill --name candidate-skill
python3 scripts/agtmls.py index --check
python3 scripts/agtmls.py status
python3 scripts/agtmls.py status --target /path/to/repo --agent codex --skills-only
python3 scripts/agtmls.py install rust claude --target /path/to/repo --skills-only --bundle noyalib
python3 scripts/agtmls.py install rust codex --target /path/to/repo --skills-only --profile noyalib
python3 scripts/agtmls.py uninstall claude --target /path/to/repo --remove-prompt
python3 scripts/agtmls.py propose-skill transcript.txt --skill-name candidate-skill
python3 scripts/agtmls.py scaffold-skill candidate-skill
```

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
