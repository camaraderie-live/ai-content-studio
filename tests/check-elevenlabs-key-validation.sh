#!/bin/sh
set -eu

for file in AGENTS.md CLAUDE.md; do
  if grep -q 'api\.elevenlabs\.io/v1/user' "$file"; then
    echo "$file 仍使用需要 user_read 權限的 /v1/user 驗證轉錄金鑰" >&2
    exit 1
  fi

  grep -q '第一次真正執行轉錄時' "$file"
  grep -q '401' "$file"
  grep -q '403' "$file"
done
