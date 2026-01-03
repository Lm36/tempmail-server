package main

import (
	"bytes"
	"strings"
	"testing"

	"github.com/jhillyerd/enmime"
)

// mockSessionDB implements SessionDB interface for testing
type mockSessionDB struct {
	addresses map[string]bool
}

func (m *mockSessionDB) AddressExists(email string) (bool, error) {
	return m.addresses[strings.ToLower(email)], nil
}

func (m *mockSessionDB) StoreEmail(email *EmailData, attachments []AttachmentData) error {
	return nil // Not used in these tests
}

func TestGetClientIP(t *testing.T) {
	tests := []struct {
		name       string
		remoteAddr string
		want       string
	}{
		{
			name:       "IPv4 with port",
			remoteAddr: "192.168.1.100:12345",
			want:       "192.168.1.100",
		},
		{
			name:       "IPv6 with port",
			remoteAddr: "[2001:db8::1]:12345",
			want:       "2001:db8::1",
		},
		{
			name:       "localhost with port",
			remoteAddr: "127.0.0.1:54321",
			want:       "127.0.0.1",
		},
		{
			name:       "Invalid format returns as-is",
			remoteAddr: "invalid",
			want:       "invalid",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			s := &Session{remoteAddr: tt.remoteAddr}
			if got := s.getClientIP(); got != tt.want {
				t.Errorf("getClientIP() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestExtractEmailData(t *testing.T) {
	tests := []struct {
		name        string
		rawMessage  string
		fromAddr    string
		wantSubject string
		wantHasHTML bool
	}{
		{
			name: "simple plain text email",
			rawMessage: `From: sender@example.com
To: recipient@tempmail.example.com
Subject: Test Email
Date: Mon, 01 Jan 2024 12:00:00 +0000
Message-ID: <test123@example.com>

This is a test email body.
`,
			fromAddr:    "sender@example.com",
			wantSubject: "Test Email",
			wantHasHTML: false,
		},
		{
			name: "multipart email with HTML",
			rawMessage: `From: sender@example.com
To: recipient@tempmail.example.com
Subject: HTML Email
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain

Plain text version
--boundary123
Content-Type: text/html

<html><body>HTML version</body></html>
--boundary123--
`,
			fromAddr:    "sender@example.com",
			wantSubject: "HTML Email",
			wantHasHTML: true,
		},
		{
			name: "email without subject",
			rawMessage: `From: sender@example.com
To: recipient@tempmail.example.com
Date: Mon, 01 Jan 2024 12:00:00 +0000

This is a test without subject.
`,
			fromAddr:    "sender@example.com",
			wantSubject: "",
			wantHasHTML: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			envelope, err := enmime.ReadEnvelope(bytes.NewReader([]byte(tt.rawMessage)))
			if err != nil {
				t.Fatalf("Failed to parse email: %v", err)
			}

			s := &Session{from: tt.fromAddr}
			emailData := s.extractEmailData(envelope, []byte(tt.rawMessage), int64(len(tt.rawMessage)))

			if emailData == nil {
				t.Fatal("extractEmailData() returned nil")
			}

			if emailData.Subject != tt.wantSubject {
				t.Errorf("extractEmailData() Subject = %v, want %v", emailData.Subject, tt.wantSubject)
			}

			if emailData.FromAddr != tt.fromAddr {
				t.Errorf("extractEmailData() FromAddr = %v, want %v", emailData.FromAddr, tt.fromAddr)
			}

			if tt.wantHasHTML && emailData.BodyHTML == "" {
				t.Error("extractEmailData() should have HTML body but doesn't")
			}

			if emailData.RawHeaders == "" {
				t.Error("extractEmailData() RawHeaders should not be empty")
			}

			if emailData.SizeBytes != int64(len(tt.rawMessage)) {
				t.Errorf("extractEmailData() SizeBytes = %v, want %v", emailData.SizeBytes, len(tt.rawMessage))
			}
		})
	}
}

func TestExtractAttachments(t *testing.T) {
	tests := []struct {
		name            string
		rawMessage      string
		wantAttachments int
	}{
		{
			name: "email without attachments",
			rawMessage: `From: sender@example.com
To: recipient@tempmail.example.com
Subject: No Attachments

Just plain text.
`,
			wantAttachments: 0,
		},
		{
			name: "email with one attachment",
			rawMessage: `From: sender@example.com
To: recipient@tempmail.example.com
Subject: With Attachment
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/plain

Email body

--boundary123
Content-Type: application/pdf; name="document.pdf"
Content-Disposition: attachment; filename="document.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQKJeLjz9MKCg==
--boundary123--
`,
			wantAttachments: 1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			envelope, err := enmime.ReadEnvelope(bytes.NewReader([]byte(tt.rawMessage)))
			if err != nil {
				t.Fatalf("Failed to parse email: %v", err)
			}

			s := &Session{}
			attachments := s.extractAttachments(envelope)

			if len(attachments) != tt.wantAttachments {
				t.Errorf("extractAttachments() returned %v attachments, want %v", len(attachments), tt.wantAttachments)
			}

			// Verify attachment structure if any exist
			for _, att := range attachments {
				if att.Filename == "" {
					t.Error("Attachment should have a filename")
				}
				if att.ContentType == "" {
					t.Error("Attachment should have a content type")
				}
				if att.SizeBytes <= 0 {
					t.Error("Attachment should have a positive size")
				}
			}
		})
	}
}

func TestSessionMail(t *testing.T) {
	cfg := &Config{}
	s := NewSession("127.0.0.1:12345", "client.example.com", cfg, nil, nil, nil)

	// Test MAIL FROM
	err := s.Mail("sender@example.com", nil)
	if err != nil {
		t.Errorf("Mail() returned error: %v", err)
	}

	if s.from != "sender@example.com" {
		t.Errorf("Mail() didn't set from address, got %v", s.from)
	}

	// Calling Mail again should reset recipients
	s.to = []string{"test@tempmail.example.com"}
	err = s.Mail("newsender@example.com", nil)
	if err != nil {
		t.Errorf("Mail() second call returned error: %v", err)
	}

	if len(s.to) != 0 {
		t.Error("Mail() should reset recipients list")
	}
}

func TestSessionRcpt(t *testing.T) {
	cfg := &Config{
		Domains: []string{"tempmail.example.com", "temp.test"},
	}

	domains := cfg.GetDomainMap()

	// Create mock DB with test addresses that exist
	mockDB := &mockSessionDB{
		addresses: map[string]bool{
			"test@tempmail.example.com": true,
			"user@temp.test":            true,
			"user@tempmail.example.com": true,
		},
	}

	s := NewSession("127.0.0.1:12345", "client.example.com", cfg, mockDB, nil, domains)

	tests := []struct {
		name      string
		recipient string
		wantError bool
	}{
		{
			name:      "valid recipient for accepted domain",
			recipient: "test@tempmail.example.com",
			wantError: false,
		},
		{
			name:      "valid recipient for second accepted domain",
			recipient: "user@temp.test",
			wantError: false,
		},
		{
			name:      "rejected - domain not accepted",
			recipient: "user@notaccepted.com",
			wantError: true,
		},
		{
			name:      "rejected - invalid email format",
			recipient: "invalid-email",
			wantError: true,
		},
		{
			name:      "rejected - no domain",
			recipient: "nodomain@",
			wantError: true,
		},
		{
			name:      "email with angle brackets",
			recipient: "<user@tempmail.example.com>",
			wantError: false,
		},
		{
			name:      "email with display name",
			recipient: "User Name <user@tempmail.example.com>",
			wantError: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Reset recipients for each test
			s.to = nil

			err := s.Rcpt(tt.recipient, nil)

			if (err != nil) != tt.wantError {
				t.Errorf("Rcpt() error = %v, wantError %v", err, tt.wantError)
			}

			if !tt.wantError {
				// Check recipient was added
				found := false
				for _, addr := range s.to {
					if strings.Contains(addr, "tempmail.example.com") || strings.Contains(addr, "temp.test") {
						found = true
						break
					}
				}
				if !found {
					t.Errorf("Rcpt() didn't add recipient %v to session, got %v", tt.recipient, s.to)
				}
			}
		})
	}
}

func TestSessionReset(t *testing.T) {
	s := &Session{
		from: "sender@example.com",
		to:   []string{"recipient1@test.com", "recipient2@test.com"},
	}

	s.Reset()

	if s.from != "" {
		t.Errorf("Reset() didn't clear from address, got %v", s.from)
	}

	if s.to != nil {
		t.Errorf("Reset() didn't clear recipients, got %v", s.to)
	}
}

func TestSessionLogout(t *testing.T) {
	s := &Session{}

	err := s.Logout()
	if err != nil {
		t.Errorf("Logout() should not return error, got %v", err)
	}
}

func TestSessionAuthPlain(t *testing.T) {
	s := &Session{}

	// MX servers should not support authentication
	err := s.AuthPlain("user", "pass")
	if err == nil {
		t.Error("AuthPlain() should return error for MX server")
	}
}

func TestFormatBoolPtr(t *testing.T) {
	tests := []struct {
		name string
		b    *bool
		want string
	}{
		{
			name: "nil pointer",
			b:    nil,
			want: "null",
		},
		{
			name: "true value",
			b:    func() *bool { v := true; return &v }(),
			want: "true",
		},
		{
			name: "false value",
			b:    func() *bool { v := false; return &v }(),
			want: "false",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := formatBoolPtr(tt.b); got != tt.want {
				t.Errorf("formatBoolPtr() = %v, want %v", got, tt.want)
			}
		})
	}
}
