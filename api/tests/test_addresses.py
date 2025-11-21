"""Comprehensive tests for address endpoints"""

import pytest
from datetime import datetime, timedelta
from app.models import Address


class TestAddressCreation:
    """Test address creation endpoint"""

    def test_create_address_success(self, client):
        """Test successful address creation"""
        response = client.post("/api/v1/addresses")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields present
        assert "id" in data
        assert "email" in data
        assert "token" in data
        assert "created_at" in data
        assert "expires_at" in data

    def test_create_address_email_format(self, client):
        """Test generated email has correct format"""
        response = client.post("/api/v1/addresses")
        data = response.json()

        email = data["email"]
        assert "@" in email

        local, domain = email.split("@")

        # Local part should be 8 characters
        assert len(local) == 8
        # Should be lowercase alphanumeric
        assert local.islower()
        assert local.isalnum()
        # Domain should be configured domain
        assert domain == "tempmail.example.com"

    def test_create_address_token_security(self, client):
        """Test token is sufficiently random and long"""
        response = client.post("/api/v1/addresses")
        data = response.json()

        token = data["token"]

        # Should be at least 32 characters for security
        assert len(token) >= 32
        # Should be URL-safe
        assert all(c.isalnum() or c in "-_" for c in token)

    def test_create_address_expiration(self, client):
        """Test address has correct expiration time"""
        response = client.post("/api/v1/addresses")
        data = response.json()

        created = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))

        # Should expire after created
        assert expires > created

        # Should be approximately 24 hours (with 1 minute tolerance)
        expected_lifetime = timedelta(hours=24)
        actual_lifetime = expires - created
        assert abs((actual_lifetime - expected_lifetime).total_seconds()) < 60

    def test_create_multiple_unique_addresses(self, client):
        """Test multiple addresses are all unique"""
        addresses = []

        for _ in range(10):
            response = client.post("/api/v1/addresses")
            assert response.status_code == 200
            addresses.append(response.json())

        # All emails should be unique
        emails = [a["email"] for a in addresses]
        assert len(emails) == len(set(emails))

        # All tokens should be unique
        tokens = [a["token"] for a in addresses]
        assert len(tokens) == len(set(tokens))

    def test_create_address_stored_in_db(self, client, db_session):
        """Test created address is stored in database"""
        response = client.post("/api/v1/addresses")
        data = response.json()

        # Check database
        address = db_session.query(Address).filter(
            Address.email == data["email"]
        ).first()

        assert address is not None
        assert address.email == data["email"]
        assert address.token == data["token"]


class TestAddressValidation:
    """Test address validation and constraints"""

    def test_address_email_valid_format(self, client):
        """Test address email passes email validation"""
        response = client.post("/api/v1/addresses")
        data = response.json()

        # Should not fail Pydantic email validation
        assert response.status_code == 200
        assert "@" in data["email"]

        # Should have valid TLD
        domain = data["email"].split("@")[1]
        assert "." in domain

    def test_duplicate_address_collision_handling(self, client, db_session):
        """Test system handles duplicate address generation"""
        # Create an address
        response1 = client.post("/api/v1/addresses")
        assert response1.status_code == 200

        # Create another - should succeed with different address
        response2 = client.post("/api/v1/addresses")
        assert response2.status_code == 200

        # Should be different
        assert response1.json()["email"] != response2.json()["email"]


