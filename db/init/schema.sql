-- Tempmail Server Database Schema
-- PostgreSQL 15+

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- ============================================================================
-- Table: addresses
-- Stores temporary email addresses with expiration
-- ============================================================================
CREATE TABLE addresses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL UNIQUE,
    token VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    CONSTRAINT addresses_email_check CHECK (email ~ '^[^@]+@[^@]+$')
);

CREATE INDEX idx_addresses_token ON addresses(token);
CREATE INDEX idx_addresses_expires_at ON addresses(expires_at);
CREATE INDEX idx_addresses_email ON addresses(email);

COMMENT ON TABLE addresses IS 'Temporary email addresses with auto-expiration';
COMMENT ON COLUMN addresses.token IS 'Access token for API authentication';
COMMENT ON COLUMN addresses.expires_at IS 'When this address will be automatically deleted';

-- ============================================================================
-- Table: emails
-- Stores received email messages with validation results
-- ============================================================================
CREATE TABLE emails (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id VARCHAR(255),
    subject TEXT,
    from_address VARCHAR(255) NOT NULL,
    to_address VARCHAR(255) NOT NULL,
    raw_headers TEXT NOT NULL,
    body_plain TEXT,
    body_html TEXT,
    raw_message BYTEA NOT NULL,
    size_bytes BIGINT NOT NULL DEFAULT 0,

    -- Validation results
    dkim_valid BOOLEAN DEFAULT NULL,
    spf_result VARCHAR(20),  -- pass, fail, softfail, neutral, none, temperror, permerror
    dmarc_result VARCHAR(20), -- pass, fail, none

    has_attachments BOOLEAN DEFAULT FALSE,
    received_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT emails_size_check CHECK (size_bytes >= 0)
);

CREATE INDEX idx_emails_message_id ON emails(message_id);
CREATE INDEX idx_emails_from ON emails(from_address);
CREATE INDEX idx_emails_to ON emails(to_address);
CREATE INDEX idx_emails_received_at ON emails(received_at DESC);
CREATE INDEX idx_emails_subject_trgm ON emails USING gin (subject gin_trgm_ops);

COMMENT ON TABLE emails IS 'Received email messages with full content and validation';
COMMENT ON COLUMN emails.raw_message IS 'Complete RFC 5322 message as received';
COMMENT ON COLUMN emails.dkim_valid IS 'DKIM signature validation result';
COMMENT ON COLUMN emails.spf_result IS 'SPF validation result';
COMMENT ON COLUMN emails.dmarc_result IS 'DMARC policy check result';

-- ============================================================================
-- Table: email_recipients
-- Links emails to addresses (many-to-many)
-- ============================================================================
CREATE TABLE email_recipients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    address_id UUID NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT email_recipients_unique UNIQUE (email_id, address_id)
);

CREATE INDEX idx_email_recipients_email_id ON email_recipients(email_id);
CREATE INDEX idx_email_recipients_address_id ON email_recipients(address_id);
CREATE INDEX idx_email_recipients_is_read ON email_recipients(is_read);

COMMENT ON TABLE email_recipients IS 'Links emails to recipient addresses with read status';

-- ============================================================================
-- Table: attachments
-- Stores email attachments in database as BYTEA
-- ============================================================================
CREATE TABLE attachments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email_id UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(127) NOT NULL,
    size_bytes BIGINT NOT NULL,
    data BYTEA NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT attachments_size_check CHECK (size_bytes >= 0)
);

CREATE INDEX idx_attachments_email_id ON attachments(email_id);
CREATE INDEX idx_attachments_filename ON attachments(filename);

COMMENT ON TABLE attachments IS 'Email attachments stored as binary data';
COMMENT ON COLUMN attachments.data IS 'File content stored in database';

-- ============================================================================
-- Functions for cleanup
-- ============================================================================

-- Function to delete expired addresses and their associated data
CREATE OR REPLACE FUNCTION cleanup_expired_addresses() RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete expired addresses (CASCADE will handle emails and recipients)
    DELETE FROM addresses
    WHERE expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_expired_addresses() IS 'Deletes addresses past their expiration time';

-- Function to enforce max emails per address
CREATE OR REPLACE FUNCTION enforce_max_emails_per_address(
    p_address_id UUID,
    p_max_emails INTEGER
) RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete oldest emails if over limit
    WITH emails_to_delete AS (
        SELECT er.email_id
        FROM email_recipients er
        JOIN emails e ON er.email_id = e.id
        WHERE er.address_id = p_address_id
        ORDER BY e.received_at DESC
        OFFSET p_max_emails
    )
    DELETE FROM emails
    WHERE id IN (SELECT email_id FROM emails_to_delete);

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION enforce_max_emails_per_address(UUID, INTEGER) IS 'Limits emails per address by deleting oldest';

-- ============================================================================
-- Initial data / constraints
-- ============================================================================

-- Add check to ensure cleanup actually deletes expired data
CREATE OR REPLACE FUNCTION check_no_expired_addresses() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.expires_at < NOW() THEN
        RAISE EXCEPTION 'Cannot insert expired address';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Stats view for monitoring
CREATE OR REPLACE VIEW tempmail_stats AS
SELECT
    (SELECT COUNT(*) FROM addresses) AS total_addresses,
    (SELECT COUNT(*) FROM addresses WHERE expires_at > NOW()) AS active_addresses,
    (SELECT COUNT(*) FROM emails) AS total_emails,
    (SELECT COUNT(*) FROM email_recipients WHERE is_read = FALSE) AS unread_emails,
    (SELECT COUNT(*) FROM attachments) AS total_attachments,
    (SELECT COALESCE(SUM(size_bytes), 0) FROM emails) AS total_email_size_bytes,
    (SELECT COALESCE(SUM(size_bytes), 0) FROM attachments) AS total_attachment_size_bytes,
    NOW() AS generated_at;

COMMENT ON VIEW tempmail_stats IS 'System-wide statistics for monitoring';
