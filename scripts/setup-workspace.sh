#!/usr/bin/env bash
# AgtMLS workspace setup script.
#
# Links the AgtMLS system prompt, skills, and slash commands into a
# target repository so a coding agent (Claude Code, Aider, Codex, ...)
# picks them up automatically. Runs from inside the target repo:
#
#   ~/dev/agtmls/scripts/setup-workspace.sh rust aider
#
set -euo pipefail

AGTMLS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TARGET_DIR=$(pwd)
LANGUAGE=${1:-}
AGENT_CLI=${2:-}

if [[ -z "$LANGUAGE" || -z "$AGENT_CLI" ]]; then
  echo "Usage: $0 <language> <agent-cli>"
  echo "  language:  python | rust | cpp | go | js"
  echo "  agent-cli: claude | aider | codex"
  echo
  echo "Example: $0 rust aider"
  echo "Example: $0 python claude"
  exit 1
fi

echo "🚀 Configuring AgtMLS workspace in $TARGET_DIR for $LANGUAGE using $AGENT_CLI"

# 1. Map CLI tool to its configuration folder / prompt file.
case "$AGENT_CLI" in
  claude) CLI_DIR=".claude"; SYS_FILE="AGENTS.md" ;;
  aider)  CLI_DIR=".aider";  SYS_FILE="CONVENTIONS.md" ;;
  codex)  CLI_DIR=".codex";  SYS_FILE="AGENTS.md" ;;
  *)      CLI_DIR=".agent";  SYS_FILE="AGENTS.md" ;;
esac

mkdir -p "$TARGET_DIR/$CLI_DIR/skills"
mkdir -p "$TARGET_DIR/$CLI_DIR/commands"

# 2. Assemble the system prompt: base + language profile.
echo "📝 Assembling system prompts → $CLI_DIR/$SYS_FILE"
cat "$AGTMLS_DIR/system-prompts/_base.md" > "$TARGET_DIR/$CLI_DIR/$SYS_FILE"
printf '\n\n' >> "$TARGET_DIR/$CLI_DIR/$SYS_FILE"

if [[ -f "$AGTMLS_DIR/system-prompts/$LANGUAGE.md" ]]; then
  cat "$AGTMLS_DIR/system-prompts/$LANGUAGE.md" >> "$TARGET_DIR/$CLI_DIR/$SYS_FILE"
else
  echo "⚠️  Language profile '$LANGUAGE.md' not found in system-prompts/. Using base only."
fi

# 3. Symlink skills and commands so hub updates propagate instantly.
echo "🔗 Linking skills and commands"
for entry in "$AGTMLS_DIR/skills/"*; do
  [[ -e "$entry" ]] || continue
  ln -sfn "$entry" "$TARGET_DIR/$CLI_DIR/skills/$(basename "$entry")"
done
for entry in "$AGTMLS_DIR/commands/"*; do
  [[ -e "$entry" ]] || continue
  ln -sfn "$entry" "$TARGET_DIR/$CLI_DIR/commands/$(basename "$entry")"
done

echo "✅ AgtMLS setup complete for $CLI_DIR."
