"""Security and edge case tests"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.models import Address, Email, EmailRecipient, Attachment


def create_test_address(db_session, email="test@tempmail.example.com", token="test_token"):
    """Helper to create a test address"""
    address = Address(
        email=email,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db_session.add(address)
    db_session.commit()
    db_session.refresh(address)
    return address


def create_test_email(db_session, address):
    """Helper to create a test email"""
    email = Email(
        message_id=f"<test-{uuid4()}@example.com>",
        subject="Test",
        from_address="sender@example.com",
        to_address=address.email,
        raw_headers="From: sender@example.com",
        body_plain="Test body",
        body_html="<p>Test body</p>",
        raw_message=b"Raw message",
        size_bytes=100,
        has_attachments=False
    )
    db_session.add(email)
    db_session.commit()
    db_session.refresh(email)

    recipient = EmailRecipient(
        email_id=email.id,
        address_id=address.id,
        is_read=False
    )
    db_session.add(recipient)
    db_session.commit()

    return email


class TestTokenSecurity:
    """Test token-based security"""

    def test_cannot_access_other_address_emails(self, client, db_session):
        """Test users cannot access emails from other addresses"""
        address1 = create_test_address(db_session, email="addr1@test.com", token="token1")
        address2 = create_test_address(db_session, email="addr2@test.com", token="token2")

        email1 = create_test_email(db_session, address1)
        email2 = create_test_email(db_session, address2)

        # Address1 should not see address2's emails
        response = client.get(f"/api/v1/{address1.token}/emails")
        data = response.json()

        email_ids = [e["id"] for e in data["emails"]]
        assert str(email1.id) in email_ids
        assert str(email2.id) not in email_ids

    def test_cannot_access_email_detail_wrong_token(self, client, db_session):
        """Test cannot view email details with wrong token"""
        address1 = create_test_address(db_session, email="addr1@test.com", token="token1")
        address2 = create_test_address(db_session, email="addr2@test.com", token="token2")

        email = create_test_email(db_session, address1)

        # Try to access with wrong token
        response = client.get(f"/api/v1/{address2.token}/emails/{email.id}")

        assert response.status_code == 404

    def test_cannot_delete_email_wrong_token(self, client, db_session):
        """Test cannot delete email with wrong token"""
        address1 = create_test_address(db_session, email="addr1@test.com", token="token1")
        address2 = create_test_address(db_session, email="addr2@test.com", token="token2")

        email = create_test_email(db_session, address1)

        # Try to delete with wrong token
        response = client.delete(f"/api/v1/{address2.token}/emails/{email.id}")

        assert response.status_code == 404

        # Verify email still exists
        still_exists = db_session.query(Email).filter(Email.id == email.id).first()
        assert still_exists is not None

    def test_token_url_safe(self, client):
        """Test generated tokens are URL-safe"""
        response = client.post("/api/v1/addresses")
        data = response.json()

        token = data["token"]

        # Should only contain URL-safe characters
        allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
        assert all(c in allowed_chars for c in token)


class TestInputValidation:
    """Test input validation and sanitization"""

    def test_invalid_uuid_format(self, client, db_session):
        """Test invalid UUID format returns 422"""
        address = create_test_address(db_session)

        response = client.get(f"/api/v1/{address.token}/emails/not-a-uuid")

        assert response.status_code == 422

    def test_negative_page_number(self, client, db_session):
        """Test negative page number is rejected"""
        address = create_test_address(db_session)

        response = client.get(f"/api/v1/{address.token}/emails?page=-1")

        assert response.status_code == 422

    def test_zero_page_number(self, client, db_session):
        """Test zero page number is rejected"""
        address = create_test_address(db_session)

        response = client.get(f"/api/v1/{address.token}/emails?page=0")

        assert response.status_code == 422

    def test_excessive_per_page(self, client, db_session):
        """Test per_page exceeding max is rejected"""
        address = create_test_address(db_session)

        response = client.get(f"/api/v1/{address.token}/emails?per_page=1000")

        assert response.status_code == 422

    def test_sql_injection_in_search(self, client, db_session):
        """Test SQL injection attempts in search are safe"""
        address = create_test_address(db_session)
        create_test_email(db_session, address)

        # Try SQL injection
        response = client.get(f"/api/v1/{address.token}/emails?search=' OR '1'='1")

        # Should not cause error, just search for the literal string
        assert response.status_code == 200
        data = response.json()
        # Should find nothing
        assert data["total"] == 0

    def test_xss_in_search(self, client, db_session):
        """Test XSS attempts in search don't cause issues"""
        address = create_test_address(db_session)
        create_test_email(db_session, address)

        # Try XSS
        response = client.get(f"/api/v1/{address.token}/emails?search=<script>alert('xss')</script>")

        # Should handle safely
        assert response.status_code == 200


