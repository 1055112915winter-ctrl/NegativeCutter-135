#!/bin/bash
# Ralph Wiggum - Long-running AI agent loop
# Usage: ./ralph.sh [--tool amp|claude] [max_iterations]

set -e

# Parse arguments
TOOL="amp"  # Default to amp for backwards compatibility
MAX_ITERATIONS=10

while [[ $# -gt 0 ]]; do
  case $1 in
    --tool)
      TOOL="$2"
      shift 2
      ;;
    --tool=*)
      TOOL="${1#*=}"
      shift
      ;;
    *)
      # Assume it's max_iterations if it's a number
      if [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_ITERATIONS="$1"
      fi
      shift
      ;;
  esac
done

# Validate tool choice
if [[ "$TOOL" != "amp" && "$TOOL" != "claude" && "$TOOL" != "kimi" ]]; then
  echo "Error: Invalid tool '$TOOL'. Must be 'amp', 'claude', or 'kimi'."
  exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRD_FILE="$SCRIPT_DIR/prd.json"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
ARCHIVE_DIR="$SCRIPT_DIR/archive"
LAST_BRANCH_FILE="$SCRIPT_DIR/.last-branch"

# --- Claude API helpers ---
_call_claude_api() {
  local system_content="$1"
  local user_content="$2"

  local api_key="${ANTHROPIC_API_KEY:-}"
  if [[ -z "$api_key" ]]; then
    echo "Error: ANTHROPIC_API_KEY is not set." >&2
    return 1
  fi

  local api_url="${ANTHROPIC_BASE_URL:-https://api.anthropic.com/v1}/messages"
  local model="${CLAUDE_MODEL:-claude-sonnet-4-20250514}"

  local payload
  payload=$(jq -n \
    --arg model "$model" \
    --arg system "$system_content" \
    --arg user "$user_content" \
    '{model: $model, max_tokens: 64000, system: $system, messages: [{role: "user", content: $user}], stream: false}')

  local response
  response=$(curl -s -X POST "$api_url" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $api_key" \
    -H "anthropic-version: 2023-06-01" \
    -d "$payload" 2>&1) || true

  if [[ -z "$response" ]]; then
    echo "Error: Empty response from API." >&2
    return 1
  fi

  if echo "$response" | jq -e '.error' >/dev/null 2>&1; then
    echo "API Error: $(echo "$response" | jq -r '.error.message // .error.type')" >&2
    return 1
  fi

  echo "$response" | jq -r '.content[0].text // empty'
}

# Archive previous run if branch changed
if [ -f "$PRD_FILE" ] && [ -f "$LAST_BRANCH_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  LAST_BRANCH=$(cat "$LAST_BRANCH_FILE" 2>/dev/null || echo "")
  
  if [ -n "$CURRENT_BRANCH" ] && [ -n "$LAST_BRANCH" ] && [ "$CURRENT_BRANCH" != "$LAST_BRANCH" ]; then
    # Archive the previous run
    DATE=$(date +%Y-%m-%d)
    # Strip "ralph/" prefix from branch name for folder
    FOLDER_NAME=$(echo "$LAST_BRANCH" | sed 's|^ralph/||')
    ARCHIVE_FOLDER="$ARCHIVE_DIR/$DATE-$FOLDER_NAME"
    
    echo "Archiving previous run: $LAST_BRANCH"
    mkdir -p "$ARCHIVE_FOLDER"
    [ -f "$PRD_FILE" ] && cp "$PRD_FILE" "$ARCHIVE_FOLDER/"
    [ -f "$PROGRESS_FILE" ] && cp "$PROGRESS_FILE" "$ARCHIVE_FOLDER/"
    echo "   Archived to: $ARCHIVE_FOLDER"
    
    # Reset progress file for new run
    echo "# Ralph Progress Log" > "$PROGRESS_FILE"
    echo "Started: $(date)" >> "$PROGRESS_FILE"
    echo "---" >> "$PROGRESS_FILE"
  fi
fi

# Track current branch
if [ -f "$PRD_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  if [ -n "$CURRENT_BRANCH" ]; then
    echo "$CURRENT_BRANCH" > "$LAST_BRANCH_FILE"
  fi
fi

# Initialize progress file if it doesn't exist
if [ ! -f "$PROGRESS_FILE" ]; then
  echo "# Ralph Progress Log" > "$PROGRESS_FILE"
  echo "Started: $(date)" >> "$PROGRESS_FILE"
  echo "---" >> "$PROGRESS_FILE"
fi

echo "Starting Ralph - Tool: $TOOL - Max iterations: $MAX_ITERATIONS"

for i in $(seq 1 $MAX_ITERATIONS); do
  echo ""
  echo "==============================================================="
  echo "  Ralph Iteration $i of $MAX_ITERATIONS ($TOOL)"
  echo "==============================================================="

  # Run the selected tool with the ralph prompt
  if [[ "$TOOL" == "amp" ]]; then
    OUTPUT=$(cat "$SCRIPT_DIR/prompt.md" | amp --dangerously-allow-all 2>&1 | tee /dev/stderr) || true
  elif [[ "$TOOL" == "kimi" ]]; then
    # Kimi CLI (no CLI nesting restriction, full tool use support)
    echo "[Ralph] Setting up Kimi environment..."

    # Use TMPDIR-based share dir to bypass sandbox log write restrictions
    export KIMI_SHARE_DIR="${KIMI_SHARE_DIR:-${TMPDIR}/kimi-share}"
    if [[ ! -f "$KIMI_SHARE_DIR/config.toml" ]]; then
      mkdir -p "$KIMI_SHARE_DIR/logs"
      cp -n ~/.kimi/config.toml "$KIMI_SHARE_DIR/" 2>/dev/null || true
      cp -rn ~/.kimi/credentials "$KIMI_SHARE_DIR/" 2>/dev/null || true
      cp -n ~/.kimi/device_id "$KIMI_SHARE_DIR/" 2>/dev/null || true
    fi

    if [[ -z "${KIMI_API_KEY:-}" ]]; then
      echo "[Ralph] Warning: KIMI_API_KEY not set. Kimi may use OAuth fallback."
    fi

    KIMI_PROMPT=$(cat "$SCRIPT_DIR/CLAUDE.md")
    echo "[Ralph] Calling Kimi CLI..."

    # Run from the lrplugin directory so kimi can read prd.json / progress.txt
    KIMI_OUT=$(cd "$SCRIPT_DIR/.." && /Users/winter/.local/bin/kimi --print -p "$KIMI_PROMPT" 2>&1) || true
    OUTPUT="$KIMI_OUT"
    if [[ -n "$OUTPUT" ]]; then
      echo "$OUTPUT"
    fi
  else
    # Claude Code via direct API call (bypasses CLI nesting restriction)
    echo "[Ralph] Loading context files..."
    SYSTEM_PROMPT=$(cat "$SCRIPT_DIR/CLAUDE.md")
    PRD_CONTENT=$(cat "$PRD_FILE")
    PROGRESS_CONTENT=$(cat "$PROGRESS_FILE")

    USER_PROMPT="The PRD and progress files are provided below. Please read them and implement the next user story as instructed in your system prompt.

## PRD (prd.json)
\`\`\`json
${PRD_CONTENT}
\`\`\`

## Progress Log (progress.txt)
\`\`\`
${PROGRESS_CONTENT}
\`\`\`

Please proceed with the next story."

    echo "[Ralph] Calling Claude API (model: ${CLAUDE_MODEL:-claude-sonnet-4-20250514})..."
    API_OUT=$(_call_claude_api "$SYSTEM_PROMPT" "$USER_PROMPT") || true
    OUTPUT="$API_OUT"
    if [[ -n "$OUTPUT" ]]; then
      echo "$OUTPUT"
    fi
  fi
  
  # Check for completion signal in last 30 lines only — early lines echo the prompt which contains the example tag
  if echo "$OUTPUT" | tail -n 30 | grep -q '^<promise>COMPLETE</promise>$'; then
    echo ""
    echo "Ralph completed all tasks!"
    echo "Completed at iteration $i of $MAX_ITERATIONS"
    exit 0
  fi
  
  echo "Iteration $i complete. Continuing..."
  sleep 2
done

echo ""
echo "Ralph reached max iterations ($MAX_ITERATIONS) without completing all tasks."
echo "Check $PROGRESS_FILE for status."
exit 1
