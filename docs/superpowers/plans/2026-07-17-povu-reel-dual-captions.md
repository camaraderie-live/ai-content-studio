# POVU Reel 雙版本字幕 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 ElevenLabs Scribe 重新轉錄既有 1.25 倍速 POVU Reel，移除舊字幕，交付 Terminal 與 Loud 兩個繁體中文字幕版本；保留既有非字幕動畫與核准音訊，且所有重要字幕都在 IG safe area（x=35..1045、y=220..1500）內。

**Architecture:** 先把 `base_effects.mp4` 的影像與既有核准成品的音訊重封裝成無字幕母帶，再只對母帶做一次 ElevenLabs 逐字轉錄。共用轉錄、人物去背 matte、音量包絡與 safe-zone 分析，然後分流到 embedded-captions 的 Terminal theme compiler 與 Loud cinematic compiler。兩版都先編譯、檢查 timing／occlusion／overflow／IG safe area 並輸出預覽圖，取得使用者確認後才完整 render；最後以同一套媒體與音訊驗證交付。

**Tech Stack:** Python 3.12、ElevenLabs Scribe v1、OpenCC、FFmpeg/FFprobe、Node.js、Bun、HyperFrames、embedded-captions、GSAP、Puppeteer、Sharp。

## Global Constraints

- 設計規格以 [`docs/superpowers/specs/2026-07-17-povu-reel-dual-captions-design.md`](../specs/2026-07-17-povu-reel-dual-captions-design.md) 為唯一依據。
- 來源影像：`/Users/seanhsiao/Desktop/povu-reel/edit/base_effects.mp4`。
- 核准音訊來源：`/Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-final-1.25x-safe.mp4`。
- 不得使用或疊回 `edit/animations/slot_captions/render.webm`。
- 既有非字幕動畫（intro、product、CTA）視為已經烘進 `base_effects.mp4`，不得重新排時或改樣式。
- 所有字幕以繁體中文顯示；`POVU`、`AI`、`Claude`、`ChatGPT`、`Antigravity CLI`、`Google`、`LINE` 保留指定大小寫。
- 影片規格維持 1080×1920、約 64.65 秒、CFR 24 fps、H.264/AAC、1.25 倍速內容。
- IG safe area 是 x=35..1045、y=220..1500；字幕文字、panel、hero、標籤與 CTA 都必須在此範圍。僅允許無語意的全畫面 dim/grain/flash 超出。
- 字幕永遠是最後一層；兩個版本都不得再套用舊字幕。
- API 金鑰只能從 `/Users/seanhsiao/Developer/video-use/.env` 讀取，任何 log、fixture、JSON、commit 與回覆都不得包含金鑰。
- 實作中不得改動使用者既有的 `AGENTS.md`、`CLAUDE.md` 與 `tests/` 未提交內容。
- 使用者尚未核准預覽前，不得執行完整 64.65 秒字幕 render。

---

### Task 1: 建立可重現的本機字幕工具鏈

**Files:**

