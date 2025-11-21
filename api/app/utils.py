"""Utility functions and helpers for address and email management"""

from fastapi import HTTPException
from sqlalchemy.orm import Session
import secrets
import random
import string

from app.config import settings
from app.models import Address


# ============================================================================
# Address Generation Utilities
# ============================================================================

def generate_random_email(domain: str = None) -> str:
    """
    Generate a random email address.

    Args:
        domain: Optional domain to use. If None, uses first from config.

    Returns:
        Random email address (8-char username)
    """
    # Generate 8-character random string (lowercase + numbers)
    chars = string.ascii_lowercase + string.digits
    local_part = ''.join(random.choice(chars) for _ in range(8))

    # Use provided domain or first domain from config
    if domain is None:
        if not settings.DOMAINS:
            raise ValueError("No domains configured")
        domain = settings.DOMAINS[0]

    return f"{local_part}@{domain}"


def generate_token() -> str:
    """
    Generate a secure random token for address access.

    Returns:
        64-character URL-safe token
    """
    return secrets.token_urlsafe(48)


# ============================================================================
# Address Validation
# ============================================================================

def validate_username(username: str) -> None:
    """
    Validate username against reserved names and config settings.

    Args:
        username: Username to validate (already validated by Pydantic schema)

    Raises:
        HTTPException: If username is reserved or custom usernames disabled
    """
    # Check if custom usernames are allowed
    if not settings.ALLOW_CUSTOM_USERNAMES:
        raise HTTPException(
            status_code=403,
            detail="Custom usernames are not allowed on this server"
        )

    # Check reserved usernames
    if username.lower() in [name.lower() for name in settings.RESERVED_USERNAMES]:
        raise HTTPException(
            status_code=400,
            detail=f"Username '{username}' is reserved and cannot be used"
        )


def validate_domain(domain: str) -> None:
    """
    Validate that domain is in the configured domains list.

    Args:
        domain: Domain to validate

    Raises:
        HTTPException: If domain is not configured on server
    """
    if not settings.DOMAINS:
        raise HTTPException(
            status_code=500,
            detail="No domains configured on server"
        )

    if domain not in settings.DOMAINS:
        raise HTTPException(
            status_code=400,
            detail=f"Domain '{domain}' is not available. Use GET /api/v1/domains to see available domains"
        )


# ============================================================================
# Authentication Utilities
# ============================================================================

def get_address_by_token(token: str, db: Session) -> Address:
    """
    Get address by token and verify not expired.

    Args:
        token: The access token
        db: Database session

    Returns:
        Address object

    Raises:
        HTTPException: If token invalid or expired
    """
    address = db.query(Address).filter(Address.token == token).first()

    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    if address.is_expired():
        raise HTTPException(status_code=404, detail="Address has expired")

    return address
