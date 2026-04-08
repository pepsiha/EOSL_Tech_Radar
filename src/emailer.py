import smtplib
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from config import settings

_FROM_NAME = "工研院電光所技術情報週報"
_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587
_SUBJECT_TMPL = "【工研院電光所】國際技術情報週報 {start}~{end}"


class Emailer:
    def __init__(self) -> None:
        self._user = settings.GMAIL_USER
        self._password = settings.GMAIL_APP_PASSWORD

    def send_report(
        self,
        members: list[dict],
        html_content: str,
        report_date: date,
    ) -> None:
        """
        逐一對每位啟用成員發送週報 Email。
        members 格式：[{"name": str, "email": str}, ...]
        """
        week_end = report_date
        week_start = report_date - timedelta(days=6)
        subject = _SUBJECT_TMPL.format(
            start=week_start.strftime("%Y%m%d"),
            end=week_end.strftime("%Y%m%d"),
        )
        for member in members:
            email = member.get("email", "").strip()
            name = member.get("name", "").strip()
            if not email:
                print(f"  [Emailer] 跳過（無 Email）：{name}")
                continue
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = formataddr((_FROM_NAME, self._user))
                msg["To"] = email
                msg.attach(MIMEText(html_content, "html", "utf-8"))

                with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as smtp:
                    smtp.ehlo()
                    smtp.starttls()
                    smtp.login(self._user, self._password)
                    smtp.sendmail(self._user, [email], msg.as_string())

                print(f"  [Emailer] 已寄送給：{name} <{email}>")
            except Exception as exc:
                print(f"  [Emailer] 寄送失敗 {name} <{email}>：{exc}")
