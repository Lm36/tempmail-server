package main

import (
	"crypto/tls"
	"testing"
)

func TestNewBackend(t *testing.T) {
	cfg := &Config{
		Domains: []string{"tempmail.example.com", "temp.test"},
	}

	backend := NewBackend(cfg, nil, nil)

	if backend == nil {
		t.Fatal("NewBackend() should not return nil")
	}

	if backend.cfg != cfg {
		t.Error("NewBackend() didn't set config correctly")
	}

	if len(backend.domains) != 2 {
		t.Errorf("NewBackend() domains count = %v, want 2", len(backend.domains))
	}

	if !backend.domains["tempmail.example.com"] {
		t.Error("NewBackend() missing domain tempmail.example.com")
	}

	if !backend.domains["temp.test"] {
		t.Error("NewBackend() missing domain temp.test")
	}
}

func TestBackendNewSession(t *testing.T) {
	cfg := &Config{
		Domains: []string{"tempmail.example.com"},
		Server: struct {
			APIPort        int    `yaml:"api_port"`
			MXPort         int    `yaml:"mx_port"`
			MaxMsgSizeMB   int    `yaml:"max_message_size_mb"`
			Hostname       string `yaml:"hostname"`
		}{
			MXPort:       25,
			MaxMsgSizeMB: 10,
			Hostname:     "mail.test.com",
		},
	}

	backend := NewBackend(cfg, nil, nil)

	// We can't easily test NewSession with a real SMTP connection,
	// but we can verify the method exists and backend is configured
	if backend == nil {
		t.Fatal("Backend should not be nil")
	}

	// Backend should have the correct configuration
	if backend.cfg != cfg {
		t.Error("Backend config not set correctly")
	}

	if backend.validator != nil {
		t.Error("Backend validator should be nil when not configured")
	}
}

func TestTLSVersionString(t *testing.T) {
	tests := []struct {
		name    string
		version uint16
		want    string
	}{
		{
			name:    "TLS 1.0",
			version: tls.VersionTLS10,
			want:    "TLS 1.0",
		},
		{
			name:    "TLS 1.1",
			version: tls.VersionTLS11,
			want:    "TLS 1.1",
		},
		{
			name:    "TLS 1.2",
			version: tls.VersionTLS12,
			want:    "TLS 1.2",
		},
		{
			name:    "TLS 1.3",
			version: tls.VersionTLS13,
			want:    "TLS 1.3",
		},
		{
			name:    "Unknown version",
			version: 0x9999,
			want:    "Unknown (0x9999)",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := tlsVersionString(tt.version); got != tt.want {
				t.Errorf("tlsVersionString() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestNewSMTPServerConfig(t *testing.T) {
	cfg := &Config{
		Domains: []string{"tempmail.example.com"},
		Server: struct {
			APIPort        int    `yaml:"api_port"`
			MXPort         int    `yaml:"mx_port"`
			MaxMsgSizeMB   int    `yaml:"max_message_size_mb"`
			Hostname       string `yaml:"hostname"`
		}{
			MXPort:       2525,
			MaxMsgSizeMB: 10,
			Hostname:     "mail.tempmail.test",
		},
		Validation: struct {
			CheckDKIM    bool `yaml:"check_dkim"`
			CheckSPF     bool `yaml:"check_spf"`
			CheckDMARC   bool `yaml:"check_dmarc"`
			StoreResults bool `yaml:"store_results"`
		}{
			CheckDKIM:  false,
			CheckSPF:   false,
			CheckDMARC: false,
		},
		TLS: struct {
			Enabled  bool   `yaml:"enabled"`
			CertFile string `yaml:"cert_file"`
			KeyFile  string `yaml:"key_file"`
		}{
			Enabled: false,
		},
	}

	server, err := NewSMTPServer(cfg, nil)

	// DB is nil, so this might fail on database operations
	// But we're testing the server configuration
	if err != nil {
		t.Fatalf("NewSMTPServer() error = %v", err)
	}

	if server == nil {
		t.Fatal("NewSMTPServer() should not return nil")
	}

	if server.cfg != cfg {
		t.Error("NewSMTPServer() didn't set config correctly")
	}

	if server.server == nil {
		t.Fatal("NewSMTPServer() should create SMTP server")
	}

	// Verify SMTP server configuration
	if server.server.Domain != "mail.tempmail.test" {
		t.Errorf("SMTP server domain = %v, want mail.tempmail.test", server.server.Domain)
	}

	expectedMaxBytes := int64(10 * 1024 * 1024)
	if server.server.MaxMessageBytes != expectedMaxBytes {
		t.Errorf("SMTP server MaxMessageBytes = %v, want %v", server.server.MaxMessageBytes, expectedMaxBytes)
	}

	if server.server.MaxRecipients != 50 {
		t.Errorf("SMTP server MaxRecipients = %v, want 50", server.server.MaxRecipients)
	}

	if !server.server.AuthDisabled {
		t.Error("SMTP server should have AuthDisabled = true")
	}

	if server.server.AllowInsecureAuth {
		t.Error("SMTP server should have AllowInsecureAuth = false")
	}
}

func TestNewSMTPServerValidation(t *testing.T) {
	tests := []struct {
		name       string
		checkDKIM  bool
		checkSPF   bool
		checkDMARC bool
	}{
		{
			name:       "all validation enabled",
			checkDKIM:  true,
			checkSPF:   true,
			checkDMARC: true,
		},
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
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := &Config{
				Domains: []string{"test.com"},
				Server: struct {
					APIPort        int    `yaml:"api_port"`
					MXPort         int    `yaml:"mx_port"`
					MaxMsgSizeMB   int    `yaml:"max_message_size_mb"`
					Hostname       string `yaml:"hostname"`
				}{
					MXPort:       25,
					MaxMsgSizeMB: 10,
					Hostname:     "mail.test.com",
				},
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
				TLS: struct {
					Enabled  bool   `yaml:"enabled"`
					CertFile string `yaml:"cert_file"`
					KeyFile  string `yaml:"key_file"`
				}{
					Enabled: false,
				},
			}

			server, err := NewSMTPServer(cfg, nil)
			if err != nil {
				t.Fatalf("NewSMTPServer() error = %v", err)
			}

			if server == nil {
				t.Fatal("NewSMTPServer() should not return nil")
			}

			// Just verify it doesn't crash - we can't easily test the validator
			// since it's internal to the backend
		})
	}
}