- Create: `/Users/seanhsiao/Developer/hyperframes/`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/runtime.env`

- [ ] **Step 1: 驗證既有基礎工具**

  Run:

  ```bash
  command -v ffmpeg
  command -v ffprobe
  command -v node
  command -v bun
  python3 -c 'import opencc, requests; print("python deps ok")'
  npx --yes hyperframes doctor
  ```

  Expected: 每一項 exit 0；Node.js 符合 HyperFrames 的最低版本，FFmpeg 與 Chrome/Chromium 可用。

- [ ] **Step 2: 安裝 embedded-captions 所需的 HyperFrames checkout**

  目前一般 `npx hyperframes` 可用，但 embedded-captions 的 matte／preview／render scripts 需要 `packages/cli/dist/cli.js` 與 monorepo 內的 Puppeteer/Sharp。若該檔不存在，執行：

  ```bash
  git clone https://github.com/heygen-com/hyperframes.git /Users/seanhsiao/Developer/hyperframes
  bun install --cwd /Users/seanhsiao/Developer/hyperframes
  bun run --cwd /Users/seanhsiao/Developer/hyperframes build
  test -f /Users/seanhsiao/Developer/hyperframes/packages/cli/dist/cli.js
  ```

  若資料夾已存在，改執行 `git -C /Users/seanhsiao/Developer/hyperframes pull --ff-only` 後重新 build，不重複 clone。

  Expected: 最後一行 exit 0。

- [ ] **Step 3: 凍結這支影片使用的字幕引擎副本**

  Run:

  ```bash
  mkdir -p /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime
  rsync -a --delete /Users/seanhsiao/.agents/skills/embedded-captions/ /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/
  printf 'HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes\n' > /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/runtime.env
  ```

  Expected: `scripts/make-theme.cjs`、`scripts/make-cinematic.cjs`、`themes/terminal.json`、`dna/loud.json` 都存在於凍結副本。

- [ ] **Step 4: 驗證凍結引擎與 runtime 相容**

  Run:

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/preview-frames.cjs --help
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/matte.cjs 2>&1 | grep 'usage:'
  ```

  Expected: 第一個指令能啟動 CLI 說明；第二個只因缺少 project-dir 而回報 usage，不得回報找不到 HyperFrames、Puppeteer 或 Sharp。

---

### Task 2: 建立無字幕、保留核准音訊的母帶

**Files:**

- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-no-captions-1.25x-safe.mp4`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/verify/no-captions/`

- [ ] **Step 1: 重封裝無字幕影像與核准音訊**

  Run:

  ```bash
  mkdir -p /Users/seanhsiao/Desktop/povu-reel/edit/verify/no-captions
  ffmpeg -y \
    -i /Users/seanhsiao/Desktop/povu-reel/edit/base_effects.mp4 \
    -i /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-final-1.25x-safe.mp4 \
    -map 0:v:0 -map 1:a:0 -c:v copy -c:a copy -shortest -movflags +faststart \
    /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-no-captions-1.25x-safe.mp4
  ```

  Expected: 不重新壓縮影像或音訊，輸出可正常播放。

- [ ] **Step 2: 驗證音訊 bitstream 與核准成品完全一致**

  Run:

  ```bash
  ffmpeg -v error -i /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-no-captions-1.25x-safe.mp4 -map 0:a:0 -c copy -f md5 -
  ffmpeg -v error -i /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-final-1.25x-safe.mp4 -map 0:a:0 -c copy -f md5 -
  ```

  Expected: 兩個 MD5 完全相同。

- [ ] **Step 3: 驗證媒體規格與尾端**

  Run:

  ```bash
  ffprobe -v error -show_streams -show_format -of json /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-no-captions-1.25x-safe.mp4
  ffmpeg -v error -i /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-no-captions-1.25x-safe.mp4 -f null -
  ffmpeg -y -ss 64.0 -i /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-no-captions-1.25x-safe.mp4 -frames:v 1 /Users/seanhsiao/Desktop/povu-reel/edit/verify/no-captions/tail.png
  ```

  Expected: 1080×1920、H.264/AAC、約 64.65 秒、無 decode error；尾端不是黑畫面。

---

### Task 3: 重新轉錄並正規化為繁體中文逐字稿

**Files:**

- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/transcripts/base_effects.json`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/transcripts/base_effects.zh-Hant.json`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/scripts/normalize_transcript.py`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/tests/test_normalize_transcript.py`

