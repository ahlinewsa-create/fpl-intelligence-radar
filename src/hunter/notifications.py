"""Provider acceptance is not evidence that the user read the email."""
from __future__ import annotations
import os
import smtplib
from email.message import EmailMessage
import httpx

def send_report(html: str, date: str, manual: bool = False) -> str:
    channel = os.getenv("HUNTER_NOTIFY_CHANNEL", "email").strip().lower()
    if channel == "email":
        sender = os.environ["GMAIL_USER"]
        password = os.environ["GMAIL_PASS"]
        recipient = os.environ["TO_EMAIL"]
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = f"TaL3D | Global Hunter | {date}" + (" | تشغيل يدوي" if manual else "")
        msg.set_content("تقرير TaL3D العربي متاح داخل الرسالة." + (" هذه نسخة تشغيل يدوي جديدة." if manual else ""))
        msg.add_alternative(html, subtype="html")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        return "smtp_accepted"
    if channel == "telegram":
        token = os.environ["TELEGRAM_BOT_TOKEN"]
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": os.environ["TELEGRAM_CHAT_ID"],
                  "text": f"TaL3D Global Hunter - {date}: التقرير متاح في reports/"},
            timeout=20)
        response.raise_for_status()
        payload = response.json()
        if payload.get("ok") is not True:
            raise RuntimeError("Telegram did not accept the request")
        return str((payload.get("result") or {}).get("message_id", "accepted"))
    raise ValueError("Select email or telegram notification channel")
