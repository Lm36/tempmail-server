package main

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// Config holds the MX server configuration loaded from YAML
type Config struct {
	Domains []string `yaml:"domains"`

	Database struct {
		URL      string `yaml:"url"`
		PoolSize int    `yaml:"pool_size"`
	} `yaml:"database"`

	Server struct {
		APIPort        int    `yaml:"api_port"`
		MXPort         int    `yaml:"mx_port"`
		MaxMsgSizeMB   int    `yaml:"max_message_size_mb"`
		Hostname       string `yaml:"hostname"`
	} `yaml:"server"`

	TLS struct {
		Enabled  bool   `yaml:"enabled"`
		CertFile string `yaml:"cert_file"`
		KeyFile  string `yaml:"key_file"`
	} `yaml:"tls"`

	Tempmail struct {
		AddressLifetimeHours int    `yaml:"address_lifetime_hours"`
		MaxEmailsPerAddress  int    `yaml:"max_emails_per_address"`
		CleanupIntervalHours int    `yaml:"cleanup_interval_hours"`
		AddressFormat        string `yaml:"address_format"`
	} `yaml:"tempmail"`

	Validation struct {
		CheckDKIM    bool `yaml:"check_dkim"`
		CheckSPF     bool `yaml:"check_spf"`
		CheckDMARC   bool `yaml:"check_dmarc"`
		StoreResults bool `yaml:"store_results"`
	} `yaml:"validation"`

	Logging struct {
		Level  string `yaml:"level"`
		Format string `yaml:"format"`
	} `yaml:"logging"`
}

// LoadConfig loads configuration from YAML file
func LoadConfig(configPath string) (*Config, error) {
	// Read YAML file
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	// Parse YAML
	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	// Validate required fields
	if cfg.Database.URL == "" {
		return nil, fmt.Errorf("database.url is required")
	}

	if len(cfg.Domains) == 0 {
		return nil, fmt.Errorf("at least one domain is required")
	}

	// Set defaults
	if cfg.Server.MXPort == 0 {
		cfg.Server.MXPort = 25
	}
	if cfg.Server.Hostname == "" {
		cfg.Server.Hostname = "mail.tempmail.local"
	}
	if cfg.Server.MaxMsgSizeMB == 0 {
		cfg.Server.MaxMsgSizeMB = 10
	}
	if cfg.Database.PoolSize == 0 {
		cfg.Database.PoolSize = 10
	}
	if cfg.Tempmail.MaxEmailsPerAddress == 0 {
		cfg.Tempmail.MaxEmailsPerAddress = 100
	}

	// Set TLS defaults
	if cfg.TLS.CertFile == "" {
		cfg.TLS.CertFile = "/config/certs/cert.pem"
	}
	if cfg.TLS.KeyFile == "" {
		cfg.TLS.KeyFile = "/config/certs/key.pem"
	}

	return &cfg, nil
}

// GetMaxMessageSize returns max message size in bytes
func (c *Config) GetMaxMessageSize() int64 {
	return int64(c.Server.MaxMsgSizeMB) * 1024 * 1024
}

// GetDomainMap returns domains as a map for fast lookup
func (c *Config) GetDomainMap() map[string]bool {
	domains := make(map[string]bool)
	for _, domain := range c.Domains {
		domains[domain] = true
	}
	return domains
}