- [ ] **Step 1: 先寫逐字稿正規化測試**

  `test_normalize_transcript.py` 必須覆蓋：

  - 簡體中文轉繁體中文，但不更動 `start`／`end`。
  - `povu` → `POVU`、`ai` → `AI`、`claude` → `Claude`、`chat gpt`/`ChatGPT` → `ChatGPT`。
  - `anti gravity cli`/相近辨識 → `Antigravity CLI`、`line` 在「社群」語境 → `LINE`。
  - 移除 `audio_event` 類 token，不把音效標籤當字幕。
  - 所有輸出 word 的 `start <= end`，時間單調遞增，最後一字不超過母帶長度 0.15 秒以上。
  - 輸出 schema 固定為 `{language_code, text, words:[{text,start,end,type,speaker_id}]}`。

  Run:

  ```bash
  python3 -m unittest /Users/seanhsiao/Desktop/povu-reel/edit/tests/test_normalize_transcript.py
  ```

  Expected: 測試先因 `normalize_transcript.py` 尚未存在而 FAIL。

- [ ] **Step 2: 上傳完整母帶音訊到 ElevenLabs Scribe**

  先確認 cache 目標不存在；若存在，只把舊檔移到 `edit/transcripts/archive/`，不可覆寫到不留紀錄。然後執行：

  ```bash
  python3 /Users/seanhsiao/Developer/video-use/helpers/transcribe.py \
    /Users/seanhsiao/Desktop/povu-reel/edit/base_effects.mp4 \
    --edit-dir /Users/seanhsiao/Desktop/povu-reel/edit \
    --language zho \
    --num-speakers 1
  ```

  Expected: HTTP 200，生成 `base_effects.json`，`language_code` 為 `zho`，有 word-level timestamps，最後時間約 64.65 秒內。

- [ ] **Step 3: 實作正規化器並讓測試通過**

  `normalize_transcript.py` 使用 `opencc.OpenCC('s2twp')` 做繁轉，保留時間戳，對上述專有名詞做最長片語優先的單調替換；禁止自行重估時間。專有名詞跨多個 token 時，合併後沿用首 token 的 `start` 與末 token 的 `end`。

  Run:

  ```bash
  python3 /Users/seanhsiao/Desktop/povu-reel/edit/scripts/normalize_transcript.py \
    /Users/seanhsiao/Desktop/povu-reel/edit/transcripts/base_effects.json \
    /Users/seanhsiao/Desktop/povu-reel/edit/transcripts/base_effects.zh-Hant.json
  python3 -m unittest /Users/seanhsiao/Desktop/povu-reel/edit/tests/test_normalize_transcript.py
  ```

  Expected: 測試 PASS；輸出 JSON 使用 UTF-8、`ensure_ascii=false`。

- [ ] **Step 4: 人工校對語意，不改動語速與時間軸**

  對照原始旁白與使用者提供的腳本，逐段檢查：阿閎、POVU、10 萬觀看、4 萬觸及、爆款鉤子、做自己、專屬 AI 創作助理、Claude、ChatGPT、Antigravity CLI、Google、LINE、不賣課、完全免費。只修文字與 token 合併，不手動平移時間。

  Run:

  ```bash
  python3 -m json.tool /Users/seanhsiao/Desktop/povu-reel/edit/transcripts/base_effects.zh-Hant.json >/dev/null
  python3 /Users/seanhsiao/Desktop/povu-reel/edit/scripts/normalize_transcript.py --validate-only /Users/seanhsiao/Desktop/povu-reel/edit/transcripts/base_effects.zh-Hant.json
  ```

  Expected: JSON 合法、沒有 `�`、沒有簡體慣用字、沒有超出片長的 word timing。

---

### Task 4: 共用人物 matte、場景安全區與音訊分析

**Files:**

- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/source.mp4`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/transcript.json`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/frames_fg/`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/frames_bg/`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/matte.fps`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/safe-zones.json`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/audio-envelope.json`

- [ ] **Step 1: 建立共用工作區**

  Run:

  ```bash
  mkdir -p /Users/seanhsiao/Desktop/povu-reel/edit/captions-shared
  ln -sfn ../povu-reel-no-captions-1.25x-safe.mp4 /Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/source.mp4
  cp /Users/seanhsiao/Desktop/povu-reel/edit/transcripts/base_effects.zh-Hant.json /Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/transcript.json
  ```

  Expected: `source.mp4` 可由工作區內正常開啟，transcript schema 正確。

- [ ] **Step 2: 只做一次人物 matte**

  Run:

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes \
    node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/matte.cjs \
    /Users/seanhsiao/Desktop/povu-reel/edit/captions-shared
  ```

  Expected: `matte.fps` 為 24；`frames_fg` 與 `frames_bg` PNG 數量相同，約 1552 張；首、中、末三張人物 alpha 不空白。

- [ ] **Step 3: 產生音訊包絡與 safe zones**

  Run:

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/audio-envelope.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-shared
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/safe-zones.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-shared
  ```

  Expected: 兩個 JSON 合法；`safe-zones.json` 有 subject、heroAnchor、heroBands 與 clearerSide。

- [ ] **Step 4: 抽查 matte 品質**

  建立 0%、25%、50%、75%、95% 的人物 matte contact sheet，確認臉、頭髮、上半身沒有大面積破洞；若手持物被 matte 捨棄，Loud 一律保持 `bodyLayer:fg`，Terminal 的 hero 才能在人物後方。

---

### Task 5: 建立 Terminal 與 Loud 的可測試作者檔

**Files:**

- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/scripts/build_caption_projects.py`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/tests/test_caption_projects.py`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal/theme.json`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-loud/cinematic.json`
- Modify: `/Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/themes/terminal.json`
- Modify: `/Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/dna/loud.json`

- [ ] **Step 1: 先寫作者檔 coverage 測試**

  測試必須保證：

  - Terminal `lines` 依 transcript 順序覆蓋每一個可見 word；hero phrase 使用同一組逐字 timing，並符合 theme compiler 的 redaction hand-off 規則。
  - Terminal hero 優先使用「專屬 AI 創作助理」；若逐字稿中沒有連續匹配，使用「完全免費」。不得使用不存在的第三個片語。
  - Loud 每組為 2–4 個可讀語意單位；每組停留至少 0.45 秒，前後時間不重疊，所有 word timing 由 transcript 取得。
  - Loud 強調詞至少涵蓋 `AI`、`POVU`、`10 萬`、`4 萬`、`做自己`、`完全免費`、`不賣課`；不得同時把整句每個字都設為 hero。
  - 兩版 width=1080、height=1920、fps=24；字幕範圍不早於 0、不晚於來源片長。

  Run:

  ```bash
  python3 -m unittest /Users/seanhsiao/Desktop/povu-reel/edit/tests/test_caption_projects.py
  ```

  Expected: 測試先因 `build_caption_projects.py` 尚未存在而 FAIL。

- [ ] **Step 2: 建立兩個專案並共享大型分析產物**

  `build_caption_projects.py` 建立 `captions-terminal` 與 `captions-loud`，複製 `source.mp4`、`transcript.json`、`matte.fps`、`safe-zones.json`、`audio-envelope.json`；`frames_fg`、`frames_bg` 使用相對 symlink 指向 `captions-shared`，避免複製數千張 PNG。

- [ ] **Step 3: 將 Terminal DNA 調整為直式中文與 POVU 配色**

  只修改凍結副本，不改全域 skill：

  - `fonts.body` 與 `fonts.hero` 使用 `POVU Heiti`；tag 保留 `VT323`。
  - `palette.body=#FFFFFF`、`palette.accent=#0F8A66`、`palette.panelBg=rgba(2,14,22,0.78)`。
  - panel：left=64、bottom=470、width=900、fontPx=54，完整落在 IG safe area。
  - hero decode：fontPx 上限 112，theme author 指定 x=540、y=430；hero 可被人物遮擋，但不可越出 safe area。
  - panel header：`POVU // CREATOR ASSISTANT`。

