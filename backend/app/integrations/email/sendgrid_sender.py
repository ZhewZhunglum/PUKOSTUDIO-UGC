import base64
import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Attachment,
    Disposition,
    FileContent,
    FileName,
    FileType,
    Mail,
    PlainTextContent,
)

from app.config import settings
from app.integrations.email.base import EmailSender

logger = logging.getLogger(__name__)


class SendGridSender(EmailSender):
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        api_key = cfg.get("api_key") or settings.sendgrid_api_key
        self.client = SendGridAPIClient(api_key=api_key)

    async def send(
        self,
        from_address: str,
        to_address: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        reply_to: str | None = None,
        headers: dict | None = None,
        attachments: list[dict] | None = None,
    ) -> str:
        message = Mail(
            from_email=from_address,
            to_emails=to_address,
            subject=subject,
            html_content=html_body,
        )

        if text_body:
            message.plain_text_content = PlainTextContent(text_body)

        if reply_to:
            message.reply_to = reply_to

        if headers:
            message.headers = headers

        for att in attachments or []:
            message.add_attachment(
                Attachment(
                    FileContent(base64.b64encode(att["content_bytes"]).decode()),
                    FileName(att["filename"]),
                    FileType(att["content_type"]),
                    Disposition("attachment"),
                )
            )

        try:
            response = self.client.send(message)
            message_id = response.headers.get("X-Message-Id", "")
            logger.info(f"SendGrid email sent: {message_id}, status: {response.status_code}")
            return message_id
        except Exception as e:
            logger.error(f"SendGrid send error: {e}")
            raise

    async def verify_connection(self) -> bool:
        try:
            self.client.client.user.account.get()
            return True
        except Exception:
            return False
