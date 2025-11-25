package main

import (
	"bytes"
	"fmt"
	"io"
	"log"
	"net"
	"net/mail"
	"strings"
	"time"

	"github.com/emersion/go-smtp"
	"github.com/jhillyerd/enmime"
)

// Session represents an SMTP session
type Session struct {
	from       string
	to         []string
	remoteAddr string
	hostname   string
	cfg        *Config
	db         *DB
	validator  *Validator
	domains    map[string]bool
}

// NewSession creates a new SMTP session
func NewSession(remoteAddr, hostname string, cfg *Config, db *DB, validator *Validator, domains map[string]bool) *Session {
	return &Session{
		remoteAddr: remoteAddr,
		hostname:   hostname,
		cfg:        cfg,
		db:         db,
		validator:  validator,
		domains:    domains,
	}
}

// Mail is called when the client sends MAIL FROM
func (s *Session) Mail(from string, opts *smtp.MailOptions) error {
	log.Printf("[%s] MAIL FROM: <%s>", s.remoteAddr, from)
	s.from = from
	s.to = nil
	return nil
}

// Rcpt is called when the client sends RCPT TO
func (s *Session) Rcpt(to string, opts *smtp.RcptOptions) error {
	log.Printf("[%s] RCPT TO: <%s>", s.remoteAddr, to)

	// Validate recipient address format
	addr, err := mail.ParseAddress(to)
	if err != nil {
		log.Printf("[%s] REJECTED: Invalid address format: %v", s.remoteAddr, err)
		return fmt.Errorf("invalid recipient address")
	}

	// Extract domain
	parts := strings.Split(addr.Address, "@")
	if len(parts) != 2 {
		log.Printf("[%s] REJECTED: Invalid email format: %s", s.remoteAddr, addr.Address)
		return fmt.Errorf("invalid email format")
	}
	domain := strings.ToLower(parts[1])

	// Check if domain is in our allowed list
	if !s.domains[domain] {
		log.Printf("[%s] REJECTED: Domain not accepted: %s (allowed: %v)", s.remoteAddr, domain, s.cfg.Domains)
		return fmt.Errorf("relay access denied for domain %s", domain)
	}

	// Normalize email address to lowercase for consistent storage
	normalizedEmail := strings.ToLower(addr.Address)

	// Accept the recipient (catch-all - any local part is accepted)
	s.to = append(s.to, normalizedEmail)
	log.Printf("[%s] ACCEPTED: <%s> -> normalized as <%s> (total recipients: %d)", s.remoteAddr, addr.Address, normalizedEmail, len(s.to))
	return nil
}

// Data is called when the client sends DATA
func (s *Session) Data(r io.Reader) error {
	log.Printf("[%s] DATA: %s -> %v", s.remoteAddr, s.from, s.to)

	// Read the message
	buf := new(bytes.Buffer)
	size, err := buf.ReadFrom(io.LimitReader(r, s.cfg.GetMaxMessageSize()))
	if err != nil {
		log.Printf("[%s] ERROR: Failed to read message: %v", s.remoteAddr, err)
		return fmt.Errorf("error reading message")
	}

	if size >= s.cfg.GetMaxMessageSize() {
		log.Printf("[%s] REJECTED: Message too large (%d bytes, max %d)", s.remoteAddr, size, s.cfg.GetMaxMessageSize())
		return fmt.Errorf("message too large (max %d MB)", s.cfg.Server.MaxMsgSizeMB)
	}

	rawMessage := buf.Bytes()
	log.Printf("[%s] Received message (%d bytes)", s.remoteAddr, size)

	// Parse the email with MIME support
	envelope, err := enmime.ReadEnvelope(bytes.NewReader(rawMessage))
	if err != nil {
		log.Printf("[%s] ERROR: Failed to parse email: %v", s.remoteAddr, err)
		return fmt.Errorf("error processing message")
	}

	// Extract email data
	emailData := s.extractEmailData(envelope, rawMessage, size)

	// Perform validation if enabled
	if s.validator != nil {
		clientIP := s.getClientIP()
		validationResult := s.validator.ValidateEmail(rawMessage, s.from, clientIP, s.hostname)

		emailData.DKIMValid = validationResult.DKIMValid
		emailData.SPFResult = validationResult.SPFResult
		emailData.DMARCResult = validationResult.DMARCResult

		log.Printf("[%s] Validation - DKIM: %v, SPF: %s, DMARC: %s",
			s.remoteAddr, formatBoolPtr(validationResult.DKIMValid), validationResult.SPFResult, validationResult.DMARCResult)
	}

	// Extract attachments
	attachments := s.extractAttachments(envelope)
	emailData.HasAttachments = len(attachments) > 0

	log.Printf("[%s] Parsed - Subject: '%s', Attachments: %d", s.remoteAddr, emailData.Subject, len(attachments))

	// Store email for each recipient
	for _, recipient := range s.to {
		emailData.ToAddr = recipient

		if err := s.db.StoreEmail(emailData, attachments); err != nil {
			log.Printf("[%s] ERROR: Failed to store email for %s: %v", s.remoteAddr, recipient, err)
			return fmt.Errorf("error storing message")
		}

		log.Printf("[%s] ✓ Stored email for %s", s.remoteAddr, recipient)
	}

	log.Printf("[%s] ✓ SUCCESS: Email delivered to %d recipients", s.remoteAddr, len(s.to))
	return nil
}