- [ ] **Step 4: 將 Loud DNA 調整為繁中可讀與 POVU 配色**

  只修改凍結副本：

  - `font.family=POVU Heiti`，保留 Loud 的 slam、scale、rotate 與 fg layer 行為。
  - `palette.accent=scene` 仍保留場景取色，但 `accent_fallback=#0F8A66`；caption 為白字，重點才使用 POVU 綠。
  - cinematic plane 固定在 `top: 31%; left: 6%; width: 88%; height: 42%; text-align:center;`，使最上緣 >=220、最下緣 <=1500。
  - 所有逐字動畫只改 transform/opacity，不做 layout-changing width animation。

- [ ] **Step 5: 實作作者檔產生器並通過測試**

  Run:

  ```bash
  python3 /Users/seanhsiao/Desktop/povu-reel/edit/scripts/build_caption_projects.py \
    /Users/seanhsiao/Desktop/povu-reel/edit/captions-shared/transcript.json \
    /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal \
    /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud
  python3 -m unittest /Users/seanhsiao/Desktop/povu-reel/edit/tests/test_caption_projects.py
  ```

  Expected: 測試 PASS；theme/cinematic compiler 尚未執行，但兩個 author JSON 都可由 `python3 -m json.tool` 解析。

---

### Task 6: 內嵌中文字型、編譯並做自動 gate

**Files:**

- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/scripts/inject_povu_font.cjs`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/scripts/check_ig_caption_bounds.cjs`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/tests/test_inject_povu_font.cjs`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal/assets/fonts/STHeiti-Medium.ttc`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-loud/assets/fonts/STHeiti-Medium.ttc`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal/index.html`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal/rail.html`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-loud/index.html`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-loud/index_fg.html`

- [ ] **Step 1: 先寫字型注入測試**

  測試建立最小 HTML fixture，執行注入器兩次，驗證：

  - 只有一個 `@font-face`，family 為 `POVU Heiti`。
  - URL 使用專案內相對路徑 `assets/fonts/STHeiti-Medium.ttc`。
  - `lang=zh-Hant` 存在。
  - 重複執行不會累積 style block。

  Expected: 測試先 FAIL。

- [ ] **Step 2: 實作字型注入器**

  從既有 `/Users/seanhsiao/Desktop/povu-reel/edit/animations/slot_captions/assets/fonts/STHeiti-Medium.ttc` 複製字型到兩個新專案；在 compiler 生成的 `index.html`、`rail.html`、`index_fg.html` 插入本地 `@font-face`。不得連網抓字型，不得依賴 macOS 系統 fallback。

- [ ] **Step 3: 編譯 Terminal**

  Run:

  ```bash
  node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/make-theme.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal
  node /Users/seanhsiao/Desktop/povu-reel/edit/scripts/inject_povu_font.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal
  ```

  Expected: 生成 `index.html`、`rail.html`、`_postfx.sh`；compiler 不得回報 phrase mismatch 或 transcript order error。

- [ ] **Step 4: 編譯 Loud**

  Run:

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/make-cinematic.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud
  node /Users/seanhsiao/Desktop/povu-reel/edit/scripts/inject_povu_font.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud
  ```

  Expected: 生成 `plan.json`、`index.html` 與 `index_fg.html`；DNA 為 `loud`，timing 全由 transcript 匹配。

- [ ] **Step 5: 執行 HyperFrames 與 embedded-captions gates**

  Run for both projects:

  ```bash
  npx --yes hyperframes lint /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal
  npx --yes hyperframes check /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal
  npx --yes hyperframes lint /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud
  npx --yes hyperframes check /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud
  node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/check-timing.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud --strict
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/check-occlusion.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud --strict
  ```

  Expected: lint/check/timing/occlusion 全 PASS；任何 FAIL 都先修 author JSON 或 layout，再重新編譯，不能用 skip flag 繞過。

