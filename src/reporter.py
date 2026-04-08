import os
from datetime import date

from jinja2 import Environment, FileSystemLoader

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
DOCS_DIR = os.path.join(BASE_DIR, "docs")


class Reporter:
    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIR),
            autoescape=True,
        )

    def generate_html(self, top_articles: list[dict], report_date: date) -> str:
        """使用 report.html.j2 模板生成週報 HTML 字串。"""
        from config import settings

        template = self._env.get_template("report.html.j2")
        html = template.render(
            report_date=report_date.strftime("%Y-%m-%d"),
            search_mode=settings.SEARCH_MODE,
            articles=top_articles,
        )
        return html

    def save_report(self, html_content: str, report_date: date) -> str:
        """儲存週報到 docs/YYYY-MM-DD_report.html，回傳檔案路徑。"""
        os.makedirs(DOCS_DIR, exist_ok=True)
        filename = f"{report_date.strftime('%Y-%m-%d')}_report.html"
        filepath = os.path.join(DOCS_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        return filepath

    def update_index(self, report_date: date) -> str:
        """
        更新 docs/index.html。
        index.html 透過 JavaScript 動態讀取同一 repo 的週報檔案，
        不需要在 Python 端維護清單。
        本方法只重新寫出最新日期的 index.html（以便讓 GitHub Actions commit）。
        """
        template = self._env.get_template("index.html.j2") if self._template_exists("index.html.j2") else None
        if template:
            html = template.render(latest_date=report_date.strftime("%Y-%m-%d"))
        else:
            # 直接讀取靜態 index.html（不需要重新生成）
            return os.path.join(DOCS_DIR, "index.html")

        filepath = os.path.join(DOCS_DIR, "index.html")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        return filepath

    def _template_exists(self, name: str) -> bool:
        return os.path.exists(os.path.join(TEMPLATES_DIR, name))
