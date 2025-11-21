"""Pydantic schemas for addresses"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
import re


class AddressCreate(BaseModel):
    """Schema for creating a new address (API request)"""
    username: Optional[str] = None  # If None, generates random username
    domain: Optional[str] = None    # If None, uses first configured domain

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        """Validate username format (basic checks only)"""
        if v is None:
            return v

        # Remove whitespace
        v = v.strip()

        # Check length
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if len(v) > 64:
            raise ValueError('Username must be at most 64 characters')

        # Check format: alphanumeric, dots, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('Username can only contain letters, numbers, dots, hyphens, and underscores')

        # Convert to lowercase
        v = v.lower()

        return v

    @field_validator('domain')
    @classmethod
    def validate_domain_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate domain format (basic check, not checking config)"""
        if v is None:
            return v

        v = v.strip().lower()

        # Basic domain format check
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$', v):
            raise ValueError('Invalid domain format')

        return v


class AddressResponse(BaseModel):
    """Schema for address API response"""
    id: UUID
    email: EmailStr
    token: str
    created_at: datetime
    expires_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2


class AddressInfo(BaseModel):
    """Detailed address information"""
    id: UUID
    email: EmailStr
    created_at: datetime
    expires_at: datetime
    email_count: int = 0  # Number of emails received
    is_expired: bool = False

    class Config:
        from_attributes = True


class DomainListResponse(BaseModel):
    """Response schema for listing available domains"""
    domains: List[str]
