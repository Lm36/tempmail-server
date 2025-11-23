-- Migration: Add trigger to delete orphaned emails
-- Date: 2025-11-23
-- Description: Adds automatic cleanup of emails when all recipients are deleted

-- Function to delete orphaned emails when all recipients are removed
CREATE OR REPLACE FUNCTION delete_orphaned_emails() RETURNS TRIGGER AS $$
BEGIN
    -- Delete emails that no longer have any recipients
    -- This cascades to attachments via ON DELETE CASCADE
    DELETE FROM emails
    WHERE id = OLD.email_id
    AND NOT EXISTS (
        SELECT 1 FROM email_recipients
        WHERE email_id = OLD.email_id
    );
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically clean up orphaned emails
DROP TRIGGER IF EXISTS trigger_delete_orphaned_emails ON email_recipients;
CREATE TRIGGER trigger_delete_orphaned_emails
AFTER DELETE ON email_recipients
FOR EACH ROW
EXECUTE FUNCTION delete_orphaned_emails();

COMMENT ON FUNCTION delete_orphaned_emails() IS 'Automatically deletes emails with no recipients, cascading to attachments';

-- Cleanup any existing orphaned emails
DELETE FROM emails
WHERE id NOT IN (
    SELECT DISTINCT email_id FROM email_recipients
);
