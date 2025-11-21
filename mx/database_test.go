package main

import (
	"testing"
	"time"
)

func TestGenerateSimpleToken(t *testing.T) {
	// Generate multiple tokens
	tokens := make(map[string]bool)

	for i := 0; i < 10; i++ {
		token := generateSimpleToken()

		// Token should not be empty
		if token == "" {
			t.Error("generateSimpleToken() returned empty string")
		}

		// Token should start with "auto_"
		if len(token) < 5 || token[:5] != "auto_" {
			t.Errorf("generateSimpleToken() = %v, should start with 'auto_'", token)
		}

		// Token should be unique
		if tokens[token] {
			t.Errorf("generateSimpleToken() generated duplicate token: %v", token)
		}
		tokens[token] = true

		// Small delay to ensure different timestamps
		time.Sleep(time.Microsecond)
	}

	// Should have generated 10 unique tokens
	if len(tokens) != 10 {
		t.Errorf("generateSimpleToken() generated %v unique tokens, want 10", len(tokens))
	}
}

func TestCheckDomainAllowed(t *testing.T) {
	// Create a DB instance (we don't need actual connection for this test)
	db := &DB{}

	allowedDomains := map[string]bool{
		"tempmail.example.com": true,
		"temp.test":            true,
		"mail.local":           true,
	}

	tests := []struct {
		name   string
		domain string
		want   bool
	}{
		{
			name:   "allowed domain",
			domain: "tempmail.example.com",
			want:   true,
		},
		{
			name:   "another allowed domain",
			domain: "temp.test",
			want:   true,
		},
		{
			name:   "case insensitive - uppercase",
			domain: "TEMPMAIL.EXAMPLE.COM",
			want:   true,
		},
		{
			name:   "case insensitive - mixed case",
			domain: "TempMail.Example.Com",
			want:   true,
		},
		{
			name:   "not allowed domain",
			domain: "notallowed.com",
			want:   false,
		},
		{
			name:   "empty domain",
			domain: "",
			want:   false,
		},
		{
			name:   "similar but different domain",
			domain: "tempmail.example.org",
			want:   false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := db.CheckDomainAllowed(tt.domain, allowedDomains); got != tt.want {
				t.Errorf("CheckDomainAllowed() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestEmailDataStructure(t *testing.T) {
	// Test EmailData structure creation
	now := time.Now()
	dkimValid := true

	emailData := &EmailData{
		MessageID:      "<test@example.com>",
		Subject:        "Test Subject",
		FromAddr:       "sender@example.com",
		ToAddr:         "recipient@tempmail.example.com",
		RawHeaders:     "From: sender@example.com\nTo: recipient@tempmail.example.com",
		BodyPlain:      "Test body",
		BodyHTML:       "<p>Test body</p>",
		RawMessage:     []byte("raw message data"),
		SizeBytes:      100,
		DKIMValid:      &dkimValid,
		SPFResult:      "pass",
		DMARCResult:    "pass",
		HasAttachments: false,
		ReceivedAt:     now,
	}

	// Verify fields
	if emailData.MessageID != "<test@example.com>" {
		t.Errorf("EmailData.MessageID = %v", emailData.MessageID)
	}

	if emailData.Subject != "Test Subject" {
		t.Errorf("EmailData.Subject = %v", emailData.Subject)
	}

	if *emailData.DKIMValid != true {
		t.Errorf("EmailData.DKIMValid = %v", *emailData.DKIMValid)
	}

	if emailData.SPFResult != "pass" {
		t.Errorf("EmailData.SPFResult = %v", emailData.SPFResult)
	}

	if emailData.DMARCResult != "pass" {
		t.Errorf("EmailData.DMARCResult = %v", emailData.DMARCResult)
	}
}

func TestAttachmentDataStructure(t *testing.T) {
	// Test AttachmentData structure creation
	attData := AttachmentData{
		Filename:    "document.pdf",
		ContentType: "application/pdf",
		SizeBytes:   1024,
		Data:        []byte("fake pdf data"),
	}

	if attData.Filename != "document.pdf" {
		t.Errorf("AttachmentData.Filename = %v", attData.Filename)
	}

	if attData.ContentType != "application/pdf" {
		t.Errorf("AttachmentData.ContentType = %v", attData.ContentType)
	}

	if attData.SizeBytes != 1024 {
		t.Errorf("AttachmentData.SizeBytes = %v", attData.SizeBytes)
	}

	if len(attData.Data) == 0 {
		t.Error("AttachmentData.Data should not be empty")
	}
}

func TestEmailDataWithNullDKIM(t *testing.T) {
	// Test EmailData with nil DKIM value (not checked)
	emailData := &EmailData{
		MessageID:      "<test@example.com>",
		Subject:        "Test",
		FromAddr:       "sender@example.com",
		ToAddr:         "recipient@tempmail.example.com",
		RawHeaders:     "From: sender@example.com",
		BodyPlain:      "Test",
		BodyHTML:       "",
		RawMessage:     []byte("test"),
		SizeBytes:      4,
		DKIMValid:      nil, // Not checked
		SPFResult:      "none",
		DMARCResult:    "none",
		HasAttachments: false,
		ReceivedAt:     time.Now(),
	}

	if emailData.DKIMValid != nil {
		t.Error("EmailData.DKIMValid should be nil when not checked")
	}
}
