# EOSL Tech Radar

自動產出工研院電光所技術情報週報的 Python 專案。

本專案會：
- 從 Google Sheets 讀取關鍵字、成員與來源白名單
- 使用 Tavily 搜尋近期文章
- 使用 Gemini 對文章做相關性評分與繁中摘要
- 依規則挑出 Top 5 文章
- 產出 HTML 週報到 `docs/`
- 寄送 Email 給成員
- 輸出 raw/debug JSON 供排查流程

---

## 專案架構

```text
Google Sheets
  ├─ keywords
  ├─ members
  └─ sources
        ↓
Tavily Search
        ↓
Date Resolve / Recent Filter
  published_date -> url -> content -> unknown
        ↓
Gemini Scoring + Summary
        ↓
Dedup + Top 5 Selection
        ↓
HTML Report + Debug JSON + Email
```

---

## 安裝

```bash
git clone https://github.com/your-org/EOSL_Tech_Radar.git
cd EOSL_Tech_Radar
pip install -r requirements.txt
```

---

## 環境變數

請建立 `.env`：

```bash
cp .env.example .env
```

至少需要以下設定：

- `TAVILY_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GMAIL_USER`
- `GMAIL_APP_PASSWORD`
- `SEARCH_MODE`

可選設定：

- `DISABLE_SSL_VERIFY=true`

---

## Google Sheets 設定

Spreadsheet 名稱固定為：

- `EOSL_Tech_Radar_DB`

需要三個工作表：

### `keywords`

建議欄位：

| 一階 | 二階 | 三階 | 啟用 | 備註 |
|------|------|------|------|------|
| Semiconductor | memory | MRAM, FRAM | 是 | |
| AI Chip, Computing Architecture | CIM, PIM |  | 是 | |

說明：
- `一階`、`二階`、`三階` 可用逗號放多個同義詞
- `啟用=是` 才會參與搜尋

### `members`

建議欄位：

| 姓名 | Email | 啟用 | 備註 |
|------|-------|------|------|
| 王小明 | user@example.com | 是 | |

### `sources`

建議欄位：

| 網域 | 網站名稱 | 類別 | 啟用 | 備註 |
|------|----------|------|------|------|
| techcrunch.com | TechCrunch | 產業新聞 | 是 | |
| semiengineering.com | Semiconductor Engineering | 半導體 | 是 | |
| thelec.net | The Elec | 面板/半導體 | 是 | |

---

## 執行方式

本機執行：

```bash
python main.py
```

---

## 目前核心邏輯

### 1. 搜尋與降階

每筆關鍵字的搜尋順序：

1. `tier1+tier2+tier3`
2. `tier1+tier2`
3. `tier1`

只要某一層有結果，就停止降階。

同欄位的逗號同義詞會做 Cartesian product 組合，例如：

- `tier1 = AI Chip, Computing Architecture`
- `tier2 = CIM, PIM`

會展開成多組查詢。

### 2. 搜尋模式

- `SEARCH_MODE=A`
  Tavily 直接使用 `include_domains`

- `SEARCH_MODE=B`
  搜尋全網，再由本地做白名單過濾

### 3. 日期判定

目前日期來源優先序：

1. `published_date`
2. `url`
3. `content`
4. `unknown`

### 4. 近期期區間

目前採用：

- 前 7 個日曆日
- 不包含今天

例如執行日是 `2026-05-18`：

- 接受 `2026-05-11` 到 `2026-05-17`
- 不接受 `2026-05-18`

### 5. content 日期 fallback

`published_date` 與 `url` 都沒有日期時，會從文章 `content` 嘗試抽取日期。

目前支援：

- `March 19, 2026`
- `March 19th, 2026`
- `2026-05-14`
- `2026/05/14`

而且會優先找像正文發布欄位的格式，例如：

- `March 19th, 2026 - By: ...`
- `Published: March 19, 2026`
- `Updated: 2026-05-14`

### 6. Gemini 評分

Gemini 會針對文章輸出：

- `relevance_score`
- `summary`

目前採保守打分：

- `10分` 非常難拿
- 沒有技術內容或量化數據時，原則上不超過 `8分`
- 不因公司知名度或熱門程度自動高分
- 主要看技術直接相關性與情報價值

目前實際寫在程式中的評分 prompt 概念如下：

