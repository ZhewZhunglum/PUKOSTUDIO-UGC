import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentResponse(BaseModel):
    """Public attachment metadata. Never exposes the on-disk storage_key."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size_bytes: int
    purpose: str
    created_at: datetime