class TestAttachmentSecurity:
    """Test attachment security"""

    def test_attachment_filename_sanitization(self, client, db_session):
        """Test attachment filenames are sanitized"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address)

        # Create attachment with path traversal attempt
        attachment = Attachment(
            email_id=email.id,
            filename="../../../etc/passwd",
            content_type="text/plain",
            size_bytes=100,
            data=b"fake data"
        )
        db_session.add(attachment)
        db_session.commit()

        response = client.get(
            f"/api/v1/{address.token}/emails/{email.id}/attachments/{attachment.id}"
        )

        assert response.status_code == 200

        # Check filename is sanitized in header
        content_disp = response.headers["content-disposition"]
        assert "../" not in content_disp
        assert ".._" in content_disp or "_.._" in content_disp  # Slashes replaced

    def test_attachment_belongs_to_correct_email(self, client, db_session):
        """Test cannot access attachment through wrong email ID"""
        address = create_test_address(db_session)
        email1 = create_test_email(db_session, address)
        email2 = create_test_email(db_session, address)

        # Create attachment for email1
        attachment = Attachment(
            email_id=email1.id,
            filename="secret.pdf",
            content_type="application/pdf",
            size_bytes=100,
            data=b"secret data"
        )
        db_session.add(attachment)
        db_session.commit()

        # Try to access via email2
        response = client.get(
            f"/api/v1/{address.token}/emails/{email2.id}/attachments/{attachment.id}"
        )

        assert response.status_code == 404


class TestRateLimiting:
    """Test behavior under high load"""

    def test_create_many_addresses(self, client):
        """Test creating many addresses in succession"""
        for i in range(50):
            response = client.post("/api/v1/addresses")
            assert response.status_code == 200

    def test_list_large_number_of_emails(self, client, db_session):
        """Test listing when many emails exist"""
        address = create_test_address(db_session)

        # Create 200 emails
        for i in range(200):
            create_test_email(db_session, address)

        # Should handle pagination correctly
        response = client.get(f"/api/v1/{address.token}/emails?per_page=50")
        data = response.json()

        assert response.status_code == 200
        assert data["total"] == 200
        assert len(data["emails"]) == 50


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_subject(self, client, db_session):
        """Test email with empty subject"""
        address = create_test_address(db_session)

        email = Email(
            message_id=f"<test-{uuid4()}@example.com>",
            subject="",  # Empty subject
            from_address="sender@example.com",
            to_address=address.email,
            raw_headers="From: sender@example.com",
            body_plain="Test",
            body_html="<p>Test</p>",
            raw_message=b"Raw",
            size_bytes=100,
            has_attachments=False
        )
        db_session.add(email)
        db_session.commit()

        recipient = EmailRecipient(
            email_id=email.id,
            address_id=address.id,
            is_read=False
        )
        db_session.add(recipient)
        db_session.commit()

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}")

        assert response.status_code == 200
        assert response.json()["subject"] == ""

    def test_very_long_subject(self, client, db_session):
        """Test email with very long subject"""
        address = create_test_address(db_session)

        long_subject = "A" * 1000

        email = Email(
            message_id=f"<test-{uuid4()}@example.com>",
            subject=long_subject,
            from_address="sender@example.com",
            to_address=address.email,
            raw_headers="From: sender@example.com",
            body_plain="Test",
            body_html="<p>Test</p>",
            raw_message=b"Raw",
            size_bytes=100,
            has_attachments=False
        )
        db_session.add(email)
        db_session.commit()

        recipient = EmailRecipient(
            email_id=email.id,
            address_id=address.id,
            is_read=False
        )
        db_session.add(recipient)
        db_session.commit()

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}")

        assert response.status_code == 200
        assert response.json()["subject"] == long_subject

    def test_unicode_in_email(self, client, db_session):
        """Test email with unicode characters"""
        address = create_test_address(db_session)

        email = Email(
            message_id=f"<test-{uuid4()}@example.com>",
            subject="Test 你好 🎉",
            from_address="sender@example.com",
            to_address=address.email,
            raw_headers="From: sender@example.com",
            body_plain="Unicode test: 你好世界 🌍",
            body_html="<p>Unicode test: 你好世界 🌍</p>",
            raw_message=b"Raw",
            size_bytes=100,
            has_attachments=False
        )
        db_session.add(email)
        db_session.commit()

        recipient = EmailRecipient(
            email_id=email.id,
            address_id=address.id,
            is_read=False
        )
        db_session.add(recipient)
        db_session.commit()

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}")

        assert response.status_code == 200
        data = response.json()
        assert "你好" in data["subject"]
        assert "🎉" in data["subject"]
        assert "你好世界" in data["body_plain"]

    def test_email_without_html_body(self, client, db_session):
        """Test email with only plain text body"""
        address = create_test_address(db_session)

        email = Email(
            message_id=f"<test-{uuid4()}@example.com>",
            subject="Plain text only",
            from_address="sender@example.com",
            to_address=address.email,
            raw_headers="From: sender@example.com",
            body_plain="Plain text body",
            body_html=None,  # No HTML version
            raw_message=b"Raw",
            size_bytes=100,
            has_attachments=False
        )
        db_session.add(email)
        db_session.commit()

        recipient = EmailRecipient(
            email_id=email.id,
            address_id=address.id,
            is_read=False
        )
        db_session.add(recipient)
        db_session.commit()

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["body_plain"] == "Plain text body"
        assert data["body_html"] is None

    def test_multiple_attachments(self, client, db_session):
        """Test email with multiple attachments"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address)

        # Add multiple attachments
        for i in range(5):
            attachment = Attachment(
                email_id=email.id,
                filename=f"file{i}.txt",
                content_type="text/plain",
                size_bytes=100,
                data=b"data"
            )
            db_session.add(attachment)
        db_session.commit()

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}")
        data = response.json()

        assert len(data["attachments"]) == 5

    def test_page_beyond_available(self, client, db_session):
        """Test requesting page beyond available emails"""
        address = create_test_address(db_session)
        create_test_email(db_session, address)

        # Only 1 email, request page 100
        response = client.get(f"/api/v1/{address.token}/emails?page=100")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["emails"]) == 0
