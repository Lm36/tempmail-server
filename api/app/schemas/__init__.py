"""Schemas package"""

from app.schemas.address import AddressCreate, AddressResponse, AddressInfo, DomainListResponse
from app.schemas.email import EmailSummary, EmailDetail, EmailListResponse, AttachmentInfo

__all__ = [
    "AddressCreate",
    "AddressResponse",
    "AddressInfo",
    "DomainListResponse",
    "EmailSummary",
    "EmailDetail",
    "EmailListResponse",
    "AttachmentInfo",
]
