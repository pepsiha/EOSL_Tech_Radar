import json
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from config import settings

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetsLoader:
    def __init__(self) -> None:
        sa_info: dict[str, Any] = settings.GOOGLE_SERVICE_ACCOUNT_JSON
        creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        client = gspread.authorize(creds)
        self._spreadsheet = client.open(settings.SPREADSHEET_NAME)

    def get_keywords(self) -> list[dict]:
        """
        回傳啟用中的關鍵字清單。
        每筆格式：
        {
            "tier1": str,
            "tier2": str,
            "tier3": str,          # 可能為空字串
            "search_levels": list  # e.g. ["tier1+tier2+tier3", "tier1+tier2", "tier1"]
                                   # 若 tier3 為空則不含最高層
        }
        工作表欄位順序：一階、二階、三階、啟用、備註
        """
        ws = self._spreadsheet.worksheet(settings.SHEET_KEYWORDS)
        rows = ws.get_all_records()
        keywords: list[dict] = []
        for row in rows:
            enabled = str(row.get("啟用", "")).strip()
            if enabled != "是":
                continue
            tier1 = str(row.get("一階", "")).strip()
            tier2 = str(row.get("二階", "")).strip()
            tier3 = str(row.get("三階", "")).strip()

            search_levels: list[str] = []
            if tier3:
                search_levels.append("tier1+tier2+tier3")
            search_levels.append("tier1+tier2")
            search_levels.append("tier1")

            keywords.append(
                {
                    "tier1": tier1,
                    "tier2": tier2,
                    "tier3": tier3,
                    "search_levels": search_levels,
                }
            )
        return keywords

    def get_members(self) -> list[dict]:
        """
        回傳啟用中的成員清單。
        每筆格式：{"name": str, "email": str}
        工作表欄位順序：姓名、Email、啟用、備註
        """
        ws = self._spreadsheet.worksheet(settings.SHEET_MEMBERS)
        rows = ws.get_all_records()
        members: list[dict] = []
        for row in rows:
            enabled = str(row.get("啟用", "")).strip()
            if enabled != "是":
                continue
            members.append(
                {
                    "name": str(row.get("姓名", "")).strip(),
                    "email": str(row.get("Email") or row.get("email", "")).strip(),
                }
            )
        return members

    def get_sources(self) -> list[str]:
        """
        回傳啟用中的網域白名單 list。
        工作表欄位順序：網域、網站名稱、類別、啟用、備註
        """
        ws = self._spreadsheet.worksheet(settings.SHEET_SOURCES)
        rows = ws.get_all_records()
        domains: list[str] = []
        for row in rows:
            enabled = str(row.get("啟用", "")).strip()
            if enabled != "是":
                continue
            domain = str(row.get("網域", "")).strip()
            if domain:
                domains.append(domain)
        return domains
