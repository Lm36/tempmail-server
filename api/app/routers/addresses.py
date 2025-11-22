"""Address management endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import get_db
from app.models import Address
from app.schemas import AddressResponse, AddressCreate, DomainListResponse
from app.config import settings
from app.utils import (
    generate_random_email,
    generate_token,
    validate_username,
    validate_domain
)

router = APIRouter(prefix="/api/v1", tags=["addresses"])


@router.get("/domains", response_model=DomainListResponse)
def list_domains():
    """
    List available domains for email address creation.

    Returns:
        List of domain names configured on the server

    Example:
        GET /api/v1/domains
        Response: {
            "domains": ["tempmail.example.com", "mail.example.org"]
        }
    """
    return DomainListResponse(domains=settings.DOMAINS)


@router.post("/addresses", response_model=AddressResponse)
def create_address(request: AddressCreate = AddressCreate(), db: Session = Depends(get_db)):
    """
    Generate a new temporary email address.

    Supports both random generation and custom usernames.

    Args:
        username: Optional custom username (3-64 chars, alphanumeric + . _ -)
        domain: Optional domain selection (must be in configured domains)

    Returns:
        - email: The generated email address
        - token: Access token for viewing emails
        - expires_at: When this address will be deleted

    Examples:
        # Random generation
        POST /api/v1/addresses
        Response: {"email": "a8f3k9x2@example.com", ...}

        # Custom username
        POST /api/v1/addresses
        Body: {"username": "myemail"}
        Response: {"email": "myemail@example.com", ...}

        # Custom username and domain
        POST /api/v1/addresses
        Body: {"username": "myemail", "domain": "temp.example.com"}
        Response: {"email": "myemail@temp.example.com", ...}
    """
    # Determine domain to use
    domain = request.domain
    if domain is None:
        # Use first configured domain
        if not settings.DOMAINS:
            raise HTTPException(status_code=500, detail="No domains configured")
        domain = settings.DOMAINS[0]
    else:
        # Validate provided domain
        validate_domain(domain)

    # Determine username and construct email
    if request.username:
        # Custom username provided
        validate_username(request.username)
        email = f"{request.username}@{domain}"

        # Check if email already exists
        existing = db.query(Address).filter(Address.email == email).first()

        if existing:
            if existing.is_expired():
                # Email expired - delete it and create new one
                db.delete(existing)
                db.commit()
            else:
                # Email is active - not available
                raise HTTPException(
                    status_code=409,
                    detail=f"Email address '{email}' is already taken"
                )
    else:
        # Random generation
        max_attempts = 10
        for attempt in range(max_attempts):
            email = generate_random_email(domain)

            # Check if already exists
            existing = db.query(Address).filter(Address.email == email).first()
            if not existing:
                break

            if attempt == max_attempts - 1:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to generate unique email address"
                )

    # Generate token
    token = generate_token()

    # Calculate timestamps - use same base time to ensure accurate lifetime
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=settings.ADDRESS_LIFETIME_HOURS)

    # Create address
    address = Address(
        email=email,
        token=token,
        created_at=now,
        expires_at=expires_at
    )

    db.add(address)
    db.commit()
    db.refresh(address)

    return address
