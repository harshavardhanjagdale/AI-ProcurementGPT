"""
Async IMAP client for reading supplier email replies.
Monitors inbox for RFQ-tagged emails and extracts attachments.
"""
import email
import imaplib
import logging
import os
import re
from datetime import datetime, timezone
from email.header import decode_header
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

RFQ_PATTERN = re.compile(r"(RFQ-\d{4}-\d{5})")


class IMAPClient:
    def __init__(self):
        self.host = settings.IMAP_HOST
        self.port = settings.IMAP_PORT
        self.username = settings.IMAP_USER
        self.password = settings.IMAP_PASSWORD
        self.upload_dir = Path(settings.UPLOAD_DIR) / "email_attachments"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Create IMAP connection (synchronous, run in executor)."""
        mail = imaplib.IMAP4_SSL(self.host, self.port)
        mail.login(self.username, self.password)
        return mail

    def _decode_header_value(self, value: str) -> str:
        """Decode email header value handling various encodings."""
        if value is None:
            return ""
        decoded_parts = decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)

    def _extract_rfq_number(self, subject: str) -> str | None:
        """Extract RFQ number from email subject line."""
        match = RFQ_PATTERN.search(subject)
        return match.group(1) if match else None

    def _save_attachment(self, part, email_uid: str) -> dict | None:
        """Save email attachment to disk and return metadata."""
        filename = part.get_filename()
        if filename is None:
            return None

        filename = self._decode_header_value(filename)
        safe_filename = f"{email_uid}_{filename}"
        file_path = self.upload_dir / safe_filename

        with open(file_path, "wb") as f:
            f.write(part.get_payload(decode=True))

        file_size = os.path.getsize(file_path)
        file_ext = Path(filename).suffix.lower().lstrip(".")

        return {
            "file_name": filename,
            "file_path": str(file_path),
            "file_type": file_ext,
            "file_size_bytes": file_size,
        }

    def read_unread_emails(self, folder: str = "INBOX", limit: int = 50) -> list[dict]:
        """
        Read unread emails from the inbox.
        Returns list of parsed email dicts with attachments saved to disk.
        """
        try:
            mail = self._connect()
            mail.select(folder)

            _, message_numbers = mail.search(None, "UNSEEN")
            email_ids = message_numbers[0].split()

            if not email_ids:
                mail.logout()
                return []

            emails = []
            for uid in email_ids[-limit:]:
                uid_str = uid.decode()
                _, msg_data = mail.fetch(uid, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = self._decode_header_value(msg.get("Subject", ""))
                from_address = self._decode_header_value(msg.get("From", ""))
                to_address = self._decode_header_value(msg.get("To", ""))
                message_id = msg.get("Message-ID", "")
                in_reply_to = msg.get("In-Reply-To", "")
                date_str = msg.get("Date", "")

                # Extract from email address
                from_match = re.search(r"<(.+?)>", from_address)
                from_email = from_match.group(1) if from_match else from_address

                rfq_number = self._extract_rfq_number(subject)

                body_text = ""
                body_html = ""
                attachments = []

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition", ""))

                        has_filename = part.get_filename() is not None
                        is_explicit_attachment = "attachment" in content_disposition

                        if is_explicit_attachment or (has_filename and content_type not in ("text/plain", "text/html")):
                            attachment = self._save_attachment(part, uid_str)
                            if attachment:
                                attachments.append(attachment)
                        elif content_type == "text/plain" and not has_filename:
                            payload = part.get_payload(decode=True)
                            if payload:
                                body_text = payload.decode("utf-8", errors="replace")
                        elif content_type == "text/html" and not has_filename:
                            payload = part.get_payload(decode=True)
                            if payload:
                                body_html = payload.decode("utf-8", errors="replace")
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode("utf-8", errors="replace")

                emails.append({
                    "uid": uid_str,
                    "message_id": message_id,
                    "in_reply_to": in_reply_to,
                    "from_address": from_email,
                    "to_address": to_address,
                    "subject": subject,
                    "body": body_text or body_html,
                    "rfq_number": rfq_number,
                    "attachments": attachments,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                })

            mail.logout()
            logger.info(f"Read {len(emails)} unread emails from {folder}")
            return emails

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error reading emails: {e}")
            return []

    def read_emails_by_subject(self, subject_search: str, folder: str = "INBOX") -> list[dict]:
        """Search for emails matching a subject pattern."""
        try:
            mail = self._connect()
            mail.select(folder)

            _, message_numbers = mail.search(None, f'SUBJECT "{subject_search}"')
            email_ids = message_numbers[0].split()

            if not email_ids:
                mail.logout()
                return []

            emails = []
            for uid in email_ids:
                uid_str = uid.decode()
                _, msg_data = mail.fetch(uid, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = self._decode_header_value(msg.get("Subject", ""))
                from_address = self._decode_header_value(msg.get("From", ""))
                from_match = re.search(r"<(.+?)>", from_address)
                from_email = from_match.group(1) if from_match else from_address

                body_text = ""
                attachments = []

                if msg.is_multipart():
                    for part in msg.walk():
                        content_disposition = str(part.get("Content-Disposition", ""))
                        if "attachment" in content_disposition:
                            attachment = self._save_attachment(part, uid_str)
                            if attachment:
                                attachments.append(attachment)
                        elif part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if payload:
                                body_text = payload.decode("utf-8", errors="replace")
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode("utf-8", errors="replace")

                emails.append({
                    "uid": uid_str,
                    "from_address": from_email,
                    "subject": subject,
                    "body": body_text,
                    "rfq_number": self._extract_rfq_number(subject),
                    "attachments": attachments,
                })

            mail.logout()
            return emails

        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            return []


imap_client = IMAPClient()
