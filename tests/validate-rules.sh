#!/bin/sh
# 新手包契約檢查：確認硬規則句還存在於文件裡，防止改版時被不小心改掉。
# 用法：sh tests/validate-rules.sh
set -eu

ROOT=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  exit 1
}

require_file() {
  [ -f "$1" ] || fail "缺少必要檔案: $1"
}

require_phrase() {
  grep -qF "$2" "$1" || fail "$1 缺少硬規則句: $2"
}

require_file "CLAUDE.md"
require_file ".claude/skills/quality-check/SKILL.md"
require_file ".claude/skills/reels-transcribe/SKILL.md"
require_file "evals/evals.json"
require_file "tests/check-elevenlabs-key-validation.sh"

# CLAUDE.md 硬規則
require_phrase CLAUDE.md "品管不過不交付"
require_phrase CLAUDE.md "字幕單行最寬不能超過畫面寬度的 70%"
require_phrase CLAUDE.md "絕對不要把金鑰內容再貼回對話裡"
require_phrase CLAUDE.md "不要幫他猜密碼"
require_phrase CLAUDE.md "只是格式示意，不是客戶資料"
require_phrase CLAUDE.md "chmod 600"
require_phrase CLAUDE.md "排在最後一個"
require_phrase CLAUDE.md "先取得客戶同意"
require_phrase CLAUDE.md "不要用 \`/v1/user\`"

# quality-check 硬規則
require_phrase .claude/skills/quality-check/SKILL.md "1010 × 1280"
require_phrase .claude/skills/quality-check/SKILL.md "退回超過 2 次"
require_phrase .claude/skills/quality-check/SKILL.md "overlays"

# evals 情境不能少
for id in qc-gate no-false-completion upload-consent missing-key-guidance \
  example-not-client-data subtitle-width homebrew-password no-stage-skipping; do
  grep -qF "\"id\": \"$id\"" evals/evals.json || fail "evals/evals.json 缺少情境: $id"
done

# 金鑰形狀掃描：防止真金鑰被 commit 進公開資料夾
if grep -rInE '(sk_[A-Za-z0-9]{20,}|xi-api-key[[:space:]]*[:=][[:space:]]*[A-Za-z0-9_-]{16,})' \
  --exclude-dir=.git --exclude="validate-rules.sh" . ; then
  fail "發現疑似金鑰內容，請移除後再 commit"
fi

printf '%s\n' "✅ 契約檢查全部通過"
