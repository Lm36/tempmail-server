"""Models package"""

from app.models.address import Address
from app.models.email import Email, EmailRecipient, Attachment

__all__ = ["Address", "Email", "EmailRecipient", "Attachment"]
