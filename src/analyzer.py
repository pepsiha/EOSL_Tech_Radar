import json

from google import genai
from google.genai import types

from config import settings

_PROMPT_TMPL = """你是工研院電光所的技術情報分析師。
請分析以下技術文章，判斷其與光電、半導體、顯示技術、感測器等領域的相關性，並提供繁體中文摘要。

文章標題：{title}
文章內容片段：{content}

摘要撰寫規則：
- 150字以內
- 若文章含有重要技術突破、關鍵數字（如效能提升幅度、製程節點、功耗數值等）或重大里程碑，必須寫出

請以 JSON 格式回覆（不要加 markdown code block）：
{{
  "relevance_score": <1到10的整數，10為最高相關性>,
  "summary": "<繁體中文摘要，150字以內，包含關鍵技術指標與重大數字>"
}}"""

_MIN_RELEVANCE = 6
TOP_N_ARTICLES = 5


class Analyzer:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def analyze_article(self, article: dict) -> dict:
        """
        呼叫 Gemini 分析單篇文章。
        回傳 article dict 並附加：
        - relevance_score: int
        - summary: str
        """
        prompt = _PROMPT_TMPL.format(
            title=article.get("title", ""),
            content=article.get("content", "")[:2000],
        )
        try:
            response = self._client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            parsed = json.loads(response.text.strip())
            article["relevance_score"] = int(parsed.get("relevance_score", 5))
            article["summary"] = parsed.get("summary", "")
        except Exception as exc:
            print(f"    [Analyzer] Gemini 分析失敗：{exc}")
            article["relevance_score"] = 5
            article["summary"] = "（摘要產生失敗）"
        return article

    def analyze_all(self, search_results: list[dict]) -> list[dict]:
        """
        對所有搜尋結果執行分析。
        search_results 結構與 Searcher.search_all() 回傳相同，
        不設最低分門檻，最終由全域 Top N 決定入選文章。
        """
        for result in search_results:
            articles = result["articles"]
            analyzed: list[dict] = []
            for art in articles:
                print(f"    [Analyzer] 分析：{art.get('title', '')[:50]}")
                analyzed.append(self.analyze_article(art))
            result["articles"] = analyzed

        # 標題相似度去重：同一事件只保留分數最高的那篇
        all_articles = [
            (art, result["keyword"])
            for result in search_results
            for art in result["articles"]
        ]
        all_articles.sort(key=lambda x: x[0].get("relevance_score", 0), reverse=True)
        deduped_urls = self._deduplicate_by_title([a for a, _ in all_articles])
        print(f"[Analyzer] 標題去重：{len(all_articles)} 篇 → {len(deduped_urls)} 篇")

        all_articles = [(a, kw) for a, kw in all_articles if a["url"] in deduped_urls]

        # Top 10 備份（依分數，不限一階）
        backup_urls = {a["url"] for a, _ in all_articles[:TOP_N_ARTICLES * 2]}
        print(f"[Analyzer] Top {TOP_N_ARTICLES * 2} 備份，共 {len(backup_urls)} 篇")

        def _enrich(art: dict, kw: dict) -> dict:
            enriched = dict(art)
            enriched["tier1"] = kw["tier1"].split(",")[0].strip()
            label_parts = [kw["tier2"]] if kw.get("tier2") else []
            if kw.get("tier3"):
                label_parts.append(kw["tier3"])
            enriched["keyword_label"] = " / ".join(label_parts)
            return enriched

        # Phase 1：每個一階取分數最高一篇
        seen_tier1: set[str] = set()
        top_articles: list[dict] = []
        remaining: list[tuple] = []
        for art, kw in all_articles:
            tier1 = kw["tier1"].split(",")[0].strip()
            if tier1 not in seen_tier1:
                seen_tier1.add(tier1)
                top_articles.append(_enrich(art, kw))
                if len(top_articles) >= TOP_N_ARTICLES:
                    break
            else:
                remaining.append((art, kw))

        # Phase 2：若不足 5 篇，從剩餘依分數補足（同一階可重複）
        if len(top_articles) < TOP_N_ARTICLES:
            top_urls_set = {a["url"] for a in top_articles}
            for art, kw in remaining:
                if art["url"] not in top_urls_set:
                    top_articles.append(_enrich(art, kw))
                    top_urls_set.add(art["url"])
                if len(top_articles) >= TOP_N_ARTICLES:
                    break

        top_urls = {a["url"] for a in top_articles}
        print(f"[Analyzer] 全域 Top {TOP_N_ARTICLES}（Phase1 各一階最多一篇，Phase2 補足），共 {len(top_articles)} 篇")

        for result in search_results:
            result["backup_articles"] = [a for a in result["articles"] if a["url"] in backup_urls]
            result["articles"] = [a for a in result["articles"] if a["url"] in top_urls]
            if not result["articles"] and result["used_level"] is not None:
                result["used_level"] = None

        return search_results, top_articles

    def _deduplicate_by_title(self, articles: list[dict]) -> set[str]:
        """
        標題相似度去重（articles 已依分數由高到低排序）。
        將標題拆成關鍵詞集合，若兩篇文章的關鍵詞 Jaccard 相似度 >= 0.5，
        視為同一事件，只保留先出現（分數較高）的那篇。
        回傳保留的 URL 集合。
        """
        kept_urls: set[str] = set()
        kept_keyword_sets: list[set[str]] = []

        for art in articles:
            title = art.get("title", "").lower()
            words = set(w for w in title.split() if len(w) > 2)
            is_duplicate = False
            for existing in kept_keyword_sets:
                if not words or not existing:
                    continue
                intersection = len(words & existing)
                union = len(words | existing)
                if union > 0 and intersection / union >= 0.5:
                    is_duplicate = True
                    break
            if not is_duplicate:
                kept_urls.add(art["url"])
                kept_keyword_sets.append(words)

        return kept_urls
