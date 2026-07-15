---
name: script-annotation
description: 處理「腳本＋動畫標註」的剪片需求。只要使用者提供、想寫、或提到影片的旁白／腳本／逐句台詞，或用「一行旁白＋（括號寫想要的動畫）」的方式描述每句要配什麼畫面（飛入、zoom in、數字暴漲、外框、終端機、疊 B-roll、疊圖／截圖／GIF 等），就套用這個 skill。Trigger on any script/narration-driven video edit, per-line animation annotations, or requests to turn a written script into an edit plan.
---

# 腳本＋動畫標註 → 剪輯執行

使用者常會直接貼一整段旁白，每句後面用括號註明想要的畫面。完整格式、給使用者看的「動畫點菜單」與範例在 [腳本動畫標註.md](../../../腳本動畫標註.md)；本 skill 是你（Claude）內部執行時要遵守的規則。全程講**繁體中文**。

## 什麼時候用

- 使用者貼了逐句腳本／旁白，或說「我把台詞寫好了」。
- 使用者用「這句話（想要的畫面）」這種括號標註描述每一段。
- 使用者問「我要怎麼把腳本交給你」→ 主動邀請他用標註格式，並指他去看 [腳本動畫標註.md](../../../腳本動畫標註.md)：「你可以把整段旁白寫下來，每句後面用括號寫想配什麼畫面，我照著做。」

## 硬性流程（不可略）

1. **先複述，再動手**（video-use SKILL.md Hard Rule 11 + 專案 CLAUDE.md 第 6 點）：逐條講一次「這句話我會怎麼呈現」，把每一條的做法、缺的素材、模糊的地方講清楚，使用者說「對」才開始剪。標註常常很精簡，你以為的和他想的可能不一樣。
2. **缺素材就列清單請他補**：對照下表「需要素材」的項目（Claude 動畫、demo 影片、截圖、要飛入的圖等），請他用數字開頭命名丟進專案的 `B-ROLL/`。**不要自己腦補替代品硬做。**
3. **配色一律套主題色**：先讀該影片專案本地的 `<videos_dir>/theme.md`（每支影片各自一份，不是全域），外框／數字／終端機等所有帶顏色的效果都用這組色；還沒設定就先套用 `video-theme-color` skill 跟使用者確認主題色，確認完才動手。
4. **疊層走 HyperFrames，render 前先讓使用者預覽確認**；字幕疊層永遠排 EDL `overlays` 陣列最後一個。
5. **剪完問一句**要不要把可重用元件（開場標題、數字動畫、終端機等）存進 `custom/`（見 CLAUDE.md「剪完之後」）。

## 標註 → 做法對照表（顏色都套 `theme.md` 主題色）

| 使用者的標註 | 做法 | 需要素材 |
|---|---|---|
| 附上 XXX 動畫 / GIF | B-ROLL 素材當 overlay 疊上；沒有現成檔就用 HyperFrames 做一段 | 該動畫/GIF |
| 附上 XXX 圖片 / 截圖 | 靜態圖 overlay，蓋在對應句子的時間區間 | 該圖/截圖 |
| 飛入 XXX / 左右飛入 | HyperFrames slide-in（左或右滑入 keyframe），輸出 webm 透明疊層 | 要飛入的圖 |
| zoom in / 放到最大 | 對底層畫面做 punch-in（scale 慢慢放大），不是疊圖 | 無 |
| 數字 0→84k 暴漲 | HyperFrames 數字滾動計數動畫，數字色套 primary | 無 |
| 外框 / IG 短影音感 | HyperFrames 邊框／標題條疊層 | 無 |
| 終端機動畫 | HyperFrames 打字機／終端機 motion graphic | 無 |
| 疊上 XXX B-roll | 用 B-ROLL 影片蓋住底層對應區間 | 該 B-roll 影片 |

剪片的技術細節（Inventory、EDL、helpers、HyperFrames render 指令）一律照 `~/.claude/skills/video-use/SKILL.md` 與專案 CLAUDE.md，不要在這裡重新發明。
