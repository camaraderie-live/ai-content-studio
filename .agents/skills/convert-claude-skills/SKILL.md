---
name: convert-claude-skills
description: 將 Claude Code 專案的 `.claude/skills/` 轉換並同步到 Codex 與 Antigravity 專案技能目錄 `.agents/skills/`。當第一次開啟含 Claude skills 的專案、Claude skills 有新增或修改，或需要檢查兩邊是否同步時使用。
---

# 轉換 Claude Skills 給 Codex 與 Antigravity

在專案根目錄執行：

```bash
python3 .agents/skills/convert-claude-skills/scripts/convert.py
```

## 流程

1. 確認 `.claude/skills/` 存在；不存在就回報無須轉換，不建立空目錄。
2. 執行轉換腳本。它會遞迴複製每個 skill，並只對文字檔做 Codex 相容替換；圖片、字型等二進位資源原樣複製。
3. 不覆寫 `.agents/skills/convert-claude-skills/`，也不刪除 Codex 專屬或使用者自建的 skill。
4. 檢查腳本摘要。若有 `ERROR`，先修正來源 skill，再重跑。
5. 執行官方 skill validator 驗證每個輸出的 skill：

```bash
for skill in .agents/skills/*; do
  [ -f "$skill/SKILL.md" ] || continue
  python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill"
done
```

若系統找不到 validator，至少確認每個 `SKILL.md` 的 YAML frontmatter 只有 `name` 與 `description`，且 skill 資料夾名稱與 `name` 相同。

## 轉換原則

- 專案規則檔：`CLAUDE.md` → `AGENTS.md` (Codex)。Antigravity 的對應版本為 `GEMINI.md`。
- 專案 skill 路徑：`.claude/skills/` → `.agents/skills/`（Codex 與 Antigravity 共用）。
- 個人 skill 路徑：`~/.claude/skills/` → `~/.codex/skills/` (Codex)。Antigravity 對應為 `~/.gemini/config/skills/`（我們在技能內使用 shell 尋找 fallback 來相容）。
- 產品名稱：`Claude Code`／`Claude` → `Codex`，但不要改檔名、網址、程式識別字或二進位檔。
- 保留 frontmatter 的 `name` 與 `description`；不要加入 Claude 專屬欄位。
- 將 frontmatter `description` 裡的尖括號佔位符改成方括號，符合 Codex/Antigravity validator；正文保持原樣。
- 來源 `.claude/skills/` 是同步來源。若要永久修改共用 skill，先改來源再重跑；Codex/Antigravity 專屬 skill 則直接放在 `.agents/skills/`，不要放回來源。
