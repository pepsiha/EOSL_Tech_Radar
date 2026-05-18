import itertools
from datetime import datetime, timedelta, timezone
from typing import Any
import datetime as _dt
from urllib.parse import parse_qs, urlparse

from tavily import TavilyClient

from config import settings
from src.date_utils import resolve_article_date


class Searcher:
    def __init__(self) -> None:
        self._client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        self._mode = settings.SEARCH_MODE
        self._max_results = settings.MAX_ARTICLES_PER_KEYWORD
        self._days = settings.DAYS_RANGE
        self.debug_info: list[dict] = []

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

    def _is_recent(self, article: dict) -> tuple[bool, str, str, str | None, str | None]:
        """判斷文章是否落在「今天之前的前 DAYS_RANGE 個日曆日」內。"""
        today = _dt.date.today()
        window_start = today - timedelta(days=self._days)
        window_end = today - timedelta(days=1)
        dt, date_source, date_confidence, date_warning = resolve_article_date(article)
        if dt is None:
            return False, date_source, date_confidence, None, date_warning

        published_date = dt.date()
        return (
            window_start <= published_date <= window_end,
            date_source,
            date_confidence,
            dt.isoformat(),
            date_warning,
        )

    def _extract_hostname(self, url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    def _domain_matches(self, url: str, domains: list[str]) -> bool:
        if not domains:
            return True
        return any(domain in url for domain in domains)

    def _is_article_like(self, url: str, title: str) -> tuple[bool, str]:
        parsed = urlparse(url)
        path = (parsed.path or "").strip("/")
        path_lower = path.lower()
        title_lower = (title or "").strip().lower()
        query = parse_qs(parsed.query)

        if not path:
            return False, "homepage"

        blocked_exact_paths = {
            "search",
            "search/",
            "archive",
            "archives",
            "tag",
            "tags",
            "category",
            "categories",
        }
        if path_lower in blocked_exact_paths:
            return False, "listing_path"

        blocked_segments = {
            "search",
            "results",
            "result",
            "tag",
            "tags",
            "category",
            "categories",
            "archive",
            "archives",
            "topics",
            "topic",
            "authors",
            "author",
            "page",
        }
        segments = [segment for segment in path_lower.split("/") if segment]
        if any(segment in blocked_segments for segment in segments[:-1]):
            return False, "listing_segment"

        if "search" in path_lower or "results.asp" in path_lower:
            return False, "search_results_page"

        if any(key in query for key in ("q", "query", "search", "keyword")):
            return False, "search_query_page"

        blocked_title_markers = (
            "news archive",
            "search results",
            "deep insights for chip engineers",
        )
        if any(marker in title_lower for marker in blocked_title_markers):
            return False, "listing_title"

        return True, "article_like"

    def _search_once(self, query: str, domains: list[str]) -> tuple[list[dict], dict]:
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
            return [], {
                "query": query,
                "mode": self._mode,
                "requested_domains": domains,
                "error": str(exc),
                "articles": [],
            }

        results: list[dict] = []
        debug_articles: list[dict] = []
        for item in response.get("results", []):
            url: str = item.get("url", "")
            published: str = item.get("published_date", "")
            title = item.get("title", "")
            article = {
                "title": title,
                "url": url,
                "published_date": published,
                "content": item.get("content", ""),
            }
            domain_match = self._domain_matches(url, domains)
            article_like, article_like_reason = self._is_article_like(url, title)
            recent_pass, date_source, date_confidence, resolved_date, date_warning = self._is_recent(article)
            selected = True

            # 模式 B 事後過濾
            if self._mode == "B" and domains:
                if not domain_match:
                    selected = False

            if not article_like:
                selected = False

            if not recent_pass:
                selected = False

            debug_articles.append(
                {
                    "title": article["title"],
                    "url": url,
                    "published_date": published,
                    "resolved_date_utc": resolved_date,
                    "date_source": date_source,
                    "date_confidence": date_confidence,
                    "date_warning": date_warning,
                    "domain_match": domain_match,
                    "article_like": article_like,
                    "article_like_reason": article_like_reason,
                    "recent_pass": recent_pass,
                    "selected": selected,
                }
            )

            if not selected:
                continue

            results.append(
                {
                    "title": article["title"],
                    "url": url,
                    "published_date": published,
                    "content": article["content"],
                    "source_domain": self._extract_hostname(url),
                    "resolved_date": resolved_date,
                    "date_source": date_source,
                    "date_confidence": date_confidence,
                    "date_warning": date_warning,
                }
            )

            if len(results) >= self._max_results:
                break

        return results, {
            "query": query,
            "mode": self._mode,
            "requested_domains": domains,
            "raw_result_count": len(response.get("results", [])),
            "selected_count": len(results),
            "articles": debug_articles,
        }

    def _search_level(self, keyword_item: dict, level: str, domains: list[str]) -> list[dict]:
        """
        對某一層級的所有同義詞組合各搜尋一次，合併結果並以 URL 去重。
        所有組合都執行完畢後才回傳，確保每個同義詞都有機會找到文章。
        """
        queries = self._build_queries(keyword_item, level)
        seen_urls: set[str] = set()
        merged: list[dict] = []
        query_debug_logs: list[dict] = []

        for query in queries:
            print(f"    [Searcher] 查詢（{level}）：{query}")
            articles, query_debug = self._search_once(query, domains)
            query_debug_logs.append(query_debug)
            for art in articles:
                if art["url"] not in seen_urls:
                    seen_urls.add(art["url"])
                    merged.append(art)

        return merged, query_debug_logs

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
            articles, query_debug_logs = self._search_level(keyword_item, level, domains)
            self.debug_info.append(
                {
                    "keyword": keyword_item,
                    "level": level,
                    "queries": query_debug_logs,
                    "deduped_selected_articles": [
                        {
                            "title": art["title"],
                            "url": art["url"],
                            "published_date": art["published_date"],
                            "resolved_date_utc": art.get("resolved_date"),
                            "date_source": art.get("date_source", "unknown"),
                            "date_confidence": art.get("date_confidence", "low"),
                            "date_warning": art.get("date_warning"),
                        }
                        for art in articles
                    ],
                }
            )
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
