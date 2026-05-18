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

TOP_N_ARTICLES = 5
MIN_TOP_SCORE = 7


class Analyzer:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.debug_info: dict = {}

    def analyze_article(self, article: dict) -> dict:
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
            print(f"    [Analyzer] Gemini analysis failed: {exc}")
            article["relevance_score"] = 5
            article["summary"] = "Gemini 分析失敗。"
        return article

    def analyze_all(self, search_results: list[dict]) -> tuple[list[dict], list[dict]]:
        for result in search_results:
            analyzed: list[dict] = []
            for art in result["articles"]:
                print(f"    [Analyzer] analyzing: {art.get('title', '')[:50]}")
                analyzed.append(self.analyze_article(art))
            result["articles"] = analyzed

        all_articles = [
            (art, result["keyword"], result.get("used_level"))
            for result in search_results
            for art in result["articles"]
        ]
        all_articles.sort(
            key=lambda x: (
                x[0].get("relevance_score", 0),
                self._level_priority(x[2]),
            ),
            reverse=True,
        )
        ranked_all_articles = list(all_articles)
        title_deduped_urls = self._deduplicate_by_title([a for a, _, _ in all_articles])
        print(f"[Analyzer] title dedup: {len(all_articles)} -> {len(title_deduped_urls)}")

        all_articles, duplicate_removed_articles = self._deduplicate_ranked_articles(
            ranked_all_articles,
            title_deduped_urls,
        )

        backup_urls = {a["url"] for a, _, _ in all_articles[: TOP_N_ARTICLES * 2]}
        print(f"[Analyzer] backup pool: {len(backup_urls)}")

        def _enrich(art: dict, kw: dict, used_level: str | None) -> dict:
            enriched = dict(art)
            enriched["tier1"] = kw["tier1"].split(",")[0].strip()
            label_parts = [kw["tier2"]] if kw.get("tier2") else []
            if kw.get("tier3"):
                label_parts.append(kw["tier3"])
            enriched["keyword_label"] = " / ".join(label_parts)
            enriched["used_level"] = used_level
            return enriched

        eligible_articles = [
            (art, kw, used_level)
            for art, kw, used_level in all_articles
            if art.get("relevance_score", 0) >= MIN_TOP_SCORE
        ]

        top_articles: list[dict] = []
        remaining_eligible: list[tuple[dict, dict, str | None]] = []
        selection_stage_by_url: dict[str, str] = {}
        selection_reason_by_url: dict[str, str] = {}
        phase1_selected_tier1: set[str] = set()
        selected_tier1_counts: dict[str, int] = {}

        # Phase 1: one best article per tier1 from >= 7 score pool.
        for art, kw, used_level in eligible_articles:
            tier1 = kw["tier1"].split(",")[0].strip()
            if tier1 not in phase1_selected_tier1:
                phase1_selected_tier1.add(tier1)
                selected_tier1_counts[tier1] = 1
                top_articles.append(_enrich(art, kw, used_level))
                selection_stage_by_url[art["url"]] = "phase1_tier1_pick"
                selection_reason_by_url[art["url"]] = "highest_score_then_level_priority_in_tier1"
                if len(top_articles) >= TOP_N_ARTICLES:
                    break
            else:
                remaining_eligible.append((art, kw, used_level))

        # Phase 2: fill remaining slots from >= 7 score pool with the same order.
        # If only tier1-level match is left, keep at most one article per tier1.
        if len(top_articles) < TOP_N_ARTICLES:
            top_urls_set = {a["url"] for a in top_articles}
            for art, kw, used_level in remaining_eligible:
                tier1 = kw["tier1"].split(",")[0].strip()
                if art["url"] in top_urls_set:
                    continue
                if used_level == "tier1" and selected_tier1_counts.get(tier1, 0) >= 1:
                    continue

                top_articles.append(_enrich(art, kw, used_level))
                top_urls_set.add(art["url"])
                selected_tier1_counts[tier1] = selected_tier1_counts.get(tier1, 0) + 1
                selection_stage_by_url[art["url"]] = "phase2_fillup"
                if used_level == "tier1+tier2+tier3":
                    selection_reason_by_url[art["url"]] = "filled_remaining_slots_by_score_then_tier123_priority"
                elif used_level == "tier1+tier2":
                    selection_reason_by_url[art["url"]] = "filled_remaining_slots_by_score_then_tier12_priority"
                else:
                    selection_reason_by_url[art["url"]] = "filled_remaining_slots_by_score_tier1_once_per_tier1"
                if len(top_articles) >= TOP_N_ARTICLES:
                    break

        top_urls = {a["url"] for a in top_articles}
        print(f"[Analyzer] final top {TOP_N_ARTICLES}: {len(top_articles)}")

        for result in search_results:
            result["backup_articles"] = [a for a in result["articles"] if a["url"] in backup_urls]
            result["articles"] = [a for a in result["articles"] if a["url"] in top_urls]
            if not result["articles"] and result["used_level"] is not None:
                result["used_level"] = None

        sorted_articles_debug: list[dict] = []
        eligible_urls = {art["url"] for art, _, _ in eligible_articles}
        for rank, (art, kw, used_level) in enumerate(all_articles, 1):
            tier1 = kw["tier1"].split(",")[0].strip()
            if art["url"] in selection_stage_by_url:
                selection_stage = selection_stage_by_url[art["url"]]
                selection_reason = selection_reason_by_url[art["url"]]
            elif art["url"] not in eligible_urls:
                selection_stage = "not_selected"
                selection_reason = "below_threshold"
            elif used_level == "tier1" and selected_tier1_counts.get(tier1, 0) >= 1:
                selection_stage = "not_selected"
                selection_reason = "tier1_level_limited_to_one_article_per_tier1"
            elif tier1 in phase1_selected_tier1:
                selection_stage = "not_selected"
                selection_reason = "tier1_already_has_higher_ranked_article"
            else:
                selection_stage = "not_selected"
                selection_reason = "top_n_reached_after_score_and_level_sort"

            sorted_articles_debug.append(
                {
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "published_date": art.get("published_date"),
                    "resolved_date_utc": art.get("resolved_date"),
                    "date_source": art.get("date_source", "unknown"),
                    "date_confidence": art.get("date_confidence", "low"),
                    "date_warning": art.get("date_warning"),
                    "relevance_score": art.get("relevance_score", 0),
                    "summary": art.get("summary", ""),
                    "source_domain": art.get("source_domain", ""),
                    "tier1": tier1,
                    "tier2": kw.get("tier2", ""),
                    "tier3": kw.get("tier3", ""),
                    "keyword_label": " / ".join(
                        part for part in [kw.get("tier2", ""), kw.get("tier3", "")] if part
                    ),
                    "used_level": used_level,
                    "level_priority": self._level_priority(used_level),
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
                    "date_confidence": art.get("date_confidence", "low"),
                    "date_warning": art.get("date_warning"),
                    "relevance_score": art.get("relevance_score", 0),
                    "summary": art.get("summary", ""),
                    "source_domain": art.get("source_domain", ""),
                    "tier1": kw["tier1"].split(",")[0].strip(),
                    "tier2": kw.get("tier2", ""),
                    "tier3": kw.get("tier3", ""),
                    "keyword_label": " / ".join(
                        part for part in [kw.get("tier2", ""), kw.get("tier3", "")] if part
                    ),
                    "used_level": used_level,
                    "level_priority": self._level_priority(used_level),
                    "sort_basis": "score_desc",
                    "rank_before_dedup": rank,
                    "selection_stage": "removed_before_selection",
                    "selection_reason": removal_reason,
                }
                for rank, art, kw, used_level, removal_reason in duplicate_removed_articles
            ],
            "deduped_urls": sorted({art["url"] for art, _, _ in all_articles}),
            "backup_urls": sorted(backup_urls),
            "final_top_urls": sorted(top_urls),
            "final_top_articles": top_articles,
            "min_top_score": MIN_TOP_SCORE,
        }

        return search_results, top_articles

    def _deduplicate_ranked_articles(
        self,
        ranked_articles: list[tuple[dict, dict, str | None]],
        title_deduped_urls: set[str],
    ) -> tuple[list[tuple[dict, dict, str | None]], list[tuple[int, dict, dict, str | None, str]]]:
        deduped_articles: list[tuple[dict, dict, str | None]] = []
        removed_articles: list[tuple[int, dict, dict, str | None, str]] = []
        seen_urls: set[str] = set()

        for rank, (art, kw, used_level) in enumerate(ranked_articles, 1):
            url = art["url"]
            if url not in title_deduped_urls:
                removed_articles.append((rank, art, kw, used_level, "duplicate_title_removed"))
                continue
            if url in seen_urls:
                removed_articles.append((rank, art, kw, used_level, "duplicate_url_removed"))
                continue

            seen_urls.add(url)
            deduped_articles.append((art, kw, used_level))

        return deduped_articles, removed_articles

    def _level_priority(self, used_level: str | None) -> int:
        priorities = {
            "tier1+tier2+tier3": 3,
            "tier1+tier2": 2,
            "tier1": 1,
            None: 0,
        }
        return priorities.get(used_level, 0)

    def _deduplicate_by_title(self, articles: list[dict]) -> set[str]:
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
