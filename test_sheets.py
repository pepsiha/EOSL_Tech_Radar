"""
本機測試腳本：驗證 Google Sheets 三個工作表的讀取結果
執行方式：py test_sheets.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.sheets_loader import SheetsLoader

def main():
    print("=" * 50)
    print("SheetsLoader 讀取測試")
    print("=" * 50)

    loader = SheetsLoader()

    # --------------------------------------------------
    # 1. Keywords
    # --------------------------------------------------
    print("\n【keywords 工作表】")
    keywords = loader.get_keywords()
    total = len(keywords)
    for i, kw in enumerate(keywords, 1):
        tier3_part = f" / {kw['tier3']}" if kw["tier3"] else ""
        print(f"  [{i}/{total}] {kw['tier1']} / {kw['tier2']}{tier3_part}")
        print(f"         search_levels: {kw['search_levels']}")

    # --------------------------------------------------
    # 2. Members
    # --------------------------------------------------
    print("\n【members 工作表】")
    members = loader.get_members()
    for m in members:
        print(f"  {m['name']}  <{m['email']}>")

    # --------------------------------------------------
    # 3. Sources
    # --------------------------------------------------
    print("\n【sources 工作表】")
    sources = loader.get_sources()
    for domain in sources:
        print(f"  {domain}")

    # --------------------------------------------------
    # 統計
    # --------------------------------------------------
    print("\n" + "=" * 50)
    print(f"關鍵字共 {len(keywords)} 筆、成員共 {len(members)} 人、來源網域共 {len(sources)} 個")
    print("=" * 50)


if __name__ == "__main__":
    main()
