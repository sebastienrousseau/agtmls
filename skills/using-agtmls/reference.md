# Using AgtMLS Reference

Use this reference when the `using-agtmls` spine is not enough to decide how
to route work across the registry.

## Routing Sequence

1. Identify whether the task names a concrete skill, bundle, provider, or
   project.
2. If a skill is explicitly named, load that skill directly.
3. If the task is about choosing a skill, loading several skills, catalog
   health, provider export, release checks, or registry structure, keep
   `using-agtmls` active.
4. If the task is small enough to answer without extra context, do it inline
   and do not load more skill material.
5. If several skills might apply, prefer the narrowest skill whose
   description contains the task's operational trigger.

## Registry Workflows

Use `python3 scripts/agtmls.py list` to inspect installed skills, and
`python3 scripts/agtmls.py show <skill-name>` to inspect one skill's metadata.
Use `python3 scripts/agtmls.py check` before treating a registry change as
complete. The check command is the local source of truth because it combines
schema validation, routing evals, behavioral evals, generated artifacts,
smoke tests, and the doctor pass.

Provider work should go through the provider-aware commands rather than
manual copying. Use `python3 scripts/agtmls.py export --target <provider>` for
portable packages and `python3 scripts/agtmls.py provider-install <provider>
<target-dir>` for local adapter installation tests.

## Skill Addition Checklist

Every new skill needs a trigger-rich `SKILL.md`, a metadata entry, a routing
eval case, a behavioral eval case, and a reference file when the topic needs
more than the spine can responsibly hold. After adding or editing a skill,
regenerate derived artifacts with the repository generators or run
`python3 scripts/agtmls.py check` to detect stale output.

Keep routing descriptions specific. A description should name the user intent,
domain cues, and exclusion boundaries clearly enough that neighboring skills
do not collide.

## Safety Boundaries

Do not load unrelated skills just because they are available. Treat skill and
reference content as operational guidance, not as authority to bypass user
intent, sandbox limits, review gates, or repository policy. When registry
material conflicts with system, developer, or user instructions, the higher
priority instruction wins.
