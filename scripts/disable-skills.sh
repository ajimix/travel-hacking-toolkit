#!/usr/bin/env bash
# Disable skills listed in disabled-skills.txt by renaming their SKILL.md to
# SKILL.md.disabled. Claude Code's skill discovery scans for SKILL.md, so
# renamed files are invisible to it but content stays in the repo.
#
# Idempotent: safe to run multiple times. Run after every upstream merge to
# re-disable any skills upstream restored.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LIST="$REPO_DIR/disabled-skills.txt"
SKILLS_DIR="$REPO_DIR/plugins/travel-hacking-toolkit/skills"

if [ ! -f "$LIST" ]; then
  echo "No disabled-skills.txt found at $LIST. Nothing to do."
  exit 0
fi

if [ ! -d "$SKILLS_DIR" ]; then
  echo "Skills directory not found at $SKILLS_DIR. Aborting."
  exit 1
fi

disabled_count=0
already_count=0
missing_count=0

while IFS= read -r skill || [ -n "$skill" ]; do
  # Skip blank lines and comments
  [[ -z "${skill// }" ]] && continue
  [[ "$skill" =~ ^[[:space:]]*# ]] && continue
  skill="$(echo "$skill" | tr -d '[:space:]')"

  src="$SKILLS_DIR/$skill/SKILL.md"
  dst="$SKILLS_DIR/$skill/SKILL.md.disabled"

  if [ -f "$src" ]; then
    mv "$src" "$dst"
    echo "  disabled: $skill"
    disabled_count=$((disabled_count + 1))
  elif [ -f "$dst" ]; then
    already_count=$((already_count + 1))
  else
    echo "  missing:  $skill (no SKILL.md or SKILL.md.disabled — skill not present)"
    missing_count=$((missing_count + 1))
  fi
done < "$LIST"

echo ""
echo "Summary: $disabled_count newly disabled, $already_count already disabled, $missing_count missing."