// Reset is called when the client sends RSET
func (s *Session) Reset() {
	log.Printf("[%s] RSET: Transaction reset", s.remoteAddr)
	s.from = ""
	s.to = nil
}

// Logout is called when the client disconnects
func (s *Session) Logout() error {
	log.Printf("[%s] QUIT: Connection closed", s.remoteAddr)
	return nil
}

// AuthPlain is not used for MX servers (no AUTH required for receiving)
// But we implement it to satisfy the smtp.Session interface
func (s *Session) AuthPlain(username, password string) error {
	return fmt.Errorf("authentication not supported on MX server")
}

// extractEmailData extracts structured data from email envelope
func (s *Session) extractEmailData(envelope *enmime.Envelope, rawMessage []byte, size int64) *EmailData {
	// Extract headers
	messageID := envelope.GetHeader("Message-ID")
	subject := envelope.GetHeader("Subject")
	dateStr := envelope.GetHeader("Date")

	// Parse date
	var dateSent time.Time
	if dateStr != "" {
		dateSent, _ = mail.ParseDate(dateStr)
	}
	if dateSent.IsZero() {
		dateSent = time.Now()
	}

	// Collect all headers as raw text
	rawHeaders := new(bytes.Buffer)
	for key, values := range envelope.Root.Header {
		for _, val := range values {
			fmt.Fprintf(rawHeaders, "%s: %s\n", key, val)
		}
	}

	// Get body content
	bodyPlain := envelope.Text
	bodyHTML := envelope.HTML

	// If no plain text but have HTML, note it
	if bodyPlain == "" && bodyHTML != "" {
		bodyPlain = "[HTML email - plain text not provided]"
	}

	return &EmailData{
		MessageID:  messageID,
		Subject:    subject,
		FromAddr:   s.from,
		RawHeaders: rawHeaders.String(),
		BodyPlain:  bodyPlain,
		BodyHTML:   bodyHTML,
		RawMessage: rawMessage,
		SizeBytes:  size,
		ReceivedAt: time.Now(),
	}
}

// extractAttachments extracts attachment data from email envelope
func (s *Session) extractAttachments(envelope *enmime.Envelope) []AttachmentData {
	var attachments []AttachmentData

	// Process regular attachments
	for _, att := range envelope.Attachments {
		attachments = append(attachments, AttachmentData{
			Filename:    att.FileName,
			ContentType: att.ContentType,
			SizeBytes:   int64(len(att.Content)),
			Data:        att.Content,
		})
	}

	// Process inline attachments (embedded images, etc.)
	for _, inline := range envelope.Inlines {
		attachments = append(attachments, AttachmentData{
			Filename:    inline.FileName,
			ContentType: inline.ContentType,
			SizeBytes:   int64(len(inline.Content)),
			Data:        inline.Content,
		})
	}

	return attachments
}

// getClientIP extracts the client IP from remote address
func (s *Session) getClientIP() string {
	host, _, err := net.SplitHostPort(s.remoteAddr)
	if err != nil {
		return s.remoteAddr
	}
	return host
}

// formatBoolPtr formats a nullable bool pointer for logging
func formatBoolPtr(b *bool) string {
	if b == nil {
		return "null"
	}
	if *b {
		return "true"
	}
	return "false"
}
