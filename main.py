"""
EOSL Tech Radar — 主程式進入點
每週日台灣時間 21:00 由 GitHub Actions 自動執行。
"""

import json
import os
import sys
from datetime import date

# 確保 project root 在 import path 中（本機直接執行時需要）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---- 開發環境 SSL 繞過（公司 proxy 有自簽憑證時使用）----
# 在 .env 設定 DISABLE_SSL_VERIFY=true 啟用（GitHub Actions 請勿設定）
from dotenv import load_dotenv as _load_dotenv
_load_dotenv()
if os.getenv("DISABLE_SSL_VERIFY", "").lower() == "true":
    import ssl
    import urllib3
    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    import requests
    _orig_request = requests.Session.request
    def _no_verify_request(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        return _orig_request(self, *args, **kwargs)
    requests.Session.request = _no_verify_request
    print("[SSL] 已停用 SSL 憑證驗證（開發模式）")


def main() -> None:
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")

    print("=" * 60)
    print(f"[主程式] EOSL Tech Radar 啟動 — {date_str}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 步驟 1：載入設定
    # ------------------------------------------------------------------
    print("\n[設定] 載入環境變數...")
    from config import settings  # noqa: F401（觸發 dotenv 載入）
    print(f"[設定] 搜尋模式：{settings.SEARCH_MODE}")

    # ------------------------------------------------------------------
    # 步驟 2：讀取 Google Sheets
    # ------------------------------------------------------------------
    print("\n[Google Sheets] 連線中...")
    from src.sheets_loader import SheetsLoader

    loader = SheetsLoader()
    keywords = loader.get_keywords()
    members = loader.get_members()
    domains = loader.get_sources()

    print(f"[Google Sheets] 關鍵字：{len(keywords)} 筆")
    print(f"[Google Sheets] 成員：{len(members)} 人")
    print(f"[Google Sheets] 來源白名單：{len(domains)} 個網域")

    if not keywords:
        print("[主程式] 無啟用關鍵字，程式結束。")
        return

    # ------------------------------------------------------------------
    # 步驟 3：搜尋並儲存原始資料
    # ------------------------------------------------------------------
    print(f"\n[搜尋] 開始搜尋（模式 {settings.SEARCH_MODE}）...")
    from src.searcher import Searcher

    searcher = Searcher()
    search_results = searcher.search_all(keywords, domains)

    total_articles = sum(len(r["articles"]) for r in search_results)
    print(f"[搜尋] 完成，共取得 {total_articles} 篇文章（過濾前）")

    # 儲存原始資料
    raw_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{date_str}_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(search_results, f, ensure_ascii=False, indent=2)
    print(f"[搜尋] 原始資料已儲存：{raw_path}")

    # ------------------------------------------------------------------
    # 步驟 4：AI 分析
    # ------------------------------------------------------------------
    print("\n[分析] Gemini 分析與過濾中...")
    from src.analyzer import Analyzer

    analyzer = Analyzer()
    analyzed_results, top_articles = analyzer.analyze_all(search_results)

    print(f"[分析] 完成，最終入選 {len(top_articles)} 篇文章")

    # ------------------------------------------------------------------
    # 步驟 5：生成週報 HTML
    # ------------------------------------------------------------------
    print("\n[週報] 生成 HTML...")
    from src.reporter import Reporter

    reporter = Reporter()
    html_content = reporter.generate_html(top_articles, today)
    report_path = reporter.save_report(html_content, today)
    print(f"[週報] 已儲存：{report_path}")

    index_path = reporter.update_index(today)
    print(f"[週報] index.html 已更新：{index_path}")

    # 同步更新 docs/reports.json（供 index.html 讀取清單）
    _update_reports_json()

    # ------------------------------------------------------------------
    # 步驟 6：發送 Email
    # ------------------------------------------------------------------
    if not members:
        print("\n[Email] 無啟用成員，略過發送。")
    else:
        print(f"\n[Email] 發送給 {len(members)} 位成員...")
        from src.emailer import Emailer

        emailer = Emailer()
        emailer.send_report(members, html_content, today)
        print("[Email] 發送完成。")

    print("\n" + "=" * 60)
    print("[主程式] 所有步驟完成！")
    print("=" * 60)


def _update_reports_json() -> None:
    """掃描 docs/ 資料夾，生成 reports.json 供 index.html 讀取。"""
    import glob as _glob

    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    pattern = os.path.join(docs_dir, "????-??-??_report.html")
    files = sorted(
        [os.path.basename(p) for p in _glob.glob(pattern)],
        reverse=True,
    )
    reports_path = os.path.join(docs_dir, "reports.json")
    with open(reports_path, "w", encoding="utf-8") as f:
        json.dump({"reports": files}, f, ensure_ascii=False, indent=2)
    print(f"[週報] reports.json 已更新（{len(files)} 份週報）")


if __name__ == "__main__":
    main()
