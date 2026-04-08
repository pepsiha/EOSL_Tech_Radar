# EOSL Tech Radar — 工研院電光所技術情報週報系統

## 專案目標
每週日台灣時間 21:00 自動執行，根據 Google Sheets 關鍵字庫對可信國際網站進行搜尋，收集近一週最新技術文章，生成繁體中文週報，透過 GitHub Pages 展示並以 Email 寄送給團隊成員。

## 系統架構
- 關鍵字與成員管理：Google Sheets（三個工作表）
- 搜尋引擎：Tavily API（免費方案，每月 1,000 credits）
- AI 分析摘要：Google Gemini API
- 自動執行：GitHub Actions（每週日 UTC 13:00）
- 網站展示：GitHub Pages（docs/ 資料夾）
- Email 通知：Resend API
- 原始資料保存：data/raw/（JSON 格式，永久保存在 repo）

## Google Sheets 結構
試算表名稱：EOSL_Tech_Radar_DB

工作表一「keywords」欄位：一階、二階、三階、啟用、備註
工作表二「members」欄位：姓名、Email、啟用、備註
工作表三「sources」欄位：網域、網站名稱、類別、啟用、備註

sources 工作表的「類別」建議值：學術論文、科技媒體、大廠部落格
搜尋模式 A 時，從 sources 讀取所有「啟用=是」的網域作為白名單限制搜尋範圍。
搜尋模式 B 時，從 sources 讀取白名單，用於搜尋結果的事後過濾。

## 搜尋策略
1. 優先用「一階+二階+三階」組合搜尋（三階欄位為空則跳過此層）
2. 找不到結果則降級為「一階+二階」
3. 再找不到則降級為「一階」
4. 每個組合最多取 3 篇一週內的最新文章
5. 三個層級都找不到時，該技術標記「本週無相關資訊」

## 搜尋模式（每次執行時從設定選擇）
- 模式 A：只搜尋 sources 工作表中啟用的白名單網站
- 模式 B：搜尋全網路，結果以 sources 白名單過濾不可信來源

## 週報格式
- 依一階技術領域分群排列
- 每篇文章包含：標題、來源網站、發布日期、繁體中文摘要、原文連結
- 找不到文章的領域顯示「本週無相關資訊」

## 技術棧
- Python 3.11+
- gspread（讀取 Google Sheets）
- tavily-python（搜尋）
- google-generativeai（Gemini 摘要）
- resend（Email 發送）
- jinja2（HTML 模板渲染）
- python-dotenv（本機環境變數載入）

## 環境變數（本機從 .env 讀取，GitHub Actions 從 Secrets 讀取）
- TAVILY_API_KEY
- GEMINI_API_KEY
- RESEND_API_KEY
- GOOGLE_SERVICE_ACCOUNT_JSON（整個 JSON 金鑰檔的內容）
- GH_PAT（GitHub Personal Access Token）
- SEARCH_MODE（A 或 B，預設為 A）

## 開發注意事項
- 所有輸出文字使用繁體中文
- .env 檔案絕對不能推上 GitHub
- 原始資料 JSON 檔名格式：data/raw/YYYY-MM-DD_raw.json
- 週報 HTML 檔名格式：docs/YYYY-MM-DD_report.html
- docs/index.html 永遠自動顯示最新一週的週報內容