- [ ] **Step 6: 執行專案的 IG safe-area gate**

  `check_ig_caption_bounds.cjs` 用 HyperFrames checkout 內的 Puppeteer，依 transcript word start/mid/end 抽樣 seek，量測 Terminal 的 `#panel`、`#blk` 與 Loud 的 `.cap` bounding box。規則為：所有有語意的可見節點 `left>=35`、`right<=1045`、`top>=220`、`bottom<=1500`；允許 `#dimP`、grain、scrim、flash 這類無字全畫面效果例外。

  Run:

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/scripts/check_ig_caption_bounds.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/scripts/check_ig_caption_bounds.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud
  ```

  Expected: 兩版都是 `PASS x=35..1045 y=220..1500`；不能靠 clipping 把半個字切掉來通過。

---

### Task 7: 產生兩套預覽並等待使用者核准

**Files:**

- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal/preview/contact-sheet.jpg`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-loud/preview/contact-sheet.jpg`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/verify/captions-preview-safe-guides.jpg`

- [ ] **Step 1: 產生 Terminal 預覽影格**

  Run:

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/preview-frames.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal
  ```

  預覽必含：開場 panel、10 萬/4 萬段、`專屬 AI 創作助理` decode hero、Claude/ChatGPT 段、`做自己` CTA、最後 `不賣課/完全免費`。

- [ ] **Step 2: 產生 Loud 預覽影格**

  Run:

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes node /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/preview-frames.cjs /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud
  ```

  預覽必含：開場、POVU 工程師、10 萬/4 萬、做自己、專屬 AI 創作助理、Claude/ChatGPT、Antigravity CLI、LINE CTA、結尾不賣課。

- [ ] **Step 3: 加上 IG safe-area guide 並人工品管**

  每張預覽疊上 x=35/1045、y=220/1500 的黃色 guide。檢查：繁中無誤字、字型不是 fallback、沒有文字互撞、沒有蓋住既有關鍵截圖/Logo、臉仍是主視覺、Terminal hero 只出現一次、Loud 不會每個字都同樣大。

- [ ] **Step 4: 暫停並把兩張 contact sheet 交給使用者確認**

  此為硬性核准點。清楚標示「Terminal 版」與「Loud 版」，等待使用者說可以或提出修改；在取得確認前不得開始 Task 8。

---

### Task 8: 完整 render 兩個字幕版本

**Files:**

- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal/final_fx.mp4`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/captions-loud/final.mp4`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-1.25x-terminal-captions.mp4`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-1.25x-loud-captions.mp4`

- [ ] **Step 1: 使用核准後的 author JSON 重新編譯與注入字型**

  重跑 Task 6 的 compile、font injection、lint、check、timing、occlusion、IG safe-area gate。任何 compiler 重跑都必須在 render 前重新注入 `POVU Heiti`。

