"""Comprehensive tests for email endpoints"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from app.models import Address, Email, EmailRecipient, Attachment


# Helper functions
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


def create_test_email(db_session, address, subject="Test Email", from_addr="sender@example.com",
                     body_plain="Test body", body_html="<p>Test body</p>", has_attachments=False):
    """Helper to create a test email"""
    email = Email(
        message_id=f"<test-{uuid4()}@example.com>",
        subject=subject,
        from_address=from_addr,
        to_address=address.email,
        raw_headers=f"From: {from_addr}\nSubject: {subject}\nTo: {address.email}",
        body_plain=body_plain,
        body_html=body_html,
        raw_message=b"Raw message data",
        size_bytes=len(body_plain),
        has_attachments=has_attachments
    )
    db_session.add(email)
    db_session.commit()
    db_session.refresh(email)

    # Link to address
    recipient = EmailRecipient(
        email_id=email.id,
        address_id=address.id,
        is_read=False
    )
    db_session.add(recipient)
    db_session.commit()

    return email


def create_test_attachment(db_session, email, filename="test.pdf", content_type="application/pdf",
                          data=b"fake pdf data"):
    """Helper to create a test attachment"""
    attachment = Attachment(
        email_id=email.id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        data=data
    )
    db_session.add(attachment)
    db_session.commit()
    db_session.refresh(attachment)
    return attachment


class TestEmailListing:
    """Test email listing endpoint"""

    def test_list_empty_inbox(self, client, db_session):
        """Test listing emails when none exist"""
        address = create_test_address(db_session)

        response = client.get(f"/api/v1/{address.token}/emails")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert len(data["emails"]) == 0
        assert data["page"] == 1
        assert data["has_next"] is False
        assert data["has_prev"] is False

    def test_list_emails_basic(self, client, db_session):
        """Test basic email listing"""
        address = create_test_address(db_session)

        # Create test emails
        for i in range(3):
            create_test_email(db_session, address, subject=f"Email {i+1}")

        response = client.get(f"/api/v1/{address.token}/emails")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 3
        assert len(data["emails"]) == 3

    def test_list_emails_structure(self, client, db_session):
        """Test email list response structure"""
        address = create_test_address(db_session)
        create_test_email(db_session, address, subject="Test", from_addr="test@example.com")

        response = client.get(f"/api/v1/{address.token}/emails")
        data = response.json()

        email = data["emails"][0]

        # Verify all expected fields present
        assert "id" in email
        assert "subject" in email
        assert "from_address" in email
        assert "to_address" in email
        assert "received_at" in email
        assert "is_read" in email
        assert "has_attachments" in email
        assert "size_bytes" in email

    def test_list_emails_ordering(self, client, db_session):
        """Test emails are ordered by received date (newest first)"""
        address = create_test_address(db_session)

        # Create emails with different timestamps
        email1 = create_test_email(db_session, address, subject="First")
        email2 = create_test_email(db_session, address, subject="Second")
        email3 = create_test_email(db_session, address, subject="Third")

        response = client.get(f"/api/v1/{address.token}/emails")
        data = response.json()

        # Should be in reverse chronological order (newest first)
        subjects = [e["subject"] for e in data["emails"]]
        assert subjects == ["Third", "Second", "First"]

    def test_list_emails_invalid_token(self, client):
        """Test listing with invalid token returns 404"""
        response = client.get("/api/v1/invalid_token_12345/emails")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_list_emails_expired_address(self, client, db_session):
        """Test listing emails with expired address token"""
        # Create expired address
        address = Address(
            email="expired@tempmail.example.com",
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(address)
        db_session.commit()

        response = client.get(f"/api/v1/{address.token}/emails")

        assert response.status_code == 404
        # Should return error (could be "expired" or "not found")
        assert response.json()["detail"]


class TestEmailPagination:
    """Test email pagination"""

    def test_pagination_first_page(self, client, db_session):
        """Test first page of results"""
        address = create_test_address(db_session)

        # Create 25 emails
        for i in range(25):
            create_test_email(db_session, address, subject=f"Email {i+1}")

        response = client.get(f"/api/v1/{address.token}/emails?page=1&per_page=10")
        data = response.json()

        assert data["total"] == 25
        assert len(data["emails"]) == 10
        assert data["page"] == 1
        assert data["per_page"] == 10
        assert data["has_next"] is True
        assert data["has_prev"] is False

    def test_pagination_middle_page(self, client, db_session):
        """Test middle page of results"""
        address = create_test_address(db_session)

        for i in range(25):
            create_test_email(db_session, address, subject=f"Email {i+1}")

        response = client.get(f"/api/v1/{address.token}/emails?page=2&per_page=10")
        data = response.json()

        assert len(data["emails"]) == 10
        assert data["page"] == 2
        assert data["has_next"] is True
        assert data["has_prev"] is True

    def test_pagination_last_page(self, client, db_session):
        """Test last page with partial results"""
        address = create_test_address(db_session)

        for i in range(25):
            create_test_email(db_session, address, subject=f"Email {i+1}")

        response = client.get(f"/api/v1/{address.token}/emails?page=3&per_page=10")
        data = response.json()

        assert len(data["emails"]) == 5  # Remaining emails
        assert data["has_next"] is False
        assert data["has_prev"] is True

    def test_pagination_invalid_page(self, client, db_session):
        """Test requesting invalid page number"""
        address = create_test_address(db_session)
        create_test_email(db_session, address)

        # Page 0 should be rejected
        response = client.get(f"/api/v1/{address.token}/emails?page=0")
        assert response.status_code == 422

    def test_pagination_per_page_limits(self, client, db_session):
        """Test per_page parameter limits"""
        address = create_test_address(db_session)
        for i in range(150):
            create_test_email(db_session, address)

        # Should enforce max per_page of 100
        response = client.get(f"/api/v1/{address.token}/emails?per_page=200")
        assert response.status_code == 422


class TestEmailFiltering:
    """Test email filtering options"""

    def test_filter_unread_only(self, client, db_session):
        """Test filtering to show only unread emails"""
        address = create_test_address(db_session)

        # Create 3 emails, mark 1 as read
        email1 = create_test_email(db_session, address, subject="Unread 1")
        email2 = create_test_email(db_session, address, subject="Read")
        email3 = create_test_email(db_session, address, subject="Unread 2")

        # Mark email2 as read
        recipient = db_session.query(EmailRecipient).filter(
            EmailRecipient.email_id == email2.id
        ).first()
        recipient.is_read = True
        db_session.commit()

        response = client.get(f"/api/v1/{address.token}/emails?unread_only=true")
        data = response.json()

        assert data["total"] == 2
        subjects = [e["subject"] for e in data["emails"]]
        assert "Read" not in subjects
        assert "Unread 1" in subjects
        assert "Unread 2" in subjects

    def test_search_by_subject(self, client, db_session):
        """Test searching emails by subject"""
        address = create_test_address(db_session)

        create_test_email(db_session, address, subject="Invoice #12345")
        create_test_email(db_session, address, subject="Meeting notes")
        create_test_email(db_session, address, subject="Invoice #67890")

        response = client.get(f"/api/v1/{address.token}/emails?search=invoice")
        data = response.json()

        assert data["total"] == 2
        subjects = [e["subject"] for e in data["emails"]]
        assert all("Invoice" in s for s in subjects)

    def test_search_by_sender(self, client, db_session):
        """Test searching emails by sender"""
        address = create_test_address(db_session)

        create_test_email(db_session, address, from_addr="alice@example.com")
        create_test_email(db_session, address, from_addr="bob@example.com")
        create_test_email(db_session, address, from_addr="alice@company.com")

        response = client.get(f"/api/v1/{address.token}/emails?search=alice")
        data = response.json()

        assert data["total"] == 2

    def test_search_case_insensitive(self, client, db_session):
        """Test search is case insensitive"""
        address = create_test_address(db_session)

        create_test_email(db_session, address, subject="URGENT Message")

        response = client.get(f"/api/v1/{address.token}/emails?search=urgent")
        data = response.json()

        assert data["total"] == 1

    def test_search_no_results(self, client, db_session):
        """Test search with no matching results"""
        address = create_test_address(db_session)
        create_test_email(db_session, address, subject="Test")

        response = client.get(f"/api/v1/{address.token}/emails?search=nonexistent")
        data = response.json()

        assert response.status_code == 200
        assert data["total"] == 0
        assert len(data["emails"]) == 0


class TestEmailDetail:
    """Test email detail endpoint"""

    def test_get_email_detail(self, client, db_session):
        """Test retrieving full email details"""
        address = create_test_address(db_session)
        email = create_test_email(
            db_session, address,
            subject="Test Subject",
            body_plain="Plain text body",
            body_html="<p>HTML body</p>"
        )

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(email.id)
        assert data["subject"] == "Test Subject"
        assert data["from_address"] == email.from_address
        assert data["to_address"] == email.to_address
        assert data["body_plain"] == "Plain text body"
        assert data["body_html"] == "<p>HTML body</p>"
        assert "raw_headers" in data

    def test_get_email_marks_read(self, client, db_session):
        """Test getting email automatically marks it as read"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address)

        # Verify initially unread
        recipient = db_session.query(EmailRecipient).filter(
            EmailRecipient.email_id == email.id
        ).first()
        assert recipient.is_read is False

        # Get email
        response = client.get(f"/api/v1/{address.token}/emails/{email.id}")
        assert response.status_code == 200

        # Verify marked as read
        db_session.refresh(recipient)
        assert recipient.is_read is True
        assert recipient.read_at is not None

    def test_get_email_without_mark_read(self, client, db_session):
        """Test getting email without marking as read"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address)

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}?mark_read=false")
        assert response.status_code == 200

        # Verify still unread
        recipient = db_session.query(EmailRecipient).filter(
            EmailRecipient.email_id == email.id
        ).first()
        assert recipient.is_read is False

    def test_get_email_not_found(self, client, db_session):
        """Test getting non-existent email"""
        address = create_test_address(db_session)
        fake_id = uuid4()

        response = client.get(f"/api/v1/{address.token}/emails/{fake_id}")

        assert response.status_code == 404

    def test_get_email_wrong_token(self, client, db_session):
        """Test accessing email with wrong token"""
        address1 = create_test_address(db_session, email="addr1@test.com", token="token1")
        address2 = create_test_address(db_session, email="addr2@test.com", token="token2")

        email = create_test_email(db_session, address1)

        # Try to access address1's email with address2's token
        response = client.get(f"/api/v1/{address2.token}/emails/{email.id}")

        assert response.status_code == 404


class TestEmailAttachments:
    """Test email attachment handling"""

    def test_email_with_attachments_flag(self, client, db_session):
        """Test email correctly shows has_attachments flag"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address, has_attachments=True)
        create_test_attachment(db_session, email)

        response = client.get(f"/api/v1/{address.token}/emails")
        data = response.json()

        assert data["emails"][0]["has_attachments"] is True

    def test_email_detail_includes_attachments(self, client, db_session):
        """Test email detail includes attachment list"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address, has_attachments=True)
        attachment = create_test_attachment(
            db_session, email,
            filename="document.pdf",
            content_type="application/pdf"
        )

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}")
        data = response.json()

        assert len(data["attachments"]) == 1
        att = data["attachments"][0]
        assert att["filename"] == "document.pdf"
        assert att["content_type"] == "application/pdf"
        assert att["size_bytes"] > 0

    def test_download_attachment(self, client, db_session):
        """Test downloading an attachment"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address, has_attachments=True)
        attachment_data = b"This is a test file content"
        attachment = create_test_attachment(
            db_session, email,
            filename="test.txt",
            content_type="text/plain",
            data=attachment_data
        )

        response = client.get(
            f"/api/v1/{address.token}/emails/{email.id}/attachments/{attachment.id}"
        )

        assert response.status_code == 200
        assert response.content == attachment_data
        assert "attachment" in response.headers["content-disposition"]

    def test_download_attachment_wrong_email(self, client, db_session):
        """Test downloading attachment from wrong email fails"""
        address = create_test_address(db_session)
        email1 = create_test_email(db_session, address, has_attachments=True)
        email2 = create_test_email(db_session, address, has_attachments=True)
        attachment = create_test_attachment(db_session, email1)

        # Try to access email1's attachment via email2
        response = client.get(
            f"/api/v1/{address.token}/emails/{email2.id}/attachments/{attachment.id}"
        )

        assert response.status_code == 404


