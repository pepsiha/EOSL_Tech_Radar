import itertools
from datetime import datetime, timedelta, timezone
from typing import Any
import datetime as _dt

from tavily import TavilyClient

from config import settings


class Searcher:
    def __init__(self) -> None:
        self._client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        self._mode = settings.SEARCH_MODE
        self._max_results = settings.MAX_ARTICLES_PER_KEYWORD
        self._days = settings.DAYS_RANGE

    # ------------------------------------------------------------------
    # 內部搜尋工具
    # ------------------------------------------------------------------

    def _parse_synonyms(self, value: str) -> list[str]:
        """將逗號分隔的同義詞字串拆分成 list，過濾空字串。"""
        return [s.strip() for s in value.split(",") if s.strip()]

    def _build_queries(self, keyword_item: dict, level: str) -> list[str]:
        """
        根據層級生成所有同義詞組合的 query 列表。
        各 tier 以逗號分隔多個同義詞，取 Cartesian product 後組成 query。
        例如 tier1="A,B", tier2="K,L", tier3="X,Y"
          tier1+tier2+tier3 → ["A K X", "A K Y", "A L X", "A L Y",
                                "B K X", "B K Y", "B L X", "B L Y"]
          tier1+tier2       → ["A K", "A L", "B K", "B L"]
          tier1             → ["A", "B"]
        """
        t1_list = self._parse_synonyms(keyword_item["tier1"])
        t2_list = self._parse_synonyms(keyword_item["tier2"])
        t3_list = self._parse_synonyms(keyword_item["tier3"])

        today = _dt.date.today()
        date_suffix = today.strftime("%B %Y")  # e.g. "April 2026"

        if level == "tier1+tier2+tier3":
            return [f"{a} {b} {c} {date_suffix}" for a, b, c in itertools.product(t1_list, t2_list, t3_list)]
        if level == "tier1+tier2":
            return [f"{a} {b} {date_suffix}" for a, b in itertools.product(t1_list, t2_list)]
        return [f"{a} {date_suffix}" for a in t1_list]

    def _is_recent(self, published_date: str | None) -> bool:
        """判斷文章是否在過去 DAYS_RANGE 天內發布。無日期視為過舊，直接拒絕。"""
        if not published_date:
            return False  # 無日期無法確認時效，拒絕
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=self._days)
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(published_date[:19], fmt[:19])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.year == now.year and dt >= cutoff
            except ValueError:
                continue
        return False  # 日期格式無法解析，拒絕

    def _search_once(self, query: str, domains: list[str]) -> list[dict]:
        """
        呼叫 Tavily 搜尋一次，回傳符合時間條件的文章 list。
        模式 A：include_domains 傳入白名單
        模式 B：搜尋全網路，事後過濾非白名單
        """
        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": self._max_results * 2,  # 多取一些再過濾
            "search_depth": "advanced",
            "days": self._days,  # 限制 Tavily 只回傳近 N 天的文章
        }
        if self._mode == "A" and domains:
            kwargs["include_domains"] = domains

        try:
            response = self._client.search(**kwargs)
        except Exception as exc:
            print(f"    [Searcher] Tavily 搜尋失敗：{exc}")
            return []

        results: list[dict] = []
        for item in response.get("results", []):
            url: str = item.get("url", "")
            published: str = item.get("published_date", "")

            # 模式 B 事後過濾
            if self._mode == "B" and domains:
                if not any(domain in url for domain in domains):
                    continue

            if not self._is_recent(published):
                continue

            results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "published_date": published,
                    "content": item.get("content", ""),
                    "source_domain": url.split("/")[2] if url else "",
                }
            )

            if len(results) >= self._max_results:
                break

        return results

    def _search_level(self, keyword_item: dict, level: str, domains: list[str]) -> list[dict]:
        """
        對某一層級的所有同義詞組合各搜尋一次，合併結果並以 URL 去重。
        所有組合都執行完畢後才回傳，確保每個同義詞都有機會找到文章。
        """
        queries = self._build_queries(keyword_item, level)
        seen_urls: set[str] = set()
        merged: list[dict] = []

        for query in queries:
            print(f"    [Searcher] 查詢（{level}）：{query}")
            articles = self._search_once(query, domains)
            for art in articles:
                if art["url"] not in seen_urls:
                    seen_urls.add(art["url"])
                    merged.append(art)

        return merged

    # ------------------------------------------------------------------
    # 公開介面
    # ------------------------------------------------------------------

    def search_with_fallback(
        self, keyword_item: dict, domains: list[str]
    ) -> dict:
        """
        三階降級搜尋。每層先跑完所有同義詞組合再判斷是否降階。
        回傳格式：
        {
            "keyword": keyword_item,
            "used_level": str | None,   # 實際成功的層級，None 代表無結果
            "articles": list[dict],
        }
        """
        for level in keyword_item["search_levels"]:
            articles = self._search_level(keyword_item, level, domains)
            if articles:
                return {
                    "keyword": keyword_item,
                    "used_level": level,
                    "articles": articles,
                }

        return {
            "keyword": keyword_item,
            "used_level": None,
            "articles": [],
        }

    def search_all(self, keywords: list[dict], domains: list[str]) -> list[dict]:
        """對所有關鍵字依序執行 search_with_fallback，回傳完整搜尋結果 list。"""
        results: list[dict] = []
        total = len(keywords)
        for idx, kw in enumerate(keywords, 1):
            label = f"{kw['tier1']} / {kw['tier2']}"
            if kw["tier3"]:
                label += f" / {kw['tier3']}"
            print(f"  [Searcher] ({idx}/{total}) {label}")
            result = self.search_with_fallback(kw, domains)
            results.append(result)
        return results
