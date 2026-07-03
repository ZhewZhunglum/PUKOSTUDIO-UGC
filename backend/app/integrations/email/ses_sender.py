import logging

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.integrations.email.base import EmailSender, build_mime_root

logger = logging.getLogger(__name__)


class SESSender(EmailSender):
    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.client = boto3.client(
            "ses",
            region_name=cfg.get("region") or settings.ses_region,
            aws_access_key_id=cfg.get("access_key_id") or settings.ses_access_key_id,
            aws_secret_access_key=cfg.get("secret_access_key") or settings.ses_secret_access_key,
        )

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
        msg = build_mime_root(html_body, text_body, attachments)
        msg["Subject"] = subject
        msg["From"] = from_address
        msg["To"] = to_address

        if reply_to:
            msg["Reply-To"] = reply_to

        if headers:
            for key, value in headers.items():
                msg[key] = value

        try:
            response = self.client.send_raw_email(
                Source=from_address,
                Destinations=[to_address],
                RawMessage={"Data": msg.as_string()},
            )
            message_id = response["MessageId"]
            logger.info(f"SES email sent: {message_id}")
            return message_id
        except ClientError as e:
            logger.error(f"SES send error: {e}")
            raise

    async def verify_connection(self) -> bool:
        try:
            self.client.get_account_sending_enabled()
            return True
        except Exception:
            return False
