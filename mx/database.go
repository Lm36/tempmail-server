package main

import (
	"database/sql"
	"fmt"
	"log"
	"strings"
	"time"

	_ "github.com/lib/pq"
)

// DB wraps the database connection
type DB struct {
	conn *sql.DB
}

// EmailData represents an email to be stored
type EmailData struct {
	MessageID      string
	Subject        string
	FromAddr       string
	ToAddr         string
	RawHeaders     string
	BodyPlain      string
	BodyHTML       string
	RawMessage     []byte
	SizeBytes      int64
	DKIMValid      *bool  // nullable
	SPFResult      string // pass, fail, softfail, neutral, none, temperror, permerror
	DMARCResult    string // pass, fail, none
	HasAttachments bool
	ReceivedAt     time.Time
}

// AttachmentData represents an email attachment
type AttachmentData struct {
	Filename    string
	ContentType string
	SizeBytes   int64
	Data        []byte
}

// NewDB creates a new database connection
func NewDB(databaseURL string, poolSize int) (*DB, error) {
	conn, err := sql.Open("postgres", databaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Configure connection pool
	conn.SetMaxOpenConns(poolSize)
	conn.SetMaxIdleConns(poolSize / 2)
	conn.SetConnMaxLifetime(5 * time.Minute)

	// Test connection
	if err := conn.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &DB{conn: conn}, nil
}

// Close closes the database connection
func (db *DB) Close() error {
	log.Println("Closing database connection...")
	return db.conn.Close()
}

// StoreEmail stores an email and its attachments in the database
func (db *DB) StoreEmail(email *EmailData, attachments []AttachmentData) error {
	tx, err := db.conn.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Insert email
	var emailID string
	err = tx.QueryRow(`
		INSERT INTO emails (
			message_id, subject, from_address, to_address, raw_headers,
			body_plain, body_html, raw_message, size_bytes,
			dkim_valid, spf_result, dmarc_result, has_attachments, received_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		RETURNING id
	`,
		email.MessageID, email.Subject, email.FromAddr, email.ToAddr,
		email.RawHeaders, email.BodyPlain, email.BodyHTML, email.RawMessage,
		email.SizeBytes, email.DKIMValid, email.SPFResult, email.DMARCResult,
		email.HasAttachments, email.ReceivedAt,
	).Scan(&emailID)

	if err != nil {
		return fmt.Errorf("failed to insert email: %w", err)
	}

	log.Printf("Stored email %s with ID %s", email.MessageID, emailID)

	// Find or create address for recipient
	addressID, err := db.getOrCreateAddress(tx, email.ToAddr)
	if err != nil {
		return fmt.Errorf("failed to get/create address: %w", err)
	}

	// Link email to address
	_, err = tx.Exec(`
		INSERT INTO email_recipients (email_id, address_id)
		VALUES ($1, $2)
	`, emailID, addressID)
	if err != nil {
		return fmt.Errorf("failed to link email to address: %w", err)
	}

	// Store attachments
	for _, att := range attachments {
		_, err = tx.Exec(`
			INSERT INTO attachments (email_id, filename, content_type, size_bytes, data)
			VALUES ($1, $2, $3, $4, $5)
		`, emailID, att.Filename, att.ContentType, att.SizeBytes, att.Data)

		if err != nil {
			return fmt.Errorf("failed to insert attachment: %w", err)
		}
		log.Printf("Stored attachment: %s (%d bytes)", att.Filename, att.SizeBytes)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	// Asynchronously enforce email limit (don't block email reception)
	go func() {
		if err := db.EnforceEmailLimit(addressID); err != nil {
			log.Printf("Warning: Failed to enforce email limit for address %s: %v", addressID, err)
		}
	}()

	return nil
}

// getOrCreateAddress gets existing address or creates a temporary catch-all address
// This is the "magic" of tempmail - any email sent to our domains auto-creates an address
func (db *DB) getOrCreateAddress(tx *sql.Tx, email string) (string, error) {
	// First try to find existing address
	var addressID string
	err := tx.QueryRow(`
		SELECT id FROM addresses WHERE email = $1
	`, email).Scan(&addressID)

	if err == nil {
		// Address exists
		return addressID, nil
	}

	if err != sql.ErrNoRows {
		// Real error
		return "", fmt.Errorf("failed to query address: %w", err)
	}

	// Address doesn't exist - create it as a catch-all temporary address
	// Note: This is auto-created, not explicitly generated via API
	// It will expire based on default lifetime
	expiresAt := time.Now().Add(24 * time.Hour) // Default 24h expiration

	// Generate a simple token for this auto-created address
	token := generateSimpleToken()

	err = tx.QueryRow(`
		INSERT INTO addresses (email, token, expires_at)
		VALUES ($1, $2, $3)
		RETURNING id
	`, email, token, expiresAt).Scan(&addressID)

	if err != nil {
		return "", fmt.Errorf("failed to create address: %w", err)
	}

	log.Printf("Auto-created address %s (expires: %s)", email, expiresAt.Format(time.RFC3339))
	return addressID, nil
}

// generateSimpleToken generates a random token for auto-created addresses
func generateSimpleToken() string {
	// Simple token generation for auto created addresses, users wont see it
	// In production API this is more sophisticated
	return fmt.Sprintf("auto_%d", time.Now().UnixNano())
}

// CheckDomainAllowed checks if a domain is in the allowed list
func (db *DB) CheckDomainAllowed(domain string, allowedDomains map[string]bool) bool {
	return allowedDomains[strings.ToLower(domain)]
}

// EnforceEmailLimit enforces max emails per address by deleting oldest
func (db *DB) EnforceEmailLimit(addressID string) error {
	// This is called asynchronously after storing email
	// Get max from config - for now hardcode to 100
	maxEmails := 100

	result, err := db.conn.Exec(`
		DELETE FROM emails
		WHERE id IN (
			SELECT e.id
			FROM emails e
			JOIN email_recipients er ON er.email_id = e.id
			WHERE er.address_id = $1
			ORDER BY e.received_at DESC
			OFFSET $2
		)
	`, addressID, maxEmails)

	if err != nil {
		return fmt.Errorf("failed to enforce email limit: %w", err)
	}

	deleted, _ := result.RowsAffected()
	if deleted > 0 {
		log.Printf("Deleted %d old emails for address %s (enforcing limit of %d)", deleted, addressID, maxEmails)
	}

	return nil
}
