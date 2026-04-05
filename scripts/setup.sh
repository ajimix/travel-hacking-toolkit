#!/usr/bin/env bash
set -euo pipefail

# Travel Hacking Toolkit - Setup Script
# Gets you from clone to working in under a minute.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Travel Hacking Toolkit Setup ==="
echo ""

# --- Which tool? ---
echo "Which AI coding tool do you use?"
echo "  1) OpenCode"
echo "  2) Claude Code"
echo "  3) Both"
echo ""
read -rp "Choice [1-3]: " TOOL_CHOICE

case "$TOOL_CHOICE" in
  1|2|3) ;;
  *)
    echo "Invalid choice. Exiting."
    exit 1
    ;;
esac

# --- API key setup (always, this is the main value) ---
setup_api_keys() {
  echo ""
  echo "Setting up API keys..."

  if [[ "$TOOL_CHOICE" == "1" || "$TOOL_CHOICE" == "3" ]]; then
    if [ ! -f "$REPO_DIR/.env" ]; then
      cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
      echo "  Created .env (OpenCode). Edit it to add your API keys."
    else
      echo "  .env already exists. Skipping."
    fi
  fi

  if [[ "$TOOL_CHOICE" == "2" || "$TOOL_CHOICE" == "3" ]]; then
    local claude_settings="$REPO_DIR/.claude/settings.local.json"
    if [ ! -f "$claude_settings" ]; then
      if [ -f "$REPO_DIR/.claude/settings.local.json.example" ]; then
        cp "$REPO_DIR/.claude/settings.local.json.example" "$claude_settings"
        echo "  Created .claude/settings.local.json (Claude Code, auto-gitignored)."
        echo "  Edit it to add your API keys."
      fi
    else
      echo "  .claude/settings.local.json already exists. Skipping."
    fi
  fi

  echo ""
  echo "  The 5 free MCP servers work without any keys."
  echo "  For the full experience, add at minimum:"
  echo "    SERPAPI_API_KEY        Cash price comparison"
  echo ""
}

# --- Atlas Obscura npm deps ---
install_atlas_deps() {
  echo "Installing Atlas Obscura dependencies..."
  if command -v npm &>/dev/null; then
    (cd "$REPO_DIR/skills/atlas-obscura" && npm install --silent 2>/dev/null)
    echo "  Done."
  else
    echo "  npm not found. Atlas Obscura will auto-install on first use if Node.js is available."
  fi
}

# --- Global install (optional) ---
offer_global_install() {
  echo ""
  echo "Skills are already available when you work from this directory."
  echo "Want to also install them system-wide (available in any project)?"
  echo ""
  read -rp "Install globally? [y/N]: " GLOBAL_CHOICE

  if [[ "$GLOBAL_CHOICE" == "y" || "$GLOBAL_CHOICE" == "Y" ]]; then
    if [[ "$TOOL_CHOICE" == "1" || "$TOOL_CHOICE" == "3" ]]; then
      install_skills_to "$HOME/.config/opencode/skills"
    fi
    if [[ "$TOOL_CHOICE" == "2" || "$TOOL_CHOICE" == "3" ]]; then
      install_skills_to "$HOME/.claude/skills"
    fi
  else
    echo "  Skipped. You can always run this script again later."
  fi
}

install_skills_to() {
  local target="$1"
  echo ""
  echo "  Installing skills to $target..."
  mkdir -p "$target"

  for skill_dir in "$REPO_DIR"/skills/*/; do
    skill_name=$(basename "$skill_dir")
    dest="$target/$skill_name"

    if [ -d "$dest" ]; then
      echo "    Updating $skill_name..."
      rm -rf "$dest"
    else
      echo "    Installing $skill_name..."
    fi

    cp -r "$skill_dir" "$dest"
  done

  echo "  Done."
}

# --- Run ---
setup_api_keys
install_atlas_deps
offer_global_install

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Launch your tool from this directory:"

if [[ "$TOOL_CHOICE" == "1" || "$TOOL_CHOICE" == "3" ]]; then
  echo "  OpenCode:    opencode"
fi
if [[ "$TOOL_CHOICE" == "2" || "$TOOL_CHOICE" == "3" ]]; then
  echo "  Claude Code: claude --strict-mcp-config --mcp-config .mcp.json"
fi

echo ""

if [[ "$TOOL_CHOICE" == "1" || "$TOOL_CHOICE" == "3" ]]; then
  echo "Add your API keys:  edit .env"
fi
if [[ "$TOOL_CHOICE" == "2" || "$TOOL_CHOICE" == "3" ]]; then
  echo "Add your API keys:  edit .claude/settings.local.json"
fi

echo ""
echo "Then ask: \"Find me a cheap business class flight to Tokyo\""
echo ""
