import email.mime.application
import email.mime.multipart
import email.mime.text
from abc import ABC, abstractmethod


def build_mime_root(
    html_body: str,
    text_body: str | None,
    attachments: list[dict] | None,
) -> email.mime.multipart.MIMEMultipart:
    """Build the MIME tree for SES/SMTP raw senders.

    Without attachments the root is a bare ``multipart/alternative`` (unchanged
    from the historical behavior). With attachments the alternative part is
    nested inside a ``multipart/mixed`` root and the files are attached after it.
    Callers MUST set all headers (Subject/From/To/Reply-To/Message-ID/...) on the
    returned root part.
    """
    alt = email.mime.multipart.MIMEMultipart("alternative")
    if text_body:
        alt.attach(email.mime.text.MIMEText(text_body, "plain"))
    alt.attach(email.mime.text.MIMEText(html_body, "html"))

    if not attachments:
        return alt

    root = email.mime.multipart.MIMEMultipart("mixed")
    root.attach(alt)
    for att in attachments:
        part = email.mime.application.MIMEApplication(att["content_bytes"])
        part.set_type(att["content_type"])
        part.add_header(
            "Content-Disposition", "attachment", filename=att["filename"]
        )
        root.attach(part)
    return root


class EmailSender(ABC):
    @abstractmethod
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
        """Send an email and return the message ID.

        ``attachments`` is an optional list of dicts shaped as
        ``{"filename": str, "content_bytes": bytes, "content_type": str}``.
        """
        ...

    @abstractmethod
    async def verify_connection(self) -> bool:
        """Verify the sender connection is working."""
        ...
