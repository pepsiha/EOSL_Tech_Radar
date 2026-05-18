import json
import os

from dotenv import load_dotenv

load_dotenv()

# API Keys
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
GH_PAT = os.getenv("GH_PAT", "")

# Google Service Account（字串解析為 dict）
_raw_sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
try:
    GOOGLE_SERVICE_ACCOUNT_JSON: dict = json.loads(_raw_sa_json)
except json.JSONDecodeError:
    GOOGLE_SERVICE_ACCOUNT_JSON = {}

# 搜尋模式：A（白名單限制）或 B（全網路＋事後過濾）
SEARCH_MODE: str = os.getenv("SEARCH_MODE", "A").upper()

# Google Sheets 設定
SPREADSHEET_NAME = "EOSL_Tech_Radar_DB"
SHEET_KEYWORDS = "keywords"
SHEET_MEMBERS = "members"
SHEET_SOURCES = "sources"

# 搜尋參數
MAX_ARTICLES_PER_KEYWORD = 3
DAYS_RANGE = 7
AUTO_SEND_EMAIL = os.getenv("AUTO_SEND_EMAIL", "false").lower() == "true"
