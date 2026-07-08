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
│   └── setup-workspace.sh       # Links AgtMLS into your active repos
├── system-prompts/              # Global behavioural rules → repo-root CLAUDE.md/AGENTS.md/CONVENTIONS.md
│   ├── _base.md                 # Universal engineering standards
│   └── rust.md                  # Rust idioms (authored)
│                                # python/cpp/go/js: not yet authored — setup
│                                # falls back to _base.md only for those.
├── skills/                      # Autonomous, multi-step workflows (SKILL.md)
│   ├── cross-language-port/     # Porting logic between polyglot repos
│   └── noyalib/                 # Project-specific skills for noyalib
│       ├── README.md            # Routing index for the 14 noyalib skills
│       └── noyalib-*/           # Per-skill directory with SKILL.md + reference.md
└── commands/                    # Interactive slash commands (author here)
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

Currently only `rust` has an authored language profile; `python`,
`cpp`, `go`, and `js` fall back to `_base.md` alone until authored.

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
