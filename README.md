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
├── system-prompts/              # Global behavioural rules (AGENTS.md / CONVENTIONS.md)
│   ├── _base.md                 # Universal engineering standards
│   ├── python.md                # Python idioms  (TODO: author)
│   ├── rust.md                  # Rust idioms    (TODO: author)
│   └── cpp.md                   # C++ idioms     (TODO: author)
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

The script picks the right CLI folder (`.claude/`, `.aider/`,
`.codex/`, or `.agent/`), assembles the system prompt from
`_base.md` + the language profile, and symlinks every skill and
command into place. Re-run it any time you add a language profile
or a skill.

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
