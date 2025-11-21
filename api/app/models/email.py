"""Email models - emails, recipients, and attachments"""

from sqlalchemy import Column, String, Text, DateTime, BigInteger, Boolean, ForeignKey, LargeBinary
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.database import Base
from app.types import GUID


class Email(Base):
    __tablename__ = "emails"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    message_id = Column(String(255), index=True)
    subject = Column(Text)
    from_address = Column(String(255), nullable=False, index=True)
    to_address = Column(String(255), nullable=False, index=True)
    raw_headers = Column(Text, nullable=False)
    body_plain = Column(Text)
    body_html = Column(Text)
    raw_message = Column(LargeBinary, nullable=False)
    size_bytes = Column(BigInteger, nullable=False, default=0)

    # Validation results
    dkim_valid = Column(Boolean, nullable=True)  # nullable - true/false if checked, NULL if not
    spf_result = Column(String(20))  # pass, fail, softfail, neutral, none, temperror, permerror
    dmarc_result = Column(String(20))  # pass, fail, none

    has_attachments = Column(Boolean, default=False)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    email_recipients = relationship("EmailRecipient", back_populates="email", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="email", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Email {self.message_id}>"


class EmailRecipient(Base):
    __tablename__ = "email_recipients"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    email_id = Column(GUID, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    address_id = Column(GUID, ForeignKey("addresses.id", ondelete="CASCADE"), nullable=False, index=True)
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    email = relationship("Email", back_populates="email_recipients")
    address = relationship("Address", back_populates="email_recipients")

    def __repr__(self):
        return f"<EmailRecipient email={self.email_id} address={self.address_id}>"


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    email_id = Column(GUID, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False, index=True)
    content_type = Column(String(127), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    data = Column(LargeBinary, nullable=False)  # Binary data stored in database
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    email = relationship("Email", back_populates="attachments")

    def __repr__(self):
        return f"<Attachment {self.filename}>"
