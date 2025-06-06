#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title sample-notion-get-db
# @raycast.mode fullOutput

# Optional parameters:
# @raycast.icon 🤖

# Documentation:
# @raycast.description NotionのDBを取得するサンプル

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/venv/bin/activate"
python "$SCRIPT_DIR/sample-notion-get-db.py"