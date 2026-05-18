import json

from google import genai
from google.genai import types

from config import settings

_PROMPT_TMPL = """你是工研院電光所的技術情報分析師。

請分析以下文章，判斷它對工研院電光所的技術情報價值，並輸出相關性分數與繁體中文摘要。

文章標題：{title}
文章內容片段：{content}

電光所核心關注領域包含：
- 光電與光通訊
- 半導體與先進封裝
- 顯示技術
- 感測器
- AI 晶片與運算架構
- HPC 散熱、資料傳輸、矽光子、CPO 等技術
- 化合物半導體（如 GaN、SiC）
- 與上述主題直接相關之材料、元件、製程、設備、系統架構與應用

請根據「技術直接相關性」與「技術情報價值」評分 relevance_score（1-10）。

保守評分規則：
- 10分：極少使用。必須同時滿足：
  1. 與電光所核心技術直接高度相關
  2. 具明確技術突破或重大里程碑
  3. 含具體量化資訊，如效能、功耗、製程節點、速度、良率、成本、尺寸、材料參數等
  4. 對技術發展、研發方向或產業競爭具有明顯高價值
- 9分：高度相關且具高情報價值，但在技術突破性、量化資訊完整度或影響程度上略低於10分
- 7-8分：明確相關，具一定技術內容或產業價值，但未達重大突破等級
- 5-6分：部分相關，偏產業新聞、產品發布、公司動態、市場訊號，技術深度有限
- 3-4分：僅間接相關，對核心技術研判幫助有限
- 1-2分：幾乎無關或情報價值很低

重要限制：
- 不要因為公司知名度高就給高分
- 不要因為文章主題熱門就給高分
- 若缺乏明確技術內容、量化數據或可供研發判讀的資訊，最高原則上不要超過8分
- 若只是活動宣傳、產品宣傳、財務消息、轉載整理或泛泛趨勢描述，分數應明顯降低
- 10分與9分必須謹慎使用，只有在技術價值非常明確時才可給出
- 評分請偏保守，不要過度集中在8分以上

摘要撰寫規則：
- 使用繁體中文
- 150字以內
- 優先寫出技術重點、關鍵數字、突破意義與潛在影響
- 若技術內容有限，請直接指出其主要價值偏向產業動態或趨勢訊號

請只輸出 JSON，不要加 markdown code block：
{{
  "relevance_score": <1到10的整數>,
  "summary": "<繁體中文摘要>"
}}"""

_MIN_RELEVANCE = 6
TOP_N_ARTICLES = 5


