import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Optional
from core.config import (
    GMAIL_USER,
    GMAIL_APP_PASSWORD,
    OUTLOOK_USER,
    OUTLOOK_APP_PASSWORD,
)


class EmailClient:
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password

    def get_unread_emails(self, limit: int = 5) -> List[Dict]:
        """Fetches recent unread emails."""
        emails = []
        try:
            mail = imaplib.IMAP4_SSL(self.host)
            mail.login(self.user, self.password)
            mail.select("inbox")

            status, messages = mail.search(None, "UNSEEN")
            if status != "OK":
                return []

            msg_ids = messages[0].split()
            for msg_id in msg_ids[-limit:]:
                res, msg_data = mail.fetch(msg_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding if encoding else "utf-8")

                        from_ = msg.get("From")
                        emails.append(
                            {"subject": subject, "from": from_, "date": msg.get("Date")}
                        )
            mail.logout()
        except Exception as e:
            print(f"Email fetch error ({self.host}): {e}")

        return emails


def get_gmail_client() -> Optional[EmailClient]:
    if GMAIL_USER and GMAIL_APP_PASSWORD:
        return EmailClient("imap.gmail.com", GMAIL_USER, GMAIL_APP_PASSWORD)
    return None


def get_outlook_client() -> Optional[EmailClient]:
    if OUTLOOK_USER and OUTLOOK_APP_PASSWORD:
        return EmailClient("outlook.office365.com", OUTLOOK_USER, OUTLOOK_APP_PASSWORD)
    return None
