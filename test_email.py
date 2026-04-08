"""
Email 發送測試腳本
執行方式：py test_email.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import resend
from config import settings

resend.api_key = settings.RESEND_API_KEY

print(f"RESEND_API_KEY: {settings.RESEND_API_KEY[:8]}...")

try:
    result = resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": ["pepsiha0717@gmail.com"],
        "subject": "EOSL Tech Radar — 測試信件",
        "html": "<p>這是測試信件，若收到表示 Resend 設定正確。</p>",
    })
    print(f"寄送成功！Email ID：{result}")
except Exception as e:
    print(f"寄送失敗：{e}")
