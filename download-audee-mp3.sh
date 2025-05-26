#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title DownloadAudeeMp3
# @raycast.mode compact

# Optional parameters:
# @raycast.icon 📥
# @raycast.argument1 { "type": "text", "placeholder": "Audee URL" }

# Documentation:
# @raycast.description AudeeのURLからmp3ファイルをダウンロードする

# 対象のURL
URL="$1"

# HTML取得
HTML=$(curl -s "$URL")

# headline（ファイル名用）を抽出
HEADLINE=$(echo "$HTML" | sed -n 's/.*"headline"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)

# mp3 URL を抽出
MP3_URL=$(echo "$HTML" | sed -n 's/.*"contentUrl"[[:space:]]*:[[:space:]]*"\(https:\/\/[^"]*\.mp3\)".*/\1/p' | head -n 1)

# ファイル名を安全に
SAFE_NAME=$(echo "$HEADLINE" | tr ' /' '__')
FILENAME="${SAFE_NAME}.mp3"

# 保存先ディレクトリ（Downloads）
SAVE_DIR="$HOME/Downloads"
OUTPUT_PATH="${SAVE_DIR}/${FILENAME}"

# ダウンロード処理
if [ -n "$MP3_URL" ] && [ -n "$HEADLINE" ]; then
  #echo "🎧 Downloading: $HEADLINE"
  #echo "➡️  From: $MP3_URL"
  echo "💾 Saving as: $OUTPUT_PATH"
  curl -L -o "$OUTPUT_PATH" "$MP3_URL"
else
  echo "❌ headline または MP3 URL が見つかりませんでした。"
fi
