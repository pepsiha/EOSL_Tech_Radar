# EOSL Tech Radar

工研院電光所國際技術情報週報自動化專案。

這個專案會：

- 從 Google Sheets 讀取關鍵字、收件人與來源網域
- 使用 Tavily 搜尋候選文章
- 用 Gemini 進行評分與摘要
- 產生 HTML 週報、審稿頁與 debug/raw JSON
- 支援 GitHub Actions 自動跑 draft
- 支援人工從 `review.html` 選稿後再正式寄信

---

## 專案流程

### Draft 流程

1. 從 Google Sheets 讀取：
   - `keywords`
   - `members`
   - `sources`
2. 用 Tavily 依關鍵字搜尋文章
3. 進行日期解析與近 7 天過濾
4. 用 Gemini 產生：
   - `relevance_score`
   - `summary`
5. 進行去重、排序與 Top 5 自動選稿
6. 輸出：
   - `docs/YYYY-MM-DD_report.html`
   - `docs/review.html`
   - `docs/review_candidates.json`
   - `data/raw/YYYY-MM-DD_raw.json`
   - `data/debug/YYYY-MM-DD_debug.json`

### Publish 流程

Publish 不會重新跑 Tavily / Gemini。

它會直接讀取 draft 存下來的：

- `docs/review_candidates.json`

再依你在 `review.html` 選出的 URL 產生正式寄送內容。

也就是說：

- `review.html` 選哪幾篇
- publish 就寄哪幾篇

---

## 目前關鍵規則

### 日期規則

- 只保留「前 7 個日曆日，不包含今天」的文章
- 例如今天是 `2026-05-19`
- 有效區間就是 `2026-05-12` 到 `2026-05-18`

### 日期解析優先序

1. `published_date`
2. URL 日期
3. content 內文日期
4. `unknown`

### 日期信心

- `high`
  - `published_date`
  - URL 含日期
  - 明確正文 byline
- `medium`
  - content 有日期，但上下文混有側欄或 related 資訊
- `low`
  - 只有低信心日期訊號
  - 或找不到可靠日期

相關欄位會寫進 debug：

- `resolved_date_utc`
- `date_source`
- `date_confidence`
- `date_warning`

### 非文章頁過濾

搜尋階段會排除明顯不是文章的頁面，例如：

- 首頁
- 搜尋結果頁
- archive / listing / tag / category 頁

### Gemini 評分

Gemini 會輸出：

- `relevance_score`
- `summary`

目前採保守評分策略：

- 10 分極少使用
- 沒有明確技術內容或量化資訊時，原則上不超過 8 分
- 重視技術直接相關性與技術情報價值

### 候選與自動 Top 5

- 候選池會進入 `review.html`
- draft 自動報告最多選 5 篇
- review 候選數可以超過 5 篇
- 你人工發布時，可以不受自動 Top 5 限制

### 最低分門檻

- 自動 Top 5 使用 `7 分` 作為主要門檻

### 同分排序邏輯

同分時優先順序為：

1. `tier1 + tier2 + tier3`
2. `tier1 + tier2`
3. `tier1`

### 去重規則

- 標題近似去重
- 全域 URL 去重

---

## review.html 的用途

`docs/review.html` 是人工審稿頁。

它顯示的是：

- 本次 draft 跑完後的候選文章池

不是：

- 最終自動 Top 5 限定名單

你可以在這裡：

- 勾選想寄出的文章
- 產生發布 URL 清單
- 將 URL 貼到 GitHub Actions 的 `selected_urls`

### 目前輸出格式

審稿頁產生的 URL 清單會輸出為逗號分隔，方便貼到 GitHub Actions 單行輸入框。

目前 `selected_urls` 解析支援：

- 逗號 `,`
- 空格
- 分號 `;`
- 換行

如果 publish 時 0 篇匹配，workflow 會直接失敗，不會假成功。

---

## 目錄結構

