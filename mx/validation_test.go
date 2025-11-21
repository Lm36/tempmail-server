package main

import (
	"net"
	"testing"
)

func TestExtractDomain(t *testing.T) {
	tests := []struct {
		name  string
		email string
		want  string
	}{
		{
			name:  "simple email",
			email: "user@example.com",
			want:  "example.com",
		},
		{
			name:  "email with angle brackets",
			email: "<user@example.com>",
			want:  "example.com",
		},
		{
			name:  "email with subdomain",
			email: "user@mail.example.com",
			want:  "mail.example.com",
		},
		{
			name:  "invalid email - no @",
			email: "invalid",
			want:  "",
		},
		{
			name:  "invalid email - empty",
			email: "",
			want:  "",
		},
		{
			name:  "email with multiple @ (invalid)",
			email: "user@test@example.com",
			want:  "", // Invalid format - split returns more than 2 parts
		},
		{
			name:  "uppercase domain",
			email: "user@EXAMPLE.COM",
			want:  "example.com", // Should be lowercase
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := extractDomain(tt.email); got != tt.want {
				t.Errorf("extractDomain() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestMatchIP(t *testing.T) {
	tests := []struct {
		name    string
		ip      string
		ipRange string
		want    bool
	}{
		{
			name:    "exact IPv4 match",
			ip:      "192.168.1.100",
			ipRange: "192.168.1.100",
			want:    true,
		},
		{
			name:    "IPv4 CIDR match",
			ip:      "192.168.1.100",
			ipRange: "192.168.1.0/24",
			want:    true,
		},
		{
			name:    "IPv4 CIDR no match",
			ip:      "192.168.2.100",
			ipRange: "192.168.1.0/24",
			want:    false,
		},
		{
			name:    "IPv4 no match",
			ip:      "192.168.1.100",
			ipRange: "192.168.1.101",
			want:    false,
		},
		{
			name:    "IPv6 CIDR match",
			ip:      "2001:db8::1",
			ipRange: "2001:db8::/32",
			want:    true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ip := net.ParseIP(tt.ip)
			if ip == nil {
				t.Fatalf("Invalid test IP: %s", tt.ip)
			}

			if got := matchIP(ip, tt.ipRange); got != tt.want {
				t.Errorf("matchIP(%s, %s) = %v, want %v", tt.ip, tt.ipRange, got, tt.want)
			}
		})
	}
}

func TestEvaluateBasicSPF(t *testing.T) {
	tests := []struct {
		name      string
		ip        string
		spfRecord string
		domain    string
		want      string
	}{
		{
			name:      "pass - IP4 match",
			ip:        "192.168.1.100",
			spfRecord: "v=spf1 ip4:192.168.1.100 -all",
			domain:    "example.com",
			want:      "pass",
		},
		{
			name:      "pass - IP4 CIDR match",
			ip:        "192.168.1.50",
			spfRecord: "v=spf1 ip4:192.168.1.0/24 -all",
			domain:    "example.com",
			want:      "pass",
		},
		{
			name:      "fail - hard fail",
			ip:        "10.0.0.1",
			spfRecord: "v=spf1 -all",
			domain:    "example.com",
			want:      "fail",
		},
		{
			name:      "softfail",
			ip:        "10.0.0.1",
			spfRecord: "v=spf1 ~all",
			domain:    "example.com",
			want:      "softfail",
		},
		{
			name:      "neutral",
			ip:        "10.0.0.1",
			spfRecord: "v=spf1 ?all",
			domain:    "example.com",
			want:      "neutral",
		},
		{
			name:      "neutral - a mechanism",
			ip:        "10.0.0.1",
			spfRecord: "v=spf1 a -all",
			domain:    "example.com",
			want:      "neutral",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			ip := net.ParseIP(tt.ip)
			if ip == nil {
				t.Fatalf("Invalid test IP: %s", tt.ip)
			}

			if got := evaluateBasicSPF(ip, tt.spfRecord, tt.domain); got != tt.want {
				t.Errorf("evaluateBasicSPF() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNewValidator(t *testing.T) {
	cfg := &Config{
		Validation: struct {
			CheckDKIM    bool `yaml:"check_dkim"`
			CheckSPF     bool `yaml:"check_spf"`
			CheckDMARC   bool `yaml:"check_dmarc"`
			StoreResults bool `yaml:"store_results"`
		}{
			CheckDKIM:  true,
			CheckSPF:   true,
			CheckDMARC: true,
		},
	}

	validator := NewValidator(cfg)

	if validator == nil {
		t.Error("NewValidator() should not return nil")
	}

	if validator.cfg != cfg {
		t.Error("NewValidator() didn't set config correctly")
	}
}

func TestValidateEmail(t *testing.T) {
	tests := []struct {
		name       string
		checkDKIM  bool
		checkSPF   bool
		checkDMARC bool
	}{
		{
			name:       "all validation disabled",
			checkDKIM:  false,
			checkSPF:   false,
			checkDMARC: false,
		},
		{
			name:       "only DKIM enabled",
			checkDKIM:  true,
			checkSPF:   false,
			checkDMARC: false,
		},
		{
			name:       "only SPF enabled",
			checkDKIM:  false,
			checkSPF:   true,
			checkDMARC: false,
		},
		{
			name:       "only DMARC enabled",
			checkDKIM:  false,
			checkSPF:   false,
			checkDMARC: true,
		},
		{
			name:       "all validation enabled",
			checkDKIM:  true,
			checkSPF:   true,
			checkDMARC: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := &Config{
				Validation: struct {
					CheckDKIM    bool `yaml:"check_dkim"`
					CheckSPF     bool `yaml:"check_spf"`
					CheckDMARC   bool `yaml:"check_dmarc"`
					StoreResults bool `yaml:"store_results"`
				}{
					CheckDKIM:  tt.checkDKIM,
					CheckSPF:   tt.checkSPF,
					CheckDMARC: tt.checkDMARC,
				},
			}

			validator := NewValidator(cfg)

			rawMessage := []byte(`From: sender@example.com
To: recipient@tempmail.example.com
Subject: Test
Date: Mon, 01 Jan 2024 12:00:00 +0000

Test body.
`)

			result := validator.ValidateEmail(rawMessage, "sender@example.com", "192.168.1.100", "client.example.com")

			if result == nil {
				t.Fatal("ValidateEmail() should not return nil")
			}

			// Check DKIM
			if tt.checkDKIM {
				if result.DKIMValid == nil {
					t.Error("ValidateEmail() DKIMValid should not be nil when enabled")
				}
			} else {
				if result.DKIMValid != nil {
					t.Errorf("ValidateEmail() DKIMValid should be nil when disabled, got %v", *result.DKIMValid)
				}
			}

			// Check SPF
			if !tt.checkSPF && result.SPFResult != "none" {
				t.Errorf("ValidateEmail() SPFResult = %v, want none (disabled)", result.SPFResult)
			}

			// Check DMARC
			if !tt.checkDMARC && result.DMARCResult != "none" {
				t.Errorf("ValidateEmail() DMARCResult = %v, want none (disabled)", result.DMARCResult)
			}
		})
	}
}

func TestValidateDMARC(t *testing.T) {
	cfg := &Config{}
	validator := NewValidator(cfg)

	tests := []struct {
		name       string
		domain     string
		spfResult  string
		dkimValid  *bool
		wantResult string
	}{
		{
			name:       "pass - SPF passes",
			domain:     "example.com",
			spfResult:  "pass",
			dkimValid:  nil,
			wantResult: "pass",
		},
		{
			name:       "pass - DKIM passes",
			domain:     "example.com",
			spfResult:  "fail",
			dkimValid:  func() *bool { v := true; return &v }(),
			wantResult: "pass",
		},
		{
			name:       "pass - both pass",
			domain:     "example.com",
			spfResult:  "pass",
			dkimValid:  func() *bool { v := true; return &v }(),
			wantResult: "pass",
		},
		{
			name:       "fail - both fail",
			domain:     "example.com",
			spfResult:  "fail",
			dkimValid:  func() *bool { v := false; return &v }(),
			wantResult: "fail",
		},
		{
			name:       "none - empty domain",
			domain:     "",
			spfResult:  "pass",
			dkimValid:  nil,
			wantResult: "none",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := validator.validateDMARC(tt.domain, tt.spfResult, tt.dkimValid)

			// For domains that exist, we expect a result (pass/fail)
			// For domains that don't exist or DNS fails, we might get "none"
			if tt.domain == "" {
				if got != "none" {
					t.Errorf("validateDMARC() = %v, want none for empty domain", got)
				}
			} else {
				// Can be pass, fail, or none (if DNS lookup fails)
				if got != tt.wantResult && got != "none" {
					t.Errorf("validateDMARC() = %v, want %v or none", got, tt.wantResult)
				}
			}
		})
	}
}

func TestValidateSPF(t *testing.T) {
	cfg := &Config{}
	validator := NewValidator(cfg)

	tests := []struct {
		name      string
		clientIP  string
		heloName  string
		from      string
		wantNone  bool // DNS lookups might fail in test environment
	}{
		{
			name:      "valid inputs",
			clientIP:  "192.168.1.100",
			heloName:  "client.example.com",
			from:      "sender@example.com",
			wantNone:  false, // example.com has SPF record
		},
		{
			name:      "invalid IP",
			clientIP:  "invalid",
			heloName:  "client.example.com",
			from:      "sender@example.com",
			wantNone:  true,
		},
		{
			name:      "no domain",
			clientIP:  "192.168.1.100",
			heloName:  "client.example.com",
			from:      "invalid",
			wantNone:  true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := validator.validateSPF(tt.clientIP, tt.heloName, tt.from)

			if tt.wantNone && got != "none" {
				t.Errorf("validateSPF() = %v, want none", got)
			}

			// Result should be one of the valid SPF results
			validResults := []string{"pass", "fail", "softfail", "neutral", "none", "temperror", "permerror"}
			found := false
			for _, valid := range validResults {
				if got == valid {
					found = true
					break
				}
			}
			if !found {
				t.Errorf("validateSPF() = %v, which is not a valid SPF result", got)
			}
		})
	}
}

func TestValidateDKIM(t *testing.T) {
	cfg := &Config{}
	validator := NewValidator(cfg)

	tests := []struct {
		name       string
		rawMessage string
		wantValid  bool
	}{
		{
			name: "message without DKIM signature",
			rawMessage: `From: sender@example.com
To: recipient@tempmail.example.com
Subject: Test
Date: Mon, 01 Jan 2024 12:00:00 +0000

Test body.
`,
			wantValid: false,
		},
		{
			name: "message with invalid DKIM signature",
			rawMessage: `DKIM-Signature: v=1; a=rsa-sha256; d=example.com; s=selector;
 h=from:to:subject;
 bh=invalid;
 b=invalidsignature
From: sender@example.com
To: recipient@tempmail.example.com
Subject: Test

Test body.
`,
			wantValid: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := validator.validateDKIM([]byte(tt.rawMessage))

			// Since we're using test messages without valid signatures,
			// we expect false
			if got != tt.wantValid {
				t.Errorf("validateDKIM() = %v, want %v", got, tt.wantValid)
			}
		})
	}
}

func TestLookupSPFRecord(t *testing.T) {
	tests := []struct {
		name       string
		domain     string
		wantError  bool
		wantPrefix string
	}{
		{
			name:       "domain with SPF record",
			domain:     "example.com",
			wantError:  false,
			wantPrefix: "v=spf1",
		},
		{
			name:      "domain without SPF record",
			domain:    "thisisadomainthatdoesnotexist123456789.com",
			wantError: true,
		},
		{
			name:      "empty domain",
			domain:    "",
			wantError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			record, err := lookupSPFRecord(tt.domain)

			if (err != nil) != tt.wantError {
				t.Errorf("lookupSPFRecord() error = %v, wantError %v", err, tt.wantError)
				return
			}

			if !tt.wantError && record[:6] != tt.wantPrefix {
				t.Errorf("lookupSPFRecord() record doesn't start with %v, got %v", tt.wantPrefix, record)
			}
		})
	}
}

func TestGetOrganizationalDomain(t *testing.T) {
	tests := []struct {
		name   string
		domain string
		want   string
	}{
		{
			name:   "subdomain - mail server",
			domain: "em7877.tm.openai.com",
			want:   "openai.com",
		},
		{
			name:   "subdomain - single level",
			domain: "mail.example.com",
			want:   "example.com",
		},
		{
			name:   "subdomain - multiple levels",
			domain: "a.b.c.example.com",
			want:   "example.com",
		},
		{
			name:   "organizational domain - already at org level",
			domain: "example.com",
			want:   "example.com",
		},
		{
			name:   "organizational domain - different TLD",
			domain: "example.org",
			want:   "example.org",
		},
		{
			name:   "single part domain - invalid",
			domain: "localhost",
			want:   "",
		},
		{
			name:   "empty domain",
			domain: "",
			want:   "",
		},
		{
			name:   "multi-part TLD subdomain",
			domain: "mail.example.co.uk",
			want:   "example.co.uk",
		},
		{
			name:   "multi-part TLD org domain",
			domain: "example.co.uk",
			want:   "example.co.uk",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := getOrganizationalDomain(tt.domain); got != tt.want {
				t.Errorf("getOrganizationalDomain(%q) = %q, want %q", tt.domain, got, tt.want)
			}
		})
	}
}

func TestLookupDMARCRecord(t *testing.T) {
	tests := []struct {
		name       string
		domain     string
		wantError  bool
		wantPrefix string
	}{
		{
			name:       "domain with DMARC record",
			domain:     "example.com",
			wantError:  false,
			wantPrefix: "v=DMARC1",
		},
		{
			name:      "domain without DMARC record",
			domain:    "thisisadomainthatdoesnotexist123456789.com",
			wantError: true,
		},
		{
			name:      "empty domain",
			domain:    "",
			wantError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			record, err := lookupDMARCRecord(tt.domain)

			if (err != nil) != tt.wantError {
				t.Errorf("lookupDMARCRecord() error = %v, wantError %v", err, tt.wantError)
				return
			}

			if !tt.wantError && record[:8] != tt.wantPrefix {
				t.Errorf("lookupDMARCRecord() record doesn't start with %v, got %v", tt.wantPrefix, record)
			}
		})
	}
}
