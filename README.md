# EOSL Tech Radar — 工研院電光所技術情報週報系統

每週自動收集國際技術情報，生成繁體中文週報，透過 GitHub Pages 展示並以 Email 寄送給團隊。

---

## 系統架構

```
Google Sheets（關鍵字/成員/來源）
        │
        ▼
  GitHub Actions（每週日 UTC 13:00）
        │
        ├─► Tavily API（搜尋）
        │         │
        │         ▼
        ├─► Gemini API（AI 分析與摘要）
        │         │
        │         ▼
        ├─► 生成 HTML 週報 ──► docs/（GitHub Pages）
        │
        └─► Resend API（Email 通知）
```

---

## 環境建置步驟

### 1. Clone 專案並安裝套件

```bash
git clone https://github.com/your-org/EOSL_Tech_Radar.git
cd EOSL_Tech_Radar
pip install -r requirements.txt
```

### 2. 建立 `.env` 檔（本機開發用）

```bash
cp .env.example .env
# 編輯 .env，填入各 API 金鑰
```

### 3. 申請所需 API 金鑰

| 服務 | 用途 | 免費方案 |
|------|------|----------|
| [Tavily](https://tavily.com) | 智慧搜尋 | 每月 1,000 credits |
| [Google Gemini](https://aistudio.google.com) | AI 摘要分析 | 每日限額 |
| [Resend](https://resend.com) | Email 發送 | 每月 3,000 封 |
| Google Cloud | Sheets API | 免費（需 Service Account） |

---

## Google Sheets 設定說明

試算表名稱須為 **`EOSL_Tech_Radar_DB`**，並共享給 Service Account 的 Email。

### 工作表一：`keywords`

| 一階 | 二階 | 三階 | 啟用 | 備註 |
|------|------|------|------|------|
| 光電技術 | VCSEL | 高功率 | 是 | |
| 光電技術 | LiDAR | 車用 | 是 | |
| 半導體 | GaN | 功率元件 | 是 | |

- **一階**：技術大分類（作為週報分群依據）
- **二階**：子領域
- **三階**：可選，更細的主題（空白則跳過三階搜尋）
- **啟用**：填 `是` 才會被系統讀取

### 工作表二：`members`

| 姓名 | Email | 啟用 | 備註 |
|------|-------|------|------|
| 王小明 | ming@itri.org.tw | 是 | |

### 工作表三：`sources`

| 網域 | 網站名稱 | 類別 | 啟用 | 備註 |
|------|----------|------|------|------|
| arxiv.org | arXiv | 學術論文 | 是 | |
| nature.com | Nature | 學術論文 | 是 | |
| techcrunch.com | TechCrunch | 科技媒體 | 是 | |
| research.google | Google Research | 大廠部落格 | 是 | |

---

## GitHub Actions Secrets 設定

至 **Settings → Secrets and variables → Actions → New repository secret** 逐一新增：

| Secret 名稱 | 說明 |
|-------------|------|
| `TAVILY_API_KEY` | Tavily API 金鑰 |
| `GEMINI_API_KEY` | Google Gemini API 金鑰 |
| `RESEND_API_KEY` | Resend API 金鑰 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Service Account JSON 金鑰檔的完整內容（字串） |
| `GH_PAT` | GitHub Personal Access Token（需有 `repo` 權限） |
| `SEARCH_MODE` | `A` 或 `B`（可省略，預設 A） |

---

## GitHub Pages 設定

1. 至 **Settings → Pages**
2. Source 選擇 **Deploy from a branch**
3. Branch 選擇 `main`，資料夾選擇 `/docs`
4. 儲存後即可透過 `https://your-org.github.io/EOSL_Tech_Radar/` 存取

---

## 本機執行方式

```bash
# 確保 .env 已設定完畢
python main.py
```

執行後會產生：
- `data/raw/YYYY-MM-DD_raw.json`（原始搜尋結果）
- `docs/YYYY-MM-DD_report.html`（週報 HTML）
- `docs/reports.json`（週報清單，供 index.html 使用）

---

## 搜尋模式說明

| 模式 | 說明 |
|------|------|
| **A** | 只搜尋 sources 白名單網站，精確度高，覆蓋範圍較窄 |
| **B** | 搜尋全網路，事後過濾非白名單結果，覆蓋較廣但可能含雜訊 |

在 `.env` 或 GitHub Secret 中設定 `SEARCH_MODE=A` 或 `SEARCH_MODE=B`。