```text
EOSL_Tech_Radar/
├─ .github/workflows/
│  └─ weekly_report.yml
├─ config/
│  └─ settings.py
├─ data/
│  ├─ raw/
│  └─ debug/
├─ docs/
│  ├─ YYYY-MM-DD_report.html
│  ├─ review.html
│  ├─ review_candidates.json
│  ├─ reports.json
│  └─ index.html
├─ src/
│  ├─ analyzer.py
│  ├─ date_utils.py
│  ├─ emailer.py
│  ├─ reporter.py
│  ├─ searcher.py
│  └─ sheets_loader.py
├─ templates/
│  ├─ email.html.j2
│  ├─ report.html.j2
│  └─ review.html.j2
├─ main.py
├─ requirements.txt
└─ README.md
```

---

## 安裝

```bash
git clone https://github.com/pepsiha/EOSL_Tech_Radar.git
cd EOSL_Tech_Radar
pip install -r requirements.txt
```

---

## 環境變數

請建立 `.env`：

```bash
cp .env.example .env
```

至少需要：

- `TAVILY_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `SEARCH_MODE`

可選：

- `DISABLE_SSL_VERIFY=true`
- `AUTO_SEND_EMAIL=true|false`
- `SELECTED_URLS=...`

---

## Google Sheets 設定

Spreadsheet 名稱：

- `EOSL_Tech_Radar_DB`

### `keywords`

建議欄位：

| tier1 | tier2 | tier3 | 啟用 | 備註 |
|------|------|------|------|------|
| Semiconductor | memory | MRAM, FRAM | Y | |
| AI Chip, Computing Architecture | CIM, PIM |  | Y | |

### `members`

建議欄位：

| name | email | 啟用 | 備註 |
|------|-------|------|------|
| User | user@example.com | Y | |

### `sources`

建議欄位：

| domain | source_name | category | 啟用 | 備註 |
|------|----------|------|------|------|
| techcrunch.com | TechCrunch | 科技新聞 | Y | |
| semiengineering.com | Semiconductor Engineering | 半導體 | Y | |
| thelec.net | The Elec | 顯示/半導體 | Y | |

---

## 本機執行

```bash
python main.py
```

---

## GitHub Actions

Workflow：

- `.github/workflows/weekly_report.yml`

### 排程

目前設定：

- 台灣時間每週一早上 `08:00`

對應 cron：

```yml
0 0 * * 1
```

### Draft 模式

排程或手動執行時：

- `send_email = false`
- `selected_urls` 留空

會產生：

- report
- review page
- review candidates
- raw/debug JSON

不會寄信。

### Publish 模式

手動執行時：

- `send_email = true`
- `selected_urls` 填入你從 `review.html` 複製的 URL

會：

- 讀取 `docs/review_candidates.json`
- 只挑你指定的文章
- 產生對應報告
- 寄出 email

---

## GitHub Pages

請在 repo 設定：

1. `Settings > Pages`
2. `Source` 選 `Deploy from a branch`
3. `Branch` 選 `main`
4. `Folder` 選 `/docs`

審稿頁網址：

```text
https://pepsiha.github.io/EOSL_Tech_Radar/review.html
```

---

## GitHub Secrets

建議設定：

- `TAVILY_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `GH_PAT`
- `SEARCH_MODE`

---

## 重要輸出檔

### 原始搜尋結果

- `data/raw/YYYY-MM-DD_raw.json`

### Debug 結果

- `data/debug/YYYY-MM-DD_debug.json`

常看欄位：

- `search`
- `analyzer.sorted_articles`
- `top_articles`
- `date_source`
- `date_confidence`
- `selection_stage`
- `selection_reason`

### 候選池

- `docs/review_candidates.json`

### 審稿頁

- `docs/review.html`

### 自動報告

- `docs/YYYY-MM-DD_report.html`

---

## 注意事項

- GitHub Pages 可能有快取，更新後若看起來不是最新內容，請用 `Ctrl + F5`
- 若你清空 `docs/` 後立即觸發 Pages，可能出現暫時 build error，重新跑 draft 後會恢復
- publish 若 0 篇匹配，現在會直接失敗，避免假成功
- 若要確保審稿與寄送完全一致，請先跑最新 draft，再從最新 `review.html` 選稿

