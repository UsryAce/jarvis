"""Email skill for Jarvis - send/receive/read via IMAP/SMTP."""
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
EMAIL_DB = DATA_DIR / "email_accounts.json"


class EmailSkill(Skill):
    name = "email"
    description = "Send, read, and manage emails via IMAP/SMTP"
    triggers = ["email", "mail", "send email", "inbox", "compose"]

    def __init__(self, jarvis=None):
        super().__init__(jarvis)
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        action = params.get("action", self._detect_action(text))

        if action == "send":
            to = params.get("to", "")
            subject = params.get("subject", "")
            body = params.get("body", "")
            return await self._send_email(to, subject, body)
        elif action == "read":
            folder = params.get("folder", "INBOX")
            limit = params.get("limit", 5)
            return await self._read_emails(folder, limit)
        elif action in ("list", "inbox"):
            return await self._read_emails("INBOX", 5)
        else:
            return "Email actions: send, read, list. Example: send email to user@example.com"

    def _detect_action(self, text: str) -> str:
        if any(w in text for w in ["send", "compose", "write to"]):
            return "send"
        if any(w in text for w in ["read", "inbox", "check"]):
            return "read"
        if any(w in text for w in ["list", "show"]):
            return "list"
        return "inbox"

    async def _send_email(self, to: str, subject: str, body: str) -> str:
        if not to or not subject:
            return "Missing required fields: to, subject. Usage: send email to user@example.com subject Hello body Message"

        import smtplib
        from email.mime.text import MIMEText

        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        smtp_user = os.environ.get("SMTP_USER", "")
        smtp_pass = os.environ.get("SMTP_PASS", "")

        if not smtp_user or not smtp_pass:
            return "SMTP credentials not configured. Set SMTP_USER and SMTP_PASS environment variables."

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["To"] = to
        msg["From"] = smtp_user

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            return f"Email sent to {to}: {subject}"
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return f"Failed to send email: {e}"

    async def _read_emails(self, folder: str = "INBOX", limit: int = 5) -> str:
        import imaplib
        import email as email_lib

        imap_server = os.environ.get("IMAP_SERVER", "imap.gmail.com")
        imap_user = os.environ.get("IMAP_USER", "")
        imap_pass = os.environ.get("IMAP_PASS", "")

        if not imap_user or not imap_pass:
            return "IMAP credentials not configured. Set IMAP_USER and IMAP_PASS environment variables."

        try:
            mail = imaplib.IMAP4_SSL(imap_server)
            mail.login(imap_user, imap_pass)
            mail.select(folder)

            status, messages = mail.search(None, "ALL")
            if status != "OK" or not messages[0]:
                return "No emails found."

            ids = messages[0].split()[-limit:]
            ids = ids if ids else messages[0].split()

            results = []
            for mid in reversed(ids):
                status, data = mail.fetch(mid, "(RFC822)")
                if status != "OK":
                    continue
                msg = email_lib.message_from_bytes(data[0][1])
                subject = msg["subject"] or "(no subject)"
                sender = msg["from"] or "(unknown)"
                date = msg["date"] or ""
                results.append(f"From: {sender} | Subject: {subject} | Date: {date}")

            mail.logout()
            if not results:
                return f"No emails in {folder}."
            return f"Inbox ({folder}) - last {len(results)}:\n\n" + "\n\n".join(reversed(results))
        except Exception as e:
            logger.error(f"Failed to read emails: {e}")
            return f"Failed to read emails: {e}"