```text
你是工研院電光所的技術情報分析師。

請分析以下文章，判斷它對工研院電光所的技術情報價值，並輸出相關性分數與繁體中文摘要。

文章標題：{title}
文章內容片段：{content}

電光所核心關注領域包含：
- 光電與光通訊
- 半導體與先進封裝
- 顯示技術
- 感測器
- AI 晶片與運算架構
- HPC 散熱、資料傳輸、矽光子、CPO 等技術
- 化合物半導體（如 GaN、SiC）
- 與上述主題直接相關之材料、元件、製程、設備、系統架構與應用

請根據「技術直接相關性」與「技術情報價值」評分 relevance_score（1-10）。

保守評分規則：
- 10分：極少使用。必須同時滿足：
  1. 與電光所核心技術直接高度相關
  2. 具明確技術突破或重大里程碑
  3. 含具體量化資訊，如效能、功耗、製程節點、速度、良率、成本、尺寸、材料參數等
  4. 對技術發展、研發方向或產業競爭具有明顯高價值
- 9分：高度相關且具高情報價值，但在技術突破性、量化資訊完整度或影響程度上略低於10分
- 7-8分：明確相關，具一定技術內容或產業價值，但未達重大突破等級
- 5-6分：部分相關，偏產業新聞、產品發布、公司動態、市場訊號，技術深度有限
- 3-4分：僅間接相關，對核心技術研判幫助有限
- 1-2分：幾乎無關或情報價值很低

重要限制：
- 不要因為公司知名度高就給高分
- 不要因為文章主題熱門就給高分
- 若缺乏明確技術內容、量化數據或可供研發判讀的資訊，最高原則上不要超過8分
- 若只是活動宣傳、產品宣傳、財務消息、轉載整理或泛泛趨勢描述，分數應明顯降低
- 10分與9分必須謹慎使用，只有在技術價值非常明確時才可給出
- 評分請偏保守，不要過度集中在8分以上

摘要撰寫規則：
- 使用繁體中文
- 150字以內
- 優先寫出技術重點、關鍵數字、突破意義與潛在影響
- 若技術內容有限，請直接指出其主要價值偏向產業動態或趨勢訊號

請只輸出 JSON，不要加 markdown code block：
{
  "relevance_score": <1到10的整數>,
  "summary": "<繁體中文摘要>"
}
```

### 7. Top 5 挑選

目前選文規則：

1. 先依 `relevance_score` 由高到低排序
2. 做標題相似事件去重
3. 做全域 URL 去重
4. Phase 1：每個一階先取分數最高的一篇
5. Phase 2：若不足 5 篇，再由剩餘高分文章補滿
6. 總數最多 5 篇
7. 同一階可以超過 1 篇

---

## 輸出檔案

執行後會產生：

- 原始搜尋資料：`data/raw/YYYY-MM-DD_raw.json`
- Debug 決策資料：`data/debug/YYYY-MM-DD_debug.json`
- 週報 HTML：`docs/YYYY-MM-DD_report.html`
- 週報索引：`docs/reports.json`

---

## Debug JSON 說明

`data/debug/YYYY-MM-DD_debug.json` 是排查主依據。

### 搜尋階段

每篇文章會記錄：

- `published_date`
- `resolved_date_utc`
- `date_source`
- `domain_match`
- `recent_pass`
- `selected`

### 分析階段

`analyzer.sorted_articles` 會記錄：

- `relevance_score`
- `tier1 / tier2 / tier3`
- `sort_basis`
- `rank_after_sort`
- `selection_stage`
- `selection_reason`

常見 `selection_stage`：

- `phase1_tier1_pick`
- `phase2_fillup`
- `not_selected`

常見 `selection_reason`：

- `highest_score_in_tier1`
- `filled_remaining_slots_by_score`
- `tier1_already_has_higher_score_article`
- `top_n_reached_before_this_tier1`

### 去重紀錄

`analyzer.duplicate_removed_articles` 會記錄：

- `duplicate_title_removed`
- `duplicate_url_removed`

---

## GitHub Actions / Pages

專案可搭配 GitHub Actions 定期執行，並把週報發佈到 GitHub Pages。

常用 secrets：

- `TAVILY_API_KEY`
- `GEMINI_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GH_PAT`
- `SEARCH_MODE`

若要啟用 GitHub Pages：

1. 到 `Settings > Pages`
2. Source 選 `Deploy from a branch`
3. Branch 選 `main` 與 `/docs`

---

## 注意事項

- Tavily 額度不足時，請避免隨意重跑 `main.py`
- 若結果異常，先看 `data/debug/`，不要只看最終 HTML
- 若文章日期有誤判，優先檢查：
  - `published_date`
  - `resolved_date_utc`
  - `date_source`