class Analyzer:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.debug_info: dict = {}

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

        # 標題相似度去重：同一事件只保留排序最前面的那篇
        all_articles = [
            (art, result["keyword"])
            for result in search_results
            for art in result["articles"]
        ]
        all_articles.sort(
            key=lambda x: x[0].get("relevance_score", 0),
            reverse=True,
        )
        ranked_all_articles = list(all_articles)
        title_deduped_urls = self._deduplicate_by_title([a for a, _ in all_articles])
        print(f"[Analyzer] 標題去重：{len(all_articles)} 篇 → {len(title_deduped_urls)} 篇")

        all_articles, duplicate_removed_articles = self._deduplicate_ranked_articles(
            ranked_all_articles,
            title_deduped_urls,
        )

        # Top 10 備份（依分數排序，不限一階）
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

        # Phase 1：每個一階取分數最高的一篇
        seen_tier1: set[str] = set()
        top_articles: list[dict] = []
        remaining: list[tuple] = []
        selection_stage_by_url: dict[str, str] = {}
        selection_reason_by_url: dict[str, str] = {}
        phase1_selected_tier1: set[str] = set()
        for art, kw in all_articles:
            tier1 = kw["tier1"].split(",")[0].strip()
            if tier1 not in seen_tier1:
                seen_tier1.add(tier1)
                phase1_selected_tier1.add(tier1)
                top_articles.append(_enrich(art, kw))
                selection_stage_by_url[art["url"]] = "phase1_tier1_pick"
                selection_reason_by_url[art["url"]] = "highest_score_in_tier1"
                if len(top_articles) >= TOP_N_ARTICLES:
                    break
            else:
                remaining.append((art, kw))

        # Phase 2：若不足 5 篇，從剩餘高分文章補足（同一階可重複）
        if len(top_articles) < TOP_N_ARTICLES:
            top_urls_set = {a["url"] for a in top_articles}
            for art, kw in remaining:
                if art["url"] not in top_urls_set:
                    top_articles.append(_enrich(art, kw))
                    top_urls_set.add(art["url"])
                    selection_stage_by_url[art["url"]] = "phase2_fillup"
                    selection_reason_by_url[art["url"]] = "filled_remaining_slots_by_score"
                if len(top_articles) >= TOP_N_ARTICLES:
                    break

        top_urls = {a["url"] for a in top_articles}
        print(f"[Analyzer] 全域 Top {TOP_N_ARTICLES}（Phase1 各一階最多一篇，Phase2 補足），共 {len(top_articles)} 篇")

        for result in search_results:
            result["backup_articles"] = [a for a in result["articles"] if a["url"] in backup_urls]
            result["articles"] = [a for a in result["articles"] if a["url"] in top_urls]
            if not result["articles"] and result["used_level"] is not None:
                result["used_level"] = None

        sorted_articles_debug: list[dict] = []
        for rank, (art, kw) in enumerate(all_articles, 1):
            tier1 = kw["tier1"].split(",")[0].strip()
            if art["url"] in selection_stage_by_url:
                selection_stage = selection_stage_by_url[art["url"]]
                selection_reason = selection_reason_by_url[art["url"]]
            elif tier1 in phase1_selected_tier1:
                selection_stage = "not_selected"
                selection_reason = "tier1_already_has_higher_score_article"
            else:
                selection_stage = "not_selected"
                selection_reason = "top_n_reached_before_this_tier1"

            sorted_articles_debug.append(
                {
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "published_date": art.get("published_date"),
                    "resolved_date_utc": art.get("resolved_date"),
                    "date_source": art.get("date_source", "unknown"),
                    "relevance_score": art.get("relevance_score", 0),
                    "tier1": tier1,
                    "tier2": kw.get("tier2", ""),
                    "tier3": kw.get("tier3", ""),
                    "sort_basis": "score_desc",
                    "rank_after_sort": rank,
                    "selection_stage": selection_stage,
                    "selection_reason": selection_reason,
                }
            )

        self.debug_info = {
            "sort_basis": "score_desc",
            "sorted_articles": sorted_articles_debug,
            "duplicate_removed_articles": [
                {
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "published_date": art.get("published_date"),
                    "resolved_date_utc": art.get("resolved_date"),
                    "date_source": art.get("date_source", "unknown"),
                    "relevance_score": art.get("relevance_score", 0),
                    "tier1": kw["tier1"].split(",")[0].strip(),
                    "tier2": kw.get("tier2", ""),
                    "tier3": kw.get("tier3", ""),
                    "sort_basis": "score_desc",
                    "rank_before_dedup": rank,
                    "selection_stage": "removed_before_selection",
                    "selection_reason": removal_reason,
                }
                for rank, art, kw, removal_reason in duplicate_removed_articles
            ],
            "deduped_urls": sorted({art["url"] for art, _ in all_articles}),
            "backup_urls": sorted(backup_urls),
            "final_top_urls": sorted(top_urls),
            "final_top_articles": top_articles,
        }

        return search_results, top_articles

    def _deduplicate_ranked_articles(
        self,
        ranked_articles: list[tuple[dict, dict]],
        title_deduped_urls: set[str],
    ) -> tuple[list[tuple[dict, dict]], list[tuple[int, dict, dict, str]]]:
        """
        在分數排序後做兩層去重：
        1. 標題近似事件去重
        2. 全域 URL 去重（同 URL 只保留排序最前面的那筆）
        """
        deduped_articles: list[tuple[dict, dict]] = []
        removed_articles: list[tuple[int, dict, dict, str]] = []
        seen_urls: set[str] = set()

        for rank, (art, kw) in enumerate(ranked_articles, 1):
            url = art["url"]
            if url not in title_deduped_urls:
                removed_articles.append((rank, art, kw, "duplicate_title_removed"))
                continue
            if url in seen_urls:
                removed_articles.append((rank, art, kw, "duplicate_url_removed"))
                continue

            seen_urls.add(url)
            deduped_articles.append((art, kw))

        return deduped_articles, removed_articles

    def _deduplicate_by_title(self, articles: list[dict]) -> set[str]:
        """
        標題相似度去重（articles 已依分數由高到低排序）。
        將標題拆成關鍵詞集合，若兩篇文章的關鍵詞 Jaccard 相似度 >= 0.5，
        視為同一事件，只保留先出現的那篇。
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
