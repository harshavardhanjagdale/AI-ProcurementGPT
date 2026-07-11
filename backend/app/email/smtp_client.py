"""
Async SMTP client for sending emails with optional attachments.
Uses aiosmtplib for non-blocking email delivery.
"""
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


class SMTPClient:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_name = settings.SMTP_FROM_NAME

    @property
    def from_address(self) -> str:
        return f"{self.from_name} <{self.username}>"

    async def send_email(
        self,
        to: str | list[str],
        subject: str,
        body_html: str,
        body_text: str | None = None,
        cc: list[str] | None = None,
        attachments: list[dict] | None = None,
    ) -> dict:
        """
        Send an email via SMTP.

        Args:
            to: Recipient email(s)
            subject: Email subject line
            body_html: HTML body content
            body_text: Plain text fallback (auto-generated if None)
            cc: CC recipients
            attachments: List of {"path": str, "filename": str} dicts

        Returns:
            dict with message_id and status
        """
        if isinstance(to, str):
            to = [to]

        msg = MIMEMultipart("mixed")
        msg["From"] = self.from_address
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)

        alt_part = MIMEMultipart("alternative")
        if body_text:
            alt_part.attach(MIMEText(body_text, "plain", "utf-8"))
        alt_part.attach(MIMEText(body_html, "html", "utf-8"))
        msg.attach(alt_part)

        if attachments:
            for attachment in attachments:
                file_path = Path(attachment["path"])
                if file_path.exists():
                    with open(file_path, "rb") as f:
                        part = MIMEApplication(f.read())
                    filename = attachment.get("filename", file_path.name)
                    part.add_header("Content-Disposition", "attachment", filename=filename)
                    msg.attach(part)
                else:
                    logger.warning(f"Attachment not found: {file_path}")

        all_recipients = to + (cc or [])

        try:
            use_tls = self.port == 465
            logger.info(f"Connecting to SMTP {self.host}:{self.port} (tls={use_tls}, starttls={not use_tls}) as {self.username}...")
            response = await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=use_tls,
                start_tls=not use_tls,
                timeout=30,
            )
            message_id = msg.get("Message-ID", "")
            logger.info(f"Email sent successfully to {all_recipients}, subject: {subject}")
            return {
                "success": True,
                "message_id": message_id,
                "recipients": all_recipients,
            }
        except aiosmtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP AUTH FAILED for {self.username}: {e}")
            return {
                "success": False,
                "error": f"Authentication failed: {e}",
                "recipients": all_recipients,
            }
        except aiosmtplib.SMTPException as e:
            logger.error(f"SMTP error sending to {all_recipients}: {e}")
            return {
                "success": False,
                "error": str(e),
                "recipients": all_recipients,
            }
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "recipients": all_recipients,
            }

    async def send_rfq_email(
        self,
        to: str,
        rfq_number: str,
        subject_suffix: str,
        body_html: str,
        attachments: list[dict] | None = None,
    ) -> dict:
        """Send an RFQ email with standardized subject tagging."""
        subject = f"{rfq_number} - {subject_suffix}"
        return await self.send_email(
            to=to,
            subject=subject,
            body_html=body_html,
            attachments=attachments,
        )


smtp_client = SMTPClient()
