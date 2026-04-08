# Google Sheets 設定教學

本文件適用於完全沒有 Google Cloud Platform（GCP）經驗的使用者，
請依序完成以下六個步驟。

---

## 步驟一：在 Google Cloud Console 建立專案

1. 開啟瀏覽器，前往 [https://console.cloud.google.com](https://console.cloud.google.com)，
   用你的 Google 帳號登入。

2. 登入後，點擊頁面左上角的**專案選擇器**（通常顯示「選取專案」或現有專案名稱）。

3. 在彈出視窗的右上角，點擊「**新增專案**」。

4. 填寫以下欄位：
   - **專案名稱**：`EOSL-Tech-Radar`（或任何你好辨識的名稱）
   - **位置**：保持預設「無機構」即可

5. 點擊「**建立**」，等待幾秒鐘直到頁面跳回主控台。

6. 確認左上角的專案選擇器已切換到剛建立的 `EOSL-Tech-Radar` 專案。
   若沒有自動切換，請手動點擊選擇器切換過去。

---

## 步驟二：啟用 Google Sheets API 和 Google Drive API

> 這兩個 API 都必須啟用，缺一不可。
> `gspread` 需要 Sheets API 讀取試算表，同時需要 Drive API 才能透過名稱搜尋試算表。

### 啟用 Google Sheets API

1. 在 GCP 主控台左側選單，點擊「**API 和服務**」→「**程式庫**」。

2. 在搜尋框輸入 `Google Sheets API`，點擊搜尋結果中的「**Google Sheets API**」。

3. 點擊「**啟用**」按鈕，等待頁面顯示「已啟用」。

### 啟用 Google Drive API

1. 返回「**API 程式庫**」頁面（點擊左側「程式庫」）。

2. 搜尋 `Google Drive API`，點擊結果中的「**Google Drive API**」。

3. 點擊「**啟用**」按鈕，等待頁面顯示「已啟用」。

---

## 步驟三：建立 Service Account 並下載 JSON 金鑰

Service Account 是一種「機器人帳號」，讓程式可以代表你存取 Google 服務，
不需要每次都用你的個人帳號登入。

### 建立 Service Account

1. 在 GCP 主控台左側選單，點擊「**API 和服務**」→「**憑證**」。

2. 點擊頁面上方的「**+ 建立憑證**」→ 選擇「**服務帳戶**」。

3. 填寫以下欄位：
   - **服務帳戶名稱**：`eosl-tech-radar`
   - **服務帳戶 ID**：會自動填入（例如 `eosl-tech-radar@eosl-tech-radar.iam.gserviceaccount.com`）
   - **服務帳戶說明**：`EOSL Tech Radar 自動化程式`（選填）

4. 點擊「**建立並繼續**」。

5. 「授予此服務帳戶對專案的存取權」這步驟可以**直接跳過**，點擊「**繼續**」。

6. 「授予使用者對這個服務帳戶的存取權」這步驟也**直接跳過**，點擊「**完成**」。

### 下載 JSON 金鑰

1. 回到「**憑證**」頁面，在「服務帳戶」區塊找到剛建立的 `eosl-tech-radar`。

2. 點擊該帳戶的 Email（藍色連結），進入服務帳戶詳細頁面。

3. 點擊上方的「**金鑰**」分頁。

4. 點擊「**新增金鑰**」→「**建立新金鑰**」。

5. 選擇格式「**JSON**」，點擊「**建立**」。

6. 瀏覽器會自動下載一個 JSON 檔案（檔名類似
   `eosl-tech-radar-xxxxxxxx.json`），請妥善保存。
   **這個檔案只能下載一次，遺失後只能重新建立。**

7. 請記下這個 JSON 檔案裡的 `client_email` 欄位值，
   例如：`eosl-tech-radar@eosl-tech-radar.iam.gserviceaccount.com`
   後續步驟六會用到。

---

## 步驟四：將 JSON 金鑰內容設定到 .env 檔案

程式需要讀取整個 JSON 金鑰檔的內容，並以單行字串的形式存在環境變數中。

### 4-1. 複製 JSON 內容

1. 用文字編輯器（記事本、VS Code 等）開啟下載的 JSON 金鑰檔。

2. 全選（`Ctrl+A`）並複製（`Ctrl+C`）整個內容。
   內容大致如下：

   ```json
   {
     "type": "service_account",
     "project_id": "eosl-tech-radar",
     "private_key_id": "abc123...",
     "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
     "client_email": "eosl-tech-radar@eosl-tech-radar.iam.gserviceaccount.com",
     "client_id": "123456789",
     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
     "token_uri": "https://oauth2.googleapis.com/token",
     ...
   }
   ```

### 4-2. 將內容寫入 .env

1. 在專案根目錄（`EOSL_Tech_Radar/`）開啟 `.env` 檔案（從 `.env.example` 複製而來）。

2. 找到 `GOOGLE_SERVICE_ACCOUNT_JSON=` 這一行，將整個 JSON 內容貼到等號後面，
   **必須壓縮成一行**（移除所有換行符號）。

   最快的方式是使用下方的 Python 指令自動完成：

   ```bash
   # 在專案根目錄執行，將路徑換成你實際的 JSON 檔案路徑
   python -c "
   import json, pathlib
   content = pathlib.Path('eosl-tech-radar-xxxxxxxx.json').read_text()
   compact = json.dumps(json.loads(content), ensure_ascii=False)
   print('GOOGLE_SERVICE_ACCOUNT_JSON=' + compact)
   "
   ```

   複製輸出的整行（`GOOGLE_SERVICE_ACCOUNT_JSON={...}`），
   貼入 `.env` 檔案中取代原有的佔位行。

3. 完成後 `.env` 檔案中該行格式應如下（內容為單行）：

   ```
   GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"eosl-tech-radar","private_key_id":"abc123...","private_key":"-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n","client_email":"eosl-tech-radar@eosl-tech-radar.iam.gserviceaccount.com",...}
   ```

> **安全提醒**：`.env` 檔案已加入 `.gitignore`，絕對不要手動把它加入 git 追蹤，
> 也不要把 JSON 金鑰檔上傳到任何公開位置。

---

## 步驟五：建立 Google Sheets 試算表與三個工作表

### 5-1. 建立試算表

1. 前往 [https://sheets.google.com](https://sheets.google.com)，點擊左上角「**+**」建立新試算表。

2. 點擊左上角的試算表名稱（預設為「未命名的試算表」），
   改為：`EOSL_Tech_Radar_DB`
   （名稱必須完全一致，程式會用這個名稱搜尋）。

### 5-2. 建立工作表一：keywords

1. 點擊畫面下方的工作表標籤（預設為「工作表1」），
   **雙擊**標籤名稱，改為 `keywords`，按 `Enter` 確認。

2. 點擊第一列（A1 開始），依序輸入以下欄位標題：

   | A | B | C | D | E |
   |---|---|---|---|---|
   | 一階 | 二階 | 三階 | 啟用 | 備註 |

3. 從第二列開始填入範例資料（之後可自行增刪修改）：

   | 一階 | 二階 | 三階 | 啟用 | 備註 |
   |------|------|------|------|------|
   | 光電技術 | VCSEL | 高功率應用 | 是 | |
   | 光電技術 | LiDAR | 車用感測 | 是 | |
   | 光電技術 | 矽光子 | | 是 | 三階留空，僅搜尋二階 |
   | 半導體 | GaN | 功率元件 | 是 | |
   | 半導體 | SiC | 電動車應用 | 是 | |
   | 顯示技術 | MicroLED | | 是 | |
   | 感測器 | 影像感測器 | CMOS | 是 | |
   | 感測器 | 紅外線感測器 | | 否 | 暫時停用 |

   **欄位說明：**
   - **一階**：技術大分類，週報會用這個欄位分群顯示
   - **二階**：子領域關鍵字
   - **三階**：可選，更細的搜尋詞；若留空，系統會跳過三階搜尋直接從二階開始
   - **啟用**：填 `是` 才會被系統讀取；填 `否` 或留空則略過

### 5-3. 建立工作表二：members

1. 點擊畫面下方「**+**」新增工作表，**雙擊**標籤名稱改為 `members`。

2. 在第一列輸入欄位標題：

   | A | B | C | D |
   |---|---|---|---|
   | 姓名 | Email | 啟用 | 備註 |

3. 從第二列填入範例資料：

   | 姓名 | Email | 啟用 | 備註 |
   |------|-------|------|------|
   | 王小明 | ming@itri.org.tw | 是 | |
   | 李研究員 | lee@itri.org.tw | 是 | |
   | 測試帳號 | test@example.com | 否 | 暫時停用 |

### 5-4. 建立工作表三：sources

1. 點擊「**+**」再新增一個工作表，改名為 `sources`。

2. 在第一列輸入欄位標題：

   | A | B | C | D | E |
   |---|---|---|---|---|
   | 網域 | 網站名稱 | 類別 | 啟用 | 備註 |

3. 從第二列填入範例資料：

   | 網域 | 網站名稱 | 類別 | 啟用 | 備註 |
   |------|----------|------|------|------|
   | arxiv.org | arXiv | 學術論文 | 是 | |
   | nature.com | Nature | 學術論文 | 是 | |
   | science.org | Science | 學術論文 | 是 | |
   | ieee.org | IEEE | 學術論文 | 是 | |
   | opticapublishing.org | Optica Publishing | 學術論文 | 是 | |
   | techcrunch.com | TechCrunch | 科技媒體 | 是 | |
   | theverge.com | The Verge | 科技媒體 | 是 | |
   | arstechnica.com | Ars Technica | 科技媒體 | 是 | |
   | semiengineering.com | Semiconductor Engineering | 科技媒體 | 是 | |
   | research.google | Google Research | 大廠部落格 | 是 | |
   | ai.meta.com | Meta AI | 大廠部落格 | 是 | |
   | blogs.microsoft.com | Microsoft Research Blog | 大廠部落格 | 是 | |
   | samsung.com/semiconductor | Samsung Semiconductor | 大廠部落格 | 是 | |

   **類別建議值**：`學術論文`、`科技媒體`、`大廠部落格`
   （程式目前不依類別做差異處理，但保留此欄供未來擴充）

### 5-5. 確認工作表結構

完成後，試算表底部應有三個標籤：

```
keywords  |  members  |  sources
```

---

## 步驟六：將 Service Account Email 加入 Google Sheets 共用權限

Service Account 是獨立的 Google 帳號，預設無法存取你的試算表。
必須手動將它加入共用名單，程式才能讀取資料。

1. 回到 `EOSL_Tech_Radar_DB` 試算表。

2. 點擊右上角「**共用**」按鈕。

3. 在「新增使用者和群組」欄位，貼上步驟三記錄的 Service Account Email，
   格式例如：
   ```
   eosl-tech-radar@eosl-tech-radar.iam.gserviceaccount.com
   ```

4. 將權限設定為「**檢視者**」（程式只需要讀取，不需要編輯）。

5. **取消勾選**「通知使用者」（Service Account 收不到 Email）。

6. 點擊「**共用**」確認。

7. 共用清單中出現該 Email 且顯示「檢視者」即代表設定成功。

---

## 驗證設定是否正確

完成以上六個步驟後，可以執行以下指令快速驗證連線：

```bash
# 在專案根目錄執行
python -c "
from src.sheets_loader import SheetsLoader
loader = SheetsLoader()
kw = loader.get_keywords()
mb = loader.get_members()
sr = loader.get_sources()
print(f'關鍵字：{len(kw)} 筆')
print(f'成員：{len(mb)} 人')
print(f'來源白名單：{len(sr)} 個網域')
print('連線成功！')
"
```

看到以下輸出即代表 Google Sheets 設定完成：

```
關鍵字：8 筆
成員：2 人
來源白名單：13 個網域
連線成功！
```

---

## 常見錯誤排除

| 錯誤訊息 | 原因 | 解法 |
|----------|------|------|
| `gspread.exceptions.SpreadsheetNotFound` | 試算表名稱不符或未共用 | 確認試算表名稱完全相同，且已加入 Service Account 共用 |
| `google.auth.exceptions.TransportError` | JSON 金鑰格式錯誤 | 確認 `.env` 中的 JSON 是完整的單行字串，無多餘換行 |
| `gspread.exceptions.WorksheetNotFound` | 工作表名稱不符 | 確認三個工作表標籤名稱為 `keywords`、`members`、`sources`（區分大小寫） |
| `APIError: PERMISSION_DENIED` | API 未啟用 | 回到步驟二，確認兩個 API 均已啟用 |
| `json.JSONDecodeError` | `.env` 中的 JSON 內容有問題 | 使用步驟四的 Python 指令重新生成單行 JSON |
