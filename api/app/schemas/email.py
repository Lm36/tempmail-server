"""Pydantic schemas for emails"""

from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, List


class AttachmentInfo(BaseModel):
    """Attachment metadata"""
    id: UUID
    filename: str
    content_type: str
    size_bytes: int

    class Config:
        from_attributes = True


class EmailSummary(BaseModel):
    """Email summary for list view"""
    id: UUID
    subject: Optional[str]
    from_address: str
    to_address: str
    received_at: datetime
    is_read: bool
    has_attachments: bool
    size_bytes: int

    class Config:
        from_attributes = True


class EmailDetail(BaseModel):
    """Full email details"""
    id: UUID
    message_id: Optional[str]
    subject: Optional[str]
    from_address: str
    to_address: str
    raw_headers: str
    body_plain: Optional[str]
    body_html: Optional[str]
    size_bytes: int

    # Validation results
    dkim_valid: Optional[bool]
    spf_result: Optional[str]
    dmarc_result: Optional[str]

    has_attachments: bool
    received_at: datetime
    is_read: bool

    # Attachments list
    attachments: List[AttachmentInfo] = []

    class Config:
        from_attributes = True


class EmailListResponse(BaseModel):
    """Paginated email list response"""
    emails: List[EmailSummary]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool

    class Config:
        from_attributes = True
