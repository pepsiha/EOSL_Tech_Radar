"""
EOSL Tech Radar main entrypoint.

Default GitHub Actions behavior should run in draft mode:
- generate reports and debug artifacts
- do not send email unless AUTO_SEND_EMAIL=true
"""

import json
import os
import re
import sys
from datetime import date

from config import settings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv as _load_dotenv

_load_dotenv()
if os.getenv("DISABLE_SSL_VERIFY", "").lower() == "true":
    import ssl

    import requests
    import urllib3

    ssl._create_default_https_context = ssl._create_unverified_context
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    _orig_request = requests.Session.request

    def _no_verify_request(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        return _orig_request(self, *args, **kwargs)

    requests.Session.request = _no_verify_request
    print("[SSL] SSL verification disabled.")


def main() -> None:
    today = date.today()
    date_str = today.strftime("%Y-%m-%d")
    selected_urls = _parse_selected_urls(os.getenv("SELECTED_URLS", ""))
    publish_mode = settings.AUTO_SEND_EMAIL and bool(selected_urls)

    print("=" * 60)
    print(f"[Start] EOSL Tech Radar run: {date_str}")
    print("=" * 60)
    print(
        f"[Config] search_mode={settings.SEARCH_MODE} "
        f"auto_send_email={settings.AUTO_SEND_EMAIL} "
        f"publish_mode={publish_mode}"
    )

    print("\n[Sheets] Loading Google Sheets data...")
    from src.sheets_loader import SheetsLoader

    loader = SheetsLoader()
    keywords = loader.get_keywords()
    members = loader.get_members()
    domains = loader.get_sources()

    print(f"[Sheets] keywords={len(keywords)} members={len(members)} domains={len(domains)}")

    if not publish_mode and not keywords:
        print("[Exit] No keywords found.")
        return

    from src.reporter import Reporter

    reporter = Reporter()

    if publish_mode:
        print("\n[Publish] Loading saved review candidates from latest draft...")
        draft_date, candidate_articles = _load_review_candidates()
        if not candidate_articles:
            print("[Publish] No saved review candidates found. Aborting publish run.")
            return

        top_articles = _select_candidate_articles(candidate_articles, selected_urls)
        _validate_selected_urls_or_raise(selected_urls, top_articles)

        print(f"[Publish] matched_selected_articles={len(top_articles)} from draft_date={draft_date}")

        html_content = reporter.generate_html(top_articles, draft_date)
        report_path = reporter.save_report(html_content, draft_date)
        index_path = reporter.update_index(draft_date)
        print(f"[Report] report saved: {report_path}")
        print(f"[Report] index updated: {index_path}")

        _update_reports_json()

        debug_path = _write_debug_report(
            date_str=draft_date.strftime("%Y-%m-%d"),
            keywords=keywords,
            domains=domains,
            search_debug=[],
            analyzer_debug={
                "mode": "publish_from_saved_review_candidates",
                "candidate_count": len(candidate_articles),
                "selected_url_count": len(selected_urls),
            },
            top_articles=top_articles,
        )
        print(f"[Debug] publish debug saved: {debug_path}")

        if not members:
            print("\n[Email] No members found. Skipping email send.")
        else:
            print(f"\n[Email] Sending report to {len(members)} recipients...")
            from src.emailer import Emailer

            emailer = Emailer()
            emailer.send_report(members, html_content, draft_date)
            print("[Email] Send complete.")

        print("\n" + "=" * 60)
        print("[Done] EOSL Tech Radar publish finished.")
        print("=" * 60)
        return

    print("\n[Search] Running Tavily search...")
    from src.searcher import Searcher

    searcher = Searcher()
    search_results = searcher.search_all(keywords, domains)
    total_articles = sum(len(r["articles"]) for r in search_results)
    print(f"[Search] selected_articles={total_articles}")

    raw_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"{date_str}_raw.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(search_results, f, ensure_ascii=False, indent=2)
    print(f"[Search] raw saved: {raw_path}")

    print("\n[Analyze] Running Gemini analysis...")
    from src.analyzer import Analyzer

    analyzer = Analyzer()
    _, top_articles = analyzer.analyze_all(search_results)
    print(f"[Analyze] top_articles={len(top_articles)}")
    candidate_articles = analyzer.debug_info.get("sorted_articles", [])

    print("\n[Report] Generating HTML report...")
    html_content = reporter.generate_html(top_articles, today)
    report_path = reporter.save_report(html_content, today)
    index_path = reporter.update_index(today)
    review_html = reporter.generate_review_html(candidate_articles, today)
    review_html_path, review_json_path = reporter.save_review_assets(review_html, candidate_articles, today)
    print(f"[Report] report saved: {report_path}")
    print(f"[Report] index updated: {index_path}")
    print(f"[Review] review page saved: {review_html_path}")
    print(f"[Review] review candidates saved: {review_json_path}")

    _update_reports_json()

    debug_path = _write_debug_report(
        date_str=date_str,
        keywords=keywords,
        domains=domains,
        search_debug=searcher.debug_info,
        analyzer_debug=analyzer.debug_info,
        top_articles=top_articles,
    )
    print(f"[Debug] debug saved: {debug_path}")

    if not settings.AUTO_SEND_EMAIL:
        print("\n[Email] Draft mode enabled. Skipping email send.")
    elif not selected_urls:
        print("\n[Email] Publish mode requires SELECTED_URLS. Skipping email send.")
    elif not members:
        print("\n[Email] No members found. Skipping email send.")
    else:
        print(f"\n[Email] Sending report to {len(members)} recipients...")
        from src.emailer import Emailer

        emailer = Emailer()
        emailer.send_report(members, html_content, today)
        print("[Email] Send complete.")

    print("\n" + "=" * 60)
    print("[Done] EOSL Tech Radar finished.")
    print("=" * 60)


def _parse_selected_urls(raw: str) -> list[str]:
    if not raw.strip():
        return []
    urls: list[str] = []
    normalized = re.sub(r"[,\s;]+", "\n", raw.strip())
    for line in normalized.splitlines():
        value = line.strip()
        if value:
            urls.append(value)
    return urls


def _select_candidate_articles(candidate_articles: list[dict], selected_urls: list[str]) -> list[dict]:
    selected_set = set(selected_urls)
    selected_articles: list[dict] = []
    seen_urls: set[str] = set()
    for article in candidate_articles:
        url = article.get("url", "")
        if url in selected_set and url not in seen_urls:
            selected_articles.append(
                {
                    "title": article.get("title", ""),
                    "url": url,
                    "published_date": article.get("published_date", ""),
                    "source_domain": article.get("source_domain", ""),
                    "resolved_date": article.get("resolved_date_utc"),
                    "date_source": article.get("date_source", "unknown"),
                    "date_confidence": article.get("date_confidence", "low"),
                    "date_warning": article.get("date_warning"),
                    "relevance_score": article.get("relevance_score", 0),
                    "summary": article.get("summary", ""),
                    "tier1": article.get("tier1", ""),
                    "keyword_label": article.get("keyword_label", ""),
                    "used_level": article.get("used_level"),
                }
            )
            seen_urls.add(url)
    return selected_articles


def _validate_selected_urls_or_raise(selected_urls: list[str], selected_articles: list[dict]) -> None:
    if not selected_urls:
        raise RuntimeError("Publish mode requires at least one selected URL.")
    if not selected_articles:
        raise RuntimeError(
            "None of the selected URLs matched the saved review candidates. "
            "Please regenerate the URL list from the latest review.html and try again."
        )


def _load_review_candidates() -> tuple[date, list[dict]]:
    review_json_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "docs",
        "review_candidates.json",
    )
    if not os.path.exists(review_json_path):
        return date.today(), []

    with open(review_json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    draft_date_raw = payload.get("date") or date.today().strftime("%Y-%m-%d")
    try:
        draft_date = date.fromisoformat(draft_date_raw)
    except ValueError:
        draft_date = date.today()

    return draft_date, payload.get("candidates", [])


def _write_debug_report(
    date_str: str,
    keywords: list[dict],
    domains: list[str],
    search_debug: list[dict],
    analyzer_debug: dict,
    top_articles: list[dict],
) -> str:
    debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "debug")
    os.makedirs(debug_dir, exist_ok=True)
    debug_path = os.path.join(debug_dir, f"{date_str}_debug.json")
    payload = {
        "date": date_str,
        "days_range": settings.DAYS_RANGE,
        "auto_send_email": settings.AUTO_SEND_EMAIL,
        "keywords_count": len(keywords),
        "domains": domains,
        "search": search_debug,
        "analyzer": analyzer_debug,
        "top_articles": top_articles,
    }
    with open(debug_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return debug_path


def _update_reports_json() -> None:
    import glob as _glob

    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    pattern = os.path.join(docs_dir, "????-??-??_report.html")
    files = sorted([os.path.basename(p) for p in _glob.glob(pattern)], reverse=True)
    reports_path = os.path.join(docs_dir, "reports.json")
    with open(reports_path, "w", encoding="utf-8") as f:
        json.dump({"reports": files}, f, ensure_ascii=False, indent=2)
    print(f"[Report] reports.json updated: {len(files)} reports")


if __name__ == "__main__":
    main()