class TestAddressLifecycle:
    """Test address lifecycle and expiration"""

    def test_expired_address_status(self, client, db_session):
        """Test expired address is properly marked"""
        # Create an address that's already expired
        address = Address(
            email="expired@tempmail.example.com",
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(address)
        db_session.commit()

        # Check is_expired method
        assert address.is_expired() is True

    def test_active_address_status(self, client, db_session):
        """Test non-expired address is marked active"""
        # Create a fresh address
        address = Address(
            email="active@tempmail.example.com",
            token="active_token",
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(address)
        db_session.commit()

        # Should not be expired
        assert address.is_expired() is False


class TestDomainEndpoint:
    """Test GET /api/v1/domains endpoint"""

    def test_list_domains_success(self, client):
        """Test listing available domains"""
        response = client.get("/api/v1/domains")

        assert response.status_code == 200
        data = response.json()

        assert "domains" in data
        assert isinstance(data["domains"], list)
        assert len(data["domains"]) > 0

    def test_domains_match_config(self, client):
        """Test returned domains match configuration"""
        response = client.get("/api/v1/domains")
        data = response.json()

        # Should include test domain from config
        assert "tempmail.example.com" in data["domains"]


class TestCustomUsername:
    """Test custom username functionality"""

    def test_create_with_custom_username_success(self, client):
        """Test creating address with valid custom username"""
        response = client.post(
            "/api/v1/addresses",
            json={"username": "testuser"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == "testuser@tempmail.example.com"
        assert "token" in data

    def test_create_with_custom_username_and_domain(self, client):
        """Test creating address with custom username and domain"""
        response = client.post(
            "/api/v1/addresses",
            json={"username": "myemail", "domain": "tempmail.example.com"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == "myemail@tempmail.example.com"

    def test_username_taken_returns_409(self, client):
        """Test that taken username returns 409 Conflict"""
        # Create first address
        response1 = client.post(
            "/api/v1/addresses",
            json={"username": "taken"}
        )
        assert response1.status_code == 200

        # Try to create with same username
        response2 = client.post(
            "/api/v1/addresses",
            json={"username": "taken"}
        )
        assert response2.status_code == 409
        assert "already taken" in response2.json()["detail"].lower()

    def test_username_too_short_returns_422(self, client):
        """Test username shorter than 3 chars is rejected"""
        response = client.post(
            "/api/v1/addresses",
            json={"username": "ab"}
        )

        assert response.status_code == 422

    def test_username_too_long_returns_422(self, client):
        """Test username longer than 64 chars is rejected"""
        long_username = "a" * 65
        response = client.post(
            "/api/v1/addresses",
            json={"username": long_username}
        )

        assert response.status_code == 422

    def test_username_with_invalid_chars_returns_422(self, client):
        """Test username with special characters is rejected"""
        invalid_usernames = [
            "test@user",  # @ not allowed
            "test user",  # spaces not allowed
            "test#user",  # # not allowed
            "test$user",  # $ not allowed
        ]

        for username in invalid_usernames:
            response = client.post(
                "/api/v1/addresses",
                json={"username": username}
            )
            assert response.status_code == 422, f"Username '{username}' should be rejected"

    def test_username_with_valid_chars_success(self, client):
        """Test username with valid special chars (. - _) works"""
        valid_usernames = [
            "test.user",
            "test-user",
            "test_user",
            "test.user-name_123"
        ]

        for username in valid_usernames:
            response = client.post(
                "/api/v1/addresses",
                json={"username": username}
            )
            assert response.status_code == 200, f"Username '{username}' should be accepted"

    def test_reserved_username_rejected(self, client):
        """Test reserved usernames are rejected"""
        reserved_usernames = [
            "admin",
            "postmaster",
            "abuse",
            "noreply",
            "root"
        ]

        for username in reserved_usernames:
            response = client.post(
                "/api/v1/addresses",
                json={"username": username}
            )
            assert response.status_code == 400, f"Reserved username '{username}' should be rejected"
            assert "reserved" in response.json()["detail"].lower()

    def test_username_case_insensitive(self, client):
        """Test username is converted to lowercase"""
        response = client.post(
            "/api/v1/addresses",
            json={"username": "TestUser"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should be lowercase
        assert data["email"] == "testuser@tempmail.example.com"


class TestDomainSelection:
    """Test domain selection functionality"""

    def test_select_valid_domain(self, client):
        """Test selecting a configured domain"""
        response = client.post(
            "/api/v1/addresses",
            json={"domain": "tempmail.example.com"}
        )

        assert response.status_code == 200
        data = response.json()

        # Should use selected domain
        assert "@tempmail.example.com" in data["email"]

    def test_invalid_domain_returns_400(self, client):
        """Test selecting non-configured domain fails"""
        response = client.post(
            "/api/v1/addresses",
            json={"domain": "notconfigured.com"}
        )

        assert response.status_code == 400
        assert "not available" in response.json()["detail"].lower()

    def test_invalid_domain_format_returns_422(self, client):
        """Test malformed domain is rejected"""
        invalid_domains = [
            "not a domain",
            "@invalid",
            "invalid@",
            ""
        ]

        for domain in invalid_domains:
            response = client.post(
                "/api/v1/addresses",
                json={"domain": domain}
            )
            assert response.status_code in [400, 422], f"Domain '{domain}' should be rejected"

    def test_fallback_to_first_domain_when_none(self, client):
        """Test falls back to first configured domain when none specified"""
        response = client.post("/api/v1/addresses")

        assert response.status_code == 200
        data = response.json()

        # Should use first configured domain
        assert "@tempmail.example.com" in data["email"]


class TestExpiredUsernameReuse:
    """Test reusing usernames from expired addresses"""

    def test_expired_username_can_be_reused(self, client, db_session):
        """Test can reuse username after address expires"""
        # Create expired address
        expired_address = Address(
            email="reuseme@tempmail.example.com",
            token="old_token",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(expired_address)
        db_session.commit()

        # Should be able to create new address with same username
        response = client.post(
            "/api/v1/addresses",
            json={"username": "reuseme"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == "reuseme@tempmail.example.com"
        # Should have new token (not the old one)
        assert data["token"] != "old_token"

    def test_expired_address_deleted_on_reuse(self, client, db_session):
        """Test expired address is deleted when username is reused"""
        # Create expired address
        expired_address = Address(
            email="deleteme@tempmail.example.com",
            token="old_token",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(expired_address)
        db_session.commit()
        expired_id = expired_address.id

        # Reuse the username
        response = client.post(
            "/api/v1/addresses",
            json={"username": "deleteme"}
        )
        assert response.status_code == 200

        # Old address should be deleted
        old_address = db_session.query(Address).filter(Address.id == expired_id).first()
        assert old_address is None

    def test_active_username_cannot_be_reused(self, client, db_session):
        """Test active (non-expired) username cannot be reused"""
        # Create active address
        active_address = Address(
            email="active@tempmail.example.com",
            token="active_token",
            expires_at=datetime.utcnow() + timedelta(hours=24)
        )
        db_session.add(active_address)
        db_session.commit()

        # Should NOT be able to reuse
        response = client.post(
            "/api/v1/addresses",
            json={"username": "active"}
        )

        assert response.status_code == 409
        assert "already taken" in response.json()["detail"].lower()


class TestBackwardCompatibility:
    """Test that existing random generation still works"""

    def test_empty_request_still_generates_random(self, client):
        """Test empty POST still generates random address"""
        response = client.post("/api/v1/addresses")

        assert response.status_code == 200
        data = response.json()

        # Should have random 8-char username
        email = data["email"]
        local_part = email.split("@")[0]
        assert len(local_part) == 8
        assert local_part.isalnum()

    def test_random_generation_unchanged(self, client):
        """Test random generation behavior unchanged"""
        response = client.post("/api/v1/addresses", json={})

        assert response.status_code == 200
        data = response.json()

        # Verify all fields present
        assert "id" in data
        assert "email" in data
        assert "token" in data
        assert "created_at" in data
        assert "expires_at" in data