- [ ] **Step 2: Render Terminal**

  因官方 `render-theme.sh` 會先重新 compile 而覆蓋中文字型注入，改用可控順序：

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes bash /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/render-and-composite.sh /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal /Users/seanhsiao/Developer/hyperframes
  bash /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal/_postfx.sh
  cp /Users/seanhsiao/Desktop/povu-reel/edit/captions-terminal/final_fx.mp4 /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-1.25x-terminal-captions.mp4
  ```

  Expected: timing、overflow、rail-climax gates PASS；沒有 page error；生成約 64.65 秒的 `final_fx.mp4`。

- [ ] **Step 3: Render Loud**

  ```bash
  HYPERFRAMES_ROOT=/Users/seanhsiao/Developer/hyperframes bash /Users/seanhsiao/Desktop/povu-reel/edit/caption-runtime/embedded-captions/scripts/render-and-composite.sh /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud /Users/seanhsiao/Developer/hyperframes
  cp /Users/seanhsiao/Desktop/povu-reel/edit/captions-loud/final.mp4 /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-1.25x-loud-captions.mp4
  ```

  Expected: timing、occlusion、overflow gates PASS；Loud fg captions 疊在人物與既有 overlays 之上，約 64.65 秒。

---

### Task 9: 最終驗證、品管與交付

**Files:**

- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/scripts/verify_caption_deliverables.py`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/verify/terminal/contact-sheet-safe.jpg`
- Create: `/Users/seanhsiao/Desktop/povu-reel/edit/verify/loud/contact-sheet-safe.jpg`
- Modify: `/Users/seanhsiao/Desktop/povu-reel/edit/QUALITY_REPORT.md`

- [ ] **Step 1: 寫並執行媒體驗證器**

  驗證器對兩個交付檔檢查：

  - 1080×1920、H.264、AAC 48kHz stereo、24 fps、片長與母帶差 <=0.10 秒。
  - 全片可 decode，無 DTS/PTS error。
  - 首尾 0.5 秒不是全黑；尾端沒有人物浮在黑底。
  - 音訊 bitstream MD5 與核准母帶相同；若 HyperFrames 因 container 重封裝導致 copy-level MD5 不同，改比對 decode 後 PCM MD5，必須相同。
  - 連續無聲不得超過原母帶對應區間 0.10 秒。

  Run:

  ```bash
  python3 /Users/seanhsiao/Desktop/povu-reel/edit/scripts/verify_caption_deliverables.py \
    /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-no-captions-1.25x-safe.mp4 \
    /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-1.25x-terminal-captions.mp4 \
    /Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-1.25x-loud-captions.mp4
  ```

  Expected: 所有項目 PASS。

- [ ] **Step 2: 產生 18-frame 全片 contact sheets 與 safe guides**

  每版至少抽 18 張，包含 0%、5%、10%…95%、99%，疊上 safe-area guide。人工逐張確認字幕沒有被既有 intro/product/CTA 圖層蓋住，且所有重要文字在 guide 內。

- [ ] **Step 3: 執行內容品管**

  套用 `quality-check`：

  - 像不像本人：語句與實際口白一致，沒有 AI 自行改寫。
  - 平台格式：9:16、IG safe area、字級可讀、CTA 清楚。
  - 影片自檢：字幕 timing、拼字、動畫、音訊、首尾、沒有舊字幕殘影。

  不合格就回到 Task 5/6 修正並重新跑 Task 7 的預覽核准；不得直接交付。

- [ ] **Step 4: 更新品質報告**

  在 `QUALITY_REPORT.md` 記錄：來源檔、ElevenLabs 語言、兩版身份、safe-area bounds、所有 gate 結果、ffprobe 摘要、audio MD5/PCM MD5、contact sheet 路徑與人工檢查結論。不得記錄 API 金鑰。

- [ ] **Step 5: 完成前證據檢查**

  套用 `superpowers:verification-before-completion`，重新執行 Task 9 Step 1 的命令並讀取最新輸出；只有所有檢查都在本次工作階段 PASS 才能宣告完成。

- [ ] **Step 6: 交付兩個版本**

  交付：

  - `/Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-1.25x-terminal-captions.mp4`
  - `/Users/seanhsiao/Desktop/povu-reel/edit/povu-reel-1.25x-loud-captions.mp4`

  同時附上兩張 safe-area contact sheet 與 `QUALITY_REPORT.md`，並詢問是否要把喜歡的字幕樣式存進 `~/.Codex/skills/video-use/custom/` 供下一支影片沿用。

---

## Commit Strategy

- 本次主要媒體輸出位於非 Git 的影片專案，不把影片、matte frames、轉錄 JSON 或 API 設定提交到 starter-kit。
- starter-kit 只提交本計畫文件；commit 訊息使用繁體中文且無前綴：`新增 POVU Reel 雙版本字幕實作計畫`。
- 保留使用者原本未提交的 `AGENTS.md`、`CLAUDE.md` 與 `tests/`，不得一起 stage。