class TestEmailDeletion:
    """Test email deletion"""

    def test_delete_email(self, client, db_session):
        """Test deleting an email"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address)

        response = client.delete(f"/api/v1/{address.token}/emails/{email.id}")

        assert response.status_code == 204

        # Verify deleted from database
        deleted = db_session.query(Email).filter(Email.id == email.id).first()
        assert deleted is None

    def test_delete_email_not_found(self, client, db_session):
        """Test deleting non-existent email"""
        address = create_test_address(db_session)
        fake_id = uuid4()

        response = client.delete(f"/api/v1/{address.token}/emails/{fake_id}")

        assert response.status_code == 404

    def test_delete_email_wrong_token(self, client, db_session):
        """Test deleting email with wrong token fails"""
        address1 = create_test_address(db_session, email="addr1@test.com", token="token1")
        address2 = create_test_address(db_session, email="addr2@test.com", token="token2")

        email = create_test_email(db_session, address1)

        # Try to delete address1's email with address2's token
        response = client.delete(f"/api/v1/{address2.token}/emails/{email.id}")

        assert response.status_code == 404

        # Verify email still exists
        still_exists = db_session.query(Email).filter(Email.id == email.id).first()
        assert still_exists is not None


class TestRawEmailDownload:
    """Test raw email download"""

    def test_download_raw_email(self, client, db_session):
        """Test downloading raw email message"""
        address = create_test_address(db_session)
        email = create_test_email(db_session, address)

        response = client.get(f"/api/v1/{address.token}/emails/{email.id}/raw")

        assert response.status_code == 200
        assert response.headers["content-type"] == "message/rfc822"
        assert "attachment" in response.headers["content-disposition"]
        assert f"{email.id}.eml" in response.headers["content-disposition"]

    def test_download_raw_email_not_found(self, client, db_session):
        """Test downloading non-existent raw email"""
        address = create_test_address(db_session)
        fake_id = uuid4()

        response = client.get(f"/api/v1/{address.token}/emails/{fake_id}/raw")

        assert response.status_code == 404


class TestEmailValidation:
    """Test email validation fields"""

    def test_email_with_validation_results(self, client, db_session):
        """Test email includes DKIM/SPF/DMARC results"""
        address = create_test_address(db_session)
        email = Email(
            message_id=f"<test-{uuid4()}@example.com>",
            subject="Test",
            from_address="sender@example.com",
            to_address=address.email,
            raw_headers="From: sender@example.com",
            body_plain="Test",
            body_html="<p>Test</p>",
            raw_message=b"Raw",
            size_bytes=100,
            has_attachments=False,
            dkim_valid=True,
            spf_result="pass",
            dmarc_result="pass"
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
        data = response.json()

        assert data["dkim_valid"] is True
        assert data["spf_result"] == "pass"
        assert data["dmarc_result"] == "pass"
